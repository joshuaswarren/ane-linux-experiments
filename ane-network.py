#!/usr/bin/env python3
"""Run a 2-layer MLP forward pass on the Apple Neural Engine.

    h = W1 @ x          (512x256 gemm, weights DMA'd by the engine)
    a = relu(h)         (elementwise max vs a zero source, 64 ch per task)
    y = W2 @ a[:256]    (512x256 gemm)

Layer outputs stay in strided fp16 device buffers between layers; the CPU only
memcpys buffer-to-buffer and checks the final result against numpy.

The gemm weight blob is 524288 bytes where the matrix needs 262144, so the
internal layout is probed empirically first (one-hot weights) instead of
assumed: probe A/B/C settle row-major order and whether the second half of the
blob matters.

Boilerplate (reg offsets, BTSP templates, buffer helpers) is taken verbatim
from allbilly/ane's examples/gemm.py and examples/elementwise.py.

  usage: python3 ane-network.py          # probe + MLP, verified vs numpy
         python3 ane-network.py probe    # layout probes only
"""
import ctypes
import mmap
import os
import struct
import sys
from fcntl import ioctl

import numpy as np

fd = os.open("/dev/accel/accel0", os.O_RDWR)

STRIDE = 32          # element stride between channels
C_GEMM = 512         # gemm channels in/out
K_GEMM = 256         # gemm reduction depth (expected = K * w for const w)
C_EW = 64            # elementwise channels per task
ANE_TILE_COUNT = 0x20
HALF_ONE = 0x3C00
DMA_EOL = 0x80000000
DMA_ACTIVE = 0x40000000
KERNEL_WEIGHT_ADDR = 0x81000000
WEIGHT_BLOB = 524288
N_WEIGHTS = WEIGHT_BLOB // 2


class reg:
    W0, W1, W2 = 0x00, 0x04, 0x08
    W3, W4, W5, W6 = 0x0C, 0x10, 0x14, 0x18
    W7, W8, W9 = 0x1C, 0x20, 0x24
    KernelDMA = 0x28
    CommonStream = 0x124
    SrcStream = 0x168
    L2Stream = 0x1DC
    PEStream = 0x228
    NEStream = 0x23C
    DstStream = 0x254
    InDim, pad0, ChCfg, Cin, Cout = 0x128, 0x12C, 0x130, 0x134, 0x138
    OutDim, pad1, ConvCfg, pad2 = 0x13C, 0x140, 0x144, 0x148
    GroupConvCfg, TileCfg, pad3, pad4, Cfg = 0x14C, 0x150, 0x154, 0x158, 0x15C
    TaskInfo, DPE = 0x160, 0x164
    L2Cfg, SourceCfg, SourceBase = 0x1E0, 0x1E4, 0x1E8
    SourceChannelStride, SourceRowStride = 0x1EC, 0x1F0
    ResultCfg, ResultBase = 0x210, 0x214
    ConvResultChannelStride, ConvResultRowStride = 0x218, 0x21C
    PECfg, BiasScale, PreScale, FinalScale = 0x22C, 0x230, 0x234, 0x238
    KernelCfg, MACCfg, MatrixVectorBias, AccBias, PostScale = 0x240, 0x244, 0x248, 0x24C, 0x250
    SrcDMAConfig, Srcpad0, SrcBaseAddr = 0x16C, 0x170, 0x174
    SrcRowStride, SrcPlaneStride, SrcDepthStride = 0x178, 0x17C, 0x180
    SrcGroupStride, Srcpad1 = 0x184, 0x188
    SrcFmt, SrcPadStream = 0x1A4, 0x1AC
    DstDMAConfig, DstBaseAddr, DstRowStride = 0x258, 0x25C, 0x260
    DstPlaneStride, DstDepthStride, DstGroupStride, DstFmt = 0x264, 0x268, 0x26C, 0x270


class drm_ane_bo_init(ctypes.Structure):
    _fields_ = [("handle", ctypes.c_uint32), ("pad", ctypes.c_uint32),
                ("size", ctypes.c_uint64), ("offset", ctypes.c_uint64)]


class drm_ane_submit(ctypes.Structure):
    _fields_ = [("tsk_size", ctypes.c_uint64), ("td_count", ctypes.c_uint32),
                ("td_size", ctypes.c_uint32), ("handles", ctypes.c_uint32 * ANE_TILE_COUNT),
                ("btsp_handle", ctypes.c_uint32), ("pad", ctypes.c_uint32)]


def _IOWR(nr, size):
    return (3 << 30) | (0x64 << 8) | (size << 16) | nr


DRM_IOCTL_ANE_BO_INIT = _IOWR(0x41, ctypes.sizeof(drm_ane_bo_init))
DRM_IOCTL_ANE_SUBMIT = _IOWR(0x43, ctypes.sizeof(drm_ane_submit))


def allocate_buffer(size):
    bo = drm_ane_bo_init(handle=0, pad=0, size=size, offset=0)
    ioctl(fd, DRM_IOCTL_ANE_BO_INIT, bo)
    buf = mmap.mmap(fd, size, mmap.MAP_SHARED,
                    mmap.PROT_READ | mmap.PROT_WRITE, offset=bo.offset)
    return bo.handle, buf


def submit_task(tsk_size, td_count, td_size, handles, btsp_handle):
    req = drm_ane_submit(tsk_size=tsk_size, td_count=td_count,
                         td_size=td_size, btsp_handle=btsp_handle, pad=0)
    for i in range(ANE_TILE_COUNT):
        req.handles[i] = handles[i] if i < len(handles) else 0
    return ioctl(fd, DRM_IOCTL_ANE_SUBMIT, req)


def make_from_segments(size, segments):
    buf = bytearray(size)
    for offset, length, data in segments:
        buf[offset:offset + length] = data
    return buf


def stream_header(hw_addr, num_words):
    return ((num_words - 1) << 26) | hw_addr


def build_seg(seg_off, seg_len, word_packs):
    max_off = max(boff for boff, _ in word_packs) if word_packs else 0
    tmp = bytearray(max(max_off + 4, seg_off + seg_len + 4))
    for boff, val in word_packs:
        struct.pack_into("<I", tmp, boff, val)
    return bytes(tmp[seg_off:seg_off + seg_len])


def pack_reg(buf, offset, value):
    struct.pack_into("<I", buf, offset, value)


def _be32(v):
    return struct.unpack(">I", struct.pack("<I", v))[0]


# ---------------------------------------------------------------- gemm layer
def gemm_btsp():
    """Task descriptor for the 512x256 gemm, verbatim from examples/gemm.py."""
    return make_from_segments(0x4000, [
        (0, 44, build_seg(0, 44, [
            (reg.W0, (0 << 0) | (0x40 << 16) | (1 << 25)),
            (reg.W1, 0),
            (reg.W2, 1058),
            (reg.W3, 0),
            (reg.W4, 0xFFF86A),
            (reg.W5, 0),
            (reg.W6, (38 << 10) | (3 << 28)),
            (reg.W7, 0),
            (reg.W8, 5 | (1 << 5) | (36 << 12) | (1 << 24) | (1 << 26)),
            (reg.W9, 0x21),
            (reg.KernelDMA, stream_header(0x1F800, 62)),
        ])),
        (0x2C, 0xF8, struct.pack(">" + "I" * 62,
                                 *([DMA_ACTIVE, 0]
                                   + [KERNEL_WEIGHT_ADDR] * 16
                                   + [_be32(i * 0x8000) for i in range(16)]
                                   + [_be32(0x8000)] * 16
                                   + [DMA_EOL] * 4 + [0] * 8))),
        (292, 184, build_seg(0x124, 184, [
            (reg.CommonStream, stream_header(0x00000, 16)),
            (reg.InDim, (1 << 16) | 1),
            (reg.OutDim, (1 << 16) | 1),
            (reg.ChCfg, 2 | (2 << 4)),
            (reg.Cin, C_GEMM),
            (reg.Cout, C_GEMM),
            (reg.pad0, 1),
            (reg.pad1, 1),
            (reg.pad2, 0x2041),
            (reg.ConvCfg, 0x5000B421),
            (reg.GroupConvCfg, 0x00010001),
            (reg.TileCfg, 1),
            (reg.Cfg, 0x00244405),
            (reg.TaskInfo, 1 << 20),
            (reg.DPE, 0),
            (reg.SrcStream, stream_header(0x13800, 28)),
            (reg.SrcDMAConfig, 1 | (8 << 4) | (8 << 8) | (3 << 12) | (3 << 16)),
            (reg.Srcpad0, 0x8880),
            (reg.SrcBaseAddr, 0),
            (reg.SrcRowStride, 0x40),
            (reg.SrcPlaneStride, 0x40),
            (reg.SrcDepthStride, 0x8000),
            (reg.SrcGroupStride, 0),
            (reg.SrcFmt, 1 | (3 << 4) | (2 << 12) | (1 << 24)),
            (reg.SrcPadStream, 0x00000100),
        ])),
        (476, 76, build_seg(0x1DC, 76, [
            (reg.L2Stream, stream_header(0x04800, 18)),
            (reg.L2Cfg, 0),
            (reg.SourceCfg, 0x00500172),
            (reg.SourceBase, 0),
            (reg.SourceChannelStride, 0x10),
            (reg.SourceRowStride, 0x2030),
            (0x1F4, 0x2000), (0x1F8, 0x2000),
            (reg.ResultCfg, 0x00500172),
            (reg.ResultBase, 0x2030),
            (reg.ConvResultChannelStride, 0x10),
            (reg.ConvResultRowStride, 0x2020),
            (0x220, 0x2000), (0x224, 0x2000),
        ])),
        (552, 44, build_seg(0x228, 44, [
            (reg.PEStream, stream_header(0x08800, 4)),
            (reg.PECfg, 0),
            (reg.BiasScale, 0),
            (reg.PreScale, 0),
            (reg.FinalScale, 0),
            (reg.NEStream, stream_header(0x0C800, 5)),
            (reg.KernelCfg, 0x82),
            (reg.MACCfg, 0x00101C00),
            (reg.MatrixVectorBias, 0),
            (reg.AccBias, 0),
            (reg.PostScale, HALF_ONE),
        ])),
        (596, 32, build_seg(0x254, 32, [
            (reg.DstStream, stream_header(0x17800, 7)),
            (reg.DstDMAConfig, 1 | (12 << 4)),
            (reg.DstBaseAddr, 0),
            (reg.DstRowStride, 0x40),
            (reg.DstPlaneStride, 0x40),
            (reg.DstDepthStride, 0x8000),
            (reg.DstGroupStride, 0),
            (reg.DstFmt, 1 | (3 << 4) | (2 << 12) | (3 << 20) | (1 << 24)),
        ])),
    ])


def run_gemm(weights_blob, x):
    """weights_blob: N_WEIGHTS fp16 array. x: K_GEMM fp16 vector. Returns C_GEMM vector."""
    btsp = gemm_btsp()
    cmd = bytearray(btsp)
    cmd.extend(b"\x00" * (32768 - len(btsp)))
    cmd[0x274:0x274 + WEIGHT_BLOB] = weights_blob.astype(np.float16).tobytes()

    cmd_h, cmd_m = allocate_buffer(len(cmd))
    out_h, out_m = allocate_buffer(0x8000)
    src_h, src_m = allocate_buffer(0x4000)
    btsp_h, btsp_m = allocate_buffer(0x4000)

    src = np.zeros(0x4000 // 2, dtype=np.float16)
    src[:C_GEMM * STRIDE:STRIDE] = 0.0
    src[:K_GEMM * STRIDE:STRIDE] = x
    src_m.write(src.tobytes())
    cmd_m.write(bytes(cmd))
    btsp_m.write(bytes(btsp))

    submit_task(0x274, 1, 0x274,
                [cmd_h, 0, 0, 0, out_h, src_h, 0] + [0] * 25, btsp_h)
    out = np.frombuffer(out_m, dtype=np.float16,
                        count=C_GEMM * STRIDE).reshape(C_GEMM, STRIDE)[:, 0].copy()
    for m in (cmd_m, out_m, src_m, btsp_m):
        m.close()
    return out


# ---------------------------------------------------------- elementwise layer
# The proven descriptor comes from the example itself: running
# examples/elementwise.py executes one add op (it has no __main__ guard) and
# leaves BTSP_BUF plus its helpers in a namespace we reuse. Hand-copying the
# descriptor was tried twice and hung the queue; the verbatim one does not.
if os.environ.get("ANE_DESCRIPTOR_ONLY") != "1":
    import runpy

    EW = runpy.run_path(os.path.expanduser("~/src/apple-ane/examples/elementwise.py"),
                        run_name="elementwise_harvest")
    EW_BUF = bytearray(EW["BTSP_BUF"])
    # Switch the harvested add descriptor to max mode: PECfg second_source=2,
    # op_mode=2. (The example does exactly this for its own mode dispatch.)
    EW["pack_reg"](EW_BUF, EW["reg"].PECfg, (2 << 18) | (2 << 2))
    EW["reg"]  # keep linters quiet


def run_ew(a, b):
    """Elementwise max over C_EW channels using the example's descriptor."""
    out_h, out_m = EW["allocate_buffer"](fd, 0x4000)
    s1_h, s1_m = EW["allocate_buffer"](fd, 0x4000)
    s2_h, s2_m = EW["allocate_buffer"](fd, 0x4000)
    btsp_h, btsp_m = EW["allocate_buffer"](fd, 0x4000)

    for m, v in ((s1_m, a), (s2_m, b)):
        buf = np.zeros(0x4000 // 2, dtype=np.float16)
        buf[:EW["CHANNELS"] * EW["STRIDE"]:EW["STRIDE"]] = v
        m.write(buf.tobytes())
    btsp_m.write(bytes(EW_BUF))

    EW["submit_task"](fd, 0x274, 1, 0x274,
                      [btsp_h, 0, 0, 0, out_h, s1_h, s2_h] + [0] * 24, btsp_h)
    n = EW["CHANNELS"]
    out = np.frombuffer(out_m, dtype=np.float16,
                        count=n * EW["STRIDE"]).reshape(n, EW["STRIDE"])[:, 0].copy()
    for m in (out_m, s1_m, s2_m, btsp_m):
        m.close()
    return out


def relu_ane(h):
    """relu over C_GEMM channels, 64 at a time via max(x, 0)."""
    out = np.empty(C_GEMM, dtype=np.float16)
    cpl = EW["CHANNELS"]
    for c0 in range(0, C_GEMM, cpl):
        out[c0:c0 + cpl] = run_ew(h[c0:c0 + cpl], np.zeros(cpl, dtype=np.float16))
    return out


# ----------------------------------------------------------------- the probe
def find_live_slots():
    """Coarse scan + bisection for blob offsets that feed out[0]."""
    x = np.ones(K_GEMM, dtype=np.float16)
    live = []
    step = N_WEIGHTS // 16
    for c0 in range(0, N_WEIGHTS, step):
        blob = np.zeros(N_WEIGHTS, dtype=np.float16)
        blob[c0:c0 + step] = 1.0
        out = run_gemm(blob, x)
        hit = np.count_nonzero(out)
        print(f"chunk [{c0:>6}..{c0 + step:>6}) -> nnz={hit}", flush=True)
        if hit:
            lo, hi = c0, c0 + step
            while hi - lo > 1:
                mid = (lo + hi) // 2
                blob = np.zeros(N_WEIGHTS, dtype=np.float16)
                blob[lo:mid] = 1.0
                if np.count_nonzero(run_gemm(blob, x)):
                    hi = mid
                else:
                    blob = np.zeros(N_WEIGHTS, dtype=np.float16)
                    blob[mid:hi] = 1.0
                    if np.count_nonzero(run_gemm(blob, x)):
                        lo = mid
                    else:
                        break
            print(f"  -> live slot near {lo} (out[0] weight for x-index TBD)")
            live.append(lo)
    return live


def map_tile0():
    """For tile-0 offsets 6+d, learn (out_channel, input_index) each feeds."""
    x = (np.arange(K_GEMM) + 1).astype(np.float16)   # x[i] = i+1
    for d in range(0, 64):
        blob = np.zeros(N_WEIGHTS, dtype=np.float16)
        blob[6 + d] = 1.0
        out = run_gemm(blob, x)
        nz = np.nonzero(out)[0]
        if len(nz):
            o = nz[0]
            print(f"off {6 + d:>4} -> out[{o:>3}] = {out[o]:.1f}  (feeds x index {int(out[o]) - 1})",
                  flush=True)
        else:
            print(f"off {6 + d:>4} -> dead", flush=True)


def probe_layout():
    """One-hot weights settle the blob layout: row-major order, second half."""
    x = np.ones(K_GEMM, dtype=np.float16)

    blob = np.zeros(N_WEIGHTS, dtype=np.float16)
    blob[0] = 1.0                       # candidate W[0][0]
    out = run_gemm(blob, x)
    print(f"probe A blob[0]=1 -> out[0]={out[0]:.4f} out[1]={out[1]:.4f} "
          f"nnz={np.count_nonzero(out)}")

    blob = np.zeros(N_WEIGHTS, dtype=np.float16)
    blob[1] = 1.0                       # candidate W[0][1]
    out = run_gemm(blob, x)
    print(f"probe B blob[1]=1 -> out[0]={out[0]:.4f} (row-major: expect 1.0)")

    blob = np.zeros(N_WEIGHTS, dtype=np.float16)
    blob[0] = 1.0
    blob[N_WEIGHTS // 2] = 1.0          # second half candidate W[256][0]
    out = run_gemm(blob, x)
    print(f"probe C blob[half]=1 too -> out[0]={out[0]:.4f} "
          f"out[256]={out[256]:.4f} (second half live: expect 1.0 there)")


# -------------------------------------------------------------- the network
def main():
    rng = np.random.default_rng(42)

    if len(sys.argv) > 1 and sys.argv[1] == "probe":
        probe_layout()
        return
    if len(sys.argv) > 1 and sys.argv[1] == "map":
        map_tile0()
        return
    if len(sys.argv) > 1 and sys.argv[1] == "live":
        print("live slots:", find_live_slots())
        return

    W1 = rng.standard_normal((C_GEMM, K_GEMM)).astype(np.float16) * 0.1
    W2 = rng.standard_normal((C_GEMM, K_GEMM)).astype(np.float16) * 0.1
    x = rng.standard_normal(K_GEMM).astype(np.float16)

    def to_blob(W):
        # Probe-decoded layout: 16 tiles x 16384 fp16. Tile t feeds output
        # channels 32t..32t+31; inside a tile, offset 6 + i*32 + (o%32) holds
        # W[o][i] (i-major), with i < 256 live.
        blob = np.zeros(N_WEIGHTS, dtype=np.float16)
        for t_ in range(16):
            base = t_ * 16384 + 6
            blob[base:base + K_GEMM * 32] = W[32 * t_:32 * t_ + 32].T.reshape(-1)
        return blob

    h = run_gemm(to_blob(W1), x)             # layer 1: 512x256 gemm
    a = relu_ane(h)                          # layer 2: relu, on device
    y = run_gemm(to_blob(W2), a[:K_GEMM])    # layer 3: 512x256 gemm

    h_ref = W1.astype(np.float32) @ x.astype(np.float32)
    a_ref = np.maximum(h_ref, 0)
    y_ref = W2.astype(np.float32) @ a_ref[:K_GEMM]

    def report(name, got, ref):
        got32 = got.astype(np.float32)
        err = np.abs(got32 - ref)
        print(f"{name}: max_abs_err={err.max():.4f} mean_abs_err={err.mean():.4f} "
              f"argmax_match={np.argmax(got32) == np.argmax(ref)}")

    report("layer1 gemm  h", h, h_ref)
    report("layer2 relu  a", a, a_ref)
    report("layer3 gemm  y", y, y_ref)
    print(f"y[:8]      = {y[:8].astype(np.float32)}")
    print(f"y_ref[:8]  = {y_ref[:8]}")


if __name__ == "__main__":
    main()
