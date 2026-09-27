#!/usr/bin/env python3
"""Chain the staged 38-program Qwen3.8-2B decoder on the Linux ANE.

One ANE program per manifest entry (macOS e5rt staged export, ANEForge
deltanet-split-decode), resident conv/recurrent/KV states kept on device in
alternating buffers, host work limited to gathers, copies, scheduling, and
token selection. Every tensor operation runs on the ANE; there is no CPU or
GPU tensor fallback.

State-block bank binding is the bitwise-verified one from the m1max-host
state-block campaign:
inputs bank4=beta bank5=gt bank7=q bank9=state bank10=k bank11=v, outputs
bank6=state' bank8=o; [16,1] gates stage at 64-byte rows in a 1024-byte
window. Other classes bind by the same window geometry, and every execution
can be hash-checked against the Apple goldens (tools/staged-decode-verify.py).
"""

import argparse
import fcntl
import hashlib
import importlib.util
import json
import mmap
import os
import struct
import time
from contextlib import ExitStack
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROBE = load_module(
    "production_anec_probe", Path(__file__).with_name("production-anec-probe.py")
)
RUNTIME = load_module("ane_runtime", ROOT / "ane-runtime.py")

ROW_STRIDE = 64  # staged gate/state rows: values at the row head, 64 B stride


def decode_channels(path):
    """Return (stage, {channel: (read_total, write_total)}) for one .anec.

    Selector words sit at +32 in each task descriptor (shifts 0/6/12/18 are
    channel fields, proven by the m1max-host TD-decode grammar); tile-DMA
    register records carry each task's own run/total byte counts. Shift 12 is
    the destination field; all other non-zero channel fields are sources.
    """
    header = PROBE.load_anec_header(path)
    stage = PROBE.stage_geometry(header)
    with path.open("rb") as stream, mmap.mmap(
        stream.fileno(), 0, access=mmap.ACCESS_READ
    ) as data:
        bases = PROBE.task_bases(data, PROBE.HEADER_SIZE, stage["task_stream_size"])
        offset = PROBE.HEADER_SIZE
        chain = []
        seen = set()
        while offset not in seen and len(chain) < stage["td_count"]:
            seen.add(offset)
            chain.append(offset)
            nxt = struct.unpack_from("<I", data, offset + 0x1C)[0]
            if not nxt:
                break
            offset = PROBE.HEADER_SIZE + nxt
        channels: dict[int, list[int]] = {}
        for base in chain:
            td = data[base:base + stage["td_size"]]
            if len(td) < stage["td_size"]:
                raise ValueError(f"{Path(path).name}: truncated task descriptor")
            selector = struct.unpack_from("<I", td, 32)[0]
            registers = walk_registers(td)
            read = max(registers.get(0x13814, 0), registers.get(0x13810, 0))
            write = max(registers.get(0x17810, 0), registers.get(0x1780C, 0))
            for shift in (0, 6, 12, 18):
                channel = (selector >> shift) & 0x1F
                if not channel:
                    continue
                totals = channels.setdefault(channel, [0, 0])
                if shift == 12:
                    totals[1] = max(totals[1], write)
                else:
                    totals[0] = max(totals[0], read)
    return stage, {ch: tuple(t) for ch, t in channels.items()}


def walk_registers(td):
    """{register byte address: value} for one task descriptor (proven walk)."""
    head = struct.unpack_from("<I", td, 0)[0]
    registers: dict[int, int] = {}
    offset = 40 + (4 if head & 0x3 == 0x3 else 0)
    while offset + 4 <= len(td):
        word = struct.unpack_from("<I", td, offset)[0]
        if not word:
            break
        register = word & 0x3FFFFFF
        words = (word >> 26) + 1
        offset += 4
        if offset + 4 * words > len(td):
            break  # only the DMA counts matter here; keep the decode safe
        for index in range(words):
            registers[register + 4 * index] = struct.unpack_from(
                "<I", td, offset + 4 * index
            )[0]
        offset += 4 * words
    return registers


def staged_bytes(array, window):
    """Pack one logical fp16 tensor into its staged window bytes.

    Rows shorter than 64 bytes sit at the head of 64-byte rows (the proven
    pack1024 gate convention and the [6144,3] conv-state window); longer rows
    are dense. The result must fill the artifact's declared window exactly;
    anything else is a binding error, not a guess.
    """
    array = np.asarray(array, dtype=np.float16)
    columns = array.shape[-1] if array.ndim else 1
    row_bytes = columns * 2
    if array.ndim < 2 or row_bytes >= ROW_STRIDE:
        payload = np.ascontiguousarray(array).reshape(-1).tobytes()
    else:
        rows = array.size // columns
        window_rows = np.zeros((rows, ROW_STRIDE // 2), dtype=np.float16)
        window_rows[:, :columns] = array.reshape(rows, columns)
        payload = window_rows.tobytes()
    if len(payload) != window:
        raise ValueError(
            f"staged {len(payload)} B does not fill the declared {window} B window"
        )
    return payload


def logical_bytes(array):
    """The compact fp16 bytes the Apple goldens hash (set_input view)."""
    return np.ascontiguousarray(array, dtype=np.float16).tobytes()


def _tile(size):
    return ((max(size, 1) + 0x3FFF) // 0x4000) * 0x4000


class StagedProgram:
    """One converted .anec with its own bank buffers and resident states."""

    def __init__(self, anec_path, device, binding, name=""):
        self.path = Path(anec_path)
        self.name = name or self.path.stem
        self.device = device
        self.stage, channels = decode_channels(self.path)
        self.binding = dict(binding)
        silent = sorted(set(self.binding) - set(channels))
        if silent:
            raise ValueError(f"{self.name}: ports bind silent channels {silent}")
        self.window = {}
        for channel, (read_total, write_total) in channels.items():
            total = max(read_total, write_total)
            if total <= 0:
                raise ValueError(f"{self.name}: channel {channel} has no DMA size")
            self.window[channel] = total
        self.closed = False
        self.stack = ExitStack()
        try:
            with self.path.open("rb") as stream, mmap.mmap(
                stream.fileno(), 0, access=mmap.ACCESS_READ
            ) as data:
                stage = self.stage
                self.command = self.stack.enter_context(
                    device.buffer(stage["content_size"])
                )
                PROBE.copy_content(
                    data, PROBE.HEADER_SIZE, stage["content_size"], self.command.map
                )
                self.workspace = (
                    self.stack.enter_context(device.buffer(stage["workspace_size"]))
                    if stage["workspace_size"]
                    else None
                )
                if self.workspace is not None:
                    self.workspace.write(b"\0" * stage["workspace_size"])
                self.btsp = self.stack.enter_context(
                    device.buffer(stage["task_stream_size"])
                )
                bases = PROBE.task_bases(
                    data, PROBE.HEADER_SIZE, stage["task_stream_size"]
                )
                bootstrap = PROBE.build_original_prefix(
                    data, PROBE.HEADER_SIZE, stage["task_stream_size"],
                    bases, stage["td_count"],
                )
                self.btsp.write(bootstrap)
                first = struct.unpack_from("<I", self.btsp.map)[0]
                self.btsp.map.seek(0)
                self.btsp.map.write(
                    struct.pack("<I", (first & 0x0F00FFFF) | (0x40 << 16))
                )
            self.banks = {}
            for channel, total in self.window.items():
                bank = self.stack.enter_context(device.buffer(_tile(total)))
                bank.write(b"\0" * bank.size)
                self.banks[channel] = bank
            self.request = RUNTIME.Submit(
                tsk_size=stage["task_stream_size"],
                td_count=stage["td_count"],
                td_size=stage["td_size"],
                btsp_handle=self.btsp.bo.handle,
                pad=0,
            )
            self.request.handles[0] = self.command.bo.handle
            if self.workspace is not None:
                self.request.handles[PROBE.WORKSPACE_BDX] = self.workspace.bo.handle
            self.states: dict[tuple[int, int], list] = {}
        except BaseException:
            self.stack.close()
            self.closed = True
            raise

    def add_state(self, in_port, out_port):
        """Register one resident state as an alternating buffer pair."""
        pair = [
            self.stack.enter_context(
                self.device.buffer(_tile(self.window[self.binding[in_port]]))
            ),
            self.stack.enter_context(
                self.device.buffer(_tile(self.window[self.binding[out_port]]))
            ),
        ]
        for bank in pair:
            bank.write(b"\0" * bank.size)
        self.states[(self.binding[in_port], self.binding[out_port])] = [pair, 0]

    def write_bank(self, port, array):
        channel = self.binding[port]
        payload = staged_bytes(array, self.window[channel])
        self.banks[channel].map.seek(0)
        self.banks[channel].write(payload)

    def write_state(self, in_port, out_port, array):
        pair, flip = self.states[(self.binding[in_port], self.binding[out_port])]
        payload = staged_bytes(
            array, self.window[self.binding[in_port]]
        )
        pair[flip].map.seek(0)
        pair[flip].write(payload)

    def read_output(self, port, shape):
        bank = self.banks[self.binding[port]]
        raw = bank.read(int(np.prod(shape)) * 2)
        return np.frombuffer(raw, dtype=np.float16).reshape(shape).copy()

    def execute(self, output_ports):
        """Submit once, poll every staged output to finiteness, swap states."""
        sentinel = np.float16(np.inf).tobytes()
        watched = []
        for (in_channel, out_channel), (pair, flip) in self.states.items():
            state_out = pair[1 - flip]
            state_out.map.seek(0)
            state_out.write(sentinel * state_out.size)
            watched.append(state_out)
        for port in output_ports:
            bank = self.banks[self.binding[port]]
            bank.map.seek(0)
            bank.write(sentinel * bank.size)
            watched.append(bank)
        for (in_channel, out_channel), (pair, flip) in self.states.items():
            self.request.handles[in_channel] = pair[flip].bo.handle
            self.request.handles[out_channel] = pair[1 - flip].bo.handle
        for port in output_ports:
            self.request.handles[self.binding[port]] = self.banks[
                self.binding[port]
            ].bo.handle
        fcntl.ioctl(self.device.fd, RUNTIME.IOCTL_SUBMIT, self.request)
        deadline = time.monotonic() + 30.0
        while True:
            pending = [
                bank for bank in watched
                if b"\x00\x7c\x00\x7c" in bank.read(64)
            ]
            if not pending:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"{self.name}: outputs stayed infinite")
            time.sleep(0.001)
        for key, (pair, flip) in self.states.items():
            pair[0], pair[1] = pair[1], pair[0]
            self.states[key] = [pair, 1 - flip]

    def rewind_states(self):
        for key, (pair, _) in self.states.items():
            for bank in pair:
                bank.map.seek(0)
                bank.write(b"\0" * bank.size)
            self.states[key] = [pair, 0]

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.stack.close()


class StagedDecoder:
    """The full 38-program decode chain for one device."""

    def __init__(self, manifest_path, anec_dir, bindings_path=None, qid=None):
        self.manifest = json.loads(Path(manifest_path).read_text())
        self.max_len = int(self.manifest["max_len"])
        self.anec_dir = Path(anec_dir)
        bindings = (
            json.loads(Path(bindings_path).read_text())
            if bindings_path
            else {"default": {}, "programs": {}}
        )
        self.device = RUNTIME.Device(qid=qid)
        self.programs = []
        try:
            for index, program in enumerate(self.manifest["programs"]):
                binding = bindings["programs"].get(str(index), bindings["default"])
                staged = StagedProgram(
                    self.anec_dir / f"prog_{index:03d}.anec", self.device,
                    binding, name=f"prog_{index:03d}",
                )
                for state in program.get("states", []):
                    staged.add_state(state["in_port"], state["out_port"])
                self.programs.append(staged)
        except BaseException:
            self.close()
            raise
        self.lanes: dict[str, np.ndarray] = {}
        self.position = 0

    def reset(self):
        for staged in self.programs:
            staged.rewind_states()
        self.lanes = {}
        self.position = 0

    def context_arrays(self, position, rope):
        """oh/inv/mask rows plus this position's rope row (host tables)."""
        m = self.max_len
        oh = np.zeros((1, m, 1), dtype=np.float16)
        oh[0, position, 0] = np.float16(1.0)
        inv = (np.float16(1.0) - oh).astype(np.float16)
        mask = np.full((1, 1, m), np.float16(-1e4), dtype=np.float16)
        mask[0, 0, : position + 1] = np.float16(0.0)
        return {
            "oh": oh, "inv": inv, "mask": mask,
            "cosp": rope["cosp"][position], "sinp": rope["sinp"][position],
        }

    def step(self, hidden, rope):
        """Run one token through all programs; returns the final hidden."""
        self.lanes["x"] = np.asarray(hidden, dtype=np.float16).reshape(1, -1)
        for staged, program in zip(self.programs, self.manifest["programs"]):
            context = self.context_arrays(self.position, rope)
            for source in program["srcs"]:
                kind, lane = source["kind"], source["lane"]
                if kind == "state_in":
                    continue  # resident; content stays on device
                value = (
                    self.lanes[lane] if kind == "lane"
                    else context[lane].reshape(tuple(source["shape"]))
                )
                staged.write_bank(source["port"], value)
            outputs = {d["port"]: tuple(d["shape"]) for d in program["dsts"]}
            staged.execute(outputs)
            for dst in program["dsts"]:
                self.lanes[dst["lane"]] = staged.read_output(
                    dst["port"], tuple(dst["shape"])
                )
        self.position += 1
        return self.lanes["h"].reshape(-1)

    def close(self):
        for staged in self.programs:
            staged.close()
        self.programs = []
        if getattr(self, "device", None) is not None:
            self.device.close()
            self.device = None


class TiedHead:
    """ANE tiled tied lm_head over the GGUF embedding (host argmax only)."""

    def __init__(self, embedding, gemm, adder):
        self.embedding = embedding  # [vocab, dim] fp16
        self.gemm = gemm            # device.gemm or tile_gemm closure
        self.adder = adder          # ANE elementwise add

    def logits(self, hidden):
        matrix = self.embedding
        result = np.empty(matrix.shape[0], dtype=np.float16)
        mid = id(matrix)
        for row0 in range(0, matrix.shape[0], 512):
            acc = None
            for col0 in range(0, matrix.shape[1], 256):
                cols = min(256, matrix.shape[1] - col0)
                x = np.zeros(256, dtype=np.float16)
                x[:cols] = hidden[col0:col0 + cols]
                partial = self.gemm((mid, 256, row0, col0), matrix, x).astype(
                    np.float16
                )
                acc = partial if acc is None else self.adder(acc, partial)
            result[row0:row0 + 512] = acc[:512]
        return result


def build_tied_head(weights, device, descriptor, elementwise_descriptors):
    """Wire the head to the ANE: persistent tiles plus ANE adds."""
    softmax = load_module(
        "ane_softmax", ROOT / "ane-softmax.py"
    )
    backend = softmax.ElementwiseBackend(device, elementwise_descriptors)
    operations = softmax.TensorOperations(backend)

    def gemm(key, matrix, x):
        tile_cache = getattr(device, "tile_gemm", None)
        _, _, row0, col0 = key
        if os.environ.get("ANE_NO_PERSISTENT") != "1" and tile_cache:
            return tile_cache(key, matrix, x, descriptor, 256)
        tile = np.zeros((512, 256), dtype=np.float16)
        rows = min(512, matrix.shape[0] - row0)
        cols = min(256, matrix.shape[1] - col0)
        tile[:rows, :cols] = matrix[row0:row0 + rows, col0:col0 + cols]
        return device.gemm(tile, x, descriptor)

    return TiedHead(
        weights.tensor("token_embd.weight"), gemm, operations.add
    ), backend


def load_rope_tables(m, weights, dh=256, default_base=10_000_000.0,
                     default_rotary_dim=64):
    """Per-position cos/sin rows (ANEForge rope_tables verbatim: the rd-wide
    duplicated-half table padded with cos=1/sin=0 pass-through)."""
    base = weights.reader.get_field("qwen35.rope.freq_base")
    rotary = weights.reader.get_field("qwen35.rope.dimension_count")
    base = _field_scalar(base) if base is not None else default_base
    rotary_dim = (
        int(_field_scalar(rotary)) if rotary is not None else default_rotary_dim
    )
    inverse = 1.0 / (base ** (np.arange(0, rotary_dim, 2) / rotary_dim))
    positions = np.arange(m)[:, None] * inverse[None, :]
    emb = np.concatenate([positions, positions], -1)
    pad = dh - rotary_dim
    cos = np.concatenate([np.cos(emb), np.ones((m, pad))], 1).astype(np.float16)
    sin = np.concatenate([np.sin(emb), np.zeros((m, pad))], 1).astype(np.float16)
    return {"cosp": cos, "sinp": sin}


def _field_scalar(field):
    """Read one scalar GGUF metadata value across gguf-py versions."""
    contents = field.contents() if callable(field.contents) else field.contents
    return contents[-1] if hasattr(contents, "__len__") else contents


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--anec-dir", type=Path, required=True)
    parser.add_argument("--bindings", help="per-program port->channel JSON")
    parser.add_argument("-m", "--model", required=True, help="the contract GGUF")
    parser.add_argument("-p", "--prompt", required=True)
    parser.add_argument("--generate", type=int, default=0)
    parser.add_argument("--qid", type=int, default=None)
    args = parser.parse_args(argv)

    weights = load_module("ane_weights", ROOT / "ane-weights.py").GGUFWeights(
        args.model
    )
    tokenizer = load_module("ane_tokenizer", ROOT / "ane-tokenizer.py").Tokenizer(
        args.model
    )
    descriptor = RUNTIME.load_descriptor(str(ROOT / "ane-network.py"))
    softmax_path = ROOT / "ane-softmax.py"
    token_runtime = load_module(
        "qwen_token_runtime", Path(__file__).with_name("qwen-token-runtime.py")
    )
    elementwise = token_runtime.harvest_elementwise_descriptors(str(softmax_path))

    decoder = StagedDecoder(
        args.manifest, args.anec_dir, args.bindings, args.qid
    )
    try:
        head, backend = build_tied_head(
            weights, decoder.device, descriptor, elementwise
        )
        rope = load_rope_tables(decoder.max_len, weights)
        embedding = head.embedding
        ids = tokenizer.encode(args.prompt)
        budget = len(ids) + max(args.generate, 1)
        if budget > decoder.max_len:
            raise SystemExit(
                f"prompt+generation ({budget}) exceeds compiled max_len "
                f"{decoder.max_len}"
            )
        generated = []
        hidden = None
        for position, token in enumerate(ids):
            hidden = decoder.step(embedding[token], rope)
            logits = head.logits(hidden)
            generated.append(int(np.argmax(logits)))
        for _ in range(args.generate - 1 if args.generate else 0):
            hidden = decoder.step(embedding[generated[-1]], rope)
            logits = head.logits(hidden)
            generated.append(int(np.argmax(logits)))
        field = weights.reader.get_field("tokenizer.ggml.tokens")
        pieces = [
            field.contents(i).decode("utf-8", "replace") if field else str(i)
            for i in generated
        ]
        print(f"generated_ids={generated}")
        print(f"generated_pieces={pieces}")
        print("STAGED_DECODE_OK")
    finally:
        decoder.close()


if __name__ == "__main__":
    main()
