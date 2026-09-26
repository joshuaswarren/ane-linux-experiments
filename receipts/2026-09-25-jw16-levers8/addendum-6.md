# jw16-levers8 addendum 6 — first staged Qwen program device-executed on T6001 (2026-09-26)

Milestone per the opened runner lane (addendum-5): a staged split-series
program (prog_002, callback_status=0 export) converted HWX→ANEC and
EXECUTED on jw16's ANE through the Linux KMD submit path
(production-anec-probe, input BO handle 4 / output BO handle 5):

```
multi-surface program: 4 input surfaces, 8 output surfaces
  (contiguous spans: source 16384 B, output 16384 B)
content=0x7090000 task-stream=0x9cf8 td=0x1f8 td-count=62
  ... source=0x4000 output=0x4000 ...
output-head=[0.0 x16] changed=2048 finite=True completed=True wrote-output=True
PRODUCTION_ANEC_EXECUTION_OK
```

Output dump: /var/tmp/levers8/qwen/prog_002-out.bin (16,384 B).

## What is proven

The staged artifacts convert (HWX→ANEC, 62 task descriptors, streamed
content) and DEVICE-EXECUTE on T6001's Linux ANE via the existing KMD
submit path: submit → engine completes → finite output buffer dumped.

## What is NOT proven (stated plainly)

NUMERICS. The conversion used a guessed geometry (2048→2048 fp16
channels); the HWX's own section spans are input 937,984 B / output
917,504 B (4 input + 8 output boundary surfaces). The all-zero output
with that mismatch is expected to be geometry-wrong, and no numeric
claim is made. Next increment: re-convert with the true per-surface
shapes (--in-shapes/--out-shapes spanning 937,984/917,504 B — per-
surface split from the stage contract in qwen35.py), re-execute, and
compare against e5rt-side outputs for the same input (needs one
instrumented studio execute to capture reference tensors, or output
consistency checks across equivalent inputs).

## Tool change (committed)

tools/production-anec-probe.py: the hard 1-input/1-output refusal is
now multi-surface span mode — staged multi-port programs lay their
boundary surfaces contiguously inside one input and one output section
span; the engine DMAs whole spans, so span-fill/span-dump is faithful
(per-surface routing belongs to the runner). Single-surface programs
behave exactly as before.

## Remaining to full acceptance (unchanged goal)

Correct-geometry conversion of all 46 programs; chained decode-step
runner (boundary-lane routing per the qwen35.py stage contract);
frozen 100-prompt corpus, 3 warmups + 10 reps, tokens == frozen
reference, installed entrypoint, no CPU tensor fallback.
