# 2026-09-24 — t6001-host QmmVecQ4 GEMV: split-K reopen path measured and REFUSED; production kernel confirmed at its dispatch-geometry ceiling; nothing installed

Lane: t6001 gemv (QmmVecQ4 GEMV bandwidth on T6001 decode). Host: t6001-host
(t6001-host, M1 Max T6001/G13C, Omarchy Linux). Base: installed serving tree
`69801d05 + mode-1 routing` = `dispatchcut/fuse` @ `0b1f24ba` (the 71.2 tok/s
install), device worktree `/var/tmp/gemv-t6001-wt`, branch
`agent/q4-gemv-t6001` @ `97a2250f` (bench tooling only — **`git diff 0b1f24ba
-- overlay/` is empty; no production change**).

**Verdict: NO-GO. The split-K reopen path named by
2026-09-23-t6001-t1-decode-profile-subfix §3 loses at every S (−11% at S=2,
−85% at S=32) on the decision-grade RAW-ring instrument. The installed kernel
measures 140–172 GB/s against a ~241 GB/s same-device streaming-read roof, and
the gap is dispatch-geometry latency at 2k–12k subgroups per GEMV — not load
width, not dequant ALU, not threadgroup shape, and not fixable by k-splitting.
No candidate reached the qualify/A/B stage; nothing installed; service
restored and verified with a real completion.**

## 0. Change under test

None landed. Instruments added to `tools/q4-bw-bench` (commit `97a2250f`):

- `--sk` mode: production single-weight qmm_vec vs a chunked split-K variant
  (`qmm_vec_splitk.comp`, per-lane stride walk confined to a k-chunk, f32
  partials) plus a deterministic fixed-order reduce (`q4_splitk_reduce.comp`,
  one thread per row, chunks summed in index order, production bf16
  round-to-nearest-even). Four single-weight shapes in a RAW ring:
  gate_up 6144×2048, down 2048×6144, qkv 4096×2048, out 2048×2048
  (21.29 MB weights/token). S ∈ {1(base), 2, 4, 8, 16, 32}, 2 passes,
  5 rounds each, wall-anchored whole submits.
- `qmm_vec_base.comp` resynced to the shipped shader: the frozen copy had
  drifted (pre-xpack, no SwiGLU fold), which (a) makes
  `tools/q4-bw-bench/run-roof-m1.sh` abort on its provenance assert, and (b)
  mislabels gap-mode output — the gap "base" arm is the pre-xpack kernel and
  the "xpack" arm is today's production. Receipts quoting gap baselines from
  this tree must use the **xpack** arm as production.

## 1. GEMV microbench — before (installed production kernel)

Exclusive-GPU windows (llm-inference.service stopped, `/tmp/m1-gpu.lock`
held, load quiet; service restored after each window).

**In-model wall, serving venv `/var/tmp/v072-venv-fused`, mx.quantized_matmul
(q4/g64/bf16), batched reps, one submit** (`artifacts/inmodel-*.log`):

| shape (n×k) | µs | GB/s | caveat |
|---|---:|---:|---|
| gate_up 6144×2048 | 74.0 | 95.8 | CPU-graph-build floor ~25–30 µs/op pollutes small shapes |
| down 2048×6144 | 62.5 | 113.4 | " |
| qkvz 8192×2048 | 132.5 | 71.4 | " |
| qkv(+z+a+b) 6144×2048 | 112.1 | 63.3 | " + first-touch order effects |
| out/z 2048×2048 | 24–26 | 90–97 | " |
| **lm_head 248320×2048** | **1460.6** | **196.2** | GPU-bound, honest; chained 1553 µs / 184.5 |

n-scaling walk at k=2048 (batched): n=1024→63, 4096→105, 16384→117,
131072→185, 248320→202 GB/s — in-model GEMV bandwidth climbs with ROW count
toward the read roof; lm_head (248k rows) already runs at ~196–202 GB/s.

**Decision-grade C++ instrument (`--2b --gap`, RAW-chained production shapes,
one weight set per layer, 24 sets widedep):**

| arm | layer_ns_med | weight GB/s | identity |
|---|---:|---:|---|
| widedep (= today's production, xpack arm) | 198965–199117 | **172.2–172.3** | production bf16 xpack + SwiGLU fold kernel |
| widedep "base" | 259414–259542 | 132.1 | STALE pre-xpack shader (mislabel; see §0) |
| widedep_unroll (pre-xpack lineage) | 254428–254618 | 134.7 | +2.0% over stale base, sub-noise vs production |
| widedep_wg128 (pre-xpack lineage) | 257214–257266 | 133.3 | +0.9% over stale base |

Same-device pure-read roof: python `mx.sum` f32, 256 MB working set (≫48 MB
SLC): **240.8 GB/s**; harness `peak_read` 38.6 µs/268 MB = 217 GB/s after the
known ~32× timestamp correction. (Roof pattern probe's 310 GB/s at 131k
subgroups is SLC-assisted at pitch 112/266 MB window and is not a DRAM roof.)

## 2. GEMV microbench — after (split-K screen, the named reopen path)

`--sk`, pass 2 (settled; pass 1 agrees in ordering), median over 5 rounds ×
8 tokens per submit (`artifacts/sk2-20260924T051020Z.ndjson`):

| arm | S | µs/token | weight GB/s | Δ vs base |
|---|---:|---:|---:|---:|
| base (production) | 1 | 151.9 | **140.2** | — |
| sk2 | 2 | 171.0 | 124.5 | **−11.2%** |
| sk4 | 4 | 197.1 | 108.0 | −22.9% |
| sk8 | 8 | 308.8 | 68.9 | −50.9% |
| sk16 | 16 | 533.0 | 39.9 | −71.5% |
| sk32 | 32 | 1006.7 | 21.1 | −84.9% |

(total_gb_s incl. partial write+read agrees in ordering: 125.8 → 24.8.)
The fixed-order reduce is deterministic by construction, but the arithmetic
order necessarily differs from the unsplit kernel, so this path could never
have been digest-identical — it had to win on the GB/s gate first. It does
not: it loses monotonically from the smallest split.

Why the 131k-curve reasoning fails: the occupancy curve's high-bandwidth
points multiply subgroups at CONSTANT per-subgroup chain depth (more rows).
Split-K multiplies subgroups by S while DIVIDING per-slot work by S —
outstanding-request depth stays flat, every subgroup still pays
launch/reduction/partial-store fixed cost, and at S≥16 the chunk (words/S,
k=2048: 8 words at S=32) leaves most of a 32-lane slot idle. lm_head already
lives at the high-n end of the curve (248k rows, ~196–202 GB/s); the
latency-bound small-n dispatches (2048–8192 rows) cannot synthesize rows
without changing what is computed.

## 3. Root cause of the ~160–172 GB/s ceiling

Discrimination, per assignment's four candidates:

1. **Occupancy/dispatch geometry — YES, this is the ceiling.** GB/s tracks
   full-depth row concurrency: nwalk climbs with n to the read roof; decode
   GEMVs have n ∈ {2048…12288} rows/dispatch and sit at 140–172 GB/s; every
   instrument that adds rows at fixed depth climbs, every instrument that
   splits depth (all S) or cuts workgroups falls. Little's-law consistent
   with the occupancy receipt's 430 ns weight-word latency.
2. **Load width — no.** bf16 xpack (uvec4 x quads) is already shipped in the
   installed kernel; weight v4 loads measured slower than v2/w2 (pattern
   arms `pat_v4_r8` 151.7 vs `pat_v2_r8` 211.2 GB/s; occupancy receipt
   agrees).
3. **Dequant ALU — no.** The near-empty-body pattern probe at production
   geometry lands in the same band as the shipped kernel (pattern `w1_r8`
   135.9 GB/s vs production-family 132–172); removing the dequant does not
   lift GB/s, so ALU is not the binding constraint.
4. **Threadgroup shape / rows per subgroup — no.** 4 cols/wg (wg128) +0.9%
   over the stale base (= regression vs production); pattern r1 104 vs r8
   136 GB/s; larger groups only remove workgroups, the wrong direction at
   2–12k subgroups.

Ceiling accounting: production GEMV family streams ~771 MB/token (decoder
projections) at 140–172 GB/s plus lm_head 286 MB at ~196–202 — against a
~241 GB/s same-device read roof. The residual (~25–40% on the decoder side)
is locked behind per-dispatch row counts the model fixes; no measured lever
reaches it.

## 4. Qualification / A/B / gates

**Not run — no candidate to qualify.** The contract gates (10-pass digest
`dbf70497`, logits 0-flip ×3, 3-warmup/10-paired-rep CIs vs 71.2) apply to a
candidate that clears the microbench gate; split-K (the only lever with
nominally positive headroom) fails the GB/s gate at every S, so there is no
arm to build, gate, or A/B. Instrument-only commit `97a2250f` carries
`git diff 0b1f24ba -- overlay/` = empty, so the installed tree is unchanged
by construction.

## 5. Install state

**Nothing installed.** Serving venv `/var/tmp/v072-venv-fused` untouched
(mlx_omarchy wheel from t6001cut-wt/dist, the 71.13/71.28 fused-norm mode-1
install; version-string suffix `a12b1aa1` is the known setup.py git-walkup
artifact, not the source commit). `llm-inference.service` was stopped for
three measurement windows and restored after each (`/health`
`{"status":"ok"}`); a real completion was verified after the final window:
HTTP 200, `chatcmpl-48V273HVfTjgassM9MlCdoo…`, 5 completion tokens generated
(`artifacts/completion-check2.json`; API-key file auth untouched).

## 6. Remaining gap (71.2 tok/s installed vs 179.5 macOS firstpass)

Unchanged from the subfix receipt, minus the GEMV item it hoped to reopen:

1. ~~GEMV concurrency reopen via split-K~~ — **closed by this receipt.**
2. Norm/elementwise/cast micro-swarm (~39% of profiled kernel time, ~350
   launches/token, launch-latency-bound) — chain-aware extension or dispatch
   coalescing.
3. Raw-route dispatch depth (the −10.6% multi-T wheel mystery, root cause
   still open in the raw-op route shape).
4. Submission boundaries (~2 × ~310 µs profiled inter-submission gaps) and
   rtmod print gating (defect fix ready, rides the next winning wheel).
5. GEMV side: only levers outside this lane's scope remain — e.g. raising
   effective rows per dispatch via more cross-weight merging (MULTI
   dependency-free frontier is already exhausted: qkv+z+a+b merged, gate+up
   SwiGLU-folded; `down` depends on gate_up's output) or prefill/ANE.

## Artifacts

- `artifacts/sk2-20260924T051020Z.ndjson` — split-K screen (this receipt's §2).
- `artifacts/gap-20260924T050643Z.ndjson` — gap screen; production = xpack arms.
- `artifacts/roof-20260924T050643Z.ndjson` — peaks + pattern arms (timestamps
  mis-scaled ~32×; wall rows authoritative).
- `artifacts/inmodel-20260924T0{45126Z.log,50643Z.log,50643Z.json}` —
  in-model shape table, n-scaling walk, read roofline.
- `artifacts/window*.log` — window/service-restore logs;
  `artifacts/completion-check2.json` — post-window completion receipt.
- Device: `/var/tmp/gemv-t6001-wt` @ `97a2250f` (branch `agent/q4-gemv-t6001`),
  binary+scripts `/tmp/gemv-sk16/`, raw outs `/tmp/gemv-sk16/out/`.
