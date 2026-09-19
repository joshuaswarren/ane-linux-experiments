# TDT joint pair-load A/B on jw16: pins EXACT both arms, decode +141.2 ms — NO-LAND (2026-09-19)

Verdict: **NO-LAND (performance).** The candidate is bit-exact on device —
all 12 measured runs hold the full pin set on both arms — but the
interleaved A/B shows the j-major uint32 pair-load joint is **slower**:
tdt_decode median **base 977.0 ms vs candidate 1118.2 ms (+141.2 ms,
+14.4 %)**, per-run ranges disjoint (base 958.2–982.8, cand 1088.2–1134.6).
The pair-load commit `2b53f44e` stays preserved on
`agent/tdt-joint-pair-load` (origin), unmerged; main is untouched.

## What was measured

One wheel built from origin/main `925cfa64` (corrected libmlx lineage:
fence-lift + ModLast fused-chain fixes;
`mlx_omarchy-0.32.3.dev202609192322+925cfa64-cp314-cp314-linux_aarch64.whl`,
sha256 `4ef82f5dd2ab5238fc8ab8e1936f3023c844c3ca9946e71876c35b326e1353ce`,
libmlx16 `bbad05a26b32a8ee`) and TWO pkg trees — base = `925cfa64` overlay,
candidate = branch tip `b4a31317` overlay — so the arms differ by exactly
the pair-load diff (`vulkan_decoder_step.py` + `vulkan_tdt_loop.py`; the
harness imports the decoder from `--pkg`, not site-packages). Byte-identity
of libmlx across arms holds by construction.

- Host jw16mbp1-linux (T6001), Python 3.14, single flock hold on
  `/tmp/m1-gpu.lock` (inode 12, never stolen/unlinked), 18:29:58–18:31:19.
- Protocol per Main's steering: interleaved warm + 6 measured runs per arm
  (base-then-candidate each round), same pinned wheel/worker/model/bundles.
- Worker `/var/tmp/jw16-oproj-place/mlx-omarchy-ane-worker`, libane
  `libane-strict-fill.so`, bundles `/var/tmp/jw16-conv-place/bundles-conv`,
  SPIR-V cache `spirv-ab.3KDGHZ`, fixture `1089-134686-0000`
  (sha `30885601…`), model pin `b650695c…`, golden capture
  `/var/tmp/EncoderParityAne/capture`.

## Gates — 6/6 pins-EXACT per arm (every run)

status match; matching prefix 104/104; transcript sha
`db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790`;
`encoder_hidden` `38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7`;
mel bit-exact `5b54f4a9…`; encoder bounds PASS; `control: gpu-loop`,
`tdt_fallback_reason: null`; `cpu_tensor_events` 0; island timeouts 0.
The pair-load change is therefore semantically exact in production —
decode pins `7da83f06`/`7fd25a86` do not move — and the perf verdict is
not a correctness artifact.

## Result

| arm | tdt_decode median (ms) | per-run (ms) |
| --- | ---: | --- |
| base (k-major scalar fp16) | **977.0** | 973.5, 980.9, 980.6, 972.1, 982.8, 958.2 |
| cand (j-major uint32 pairs) | **1118.2** | 1119.1, 1098.3, 1134.6, 1088.2, 1118.1, 1118.2 |

Base median sits inside the known jw16 band (966–986 ms), so the baseline
arm is sane. The regression is uniform across all six candidate runs.

## Reading (hypothesis falsified, mechanism recorded)

The trace predicted the joint's k-major 16 KB-stride scalar walk was
issue-slot-dominated and that contiguous per-thread u32 pair loads would
cut slots per MAC. On this stack (Mesa Honeykrisp, Apple T6001) the
opposite holds: the wave-coalesced k-major pattern — all 32 lanes of a
wave consuming one 64 B line per k-step in lockstep — beats per-thread
sequential streams plus `unpackHalf2x16` pairing. Layout levers against
this memory system should start from the coalesced pattern as the
measured optimum, not as an assumption to displace. The exactness result
stands: any future candidate can be A/B'd with the same harness at this
identity (`bbad05a26b32a8ee`, appended to
`/var/tmp/v063-jw16/scripts/certified-libmlx-identities.txt` per the
LOCAL-candidate-line convention).

## Window discipline

`TAKE` announced to live lanes before acquisition. Protocol: stop
`llm-inference.service` (inactive verified) → stop
`llm-benchmark-recovery.timer` (Main-directed; verified inactive during
the hold; it would have fired 18:30:13 mid-battery) → lock verified free
(fuser empty) → one flock hold → battery → lock released on script exit →
service restarted (`active`) → recovery timer restarted (`active`) →
llama-server re-acquired the lock (PIDs 579233/579235) → real completion
verified on the restored server (`chatcmpl-fvotpbH0ypkyAtC8EGQQUI4sNv8oxvCo`,
qwen3.8-27b, real generated tokens). jwm1 untouched. GpuDispatchParity
cleared as the next slot.

## Identity

- Battery script: `scripts-local/tdt-pairload-ab-window.sh` at branch tip
  `b4a31317` (fixes: pkg path level, wheel/python parameterization,
  env-through-pipeline staging); executed copy archived here.
- Candidate commit: `2b53f44e` (pair-load), base `925cfa64`.
- CPU-side exactness evidence (unchanged, still holds):
  `test_tdt_joint_pair_layout.py` — old/new addressings bit-identical on
  the pinned component against all 16 captured joint traces.
- Note: `venv-identity-guard.py` refuses the unlisted identity by design;
  this window ran under Main's corrected-lineage order with the identity
  sha-pinned here and the certified row appended post-gate with real
  evidence.

## Artifacts

`receipts/2026-09-19-tdt-pairload-ab/`: `summary.json` (full rows, gates,
medians, delta), `run-window.sh` (executed copy), `e2e-report-base-1.json`
/ `e2e-report-cand-1.json` (schema-1 samples), `decoder-trace-*.json`
(per-run token/duration traces, both arms), `log-{base,cand}-warm.txt`.
jw16-side: `/var/tmp/tdt-pairload-ab/` (all out dirs, logs, pkg trees,
venv), wheel `/var/tmp/tdt-ab-build/dist/`.

## Not claimed

- No speed claim for the candidate — the claim is the measured regression.
- No claim beyond this fixture/host/wheel; the divisor goal line
  (macOS decode 132.7–141.4 ms) is unchanged and remains the full goal.
- The LSTM thread-rebalance and LDS-pair-staging rungs are NOT validated by
  this result; both target buckets (joint LDS traffic, LSTM balance) that
  remain unmeasured on device.
