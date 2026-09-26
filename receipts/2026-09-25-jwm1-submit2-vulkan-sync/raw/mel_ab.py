import ctypes, hashlib, json, statistics, sys, time
from pathlib import Path

PKG = Path.home() / "q38-build" / "mlx-omarchy" / "overlay" / "tools"
AUDIO = Path("/var/tmp/ParakeetE2E/audio/fixture.flac")
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(PKG / "coreml"))
sys.path.insert(0, "/var/tmp/jwm1-ane-step2/fused-e2e")

import mlx.core as mx  # noqa: E402
import numpy as np  # noqa: E402
from coreml import vulkan_mel as vm  # noqa: E402
from fused_e2e import decode_flac  # noqa: E402

_lib = ctypes.CDLL(str(Path(mx.__file__).parent / "lib" / "libmlx.so"))


class Snap(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in (
        "gpu_primitive_dispatches", "vk_submissions", "vk_buffer_copies",
        "vk_buffer_fills", "vk_compute_dispatches", "omarchy_finalize_calls",
        "commit_calls_with_work", "commit_calls_noop")]



_lib.mlx_omarchy_trace_snapshot.argtypes = [ctypes.POINTER(Snap)]


def snap():
    s = Snap()
    _lib.mlx_omarchy_trace_snapshot(ctypes.byref(s))
    return s


mx.set_default_device(mx.gpu)
pcm, rate, _ = decode_flac(AUDIO)
waveform = mx.array(pcm).astype(mx.float32) / 32768.0
mx.eval(waveform)
constants = vm._constant_arrays(mx)
mx.eval(constants.hann, constants.filterbank)


def whole():
    r = vm.extract_chunk_features(waveform)
    return (r.mel, r.mask, r.encoder_features, r.encoder_mask)


for _ in range(3):
    mx.eval(*whole())

arm = sys.argv[1]
s0 = snap()
walls = []
o = None
for _ in range(10):
    t0 = time.monotonic_ns()
    o = whole()
    mx.eval(*o)
    walls.append((time.monotonic_ns() - t0) / 1e6)
s1 = snap()
digs = [hashlib.sha256(np.ascontiguousarray(np.array(x, copy=False))).hexdigest()[:16]
        for x in o]
delta = {f: int(getattr(s1, f) - getattr(s0, f)) for f, _ in Snap._fields_}
print(json.dumps({
    "arm": arm,
    "wall_ms_med": round(statistics.median(walls), 2),
    "wall_ms_min": round(min(walls), 2),
    "wall_ms_max": round(max(walls), 2),
    "digests": digs,
    "delta": delta,
}))
