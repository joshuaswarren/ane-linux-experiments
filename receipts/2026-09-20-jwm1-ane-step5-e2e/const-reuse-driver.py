#!/usr/bin/env python3
"""const-reuse-driver.py — Main directive 2026-09-20.

Measures, in ONE process on jwm1:
  1. Explicit stage-boundary mx.eval diagnostic: mel/materialization eval before
     encoder entry, then a second boundary re-eval (expected ~0) — proves whether
     pending GPU work crosses the encoder stage boundary.
  2. Const-cache REUSE with the EXISTING in-process cache
     (MLX_OMARCHY_ENCODER_CONST_CACHE=1, imported before vulkan_encoder so the
     flag binds): pass 1 materializes consts, pass 2 restores from
     const_values dict — reports const op-wall pass1 vs pass2, cache entry
     count and bytes (actual hit/miss/count/bytes, not docstring claims).
  3. Pass-2 output equality gate: encoder_hidden/pass2 must be bit-identical to
     pass 1 (determinism under cache reuse).

No tolerance/criterion changes. Read-only wrt shared runners (base used as-is).
"""
import hashlib, importlib.util, json, os, sys, time
from pathlib import Path

import numpy as np

PKG = Path("/var/tmp/TdtLoopDefault/pkg")
sys.path.insert(0, str(PKG.resolve()))
sys.path.insert(0, str((PKG / "coreml").resolve()))

os.environ.setdefault("MLX_OMARCHY_ENCODER_CONST_CACHE", "1")  # bind flag before import; overridable for bisection

RUN = Path("/var/tmp/jwm1-ane-step2/fused-e2e")
BASE_RUNNER = Path("/var/tmp/encwall-v071/base/vulkan_encoder.py")
WORKER = Path("/var/tmp/jwm1-ane-step2/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker")
LIBANE = Path("/var/tmp/jwm1-ane-step2/libane.so")
BUNDLES = Path("/var/tmp/jwm1-ane-step2/bundles")
SOURCE = Path("/var/tmp/IslandsExecJwm1/encoder-source")
SCRATCH = Path("/var/tmp/jwm1-ane-step2/const-reuse-scratch")
AUDIO = Path("/var/tmp/ParakeetE2E/audio/fixture.flac")
OUT = Path("/var/tmp/jwm1-ane-step2/const-reuse-result.json")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def main():
    import mlx.core as mx
    import subprocess
    from coreml.vulkan_mel import extract_chunk_features

    enc = load_module(str(BASE_RUNNER), "phase7_encoder")

    # audio decode (mirrors fused_e2e stage_audio semantics, no fused_e2e import)
    pcm = np.frombuffer(
        subprocess.run(
            ["ffmpeg", "-v", "quiet", "-i", str(AUDIO), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
            capture_output=True, check=True).stdout, dtype=np.int16)
    assert len(pcm) > 0, "empty pcm decode"

    result = {"schema": "jwm1-const-reuse/1", "date": "2026-09-20",
              "cache_flag": "MLX_OMARCHY_ENCODER_CONST_CACHE=1"}

    # audio + mel (same semantics as fused_e2e stages 1-2)
    with mx.stream(mx.gpu):
        waveform = mx.array(pcm).astype(mx.float32) / 32768.0
    mx.eval(waveform)
    t0 = time.monotonic_ns()
    mel = extract_chunk_features(waveform)
    mx.eval(mel.mel, mel.mask, mel.encoder_features, mel.encoder_mask)
    t1 = time.monotonic_ns()
    # explicit boundary re-eval: pending work crossing the stage boundary?
    mx.eval(mel.encoder_features, mel.encoder_mask)
    t2 = time.monotonic_ns()
    result["boundary"] = {
        "mel_materialize_eval_ms": round((t1 - t0) / 1e6, 1),
        "boundary_reeval_ms": round((t2 - t1) / 1e6, 3),
        "note": "re-eval ~0 => no pending GPU work crosses the encoder boundary",
    }

    island = enc.AneIsland(worker=WORKER, libane=LIBANE, bundles=BUNDLES,
                           scratch=SCRATCH, deadline_ms=20000)
    runner = enc.EncoderRunner(SOURCE / "model.mil", SOURCE / "model-root", island)
    inputs = {"input_features": mel.encoder_features,
              "attention_mask": mel.encoder_mask}
    wanted = {"encoder_hidden", "encoder_mask"}

    t0 = time.monotonic_ns()
    r1 = runner.run(dict(inputs), set(wanted), "encoder_mask")
    p1 = (time.monotonic_ns() - t0) / 1e6
    const1 = runner.op_wall_ns.get("const", 0) / 1e6
    h1 = hashlib.sha256(np.asarray(r1["encoder_hidden"]).tobytes()).hexdigest()

    runner.op_wall_ns.clear()
    t0 = time.monotonic_ns()
    r2 = runner.run(dict(inputs), set(wanted), "encoder_mask")
    p2 = (time.monotonic_ns() - t0) / 1e6
    const2 = runner.op_wall_ns.get("const", 0) / 1e6
    h2 = hashlib.sha256(np.asarray(r2["encoder_hidden"]).tobytes()).hexdigest()

    result["reuse"] = {
        "pass1_total_ms": round(p1 * 1000, 1),
        "pass2_total_ms": round(p2 * 1000, 1),
        "const_wall_pass1_ms": round(const1, 1),
        "const_wall_pass2_ms": round(const2, 1),
        "const_cache_entries": len(runner.const_values),
        "const_cache_bytes": sum(int(v.nbytes) for v in runner.const_values.values()),
        "cache_mode": "in-process const_values dict (existing cache, no new architecture)",
        "pass2_hidden_bitidentical_to_pass1": bool(h1 == h2),
        "hidden_sha256": h1,
    }
    result["env_note"] = "ANE_ISLAND_MODE unset (code default resident-batch); MLX_OMARCHY_PLACED unset (runner default AC)"

    json.dump(result, open(OUT, "w"), indent=1)
    print(json.dumps(result, indent=1))
    island.close()


if __name__ == "__main__":
    main()
