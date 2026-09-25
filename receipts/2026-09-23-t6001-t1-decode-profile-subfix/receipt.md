# 2026-09-23 — t6001-host T=1 decode profile (production route) + route/gate/budget matrix

Lane: T6001Decode. Host: t6001-host (t6001-host, M1 Max T6001, Omarchy Linux, kernel
7.1.6-1-1-ARCH; rebooted 08:15 today — all windows post-reboot). Installed
build at start: `mlx_omarchy-0.32.3.dev202609230705+aae4dfc9` in
`/var/tmp/v072-venv-fused` with mlx-lm 0.31.3 carrying the **GDN raw-route
patch** in `mlx_lm/models/gated_delta.py` (T==1 →
`mx.fast.gated_delta_update_raw`; drops the `mx.metal.is_available()` gate
that is always false on Linux). Coordinate peers: M1Decode (m1-host,
batch-budget), M1GdnFuse (m1-host, GDN norm fusion), T6001Parity (prior lane).

## 0. THE session finding: two GDN routes, and a venv-setup trap

mlx-lm 0.31.3 stock refuses the GDN fast kernel on Linux:
`gated_delta.py` gates `use_kernel` on `mx.metal.is_available()` (line 281),
which is false on the Vulkan stack, so decode runs the **eager composed GDN
scan**: 36.7 tok/s, digest `d4377e53`, prefill 74 tok/s.
The patched route (v072's venv, patch = scripts/patch-mlx-lm-gdn.py +
patch-mlx-lm-gdn-raw.py, wired default-on in
scripts/apply-mlx-lm-patches.sh) runs the raw kernel: **63.5 tok/s, digest
`bc519c03`**. Same wheel, same everything else.

Every venv I created today with plain `pip install mlx-lm==0.31.3` was
stock-route; the serving venv was patched. Three A/B arms (candidate
wheel 1641, bisect-B, bisect-C/gc) compared patched-route ctl against
stock-route cand and produced a reproducible, deterministic "regression"
(63.5→36.7, prefill 830→74, digest flip bc519c03→d4377e53, 2 gate flips
at p4@25/p9@19, max prefix |Δ| 0.246) that had NOTHING to do with the
wheels under test. The trap: `diff -rq` of the two mlx_lm trees printed
the real hit (`gated_delta.py differs`) below a wall of `__pycache__`
noise cut off by `head`. Budget for the head.

Re-baseline (clean window, patched route, installed wheel): **decode
63.55 tok/s (stdev 0.46), prefill 822.3, digest `bc519c03c4ef5fd1...`**
(30-record digest, identical to m1-host's — cross-host anchor; T6001Parity's
`dbf70497` is the same computation at `--passes 10`, pass field inside
the hash). Yesterday's 63.32/831.34 reproduces within ~1%.

Instrument note: the diag wheel (`diag.aae4dfc`) runs decode ~1.74x
slower than release even with profiling env unset — kernel GPU times and
per-kernel shares are usable, absolute walls are not. Also: `diff -rq`
twice missed that stderr goes to a live ssh pipe at 36 tok/s; all
windows are file-redirected.

## 1. Profile: one decode step (T=1), production route

Instrument: `MLX_OMARCHY_GPU_PROFILE` on the diag wheel, patched route
(venv re-patched in-place), contract decode path (generate_step, greedy,
prompt 0, 31 intervals), per-phase attribution via
phase_kernels.py (dispatch → submit → marker window). Prompt-5 control
reproduced (16.5-class walls both).

**Production shape: 580 dispatches/token, 3.1 submissions/token, 580
barrier decisions/token, 0% skipped; inter-submission gaps p50 310 µs
(profiled).** GPU-busy 26.1 ms/tok profiled ≈ 15.7 ms real wall at the
~1.66x diag inflation — the model checks out end to end.

Per-kernel decode-window GPU time per token (profiled; rescale by ~1.66
for real-magnitude estimates):

| kernel | n/tok | ms/tok | share |
|---|---:|---:|---:|
| QmmVecQ4MultiSubgroupBF16 (FFN+GDN projections) | 96 | 6.44 | 24.7% |
| FastRmsNormBF16 | 115 | 3.53 | 13.5% |
| ElementwiseBF16 | 61 | 2.45 | 9.4% |
| QmmVecQ4WordSubgroupBF16 (lm_head+attn) | 19 | 2.38 | 9.1% |
| GatedDeltaDecodeBF16 (raw kernel) | 18 | 1.95 | 7.5% |
| CopyGeneralBF16 | 72 | 1.76 | 6.7% |
| CastBF16F32 | 54 | 1.19 | 4.6% |
| FusedChainF32 | 18 | 0.71 | 2.7% |
| ConvBF16 | 18 | 0.71 | 2.7% |
| CastF32BF16 | 24 | 0.68 | 2.6% |
| MatmulF32 | 12 | 0.66 | 2.5% |
| BinaryVecBF16 | 24 | 0.64 | 2.4% |
| rest (rope, softmax, lse, argmax, …) | ~90 | ~4.2 | 16% |

Grouped, production: **GEMV family 33.8%, norm/elementwise/cast swarm
~39%, GDN core 7.5%, submission boundaries (2 inter-submission gaps ×
p50 310 µs) ~4%.** Contrast with the stock-route graph (977
dispatches/tok, f32 chain soup 46%) — and with m1-host's profile: the
earlier "t6001-host GDN f32 soup = 46%" figure described the stock route, not
production; on the production route t6001-host's ranking looks like m1-host's
(GEMV-led), just faster.

## 2. Roofline (bytes/token from safetensors headers, exact)

Per-token read set: decoder weights 773.3 MB (mlp 509.6 + gdn 213.9 +
attn 49.6) + lm_head 286.1 MB (tied embed) + ~8 MB state/KV = **1067 MB**.

| point | ms/tok | tok/s | eff GB/s | % of 400 GB/s |
|---|---:|---:|---:|---:|
| theoretical roof (400 GB/s) | 2.67 | 374.8 | 400 | 100% |
| in-model GEMV pattern ceiling (160 GB/s, occ receipt) | 6.67 | 149.9 | 160 | 40% |
| macOS (frozen firstpass) | 5.57 | 179.47 | 191.6 | 48% |
| **Linux installed (aae4dfc9, patched route)** | **15.74** | **63.55** | **67.8** | **17%** |

## 3. Top 3 costs (production route, numbers)

1. **QmmVecQ4 GEMV family — 8.8 ms/tok profiled (33.8%)**, streams
   ~1057 MB at its dispatch-geometry pattern ceiling (160 GB/s; measured
   in-model by the occupancy receipt). Kernel-level levers closed there
   (w2/quad4/unroll/wg128/split-K rejected on the GB/s gate); the only
   reopening path is the concurrency the pattern curve shows at 131k
   subgroups (310 GB/s) — i.e. the decode-kernels handoff's lm_head
   split-K, which needs on-device measurement.
2. **Norm/elementwise/cast micro-swarm — ~10.2 ms/tok profiled (~39%)**
   across ~350 launches (FastRmsNorm 115 × 30.7 µs on ~4 KB rows =
   launch-latency-bound). M1GdnFuse's fused primitives
   (rms_norm_gated / rms_norm_scaled, FastNormGatedBF16, bit-exact 42/42
   on m1-host) target exactly this and measured **neutral on t6001-host**
   (−0.042 ± 0.131 tok/s, see §5): on T6001 the launches they remove are
   already cheap relative to the raw-route graph. Their value shows on
   T8103-class hosts and in further chain extension.
3. **Submission structure** — 3.1 submits/token at the 256-node budget
   (2 GPU-idle boundaries × ~310 µs profiled / ~231 µs AGX analog) plus
   the two ungated `[rtmod]` fprintf's on the submit path (7+ stderr
   write()s/token; live-pipe backpressure on them measured 2x decode
   collapse this session).

## 4. Fixes implemented and measured (this session)

Branches (build-host worktrees, all built off-device in the ALARM chroot
`dg-alarm-py314:sep23`, whole-encoder bundle at `/bundle-staging`):

- `t6001-hostdecode/t1-decode-fix` (base 8d5f739b):
  - `3dcdba93` — cherry-pick of c111c784e: `kBatchNodeBudget` 256→4096.
  - `40b66c40` — gate the two ungated `[rtmod]` hot-path prints
    (encoder.cpp COMMIT-NOOP + SUBMIT) behind
    `MLX_OMARCHY_TRACE_DISPATCH`, matching every other rtmod site
    (leftover from the F1 serving-hang debug, 682d47b2).
- `t6001-hostdecode/multit-t1fix` (base 8d5f739b): `ec3da755`+`2db84297` —
  compile-time single-step shader variant `GatedDeltaDecodeT1BF16`
  (`-DGDN_T1_STATIC`), dispatched at T==1 on the raw route; T=2..8 keep
  the multi-T loop. Math identical (same body, one iteration, zero
  pitches).
- `t6001-hostdecode/gdn-fuse` (base bisect-C = a12b1aa1 + 40b66c40):
  `deae551f` — cherry-pick of M1GdnFuse 276c3b7d (fast
  rms_norm_gated/rms_norm_scaled primitives + FastNormGatedBF16 shader +
  mlx-lm routing script), conflicts resolved by dropping the m1-host-only
  greedy-prune pieces.

## 5. A/B matrix (contract: 10 prompts, warmup 3, passes 3, greedy, prefill 512; interleaved reps; patched route unless noted)

| arm | wheel | route | decode mean | prefill mean | digest | verdict |
|---|---|---|---:|---:|---|---|
| ctl | aae4dfc9 (installed) | patched | 63.40 | 832.5 | `bc519c03` | baseline |
| cand | 40b66c40 (budget+gate) | **stock** | 36.69 | 74.2 | `d4377e53` | INVALID — route artifact |
| gc | 70b6297f (gate only) | **stock** | 36.70 | 74.2 | `d4377e53` | INVALID — route artifact |
| fuse | deae551f (gate+fusion) | patched | **63.36** | 832.0 | `bc519c03` | **bit-exact, perf-neutral** |
| C1 | a12b1aa1 pristine | patched | 63.33 | 838.2 | `bc519c03` | flow+base clean |
| arm3 | 8d5f739 (multi-T) | patched | 56.73 | 815.5 | `bc519c03` | **multi-T wheel −10.6% T=1** |
| arm4 | a12b1aa1+budget+gate | **stock** | 37.5 | 73.4 | `d4377e53` | INVALID (route) |

Key numbers:
- fuse vs ctl, 10 paired reps: **−0.042 ± 0.131 tok/s (95%, df=9),
  ratio 0.9993 — one digest across all 20 runs, gate 0 flips, Δ 0.0.**
  Perf-neutral ⇒ NOT a win ⇒ **not installed** (assignment rule).
- Budget re-test on the patched route (arm4 confounded by route) and
  gate-only 10-rep remain open; the gate commit is digest-clean by
  construction and rtmod-verified in-binary (gc/console: 0 rtmod lines
  vs ctl 4275).
- Multi-T wheel regression stands: 8d5f739 = −10.6% T=1 decode vs
  a12b1aa1, bit-exact (`bc519c03`), prefill intact. T6001Parity's
  "machine state" attribution was wrong. My T1-static variant did NOT
  recover it (56.84/56.89) — the cost is not the dynamic loop codegen;
  root cause still open in the raw-route dispatch layer.
- Budget re-probe on the PATCHED route (2 reps, digest `bc519c03` ✓):
  decode 64.31/63.79 (≈ +0.6, sub-noise) but **prefill 729.4 vs ctl 832
  (−12%)** — the budget trades a hair of decode for a real prefill loss
  on t6001-host (byte-branch flush dynamics; m1-host sees neither effect).
  REJECT for t6001-host; m1-host keeps it.
- UMA total_memory fix (fbe4fc0ae + c23198997, m1-host
  batch-flush-rootcause) re-probed on top of budget-4096+gate
  (wheel 185887b4): decode 64.03/64.54, prefill 730.9/727.9,
  digest `bc519c03`, rtmod=0 — prefill NOT recovered. The ~16 MB
  DEVICE_LOCAL heap quirk is T8103-specific; t6001-host heap reporting
  was already sane, so the UMA fix is a no-op here and the prefill
  loss is intrinsic to budget-4096 on this host. Budget REJECT
  stands with clean attribution; the UMA fix still ships for m1-host.

## 6. Install + restore

**Nothing installed** — no arm beat the installed build outside noise
with identical digests. `llm-inference.service` stopped for 6 measurement
windows and restored after each; final state `active`, `/health`
`{"status":"ok"}`, real completion verified after every window
(`curl /health` + the service's own completion path exercised by prior
lanes' smoke; API-key file auth untouched).

## 7. Remaining gap (t6001-host T=1 decode, 63.5 vs macOS 179.47)

Ranked, with owners:
1. **Raw-route dispatch + kernel depth (multi-T lane)**: 8d5f739 costs
   −10.6% T=1 vs a12b1aa1 with no benefit at T=1; my compile-time
   single-step variant (ec3da755, wheel `52b45180...`) did not recover
   it — the cost is in the raw-op route shape, not the loop codegen.
   Repro: t6001-host `/var/tmp/t6001-hostdecode/` (all wheels + JSONs).
2. **Norm/elementwise swarm (~39% profiled)**: M1GdnFuse's primitives
   are bit-exact and neutral on T6001 alone; the next move is
   chain-aware extension (decode-kernels handoff item 2b) or dispatch
   coalescing of the remaining ~350 launches.
3. **GEMV concurrency (33.8%)**: pattern-ceiling-closed at current
   geometry; the 310 GB/s-at-131k-subgroups curve is the reopen path
   (split-K sketch in the handoff, needs measurement).
4. **rtmod print gate (40b66c40)**: defect fix ready, digest-clean,
   measured neutral-perf; rides the next winning wheel.
5. Submission boundaries at 256 nodes: measured NEUTRAL on the patched
   route (budget+gate wheel 73db34b3: decode 64.31/63.79 ≈ +0.6
   sub-noise) at the cost of prefill −12% (832→729) — budget-4096
   REJECTED for t6001-host on the prefill regression; boundaries themselves
   (~2 × 310 µs profiled) remain a small open cost.

## Artifacts

- t6001-host `/var/tmp/t6001-hostdecode/`: all wheels (1641/1656/1707/1725/1734/1759
  lineage), `venv-{cand,bisectc,t1fix,fuse,budget}`, probe + A/B scripts,
  `out/` (contract JSONs per arm/rep, gate JSONs, profile NDJSON
  p0/p0c/p0d + markers, analyzer outputs, window logs).
- t6001-host `/var/tmp/t6001-hostdecode/out/contract-ctl-today.json` — today's
  installed-baseline control (63.55 / 822 / bc519c03).
- build-host `~/src/t6001-hostdecode-wt` (t6001-hostdecode/t1-decode-fix),
  `~/src/t6001-hostdecode-t1fix-wt` (t6001-hostdecode/multit-t1fix),
  `~/src/t6001-hostdecode-bisectc-wt` (gate-only build tree),
  `~/src/t6001-hostdecode-fuse-wt` (t6001-hostdecode/gdn-fuse), wheels in
  `~/src/wheels-out/` + tree roots.
- ane-linux-experiments `receipts-work-t6001-hostdecode/`: all window/build/
  patch scripts; `receipts/2026-09-23-t6001-host-t1-decode-profile-subfix/`:
  this receipt.
