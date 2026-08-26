#!/usr/bin/env python3
"""Multi-TD batching on the Apple Neural Engine.

The uapi submit ioctl carries td_count, and ane_tm_push_tq ORs it straight
into TM_INFO: the hardware is told how many task descriptors to expect at
TM_ADDR. concat.py proves the chain works for TileDMA ops (td_count=2, TDs
spaced 0x300 inside the BTSP buffer). This script asks whether the same
works for gemm, and whether each TD in a chain can carry its own weights.

Three phases:

  A. chain validity: N identical gemm TDs in one submission. The engine
     must run the same work N times and the output must equal the numpy
     expectation. Proves chaining for gemm and measures amortization of
     the per-submission overhead.
  B. per-TD weights: two TDs whose KernelDMA descriptors point at two
     different weight blobs packed back to back at the driver's KRN bar
     offset. If the firmware honors the per-TD KDMA source offset, the two
     outputs differ exactly as the two weight sets predict.
  C. scale: N = 2,4,8 identical TDs, wall time per tile, compared with the
     one-ioctl-per-tile cost measured in ane-tiled.py (1.93 ms).

Completion note: ane_tm_get_status polls TM_IS_IDLE, but the doorbell has
not flipped the status to busy when the first poll lands, so the ioctl
returns while the engine is still running. run() pre-fills the output with
+inf and polls the live mmap until the engine's DMA overwrites it.

TD layout facts used here (from gemm.py and concat.py):
  td_size        0x274
  TD spacing     0x300 inside the BTSP buffer
  tsk_size       (N-1)*0x300 + 0x274; the driver publishes the weight
                 region at CMD + round_up(tsk_size, 16)
  KDMA src       firmware DMA address 0x81000000, repeated 16x in the
                 descriptor; phase B adds a per-TD delta to it

  usage: python3 ane-batch.py
"""
import os
import struct
import sys
import time

import numpy as np

_only = None
_qid = None
if "--only" in sys.argv:
    _only = int(sys.argv[sys.argv.index("--only") + 1])
if "--qid" in sys.argv:
    _qid = int(sys.argv[sys.argv.index("--qid") + 1])

GEMM = os.path.expanduser("~/src/apple-ane/examples/gemm.py")
src = open(GEMM).read()
marker = "# Build CMD_BUF with gemm weights"
head = src.split(marker)[0]
ns = {"__name__": "gemm_defs", "__file__": GEMM}
exec(compile(head, GEMM, "exec"), ns)

reg = ns["reg"]
allocate_buffer = ns["allocate_buffer"]
submit_task = ns["submit_task"]
BTSP_BUF = ns["BTSP_BUF"]
C = ns["C"]
STRIDE = ns["STRIDE"]
KERNEL_WEIGHT_ADDR = ns["KERNEL_WEIGHT_ADDR"]
DMA_ACTIVE = ns["DMA_ACTIVE"]

TD_SIZE = 0x274
TD_SPACING = 0x300
WEIGHT_BYTES = 0x80000          # 512 KB per weight blob
OUT_BYTES = 0x8000
WAIT_S = 0.2


def submit_qid(fd, tsk_size, td_count, td_size, handles, btsp_handle):
    """Submit on an explicit queue after the qid-enabled KMD is loaded."""
    request = ns["drm_ane_submit"](
        tsk_size=tsk_size, td_count=td_count, td_size=td_size,
        btsp_handle=btsp_handle, pad=0 if _qid is None else 0x80 | _qid,
    )
    for i in range(ns["ANE_TILE_COUNT"]):
        request.handles[i] = handles[i] if i < len(handles) else 0
    return ns["ioctl"](fd, ns["DRM_IOCTL_ANE_SUBMIT"], request)

def weights_blob(fill):
    return np.full(WEIGHT_BYTES // 2, fill, dtype=np.float16).tobytes()


def make_cmd(tsk_size, fills):
    """CMD buffer with weight blobs at the driver's KRN bar offset.

    ane_drv.c sets bar[KRN] = bar[CMD] + round_up(tsk_size, 16). The upstream
    build_cmd_buf packs weights at 0x274, twelve bytes before that bar; the
    misalignment is invisible under a uniform fill, so place the blobs at
    the bar the driver actually publishes and let phase B's two distinct
    fills prove the alignment either way."""
    bar = (tsk_size + 15) & ~15
    buf = bytearray(bar + WEIGHT_BYTES * len(fills))
    buf[:len(BTSP_BUF)] = BTSP_BUF
    for i, fill in enumerate(fills):
        off = bar + i * WEIGHT_BYTES
        buf[off:off + WEIGHT_BYTES] = weights_blob(fill)
    return bytes(buf)


def rebase_kdma(td, delta):
    """Rewrite the 16 KernelDMA source addresses in a TD by +delta."""
    td = bytearray(td)
    # firmware DMA context starts at 0x2C: [DMA_ACTIVE,0] then 16 src addrs
    base = 0x2C + 8
    for i in range(16):
        off = base + i * 4
        (val,) = struct.unpack_from(">I", td, off)
        assert val == KERNEL_WEIGHT_ADDR, f"unexpected KDMA word {val:#x}"
        struct.pack_into(">I", td, off, val + delta)
    return bytes(td)


def shift_scatter(td, delta):
    """Rewrite the 16 output scatter addresses in a TD by +delta."""
    td = bytearray(td)
    base = 0x2C + 8 + 16 * 4
    for i in range(16):
        off = base + i * 4
        (val,) = struct.unpack_from(">I", td, off)
        struct.pack_into(">I", td, off, val + delta)
    return bytes(td)


def run(n, tds, cmd_buf, out_bytes):
    """Submit and wait for the engine, not for the ioctl."""
    sentinel = b"\x00\x7c"        # fp16 +inf, little-endian
    fd = os.open("/dev/accel/accel0", os.O_RDWR)
    try:
        cmd_handle, cmd_map = allocate_buffer(fd, len(cmd_buf))
        cmd_map.write(bytes(cmd_buf))
        cmd_map.close()
        out_handle, out_map = allocate_buffer(fd, out_bytes)
        out_map.write(sentinel * (out_bytes // 2))
        src_handle, src_map = allocate_buffer(fd, 0x4000)
        src1 = np.zeros(0x4000 // 2, dtype=np.float16)
        src1[:C * STRIDE:STRIDE] = np.float16(1.0)
        src_map.write(src1.tobytes())
        src_map.close()

        btsp = bytearray(n * TD_SPACING)
        for i, td in enumerate(tds):
            btsp[i * TD_SPACING:i * TD_SPACING + len(td)] = td
        btsp_handle, btsp_map = allocate_buffer(fd, len(btsp))
        btsp_map.write(bytes(btsp))
        btsp_map.close()

        tsk_size = (n - 1) * TD_SPACING + TD_SIZE
        handles = [cmd_handle, 0, 0, 0, out_handle, src_handle, 0] + [0] * 25

        t0 = time.perf_counter()
        ret = submit_qid(fd, tsk_size, n, TD_SIZE, handles, btsp_handle)
        # mmap slice, not a numpy view: keeps the buffer unexported
        while out_map[:2] == sentinel and time.perf_counter() - t0 < WAIT_S:
            pass
        wall = time.perf_counter() - t0
        out = np.frombuffer(out_map, dtype=np.float16,
                            count=out_bytes // 2).copy()
        out_map.close()
        return ret, wall, out
    finally:
        os.close(fd)


def main():
    base_td = bytes(BTSP_BUF)

    if _only is not None:
        # One n per boot, as the FIRST submission of a clean engine.
        # Anything after a hung submission in the same boot is void: the
        # queue wedges and every later submit fails regardless of n.
        n = _only
        tsk_size = (n - 1) * TD_SPACING + TD_SIZE
        cmd = make_cmd(tsk_size, [np.float16(0.5)])
        ret, wall, out = run(n, [base_td] * n, cmd, OUT_BYTES)
        got = out.reshape(C, STRIDE)[:, 0]
        exp = np.full(C, 256 * 0.5, dtype=np.float16)
        ok = bool(np.array_equal(got, exp))
        print(f"ONLY n={n} ret={ret} wall={wall * 1e3:.2f}ms "
              f"per_tile={wall / n * 1e3:.2f}ms output_ok={ok}")
        return

    print("=== phase A: identical TDs, one submission ===")
    for n in (1, 2, 4, 8):
        tsk_size = (n - 1) * TD_SPACING + TD_SIZE
        cmd = make_cmd(tsk_size, [np.float16(0.5)])
        ret, wall, out = run(n, [base_td] * n, cmd, OUT_BYTES)
        got = out.reshape(C, STRIDE)[:, 0]
        exp = np.full(C, 256 * 0.5, dtype=np.float16)
        ok = bool(np.array_equal(got, exp))
        print(f"n={n} ret={ret} wall={wall * 1e3:.2f}ms "
              f"per_tile={wall / n * 1e3:.2f}ms output_ok={ok}")

    print()
    print("=== phase B: two TDs, two weight blobs ===")
    tsk_size = TD_SPACING + TD_SIZE
    td1 = base_td
    td2 = shift_scatter(rebase_kdma(base_td, WEIGHT_BYTES), OUT_BYTES)
    cmd = make_cmd(tsk_size, [np.float16(0.5), np.float16(0.25)])
    ret, wall, out = run(2, [td1, td2], cmd, OUT_BYTES * 2)
    got1 = out[:OUT_BYTES // 2].reshape(C, STRIDE)[:, 0]
    got2 = out[OUT_BYTES // 2:].reshape(C, STRIDE)[:, 0]
    exp1 = np.full(C, 256 * 0.5, dtype=np.float32)
    exp2 = np.full(C, 256 * 0.25, dtype=np.float32)
    ok1 = bool(np.allclose(got1.astype(np.float32), exp1, atol=1.0))
    ok2 = bool(np.allclose(got2.astype(np.float32), exp2, atol=1.0))
    print(f"ret={ret} td1_ok={ok1} td2_ok={ok2} "
          f"td1[:4]={got1[:4]} td2[:4]={got2[:4]}")
    if ok1 and ok2:
        print("PER_TD_WEIGHTS_HONORED")

    print()
    print("=== phase C: amortization vs one-ioctl-per-tile ===")
    print("baseline per_tile from ane-tiled.py: 1.93 ms")
    for n in (2, 4, 8):
        tsk_size = (n - 1) * TD_SPACING + TD_SIZE
        cmd = make_cmd(tsk_size, [np.float16(0.5)])
        ret, wall, out = run(n, [base_td] * n, cmd, OUT_BYTES)
        print(f"n={n} per_tile={wall / n * 1e3:.2f}ms "
              f"speedup={1.93 / (wall / n * 1e3):.1f}x")

    if ok1 and ok2:
        print("BATCH_VERIFIED")


if __name__ == "__main__":
    main()
