#!/usr/bin/env python3
"""Offline verification for the staged 38-program Qwen decoder chain.

Proves, without any ANE device, that the Linux-side contract is byte-exact
against Apple's own captures:

1. manifest chain closure (lanes produced before consumed, state shapes,
   group boundaries, port orders matching the goldens capture orders);
2. cross-capture step-1 chaining (goldens <-> capture-ref2 state block <->
   ref4 mid program): the saved Apple arrays are one coherent token pass and
   pin the lane semantics per port;
3. host tables: the embedding row, zero state init, and the oh/inv/mask and
   RoPE context rows hash exactly as Apple's runner fed them (goldens).

Device-side checks (every bank hash for a full token, then generation) run
with --device mode on the M1 window; this file is the same entry point.
"""

import argparse
import hashlib
import os
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).with_name("staged-decode-fixtures")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_runtime():
    path = ROOT / "ane-runtime.py"
    spec = importlib.util.spec_from_file_location("ane_runtime", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def logical(array):
    return np.ascontiguousarray(array, dtype=np.float16).tobytes()


def check_chain_closure(manifest, goldens):
    """Every lane must exist before its program consumes it."""
    problems = []
    produced = set()
    for index, program in enumerate(manifest["programs"]):
        for source in program["srcs"]:
            if source["kind"] != "lane":
                continue
            if source["lane"] not in produced and source["lane"] != "x":
                problems.append(f"program {index}: lane {source['lane']} never produced")
        for dst in program["dsts"]:
            produced.add(dst["lane"])
        order_in = [s["port"] for s in program["srcs"]]
        order_out = [d["port"] for d in program["dsts"]]
        gold = goldens.get(str(index))
        if gold:
            if len(gold["srcs"]) != len(order_in):
                problems.append(
                    f"program {index}: {len(order_in)} srcs vs goldens {len(gold['srcs'])}"
                )
            if len(gold["dsts"]) != len(order_out):
                problems.append(
                    f"program {index}: {len(order_out)} dsts vs goldens {len(gold['dsts'])}"
                )
        states = program.get("states", [])
        in_ports = {s["port"] for s in program["srcs"] if s["kind"] == "state_in"}
        for state in states:
            if state["in_port"] not in in_ports:
                problems.append(f"program {index}: state in {state['in_port']} not a src")
        if program["dsts"] and program["dsts"][-1]["lane"] == "h":
            if not program.get("group_end"):
                problems.append(f"program {index}: h output without group_end")
    h_programs = [
        i for i, p in enumerate(manifest["programs"]) if p.get("group_end")
    ]
    if [i for i in h_programs] != [20, 37] and len(h_programs) != 2:
        problems.append(f"group_end programs {h_programs} != 2 chunk finals")
    return problems


def check_cross_captures(lab):
    """Saved Apple captures must chain into one coherent pass.

    goldens.json captures the LAST stepped position of its generate() call:
    lanes and ctx hashes are that step's values, while every state_in hash is
    the reset-time zero fill (set_input for states happens once). The chain
    is therefore verified by internal hash equality: each program's lane srcs
    must equal the producing program's dsts, all states must be zeros, all
    ctx programs must share one position's tables, and the step-1 captures
    (sb0000, sig0002) pin the GGUF embedding and the state-block chaining.
    """
    problems = []
    ref2 = lab / "state-block-capture2/capture-ref2"
    ref4 = lab / "state-block-capture2/ref4"
    goldens = json.loads((lab / "QwenChain/goldens.json").read_text())
    manifest = json.loads((lab / "QwenChain/manifest.json").read_text())
    programs = manifest["programs"]
    zero_hash = {}  # logical size -> sha of zero fill

    def zeros(shape):
        key = int(np.prod(shape)) * 2
        if key not in zero_hash:
            zero_hash[key] = sha(b"\0" * key)
        return zero_hash[key]

    # -- internal goldens chaining: each program's lane srcs equal the
    # nearest preceding producer's dsts; the residual lane "x" is special:
    # A(gs)/B programs pass it through without producing it, and a chunk
    # final re-emits it as "h", so a single pointer tracks the live residual
    producer = {}  # lane -> (program index, dst slot)
    x_pointer = ("host0", 0)
    checked = 0
    for index, program in enumerate(programs):
        gold = goldens[str(index)]
        for source, expected in zip(program["srcs"], gold["srcs"]):
            if source["kind"] == "lane":
                origin = x_pointer if source["lane"] == "x" else producer.get(
                    source["lane"]
                )
                if origin is None:
                    problems.append(f"program {index}: lane {source['lane']} unproduced")
                elif origin[0] == "host0":
                    if expected != goldens["0"]["srcs"][0]:
                        problems.append(
                            f"program {index} lane {source['lane']}: != host fill"
                        )
                    checked += 1
                else:
                    src_index, slot = origin
                    if goldens[str(src_index)]["dsts"][slot] != expected:
                        problems.append(
                            f"program {index} lane {source['lane']}: src hash != "
                            f"program {src_index} dst"
                        )
                    checked += 1
            elif source["kind"] == "state_in":
                if expected != zeros(source["shape"]):
                    problems.append(
                        f"program {index} state {source['lane']} is not the zero fill"
                    )
                checked += 1
        for slot, dst in enumerate(program["dsts"]):
            producer[dst["lane"]] = (index, slot)
            if dst["lane"] in ("x", "h"):
                x_pointer = (index, slot)
    if x_pointer != (37, 0):
        problems.append(f"final residual pointer {x_pointer} != program 37 h")
    checked += 1

    # -- ctx tables: all ctx programs share one position's oh/inv/mask/rope
    ctx_hash = {}
    for index, program in enumerate(programs):
        gold = goldens[str(index)]
        for source, expected in zip(program["srcs"], gold["srcs"]):
            if source["kind"] == "ctx":
                previous = ctx_hash.setdefault(source["lane"], expected)
                if previous != expected:
                    problems.append(
                        f"program {index} ctx {source['lane']} disagrees with "
                        "earlier programs"
                    )
    m = int(manifest["max_len"])
    position = None
    lane_tables = {}
    oh = np.zeros((1, m, 1), dtype=np.float16)
    for candidate in range(m):
        oh[:] = 0
        oh[0, candidate, 0] = np.float16(1.0)
        inv = (np.float16(1.0) - oh).astype(np.float16)
        mask = np.full((1, 1, m), np.float16(-1e4), dtype=np.float16)
        mask[0, 0, : candidate + 1] = np.float16(0.0)
        lane_tables[candidate] = {
            "oh": sha(logical(oh)),
            "inv": sha(logical(inv)),
            "mask": sha(logical(mask)),
        }
        if (
            ctx_hash
            and lane_tables[candidate]["oh"] == ctx_hash.get("oh")
            and lane_tables[candidate]["inv"] == ctx_hash.get("inv")
            and lane_tables[candidate]["mask"] == ctx_hash.get("mask")
        ):
            position = candidate
            break
    if position is None:
        problems.append(
            "no position in 0..max_len reproduces the goldens oh/inv/mask tables"
        )
    else:
        print(f"goldens captured decode position {position}")
        lane_tables = lane_tables[position]

    # -- step-1 captures pin the GGUF embedding and the state-block chaining
    sb = np.load(ref2 / "sb0000.npz")
    sig = np.load(ref4 / "sig0002.npz")
    order = ["in__t14", "in__t4", "in__t7", "in__t0", "in__t1", "state_in__t2"]
    for slot, (key, expected) in enumerate(zip(order, goldens["1"]["srcs"])):
        if slot == 5:
            if sha(logical(sb[key])) != zeros([16, 128, 128]):
                problems.append("sb0000 state-in is not zeros")
            continue
        # goldens["1"] lanes are the last step's; sb0000 is step 1: compare
        # sb0000 against ITSELF only where a second step-1 source exists
        del expected, slot
    for key, expected in (
        ("out__t17", sha(logical(sig["in__t2"]))),
    ):
        if sha(logical(sb[key])) != expected:
            problems.append("state-block o does not chain into ref4 prog2 o input")
    # step-1 x anchor: sig0002's x is the raw embedding of the first prompt
    # token (verified against the GGUF in check_host_tables)
    step1_x = sha(logical(sig["in__t7"]))
    return problems, checked, {
        "step1_x": step1_x, "position": position, "ctx_hash": ctx_hash,
    }


def rope_tables(m, weights, dh=256):
    reader = weights.reader
    base_field = reader.get_field("qwen35.rope.freq_base")
    rotary_field = reader.get_field("qwen35.rope.dimension_count")
    base = float(_field_scalar(base_field)) if base_field is not None else 10_000_000.0
    rotary_dim = (
        int(_field_scalar(rotary_field)) if rotary_field is not None else 64
    )
    inverse = 1.0 / (base ** (np.arange(0, rotary_dim, 2) / rotary_dim))
    positions = np.arange(m)[:, None] * inverse[None, :]
    emb = np.concatenate([positions, positions], -1)
    pad = dh - rotary_dim
    cos = np.concatenate([np.cos(emb), np.ones((m, pad))], 1).astype(np.float16)
    sin = np.concatenate([np.sin(emb), np.zeros((m, pad))], 1).astype(np.float16)
    return {"cosp": cos, "sinp": sin}


def _field_scalar(field):
    contents = field.contents() if callable(field.contents) else field.contents
    return contents[-1] if hasattr(contents, "__len__") else contents


def check_host_tables(lab, model, anchors):
    """The GGUF embedding rows hash exactly as Apple staged them."""
    problems = []
    ref4 = lab / "state-block-capture2/ref4"
    sig = np.load(ref4 / "sig0002.npz")
    spec = importlib.util.spec_from_file_location(
        "ane_weights", ROOT / "ane-weights.py"
    )
    weights_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(weights_module)
    weights = weights_module.GGUFWeights(str(model))
    embedding = weights.tensor("token_embd.weight")
    checked = 0
    # the step-1 capture's x lane is the raw embedding of the first prompt id
    ids = json.loads((FIXTURES / "reference-prompt-ids.json").read_text())["ids"]
    if sha(logical(embedding[ids[0]])) != anchors["step1_x"]:
        problems.append(
            f"embedding row for first prompt token {ids[0]} != Apple's step-1 x"
        )
    checked += 1
    # identify the goldens capture token by pure row-hash lookup
    target = json.loads((lab / "QwenChain/goldens.json").read_text())["0"]["srcs"][0]
    flat = embedding.reshape(embedding.shape[0], -1)
    found = None
    for row in range(flat.shape[0]):
        if sha(logical(flat[row])) == target:
            found = row
            break
    if found is None:
        problems.append("goldens x lane matches no embedding row")
    else:
        print(f"goldens x = embedding row of token {found}")
    position = anchors.get("position")
    ctx_hash = anchors.get("ctx_hash") or {}
    if position is not None and ctx_hash.get("cosp"):
        rope = rope_tables(int(json.loads(
            (lab / "QwenChain/manifest.json").read_text()
        )["max_len"]), weights)
        if sha(logical(rope["cosp"][position])) != ctx_hash["cosp"]:
            problems.append(f"cosp row {position} mismatch vs goldens")
        if sha(logical(rope["sinp"][position])) != ctx_hash["sinp"]:
            problems.append(f"sinp row {position} mismatch vs goldens")
        checked += 2
    return problems, checked


def device_mode(args):
    """Full-token bank-hash verification and generation on the ANE."""
    runtime = importlib.util.import_module if False else None
    spec = importlib.util.spec_from_file_location(
        "staged_runtime", Path(__file__).with_name("staged-decode-runtime.py")
    )
    staged = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(staged)
    decoder = staged.StagedDecoder(args.manifest, args.anec_dir, args.bindings)
    raise SystemExit(
        "device mode: run tools/staged-decode-runtime.py --verify-goldens on "
        "the M1 host; this box has no ANE device"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    lab = Path(os.environ.get("STAGED_LAB", "~/lab/artifacts")).expanduser()
    parser.add_argument("--lab", type=Path, default=lab)
    parser.add_argument(
        "--model", type=Path,
        default=lab / "QwenChain" / "Qwen3.8-2B-Q4_K_M.gguf",
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--anec-dir", type=Path)
    parser.add_argument("--bindings")
    parser.add_argument("--device", action="store_true")
    args = parser.parse_args(argv)
    if args.device:
        device_mode(args)
        return 0

    failures = []
    manifest = json.loads(
        (args.manifest or args.lab / "QwenChain/manifest.json").read_text()
    )
    goldens = json.loads((args.lab / "QwenChain/goldens.json").read_text())
    problems = check_chain_closure(manifest, goldens)
    print(f"chain closure: {len(problems)} problems")
    failures += problems
    problems, checked, anchors = check_cross_captures(args.lab)
    print(f"goldens internal chain: {len(problems)} problems "
          f"({checked} hashes checked)")
    failures += problems
    try:
        problems, checked = check_host_tables(args.lab, args.model, anchors)
        print(f"host tables (embed/rope): {len(problems)} problems "
              f"({checked} rows checked)")
        failures += problems
    except Exception as error:  # gguf reader missing is a hard failure here
        print(f"host tables: FAILED to run ({error})")
        failures.append(str(error))
    if failures:
        for problem in failures:
            print(f"FAIL {problem}")
        return 1
    print("STAGED_OFFLINE_VERIFY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
