#!/usr/bin/env python3
"""Whole-weight-class baseline runner for the KernelDMA boundary question.

Context (eiln 2026-08-10, https://eiln.github.io/posts/ane-dma.html): on M3
Air, KernelDMA tasks of exactly k x 1 MiB per core throttle DRAM streaming.
Applicability to our chips (T8103/T6001) is UNKNOWN. An earlier revision of
this tool also re-wrote the task's per-core kernel-DMA size fields to probe
sizes the compute does not consume; that form is INVALID on T6001 — the
submit timed out and the driver wedged (receipts/2026-09-27-kdma-boundary-
jw16-wedge-and-source-analysis.md). The size-patch mode was REMOVED; a lone
timeout does not establish the mechanism, and a runnable known-wedging tool
must not ship.

What remains is the validated safe half: mint the pinned compiler's chunk
program (single 628-byte TD, 16 cores x 0x8000 B kernel DMA, 512 KiB kernel
blob), submit it once, and report the KMD-synchronous completion time and
output digest. Any transfer-size sweep must use whole-weight compiled
workloads where compute == transfer (see the receipt's proposal) and needs
separate review before execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
BASE_SLICE = 0x8000
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
        target = out_dir / "program-chunk.anec"
        target.write_bytes(chunk.read_bytes())
        print(f"minted: {result.stdout.strip()}")
        print(f"chunk program {chunk.name} -> {target} ({target.stat().st_size} bytes)")
        return target


def load_program(path: Path):
    """Return (td_bytes, kernel_bytes, src_bytes, header)."""
    data = path.read_bytes()
    header = struct.unpack_from("<QIIQQII32I192Q", data, 0)
    content_size, td_size, td_count, task_stream = header[0], header[1], header[2], header[3]
    kernel_size = header[4]
    if td_size != TD_SIZE or td_count != 1 or task_stream != TD_SIZE:
        raise ValueError(f"runner calibrated for single-TD programs, got "
                         f"td_size={td_size:#x} td_count={td_count}")
    if kernel_size != CORES * BASE_SLICE:
        raise ValueError(f"runner calibrated for {CORES * BASE_SLICE:#x} kernel, "
                         f"got {kernel_size:#x}")
    if len(data) < HEADER_SIZE + content_size:
        raise ValueError("file truncated below declared content")
    content = data[HEADER_SIZE:HEADER_SIZE + content_size]
    td = bytes(content[:TD_SIZE])
    kernel_start = (TD_SIZE + 15) & ~15
    kernel = bytes(content[kernel_start:kernel_start + kernel_size])
    src = np.full(0x8000 // 2, np.float16(1.0), dtype=np.float16)
    return td, kernel, src, header


def decode_kdma(td: bytes):
    """Decode the 62-word kernel_dma_src table; returns (offsets, sizes)."""
    words = struct.unpack(f"<{len(td) // 4}I", td)
    header_word = words[10]
    if header_word & 0x3FFFFFF != 0x1F800:
        raise ValueError(f"task has no kernel_dma table (hdr {header_word:#x})")
    nwords = ((header_word >> 26) & 0x3F) + 1
    if nwords != 62:
        raise ValueError(f"kernel_dma table is {nwords} words, runner expects 62")
    ctx = words[11:73]
    if ctx[0] & 0x40 != 0x40:
        raise ValueError("kernel DMA not active in baseline task")
    return list(ctx[18:34]), list(ctx[34:50])


def load_runtime():
    runtime_path = ROOT / "ane-runtime.py"
    import importlib.util
    spec = importlib.util.spec_from_file_location("ane_runtime", runtime_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {runtime_path}")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    return runtime


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
    parser.add_argument("--artifact", type=Path, default=None)
    args = parser.parse_args()

    if args.mint or args.bundle is None:
        program_path = mint_bundle(args.work_dir, args.compiler)
    else:
        program_path = args.bundle
    td, kernel, src, header = load_program(program_path)
    offsets, sizes = decode_kdma(td)
    if sizes != [BASE_SLICE] * CORES:
        raise ValueError(f"baseline sizes {sizes[:2]}... not uniform")

    kernel_start = (TD_SIZE + 15) & ~15
    cmd = bytearray(kernel_start + len(kernel))
    cmd[:len(td)] = td
    cmd[kernel_start:kernel_start + len(kernel)] = kernel

    print(f"program: {program_path}")
    print(f"task: single TD, 16 cores x {BASE_SLICE:#x} kernel DMA at "
          f"offsets {offsets[0]:#x}..{offsets[-1]:#x}")

    runtime = load_runtime()
    with runtime.Device() as device, \
            device.buffer(len(cmd)) as command, \
            device.buffer(TD_SIZE) as btsp, \
            device.buffer(0x8000) as src_buf, \
            device.buffer(0x8000) as dst_buf:
        src_buf.write(src.tobytes())
        command.map.seek(0)
        command.map.write(bytes(cmd))
        btsp.map.seek(0)
        btsp.map.write(td)
        request = runtime.Submit(
            tsk_size=TD_SIZE, td_count=1, td_size=TD_SIZE,
            btsp_handle=btsp.bo.handle, pad=0,
        )
        request.handles[0] = command.bo.handle
        request.handles[4] = dst_buf.bo.handle
        request.handles[5] = src_buf.bo.handle
        from fcntl import ioctl
        t0 = time.perf_counter_ns()
        ioctl(device.fd, runtime.IOCTL_SUBMIT, request)
        t1 = time.perf_counter_ns()
        out = bytes(dst_buf.read(0x8000))

    digest = hashlib.sha256(out).hexdigest()
    artifact = {
        "host": platform.node(),
        "machine": platform.machine(),
        "kernel": platform.release(),
        "driver_srcversion": _driver_srcversion(),
        "program_sha256": hashlib.sha256(program_path.read_bytes()).hexdigest(),
        "output_sha256": digest,
        "submit_completion_ns": t1 - t0,
        "note": "baseline runner only; size-patch mode removed "
                "(invalid form, see receipt 2026-09-27)",
    }
    artifact_path = args.artifact or args.work_dir / "kdma_baseline.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=1))
    print(f"submit completion: {(t1 - t0) / 1000:.1f} us, output sha256 {digest}")
    print(f"artifact: {artifact_path}")
    return 0


def _driver_srcversion():
    for name in ("ane", "apple_ane"):
        path = Path(f"/sys/module/{name}/srcversion")
        if path.exists():
            return path.read_text().strip()
    return "unknown"


if __name__ == "__main__":
    sys.exit(main())
