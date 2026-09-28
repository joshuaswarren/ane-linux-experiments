#!/usr/bin/env python3
"""Qwen3.8 decode+prefill benchmark on mlx (macOS Metal / Omarchy Vulkan).

Fixed protocol (benchmarks/qwen38-2b-contract.json): greedy (temp 0), fixed
prompt corpus, warmup then measured repeats. Records runtime dist+commit, OS,
model/tokenizer/config hashes, backend and adapter evidence, median and
dispersion, and an ORDERED per-record token hash.

Metrics are labelled precisely:
  - ttft_tok_rate: prompt tokens / time-to-first-token (prompt-through-first-token)
  - pure_prefill_tok_rate: prompt tokens / time to evaluate the whole prompt
    with no token generated (prefill leg only)
  - decode_tok_rate: (actual_generated-1) / decode wall time; actual counts recorded
"""
import argparse, hashlib, json, os, platform, statistics, subprocess, sys, time

p = argparse.ArgumentParser()
p.add_argument("--model", required=True)
p.add_argument("--prompts", required=True)
p.add_argument("--limit", type=int, default=10, help="prompts per pass")
p.add_argument("--new-tokens", type=int, default=32)
p.add_argument("--prefill-tokens", type=int, default=512, help="pure prefill leg length (0 disables)")
p.add_argument("--warmup", type=int, default=2)
p.add_argument("--passes", type=int, default=3)
p.add_argument("--threads", type=int, default=0, help="0 = platform default")
p.add_argument("--label", default="")
p.add_argument("--out", default="")
p.add_argument("--check-compat", default="",
               help="after the run, verify the contract shape (prompt count, "
                    "warmup, passes, new-tokens, prefill leg, corpus) matches "
                    "this reference JSON; exit 3 on mismatch")
a = p.parse_args()

if a.threads:
    os.environ["MLX_NUM_THREADS"] = str(a.threads)

import mlx.core as mx
from qwen38_bench_lib import sha256_file, ordered_records_hash, summarize
from mlx_lm import load, generate
from mlx_lm.models.cache import make_prompt_cache
from mlx_lm.generate import generate_step


def contract_shape(args, corpus_sha):
    """Frozen contract fingerprint: everything that must match before two
    run records may be compared. The 2026-09-26 flip incident: a
    --limit 1 digest (100a61b6) was compared against the --limit 10 pin
    (486872c4) and read as a machine-state flip. Different shape = different
    record set = different digest, trivially. Never compare across shapes."""
    return {
        "prompts_per_pass": None,  # filled by caller after prompt load
        "warmup": args.warmup,
        "passes": args.passes,
        "new_tokens": args.new_tokens,
        "prefill_leg_tokens": args.prefill_tokens or None,
        "prompts_corpus_sha256": corpus_sha,
    }


def shapes_compatible(a, b):
    """True iff two contract_shape dicts describe the same benchmark shape.
    Missing keys on either side count as incompatible (unknown != known)."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False, "shape is not a dict"
    for key in ("prompts_per_pass", "warmup", "passes", "new_tokens",
                "prefill_leg_tokens", "prompts_corpus_sha256",
                "prompts_identity_sha256"):
        av, bv = a.get(key), b.get(key)
        if av is None or bv is None:
            return False, f"missing shape key: {key}"
        if av != bv:
            return False, f"{key}: {av} != {bv}"
    return True, ""


def metadata(model_path):
    md = {
        "os": platform.platform(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "model_path": os.path.basename(model_path.rstrip("/")),
        "label": a.label,
        "mlx_commit": os.environ.get("MLX_COMMIT_TAG", ""),
        "threads_env": os.environ.get("MLX_NUM_THREADS", "unset/platform-default"),
    }
    import mlx_lm
    from importlib import metadata as _im
    md["mlx_lm_version"] = mlx_lm.__version__
    md["backend"] = str(mx.default_device())
    for dist in ("mlx-omarchy", "mlx"):
        try:
            md["mlx_dist_name"] = dist
            md["mlx_dist_version"] = _im.version(dist)
            break
        except _im.PackageNotFoundError:
            continue
    for f, key in (("model.safetensors", "model_sha256"),
                   ("tokenizer.json", "tokenizer_sha256"),
                   ("config.json", "config_sha256")):
        fp = os.path.join(model_path, f)
        if os.path.exists(fp):
            md[key] = sha256_file(fp)
    for f in ("/proc/device-tree/model", "/sys/firmware/devicetree/base/model"):
        try:
            md["soc"] = open(f).read().strip("\x00\n")
            break
        except OSError:
            pass
    if platform.system() == "Darwin":
        try:
            md["metal_gfx"] = subprocess.run(
                ["system_profiler", "SPDisplaysDataType", "-detaillevel", "mini"],
                capture_output=True, text=True, timeout=30).stdout[:600]
        except Exception as e:
            md["metal_gfx"] = f"error: {e}"
    else:
        try:
            out = subprocess.run(["vulkaninfo", "--summary"], capture_output=True,
                                 text=True, timeout=20).stdout
            import re as _re
            md["vk_devices"] = _re.findall(r"deviceName\s*=\s*(.+)", out)
            md["vk_drivers"] = _re.findall(r"driverName\s*=\s*(\S+)", out)
        except Exception as e:
            md["vk_devices"] = f"error: {e}"
    try:
        md["thermal_c"] = [int(open(f"/sys/class/thermal/{z}/temp").read()) / 1000.0
                           for z in sorted(os.listdir("/sys/class/thermal"))
                           if z.startswith("thermal_zone")]
    except OSError:
        md["thermal_c"] = []
    md["loadavg_start"] = round(os.getloadavg()[0], 2)
    return md


def main():
    prompts = [json.loads(l)["text"] for l in open(a.prompts) if l.strip()][: a.limit]
    corpus_sha = sha256_file(a.prompts)
    model, tok = load(a.model)
    model_dir = a.model.rstrip("/")

    # Pure prefill leg: fixed ~prefill_tokens prompt, evaluated with no token generated.
    import glob, threading

    busy = []
    stop_evt = threading.Event()

    def sample_busy():
        for pth in glob.glob("/sys/class/drm/card*/device/gpu_busy_percent"):
            pass
        paths = glob.glob("/sys/class/drm/card*/device/gpu_busy_percent")
        while not stop_evt.is_set():
            for pth in paths:
                try:
                    busy.append(int(open(pth).read().strip()))
                except (OSError, ValueError):
                    pass
            stop_evt.wait(0.25)

    def pure_prefill_leg():
        text = " ".join(prompts)
        ids = tok.encode(text)
        while len(ids) < a.prefill_tokens:
            ids = ids + tok.encode(" " + text)
        ids = ids[: a.prefill_tokens]
        cache = make_prompt_cache(model)
        th = threading.Thread(target=sample_busy, daemon=True)
        th.start()
        t0 = time.perf_counter()
        mx.eval(model(mx.array(ids)[None], cache=cache))
        dt = time.perf_counter() - t0
        stop_evt.set()
        th.join(timeout=1)
        return {"prompt_tokens": len(ids), "wall_s": round(dt, 4),
                "gpu_busy_percent_samples": busy[:40],
                "pure_prefill_tok_rate": round(len(ids) / dt, 2) if dt > 0 else 0.0}

    records = []
    # Prompt identity/order fingerprint: sha256 over the ordered per-prompt
    # input_ids lists AS the acceptance run tokenizes them (post-limit).
    # Covers identity AND order, independent of file formatting.
    import hashlib as _hl
    ids_per_prompt = [tok.encode(t) for t in prompts]
    prompts_identity_sha = _hl.sha256(
        b"".join(
            str(len(ii)).encode() + b"|"
            + ",".join(map(str, ii)).encode() + b"|"
            for ii in ids_per_prompt
        )
    ).hexdigest()
    print("prompts_identity_sha:", prompts_identity_sha, flush=True)

    for w in range(a.warmup):
        generate(model, tok, prompt=prompts[0], max_tokens=8, verbose=False)

    for ps in range(a.passes):
        for i, text in enumerate(prompts):
            ids = tok.encode(text)
            cache = make_prompt_cache(model)
            t0 = time.perf_counter()
            it = generate_step(mx.array(ids), model, prompt_cache=cache, max_tokens=a.new_tokens)
            first = next(it)[0]
            mx.eval(first)
            ttft = time.perf_counter() - t0
            out = [int(first)]
            t1 = time.perf_counter()
            for tk, _ in it:
                out.append(int(tk))
                mx.eval(tk)
                if len(out) >= a.new_tokens:
                    break
            decode_dt = time.perf_counter() - t1
            records.append({
                "pass": ps, "prompt_idx": i, "input_ids": ids, "output_ids": out,
                "prompt_tokens": len(ids), "generated_tokens": len(out),
                "ttft_s": round(ttft, 4),
                "ttft_tok_rate": round(len(ids) / ttft, 2) if ttft > 0 else 0.0,
                "decode_s": round(decode_dt, 4),
                "decode_tok_rate": round((len(out) - 1) / decode_dt, 2)
                if len(out) >= 2 and decode_dt > 0 else 0.0,
            })
        print(f"pass {ps} done", flush=True)

    prefill_leg = pure_prefill_leg() if a.prefill_tokens else None
    result = {
        "meta": metadata(model_dir),
        "contract_shape": dict(contract_shape(a, corpus_sha),
                               prompts_per_pass=len(prompts),
                               prompts_identity_sha256=prompts_identity_sha),
        "protocol": {
            "new_tokens": a.new_tokens, "temperature": 0.0, "greedy": True,
            "prompts_file": os.path.basename(a.prompts), "prompts_corpus_sha256": corpus_sha,
            "prompts_per_pass": len(prompts), "warmup": a.warmup, "passes": a.passes,
            "threads_requested": a.threads or "default",
            "prefill_leg_tokens": a.prefill_tokens or None,
        },
        "ttft_tok_rate": summarize([r["ttft_tok_rate"] for r in records]),
        "decode_tok_rate": summarize([r["decode_tok_rate"] for r in records]),
        "pure_prefill": prefill_leg,
        "ordered_records_sha256": ordered_records_hash(records),
        "per_prompt": records,
    }
    js = json.dumps(result, indent=1)
    print("pure_prefill:", prefill_leg, file=sys.stderr)
    print("ordered_records_sha256:", result["ordered_records_sha256"], file=sys.stderr)
    if a.out:
        open(a.out, "w").write(js)
    else:
        print(js)
    if a.check_compat:
        ref = json.load(open(a.check_compat))
        ok, why = shapes_compatible(result.get("contract_shape"),
                                    ref.get("contract_shape") or shape_from_protocol(ref.get("protocol", {})))
        if not ok:
            print(f"CONTRACT-SHAPE MISMATCH vs {a.check_compat}: {why}", file=sys.stderr)
            sys.exit(3)
        print(f"contract-shape compatible with {a.check_compat}", file=sys.stderr)

if __name__ == "__main__":
    main()
