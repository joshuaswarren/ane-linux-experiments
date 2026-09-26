import json
import statistics
import sys
import time
from pathlib import Path

PKG = Path.home() / "q38-build" / "mlx-omarchy" / "overlay" / "tools"
AUDIO = Path("/var/tmp/ParakeetE2E/audio/fixture.flac")
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(PKG / "coreml"))
sys.path.insert(0, "/var/tmp/jwm1-ane-step2/fused-e2e")

import mlx.core as mx  # noqa: E402
from coreml import vulkan_mel as vm  # noqa: E402
from fused_e2e import decode_flac  # noqa: E402

mx.set_default_device(mx.gpu)
pcm, rate, _ = decode_flac(AUDIO)
waveform = mx.array(pcm).astype(mx.float32) / 32768.0
mx.eval(waveform)
constants = vm._constant_arrays(mx)
mx.eval(constants.hann, constants.filterbank)
frames = vm._frames(waveform, constants.hann)
mx.eval(frames)


def wall(fn):
    t0 = time.monotonic_ns()
    fn()
    return (time.monotonic_ns() - t0) / 1e6


arm = sys.argv[1]
out = {}
if arm == "iso":
    vm._dft_frames(frames)
    mx.eval(vm._dft_frames(frames))
    walls = [wall(lambda: mx.eval(vm._dft_frames(frames))) for _ in range(10)]
    out["iso_dft_ms_med"] = round(statistics.median(walls), 3)
elif arm == "flood":
    outs = [vm._dft_frames(frames) for _ in range(50)]
    mx.eval(outs[-1])
    outs = [vm._dft_frames(frames) for _ in range(50)]
    dt = wall(lambda: mx.eval(*outs))
    out["flood_total_ms"] = round(dt, 3)
    out["flood_per_dispatch_ms"] = round(dt / 50, 3)
elif arm == "pipe":
    for _ in range(3):
        mx.eval(*[vm.extract_chunk_features(waveform).mel])
    walls = [wall(lambda: mx.eval(vm.extract_chunk_features(waveform).mel))
             for _ in range(10)]
    out["pipe_ms_med"] = round(statistics.median(walls), 3)
elif arm == "info":
    out["frames_shape"] = list(frames.shape)
    out["waveform_samples"] = int(waveform.shape[0])
print(json.dumps({"arm": arm, **out}))
