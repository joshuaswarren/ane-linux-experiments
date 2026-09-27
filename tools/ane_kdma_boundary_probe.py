#!/usr/bin/env python3
"""KernelDMA per-core-size boundary probe (paired, interleaved, bounded).

Question (eiln 2026-08-10, https://eiln.github.io/posts/ane-dma.html): on M3
Air, a KernelDMA task whose per-core transfer size is an exact 1 MiB multiple
throttles DRAM streaming to 17-19 GB/s from a 45-60 GB/s nominal. The article
measured M3 only. This probe measures whether T8103/T6001 show the notch at
all. It makes NO end-to-end model claim: the numbers are per-task 16-core
KernelDMA bytes divided by submit-completion time, nothing else.

Mechanics: a pinned-compiler-minted H13 chunk program (single 628-byte task,
KDMA table = 62 words: flag, pad, 16 x base address, 16 x per-core offset,
16 x per-core size, 4 x EOL — layout per H13Program.cpp putFirmwareDMA and
decoded verbatim into receipts) is re-emitted with per-core size S and
disjoint slices at i*S. Slice content is RELOCATED: original bytes
[i*0x8000, +0x8000) land at [i*S, +0x8000), tail zero-filled, so the compute
consumes the same weights and the output must equal the unpatched device
baseline bit-exact. Every submit is verified before its timing counts.

Timing: ANE_SUBMIT is KMD-synchronous (ane_tm.c read_poll_timeout on engine
status; production-anec-probe.py documents the ABI) — each sample is wall
time around the submit ioctl, which returns at terminal completion. No
output sentinels, no completion polling.

Protocol: interleaved round-robin across all sizes, fixed order per round;
2 untimed warmup rounds, then --rounds timed rounds. Per size: n, min, p25,
median, p75, max, and 16*S/median. Raw samples land in a JSON artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
HEADER_SIZE = 0x1000
TD_SIZE = 0x274
KERNEL_FIELD_BASE = 0x81000000  # bar[KRN] bank-relative base (wire BE word 0x81)
BASE_SLICE = 0x8000             # minted per-core size and stride
CORES = 16

MIL_TEMPLATE = """program(1.3)
[buildInfo = dict<string, string>({{}})]
{{
  func main<ios18>(tensor<fp16, [1, {k}]> x) {{
    tensor<fp16, [{n}, {k}]> w = const()[name = string("w"), val = tensor<fp16, [{n}, {k}]>(BLOBFILE(path = string("@model_path/weights.bin"), offset = uint64(64)))];
    tensor<fp16, [1, {n}]> y = matmul(x = x, y = w, transpose_x = false, transpose_y = true)[name = string("y")];
  }} -> (y);
}}
"""


def mint_bundle(out_dir: Path, compiler: Path) -> Path:
    """Mint the k4096 x n2048 constant-weight matmul; return the chunk program."""
    import tempfile

    k, n = 4096, 2048
    rng = np.random.default_rng(11)
    w = (rng.standard_normal((n, k)) * 0.02).astype(np.float16)
    w_bytes = w.tobytes()
    data_start = (64 + 4096 * 24 + 63) & ~63
    blob = bytearray(data_start + len(w_bytes))
    struct.pack_into("<II", blob, 0, 2, 2)
    struct.pack_into("<II", blob, 64, 0xDEADBEEF, 1)
    struct.pack_into("<QQ", blob, 64 + 8, len(w_bytes), data_start)
    blob[data_start:] = w_bytes

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "weights.bin").write_bytes(bytes(blob))
        (tmp / "test.mil").write_text(MIL_TEMPLATE.format(k=k, n=n))
        result = subprocess.run(
            [str(compiler), "--mil", str(tmp / "test.mil"),
             "--model-root", str(tmp), "--output", str(tmp / "out"),
             "--target", "H13", "--format", "anec"],
            capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"mil-hwxc failed: {result.stderr[-400:]}")
        out_dir.mkdir(parents=True, exist_ok=True)
        programs = sorted((tmp / "out").glob("program-*.anec"))
        chunk = max(programs, key=lambda p: p.stat().st_size)
        payload = chunk.read_bytes()
        target = out_dir / "program-chunk.anec"
        target.write_bytes(payload)
        print(f"minted: {result.stdout.strip()}")
        print(f"chunk program {chunk.name} -> {target} ({len(payload)} bytes)")
        return target


def load_program(path: Path):
    """Return (td_bytes, kernel_bytes, src_bytes, dst_bytes, header)."""
    data = path.read_bytes()
    header = struct.unpack_from("<QIIQQII32I192Q", data, 0)
    content_size, td_size, td_count, task_stream = header[0], header[1], header[2], header[3]
    kernel_size = header[4]
    if td_size != TD_SIZE or td_count != 1 or task_stream != TD_SIZE:
        raise ValueError(f"probe calibrated for single-TD programs, got "
                         f"td_size={td_size:#x} td_count={td_count}")
    if kernel_size != CORES * BASE_SLICE:
        raise ValueError(f"probe calibrated for {CORES * BASE_SLICE:#x} kernel, "
                         f"got {kernel_size:#x}")
    if len(data) < HEADER_SIZE + content_size:
        raise ValueError("file truncated below declared content")
    content = data[HEADER_SIZE:HEADER_SIZE + content_size]
    td = bytes(content[:TD_SIZE])
    kernel_start = (TD_SIZE + 15) & ~15
    kernel = bytes(content[kernel_start:kernel_start + kernel_size])
    src = np.full(0x8000 // 2, np.float16(1.0), dtype=np.float16)
    dst = bytes(content[kernel_start + kernel_size:content_size])  # tile scratch, if any
    return td, kernel, src, dst, header


def decode_kdma(td: bytes):
    """Decode the 62-word kernel_dma_src table; returns (offsets, sizes)."""
    words = struct.unpack(f"<{len(td) // 4}I", td)
    header_word = words[10]
    if header_word & 0x3FFFFFF != 0x1F800:
        raise ValueError(f"task has no kernel_dma table (hdr {header_word:#x})")
    nwords = ((header_word >> 26) & 0x3F) + 1
    if nwords != 62:
        raise ValueError(f"kernel_dma table is {nwords} words, probe expects 62")
    ctx = words[11:73]
    if ctx[0] & 0x40 != 0x40:
        raise ValueError("kernel DMA not active in baseline task")
    return list(ctx[18:34]), list(ctx[34:50]), ctx


def patch_td(td: bytes, size: int) -> bytes:
    """Rewrite per-core offsets to i*size and sizes to size (disjoint slices)."""
    if size % 64:
        raise ValueError(f"size {size:#x} is not 64-byte line aligned")
    if size < BASE_SLICE:
        raise ValueError(f"size {size:#x} below baseline slice {BASE_SLICE:#x} "
                         "would truncate the weights the compute consumes")
    if size * CORES > 0xFFFFFFFF:
        raise ValueError(f"extent {size * CORES:#x} overflows u32 slice fields")
    buf = bytearray(td)
    for i in range(CORES):
        struct.pack_into("<I", buf, 0x2C + 4 * (18 + i), i * size)   # offset words
        struct.pack_into("<I", buf, 0x2C + 4 * (34 + i), size)       # size words
    return bytes(buf)


def relocate_kernel(kernel: bytes, size: int) -> bytes:
    """Move each core's original slice to the start of its new slice."""
    if size * CORES > 0x100000000:
        raise ValueError("relocated kernel exceeds 4 GiB addressability")
    out = bytearray(CORES * size)
    for i in range(CORES):
        out[i * size:i * size + BASE_SLICE] = kernel[i * BASE_SLICE:(i + 1) * BASE_SLICE]
    return bytes(out)


def build_command(td: bytes, kernel: bytes):
    """Command BO layout: TD at 0, kernel blob at round_up(tsk, 16)."""
    kernel_start = (TD_SIZE + 15) & ~15
    cmd = bytearray(kernel_start + len(kernel))
    cmd[:len(td)] = td
    cmd[kernel_start:kernel_start + len(kernel)] = kernel
    return bytes(cmd)


def load_runtime():
    runtime_path = ROOT / "ane-runtime.py"
    import importlib.util
    spec = importlib.util.spec_from_file_location("ane_runtime", runtime_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {runtime_path}")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    return runtime


def submit_once(runtime, device, cmd_handle, btsp_handle, src_buf, dst_buf,
                dst_bytes):
    """One KMD-synchronous submit; returns (ns, output bytes)."""
    request = runtime.Submit(
        tsk_size=TD_SIZE, td_count=1, td_size=TD_SIZE,
        btsp_handle=btsp_handle, pad=0,
    )
    request.handles[0] = cmd_handle      # command + kernel BO
    request.handles[4] = dst_buf.bo.handle
    request.handles[4 + 1] = src_buf.bo.handle
    t0 = time.perf_counter_ns()
    from fcntl import ioctl
    ioctl(device.fd, runtime.IOCTL_SUBMIT, request)
    t1 = time.perf_counter_ns()
    return t1 - t0, bytes(dst_buf.read(dst_bytes))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mint", action="store_true",
                        help="mint the base bundle with the host mil-hwxc")
    parser.add_argument("--bundle", type=Path, default=None,
                        help="pre-minted chunk program (skips mint)")
    parser.add_argument("--compiler", type=Path,
                        default=Path("~/src/mil-hwx-compiler/build/mil-hwxc")
                        .expanduser())
    parser.add_argument("--work-dir", type=Path,
                        default=Path("/tmp/ane-kdma-boundary-probe"))
    parser.add_argument("--sizes", type=str, default=",".join(
        hex(s) for s in (0x8000, 0xFF000, 0xFFC0, 0x100000, 0x100040,
                         0x101000, 0x180000, 0x1FF000, 0x200000, 0x200040,
                         0x300000)))
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--artifact", type=Path, default=None)
    args = parser.parse_args()

    sizes = [int(s, 16) for s in args.sizes.split(",")]
    max_extent = max(sizes) * CORES

    if args.mint or args.bundle is None:
        program_path = mint_bundle(args.work_dir, args.compiler)
    else:
        program_path = args.bundle
    td, kernel, src, _dst, header = load_program(program_path)
    base_offsets, base_sizes, _ = decode_kdma(td)
    if base_sizes != [BASE_SLICE] * CORES:
        raise ValueError(f"baseline sizes {base_sizes[:2]}... not uniform")

    print(f"program: {program_path}")
    print(f"sizes:   {[hex(s) for s in sizes]}")
    print(f"max command allocation: {(TD_SIZE + 15) // 16 * 16 + max_extent:#x} bytes")
    print(f"per-size DRAM traffic: 16 x S bytes; S in "
          f"[{min(sizes):#x}, {max(sizes):#x}]")

    # Pre-build all variants outside any timed region.
    variants = {}
    for size in sizes:
        ptd = patch_td(td, size)
        blob = relocate_kernel(kernel, size) if size != BASE_SLICE else kernel
        variants[size] = {
            "td": ptd,
            "cmd": build_command(ptd, blob),
            "btsp": ptd,
        }
        # Bounds proof for the artifact: patched table must decode as intended.
        off, sz, _ = decode_kdma(ptd)
        assert off == [i * size for i in range(CORES)], size
        assert sz == [size] * CORES, size

    runtime = load_runtime()
    baseline = None
    samples = {size: [] for size in sizes}
    digest = lambda b: hashlib.sha256(b).hexdigest()[:16]

    with runtime.Device() as device, \
            device.buffer((TD_SIZE + 15) + max_extent) as command, \
            device.buffer(TD_SIZE) as btsp, \
            device.buffer(0x8000) as src_buf, \
            device.buffer(0x8000) as dst_buf:
        src_buf.write(src.tobytes())
        cmd_handle = command.bo.handle
        btsp_handle = btsp.bo.handle
        dst_bytes = 0x8000

        for size in sizes:
            command.map.seek(0)
            command.map.write(variants[size]["cmd"])
            btsp.map.seek(0)
            btsp.map.write(variants[size]["btsp"])
            _, out = submit_once(runtime, device, cmd_handle, btsp_handle,
                                 src_buf, dst_buf, dst_bytes)
            if baseline is None:
                baseline = out
                print(f"baseline digest {digest(out)} (size {size:#x})")
            elif out != baseline:
                raise RuntimeError(
                    f"size {size:#x} warmup output differs from baseline — "
                    "relocation semantics broken; refusing to time")

        total = args.warmups + args.rounds
        for rnd in range(total):
            for size in sizes:  # fixed interleaved order
                # Full command rewrite (TD + this size's blob) is untimed;
                # only the KMD-synchronous submit ioctl is timed.
                command.map.seek(0)
                command.map.write(variants[size]["cmd"])
                btsp.map.seek(0)
                btsp.map.write(variants[size]["btsp"])
                ns, out = submit_once(runtime, device, cmd_handle,
                                      btsp_handle, src_buf, dst_buf, dst_bytes)
                if out != baseline:
                    raise RuntimeError(
                        f"size {size:#x} round {rnd}: output differs from "
                        "baseline; timing discarded")
                if rnd >= args.warmups:
                    samples[size].append(ns)
            print(f"round {rnd + 1}/{total} done", flush=True)

    artifact = {
        "host": platform.node(),
        "machine": platform.machine(),
        "kernel": platform.release(),
        "driver_srcversion": _driver_srcversion(),
        "program_sha256": hashlib.sha256(program_path.read_bytes()).hexdigest(),
        "baseline_output_sha256": hashlib.sha256(baseline).hexdigest(),
        "td_baseline_hex": td.hex(),
        "td_patched_examples": {hex(s): variants[s]["td"].hex()
                                for s in (0x100000,)},
        "sizes": [hex(s) for s in sizes],
        "rounds": args.rounds,
        "warmups": args.warmups,
        "samples_ns": {hex(s): samples[s] for s in sizes},
    }
    artifact_path = args.artifact or args.work_dir / "kdma_boundary_samples.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=1))

    print(f"\n=== per-size results (ns samples, {args.rounds} rounds) ===")
    print(f"{'size':>10} {'median us':>10} {'p25':>10} {'p75':>10} "
          f"{'min':>10} {'max':>10} {'16*S/med GB/s':>14}")
    medians = {}
    for size in sizes:
        arr = np.asarray(samples[size], dtype=float) / 1000.0
        med = float(np.median(arr))
        medians[size] = med
        print(f"{size:#10x} {med:10.1f} {np.percentile(arr, 25):10.1f} "
              f"{np.percentile(arr, 75):10.1f} {arr.min():10.1f} "
              f"{arr.max():10.1f} {CORES * size / (med * 1e3):14.1f}")
    artifact["summary"] = {
        hex(s): {"median_us": medians[s],
                 "gb_per_s": CORES * s / (medians[s] * 1e3)}
        for s in sizes
    }
    artifact_path.write_text(json.dumps(artifact, indent=1))
    print(f"\nartifact: {artifact_path}")
    return 0


def _driver_srcversion():
    for name in ("ane", "apple_ane"):
        path = Path(f"/sys/module/{name}/srcversion")
        if path.exists():
            return path.read_text().strip()
    return "unknown"


if __name__ == "__main__":
    sys.exit(main())
