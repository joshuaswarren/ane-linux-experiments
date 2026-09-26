# jw16-levers8 addendum 5 — Qwen Linux ANE runner lane OPENED (2026-09-26)

Per Main decision: implement the Linux ANE-program runner for the staged
38-program Qwen chain. Status at this receipt: STAGING COMPLETE, first
conversion/execution milestone next. Nothing claimed beyond that.

## Staged on jw16 (/var/tmp/levers8/qwen/)

- hwx/ — the full studio export set, 8.4 GB: prog_002..prog_047
  (46 programs, callback_status=0, each with model.hwx +
  model.hwx.additional_weights.bin + export log). prog_001 EXCLUDED
  (the known failed fused-graph entry, callback_status=22, no output).
- aneforge-check/ — fresh sbryngelson/ANEForge clone + fetched bundle
  branch, checked out at `2ea941c` (loader fix verified on this host:
  contract GGUF loads clean -> LlamaPrefill).
- Contract GGUF (4aa0fb13…) + reference chunk_00.json staged.

## Tools staged (from ane-linux-experiments)

tools/hwxv2-to-anec.py (HWX→ANEC converter; derives rows/plane layout
from each program's own task DMA fields — channels are the remaining
per-program inputs), tools/production-anec-probe.py (Linux ANE KMD
submit; input BO handle 4, output BO handle 5, --dump-output),
ane-runtime.py, docs/fresh-hwx-usage.md. Precedent: a captured
production Qwen HWX already converted (3072 descriptors) and executed
on Linux with numeric parity (max_err=0.0004772, matching argmax,
9216x2048 output) — the single-program path is PROVEN; what does not
exist yet is the chained 38-program decode runner (disclosed gap).

## Boundary-lane contract (extracted from source: aneforge/qwen35.py @ 2ea941c)

Per GDN layer, three staged programs:
- stage A (host block): in {"x"}; out {"x" carried, "q","k","v","beta",
  "gt","z"}; owns resident conv state [conv_dim, K-1] (carried pair).
- stage B (state block): DeltaNet recurrence from dedicated ports;
  owns recurrent state [nv, dk, dv].
- stage C (readout tail): in {"x","o","z"}; out {"h"}.
Carried lanes re-rooted by the decoder; never enter the graphs.
Program count per step (38) = the model's staged-layer mix across 24
layers + attention layers' programs; the exact per-program list is
recorded by the studio verify run (ane_programs_total=38,
ane_program_executes_per_step=38, all e5rt ANE — no CPU fallback exists
in e5rt, so every execute was an ANE program).

## Runner milestones (remaining engineering)

- M2: per-program geometry derivation (channels from each HWX's own
  DMA-plane fields or the studio export metadata) -> convert all 46
  HWX -> ANEC.
- M3: single-program execution on T6001 ANE via production-anec-probe
  (numeric parity vs studio outputs where capturable).
- M4: chained decode-step runner: boundary-lane routing per
  qwen35.py's DECODE_MIXER_STAGES contract + host-side greedy control
  (port of the studio e5rt orchestration).
- M5: acceptance per Main: frozen 10 prompts, 3 warmups + 10 reps,
  tokens == frozen reference (chunk_00), installed entrypoint, no CPU
  tensor fallback.

## Constraints

jw16 research-exclusive; llm-inference remains inactive+disabled;
HWX transfer was pure file movement; no ANE execution has happened for
the Qwen artifacts yet (M3 is the first device contact); no PMP work.
