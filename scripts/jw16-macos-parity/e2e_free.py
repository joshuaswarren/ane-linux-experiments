#!/usr/bin/env python3
"""Golden-free Parakeet TDT e2e over a corpus manifest, one process (models/session opened once), the same stages
and code paths as fused_e2e.py (audio -> mel -> whole-encoder ANE -> fused decoder/joint TDT -> detokenize).
Extras vs fused_e2e: per-clip JSON lines, --valid-frames {mask,full}, chunking of audio longer than 30 s.
Run with the environment of run-contract-resident.sh (ANE_ISLAND_MODE=inprocess, shim, worker, libane, ...).
usage: e2e_free.py --corpus DIR --out FILE.jsonl [--valid-frames mask|full] [--reps N] plus the fused_e2e path args."""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p = argparse.ArgumentParser()
p.add_argument("--corpus", type=Path, required=True)
p.add_argument("--out", type=Path, required=True)
p.add_argument("--model", type=Path, required=True)
p.add_argument("--pkg", type=Path, required=True)
p.add_argument("--encoder-runner", type=Path, required=True)
p.add_argument("--source", type=Path, required=True)
p.add_argument("--bundles", type=Path, required=True)
p.add_argument("--worker", type=Path, required=True)
p.add_argument("--libane", type=Path, required=True)
p.add_argument("--scratch", type=Path, required=True)
p.add_argument("--deadline-ms", type=int, default=20000)
p.add_argument("--valid-frames", choices=["mask", "full"], default="full")
p.add_argument("--reps", type=int, default=1)
p.add_argument("--only", type=str, default="")
p.add_argument("--tdt-mode", choices=["host", "chain"], default="chain")
args = p.parse_args()
sys.path.insert(0, str(args.pkg.resolve()))
sys.path.insert(0, str((args.pkg / "coreml").resolve()))
import mlx.core as mx  # noqa: E402
import soundfile  # noqa: E402
from coreml.parakeet_tdt import DecoderStep, JointDecision, tdt_decode  # noqa: E402
from coreml.reference import ReferenceLock  # noqa: E402
from coreml.tokenizer import ParakeetTokenizer  # noqa: E402
from coreml.vulkan_decoder import load_decoder  # noqa: E402
from coreml.vulkan_decoder_step import pack_step_weights, run_step  # noqa: E402
from coreml.vulkan_mel import extract_chunk_features  # noqa: E402

encoder_module = load_module(args.encoder_runner.resolve(), "phase7_encoder")
mx.set_default_device(mx.gpu)
lock = ReferenceLock.load(args.pkg / "coreml" / "parakeet-reference.lock")
tok_sha = next(i.sha256 for i in lock.files if i.path == "tokenizer.json")
island = encoder_module.AneIsland(args.worker, args.libane, args.bundles, args.scratch, args.deadline_ms)
runner = encoder_module.EncoderRunner(args.source / "model.mil", args.source / "model-root", island)
decoder = load_decoder(args.model / "decoder.mlpackage")
packed = pack_step_weights(decoder, args.model / "joint.mlpackage")
tokenizer = ParakeetTokenizer.load(args.model / "tokenizer.json", expected_sha256=tok_sha)
CHUNK = 30 * 16000


def decode_chunk(pcm16):
    t = {}
    t0 = time.monotonic_ns()
    with mx.stream(mx.gpu):
        wave = mx.array(pcm16).astype(mx.float32) / 32768.0
    mx.eval(wave)
    t["audio_ms"] = (time.monotonic_ns() - t0) / 1e6
    t0 = time.monotonic_ns()
    mel = extract_chunk_features(wave)
    mx.eval(mel.mel, mel.mask, mel.encoder_features, mel.encoder_mask)
    t["mel_ms"] = (time.monotonic_ns() - t0) / 1e6
    t0 = time.monotonic_ns()
    enc = runner.run(inputs={"input_features": mel.encoder_features, "attention_mask": mel.encoder_mask},
                     wanted={"encoder_hidden", "encoder_mask"}, stop_after="encoder_mask")
    hidden = enc["encoder_hidden"].astype(mx.float32)
    emask = enc["encoder_mask"].astype(mx.int32)
    mx.eval(hidden, emask)
    t["encoder_ms"] = (time.monotonic_ns() - t0) / 1e6
    frames_total = int(hidden.shape[1])
    mel_valid = int(pcm16.shape[0] // 160 + 1)            # mel frames covering the audio (hop 160); masks are all ones
    frames_valid = min(frames_total, (mel_valid + 7) // 8)  # 8x subsampling
    rec_extra = {"mel_valid_frames": mel_valid}
    valid = frames_valid if args.valid_frames == "mask" else frames_total
    fused = {"frame": None, "state": None, "tok": None, "dur": None}
    holder = [0]

    def dec_cb(token_id, h, c):
        state_out, tk, du, _, _ = run_step(packed, h, c, token_id, hidden, holder[0])
        mx.eval(state_out)
        ds = state_out[0:640].reshape(1, 640)
        fused.update(frame=holder[0], state=ds, tok=tk, dur=du)
        return DecoderStep(ds, state_out[640:1920].reshape(2, 1, 640), state_out[1920:3200].reshape(2, 1, 640))

    def joint_cb(frame_index, dec_state):
        holder[0] = frame_index
        if fused["frame"] == frame_index and fused["state"] is dec_state:
            return JointDecision(fused["tok"], fused["dur"])
        state_out, tk, du, _, _ = run_step(packed, None, None, 0, hidden, frame_index, skip_lstm=True, dec_in=dec_state)
        mx.eval(state_out)
        return JointDecision(tk, du)

    t0 = time.monotonic_ns()
    with mx.stream(mx.gpu):
        h0 = mx.zeros((2, 1, 640), dtype=mx.float32)
        c0 = mx.zeros((2, 1, 640), dtype=mx.float32)
    mx.eval(h0, c0)
    tdt = tdt_decode(packed=packed, encoder=hidden, valid_frames=valid, config=lock.tdt, initial_hidden=h0,
                     initial_cell=c0, run_decoder=dec_cb, run_joint=joint_cb, force_host=(args.tdt_mode == "host"))
    t["tdt_ms"] = (time.monotonic_ns() - t0) / 1e6
    t0 = time.monotonic_ns()
    text = tokenizer.decode(tdt.token_ids)
    t["detok_ms"] = (time.monotonic_ns() - t0) / 1e6
    return text, list(tdt.token_ids), t, frames_valid, frames_total


manifest = json.loads((args.corpus / "manifest.json").read_text())
if args.only:
    manifest = [m for m in manifest if args.only in m["file"]]
args.out.parent.mkdir(parents=True, exist_ok=True)
with open(args.out, "a") as fh:
    for rep in range(args.reps):
        for m in manifest:
            pcm, rate = soundfile.read(str(args.corpus / m["file"]), dtype="int16")
            rec = {"file": m["file"], "sec": m["sec"], "rep": rep, "valid_frames_mode": args.valid_frames}
            try:
                parts = [pcm[i:i + CHUNK] for i in range(0, len(pcm), CHUNK)]
                texts, ids, agg, fv, ft = [], [], {}, 0, 0
                for part in parts:
                    text, tid, t, v, tot = decode_chunk(np.ascontiguousarray(part))
                    texts.append(text)
                    ids += tid
                    fv += v
                    ft += tot
                    for k, val in t.items():
                        agg[k] = agg.get(k, 0.0) + val
                agg["total_ms"] = sum(agg.values())
                rec.update(status="ok", chunks=len(parts), transcript=" ".join(texts), tokens=len(ids),
                           frames_valid=fv, frames_total=ft, **{k: round(v, 2) for k, v in agg.items()})
            except Exception as exc:  # recorded, never hidden
                rec.update(status="error", error=f"{type(exc).__name__}: {exc}")
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            print(rec.get("status"), m["file"], rec.get("total_ms"), flush=True)
