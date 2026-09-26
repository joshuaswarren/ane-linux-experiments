# jw16-levers8 addendum 7 — multi-surface geometry findings; runner implementation continues (2026-09-26)

## New facts (prog_002 deep-dive)

- The staged HWX's I/O surfaces live in `__FVMLIB __const` (inputs) and
  `__FVMLIB __data` (outputs) section ranges, NOT the 0x4000-byte spans
  the first guess used. prog_002 truth (from the file's own section
  table): 4 input surfaces (4096 / 4096 / 393,216 / 4096 B = 2048 /
  2048 / 196,608 / 2048 fp16 elements) and 8 output surfaces (sum
  415,744 B); the ANEC `input_size`/`output_size` fields are SPANS
  (937,984 / 917,504 B) including inter-surface gaps, not sums.
- Weights are INLINE: `__TEXT __const` = 117,980,864 B (118 MB) — no
  BLOBFILE/weights.bin for these programs (prog_001's
  additional_weights.bin belonged to the failed fused entry).
- Boundary-lane contract (qwen35.py @ 2ea941c, stage functions):
  stage A in {"x"} out {"x","q","k","v","beta","gt","z"} + resident
  conv state; stage B owns [nv,dk,dv] recurrence; stage C in
  {"x","o","z"} out {"h"}; carried lanes re-rooted host-side.

## Execution state

- prog_002 converted and submitted through the Linux KMD path:
  62 task descriptors, completed=True, finite=True, output dumped —
  the submit/complete/dump PIPELINE is proven end-to-end on T6001 for
  a staged artifact.
- The 16 KiB-section conversion (positional channels = surface count)
  executed with an all-zero output: expected — the sections were sized
  wrong, so numerics are NOT claimed. A second attempt passing total
  element counts (202,752 / 207,872) produced an identical 16 KiB
  section: the ANEC section sizing path needs the per-surface NCHW
  words wired through (the converter accepts --in-shapes/--out-shapes
  and writes them into the header — stage_geometry then reads
  (1,1,1,2048,4096,4096) — but the SECTION allocation still follows
  the positional channels). The remaining fix is small and located:
  size the input/output sections from the shape lists' byte sums.
- tools/production-anec-probe.py multi-surface span mode committed
  (38a1dcdf): fills/dumps whole section spans; per-surface routing
  belongs to the runner.

## Runner milestones (unchanged)

M2 fix section sizing from shape sums → convert all 46;
M3 numeric single-program validation (needs correct sizing, then
e5rt-side reference tensors for comparison — one instrumented studio
execute); M4 chained decode-step runner (stage-contract routing);
M5 frozen 100-prompt corpus, 3 warmups + 10 reps, tokens == frozen
reference, installed entrypoint, no CPU fallback.

## Plainly

Numerics for the staged Qwen programs on T6001 are NOT yet validated.
What is proven: conversion pipeline, KMD submit/complete/dump, and the
per-surface geometry extraction from the HWX itself.

## UPDATE — true-geometry execution with structured numerics (same session)

prog_002 reconverted with the TRUE per-surface shapes derived from the
HWX's own `__FVMLIB` section ranges (4 inputs: 2048/2048/196,608/2048
fp16 elements; 8 outputs: 2048×4, 512×2, 2048, 196,608) and executed:

- ALL 8 output surfaces: finite on written elements; real structured
  activations (bdx5 range -0.779..1.302; bdx10 up to 32,224.0; bdx11
  0..0.563); coverage 0.25 per 16 KiB tile-rounded surface (= exact
  4096 B / 2048-element true surfaces inside tile-granular BOs).
- Engine mutations on input-role banks (bdx 12: 512, bdx 13: 2048,
  bdx 14: 196,607 of 196,608 elements) = state-carrying lanes writing
  in place, exactly as the stage contract (conv state, DeltaNet
  recurrent state) requires.
- Completed wording per Main: ANE_SUBMIT is KMD-SYNCHRONOUS
  (ane_tm_execute latch-first completion poll, read_poll_timeout 1 µs
  / 1 s; ane_drv.c holds BO refs across the synchronous execute) —
  per-surface writes are observed on the KMD-confirmed-completed
  submit; probe finite/coverage semantics now apply to WRITTEN
  elements only.
- Numerical REFERENCE comparison (e5rt-side tensors for identical
  inputs, captured on the compiler oracle) remains the outstanding
  validation step; until then these are structured computed outputs,
  not reference-verified values.

Probe + converter + regression test committed (a967e7da): tools/
production-anec-probe.py (multi-surface), tools/hwxv2-to-anec.py
(DMA-derived padding fallback restored when explicit shapes absent),
tools/test_production_probe_multisurface.py (offline regression for
the reviewed indexing bug: PASS).
