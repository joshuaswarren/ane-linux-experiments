# TDT LSTM thread-rebalance A/B on jw16: pins EXACT both arms, decode −124.8 ms — LAND candidate (2026-09-19)

Verdict: **WIN — LAND candidate.** The LSTM thread-rebalance is bit-exact on
device (all 12 measured runs hold the full pin set on both arms) and
**faster on this host**: tdt_decode median **base 974.0 ms vs candidate
849.2 ms (−124.8 ms, −12.8 %)**, per-run ranges fully disjoint (base
962.9–988.9, cand 840.4–866.0). Candidate branch `agent/tdt-lstm-rebalance` @
`557db2de` (rebased onto origin/main `9e18c3a8`), unmerged, ready for the
merge/recert flow. Same-host win only: no cross-host or divisor
comparisons are claimed (no matched proven oracle); the macOS decode
goal line is tracked separately and remains open.

## What was measured

Identical protocol to the pair-load A/B: ONE wheel built from the
corrected libmlx lineage (`925cfa64` at build time;
`mlx_omarchy-0.32.3.dev202609192322+925cfa64-cp314-cp314-linux_aarch64.whl`,
sha256 `4ef82f5d…1353ce`, libmlx16 `bbad05a26b32a8ee`) with TWO pkg trees —
base = origin/main overlay, candidate = rebalance branch overlay — so the
arms differ by exactly the rebalance diff (`vulkan_tdt_loop.py` only).
The candidate adds no C++, so libmlx bytes are identical across arms by
construction.

- Candidate commit `1b82d4aa` (kernel) + script cherry-picks; branch
  rebased onto `9e18c3a8` mid-window after origin/main moved
  (installer/community-data commits; zero touches to the TDT file; the
  battery's ancestry gate correctly refused the stale base on the first
  attempt).
- Host jw16mbp1-linux (T6001), single flock hold on `/tmp/m1-gpu.lock`
  (inode 12), 19:12:37–19:13:48. Interleaved warm + 6 measured runs per
  arm (base-then-candidate each round), same pinned
  worker/libane/bundles/fixture/model/capture as every prior window.

## The change

The loop kernel's LSTM chains ran only on threads 0–639 — 384 of 1024
threads idle for the whole section — with all four gate folds inline per
lane thread. The 2560 `(lane, gate)` fold items now map 2–3 per thread
across all 1024 threads (512 threads carry 3 items, 512 carry 2), and
each gate pre-activation stages through a bit-exact carrier before the
unchanged gate-pairing phase reads it back: gate 0 native fp16 in
`s_relu` (dead during chains; the projector overwrites it only after
pairing consumes it), gate 1 float carrier in `s_bval`, gate 2
`floatBitsToUint` carrier in `s_bidx`, gate 3 float carrier in `s_h1`
(pairing reads it back before overwriting the slot with the layer's h1,
same thread). Fold, bias add, gate pairing, cell update, argmax, control,
and the joint head are untouched; threadgroup budget
unchanged (26208 B actual, 28768 requirement ceiling, M1 32 KiB limit).
BARRIER CORRECTION (review finding): the rebalance ADDS one workgroup
barrier per LSTM layer — the staging barrier between the chains and
pairing phases, required for cross-thread visibility of the carriers
(static count 12 → 13; two extra executions per full decoder step). All
other barriers are unchanged; the cost is inside the measured win.

## Measured revisions and byte provenance (per Main)

The battery's first attempt was refused by the script's ancestry gate
because origin/main moved mid-window (`925cfa64` → `9e18c3a8`); the
branch was rebased and PUSHED BEFORE the successful battery — the
measured candidate revision IS the rebased tip `557db2de`, no exercised
bytes were substituted. Proof, per arm:

| file | arm | git blob at named rev | content sha256 (extracted on jw16) |
| --- | --- | --- | --- |
| `overlay/tools/coreml/vulkan_tdt_loop.py` | base | `9e18c3a8` = `ca672fd6…` | `4129da308e5783814bf3df32b450bd177c49df0f5a7e9c6fc77a5289dadde823` |
| `overlay/tools/coreml/vulkan_tdt_loop.py` | cand | `557db2de` = `9047bbb7…` | `76aef6670417b46d1ef8a57f1a2fe9c5db0e13a8ac42c57a810765c89b903a0a` |
| `overlay/tools/coreml/vulkan_decoder_step.py` | both | identical `a36ebcba…` | `a36ebcbabad69474c690e44a4096667b53698b7075a74139dbe15bebbe758dd4` |

- Pre-rebase candidate commit `1b82d4aa` carries the SAME
  `vulkan_tdt_loop.py` blob (`9047bbb7…`) as the measured tip
  `557db2de` — the rebase moved the base only, exercised candidate bytes
  identical.
- `git diff 925cfa64 9e18c3a8 -- overlay/tools/coreml/` is EMPTY — the
  base arm's bytes are identical under either main tip naming.
- The pkg trees extracted on jw16 and executed are the bytes hashed
  above; `vulkan_decoder_step.py` is byte-identical across arms,
  matching the script's pkg-delta line (only `vulkan_tdt_loop.py`
  differs).
- Branch diff `origin/main..agent/tdt-lstm-rebalance`: exactly
  `overlay/tools/coreml/vulkan_tdt_loop.py`,
  `overlay/tests/omarchy/coreml/test_tdt_lstm_rebalance.py`,
  `scripts-local/tdt-pairload-ab-window.sh`.
- PR tip: `3def32c0` (tree `84f2f068`) — adds the code-linked guard test
  on top of the measured tip `557db2de` (tree `f77ce1fd`);
  `git diff 557db2de 3def32c0 -- overlay/tools/coreml/` is EMPTY, so the
  exercised bytes of the measured battery and the PR tip are identical.
- Raw battery JSON: jw16 `/var/tmp/tdt-pairload-ab-reb/out-{base,cand}-{warm,1..6}/e2e-report.json`
  (14 reports), `summary.json`, per-run logs, decoder traces; mirrored in
  this receipt directory.

## Gates — 6/6 pins-EXACT per arm (every run)

status match; matching prefix 104/104; transcript sha
`db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790`;
`encoder_hidden` `38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7`;
mel bit-exact `5b54f4a9…`; encoder bounds PASS; `control: gpu-loop`,
`tdt_fallback_reason: null`; `cpu_tensor_events` 0; island timeouts 0.
Decode pins `7da83f06`/`7fd25a86` hold.

## Result

| arm | tdt_decode median (ms) | per-run (ms) |
| --- | ---: | --- |
| base (640-thread inline lanes) | **974.0** | 982.1, 988.9, 972.6, 975.2, 962.9, 972.9 |
| cand (1024-thread rebalance) | **849.2** | 848.0, 850.3, 866.0, 840.4, 850.7, 847.4 |

Base median inside the known jw16 band (966–986) ✓. Win uniform across
all six candidate runs. Mechanism consistent with the design bound
(~1.33× max on the chains wall ≈ 4–6 % of stage predicted; measured
12.8 % — the chains section was a larger share of the wall than the numpy
split estimated, and/or the balance also shortened the pairing phase's
tail; internal attribution not decomposed further).

## Exactness evidence chain

- CPU: `test_tdt_lstm_rebalance.py` 5/5 — exact-once item coverage with
  the measured 512×3 + 512×2 balance; bit-exact round trips of all three
  carrier forms (native fp16, float, uint float-bits) including
  zero/subnormal/max edges; plus the code-linked `RenderedShaderGuard`
  over the REAL rendered `_loop_glsl()` (mapping bound/stride, staging
  barrier between chains and pairing, all four carrier writes and reads,
  s_h1 read-before-store order, and a byte budget derived from the
  shader's own parsed declarations vs `LOOP_WORKGROUP_MEMORY_BYTES` and
  the 32 KiB M1 limit) with failing-first `test_guard_is_load_bearing`
  (staging-barrier removal, mapping-bound shrink, carrier-write drop
  each fail). PR-tip run log: `pr-tip-tests.log` (5+8+3 tests OK, run at
  tip `3def32c0`, tree `84f2f068`).
- glslangValidator compiles the rendered kernel clean.
- Device: both arms 6/6 pins-EXACT above. `validate_loop` 5-seed
  bit-exact at the candidate identity is a REQUIRED item of the
  scheduled recert and is PENDING until run — it is not satisfied by the
  file being unchanged.

## Window discipline

`TAKE` announced. Protocol per Main: EncoderSubmitRepair's explicit slot
pass (mint not device-ready; they continue host-side) → stopped BOTH
`llm-inference.service` and `llm-benchmark-recovery.timer` (verified
inactive during the hold) → lock verified free → one flock hold → battery
→ lock released on script exit → both units restarted (`active`) →
llama-server re-acquired the lock (PIDs 581279/581282) → real completion
verified (`chatcmpl-6DzFTOtovmtDapLeHyXSLfdveHgQeniI`, qwen3.8-27b;
first probe raced model warm-up, retry real). jwm1 untouched. Explicit
handoff to GpuDispatchParity next per Main's queue.

## Artifacts

`receipts/2026-09-19-tdt-lstm-rebalance-ab/`: `summary.json` (rows,
gates, medians, delta), `run-window.sh` (executed copy),
`e2e-report-{base,cand}-1.json` (schema-1 samples),
`decoder-trace-*.json` (per-run token/duration traces, both arms, 14
files). jw16-side: `/var/tmp/tdt-pairload-ab-reb/` (out dirs, logs, pkg
trees, venv).

## Not claimed

- No claim beyond this fixture/host/wheel; the decode goal line
  (macOS-hosted decode split) remains open and is tracked without
  cross-host ratios (no matched proven oracle).
- Internal attribution of the 124.8 ms (chains balance vs pairing tail)
  is not decomposed.
- No cross-host comparison of any kind: the measured win is
  base-vs-candidate on jw16 only.

## Recert (scheduled gate, 2026-09-19 ~19:4x, jw16)

- `validate_loop` 5-seed at the candidate identity (pkg-cand overlay =
  measured shader bytes, venv libmlx16 `bbad05a26b32a8ee`):
  **5/5 PASS, FAILURES: 0** — seeds 20260915–20260919, windowed mode OK
  per seed (emission streams identical host-control vs GPU loop).
- Code-linked regression `test_tdt_lstm_rebalance.py` (incl.
  `RenderedShaderGuard` + failing-first mutations): **5/5 OK** at PR tip
  `81c3c227` (log `pr-tip-tests.log`); duplicate `__main__` block found
  by Main's review removed in `81c3c227`.
- Window: dual-consent TAKE (GpuDispatchParity release + EncoderSubmitRepair
  pass + Main grant) → both units stopped/verified → single flock hold →
  restore: both units `active`, llama-server re-acquired the lock
  (PIDs 593142/593144), real completion
  `chatcmpl-eAZyrPoeYjxly9L2XNmZ3Mq3gJCMXtcS`. Named handoff to
  EncoderSubmitRepair.
