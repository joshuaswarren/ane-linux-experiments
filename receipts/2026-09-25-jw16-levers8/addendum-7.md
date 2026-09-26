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
