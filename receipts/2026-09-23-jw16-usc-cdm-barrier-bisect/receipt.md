# 2026-09-23 — t6001-host (T6001) decode: installed-stack re-profile + CDM-barrier bit bisection (uscstudy)

Lane: uscstudy lane (T6001). Host: t6001-host (M1 Max T6001/G13C, Omarchy Linux,
kernel 7.1.6-1-1-ARCH). Denominator: macOS frozen firstpass 179.47 tok/s
(receipts/2026-09-23, parity-pkdeep-qwen-multit). Starting state:
MaxDispatch designedusc driver installed (`/usr/local/lib/
libvulkan_asahi.so.d3fa18e`), serving venv `/var/tmp/v072-venv-fused`
(mlx-lm 0.31.3 + GDN raw-route patches), documented 68.4 tok/s.

## 0. State repair found on arrival

`/var/tmp/v072-venv-fused` held the **diag** wheel
(`0.32.3.dev202609230703+diag.aae4dfc`), a leftover from the MaxDispatch
profiled-streams step, not the documented release aae4dfc9. Restored via
`pip install --force-reinstall --no-deps /var/tmp/gdncoop/wheels/
mlx_omarchy-0.32.3.dev202609230705+aae4dfc9-...whl`; raw-route patch intact
(2 `gated_delta_update_raw` refs). llm-inference (llama-server on the 27B
GGUF) does not use this venv; the wheel swap is mlx-stack-only.

## 1. Profile: one decode token on the installed stack (post-MaxDispatch)

Instrument: diag wheel (venv-diag) + `MLX_OMARCHY_GPU_PROFILE`, contract
decode path (prompt 0, prefill 512, 32 tokens greedy), phase attribution
via `phase_kernels.py` (dispatch → submit → marker window), analyzer
`profile_analyze.py`. Stream: 21014 dispatches, 107 submissions, 96 decode
submissions = 3/token, barrier decisions 21014 emitted / 0 skipped.

Per-kernel decode-window GPU time (profiled; diag wheel inflates absolute
walls ~1.7x — SHARES are the usable signal, release walls quoted separately):

| kernel | n/tok | share |
|---|---:|---:|
| QmmVecQ4MultiSubgroupBF16 (FFN+GDN proj) | 32 | 24.6% |
| FastRmsNormBF16 | 38.3 | 13.5% |
| QmmVecQ4WordSubgroupBF16 (lm_head+attn) | 6.3 | 9.2% |
| GatedDeltaDecodeBF16 (raw) | 6.0 | 7.5% |
| CopyGeneralBF16 | 24 | 7.1% |
| ElementwiseBF16 | 14.3 | 6.9% |
| CastBF16F32 | 18 | 5.3% |
| FusedChainF32 | 12 | 4.4% |
| ConvBF16 | 6 | 3.4% |
| rest | | ~18% |

Gap structure: intra-submission gaps p50 11.6 us / p90 55.2 us (20907
gaps, 416.9 ms total); inter-submission p50 217.9 us (106 gaps). Dependency
proxy: 39% of consecutive pairs fully disjoint. Host submit() p50 6.95 ms
(instrumented diag wall — release is lighter).

### Top-3 costs (installed stack)

1. **Dispatch/barrier serialization structure** — the live lever. Evidence:
   dropping the CDM barrier to USC-invalidate-only (perf arm, below) moves
   release-wall decode 68.24 → 102.85 tok/s (+50.7%), i.e. ~4.9 ms/tok of
   the 14.65 ms/tok wall is barrier/wait structure, not kernel arithmetic.
2. **QmmVecQ4 GEMV family** — ~34% of kernel time (2.95 ms/tok profiled);
   dispatch-geometry ceiling ~160 GB/s (occupancy receipt), kernel-level
   levers closed there; split-K-at-131k-subgroups is the reopen path.
3. **Norm/elementwise/cast micro-kernel swarm** — ~48% of kernel time
   (~350+ launches/token at 20-50 us). M1GdnFuse's fused primitives
   (rms_norm_gated/rms_norm_scaled) measured bit-exact and perf-neutral on
   T6001 pre-MaxDispatch (receipt 2026-09-23-t6001-t1-decode-profile-subfix
   §5); post-fix the launches they remove are cheaper still — neutral
   verdict stands; chain-aware extension or dispatch coalescing is the
   future lane, not this one.

## 2. Candidate: per-dispatch CDM barrier bit reduction (mesa-1)

Installed default emits the designed set {unk_4, unk_5, unk_6, unk_8} +
`usc_cache_inval` per launch (d3fa18e8dd0). Floor matrix (MaxDispatch
receipt §1): the remaining CDM-barrier arm costs ~4.6-5.1 us/dispatch on
real MLX pairs vs ~1.2-1.5 us for usc-inval-only. Question: which designed
bits are actually REQUIRED for digest-clean decode?

### usc-only probe (zero-build, installed driver, HK_PERFTEST=usccdmbarrier)

| arm | decode | prefill | 3-pass digest |
|---|---:|---:|---|
| installed default (sanity) | 68.24 | 808.9 | `bc519c03` |
| usc-only r1 | 102.85 | 795.0 | `40e37a43` |
| usc-only r2 | 102.95 | 787.0 | `93552670` |
| usc-only r3 | 103.32 | 784.1 | `b1ec6ade` |

Logits gate (usc-only): **steps=320 flips=320 max|d_top1|=28.125** (prompt
0) — gross, nondeterministic cache-coherence corruption, not a rounding
class. usc-only is BROKEN; the +50% was corruption speed. At least some of
{4,5,6,8} enforce a real dependency.

### Bit bisection (build: mesa-1 `usc-barrier-study` @ 549ddbb8a7d)

New perftest arm `HK_PERFTEST=maskcdmbarrier` + `HK_CDM_BARRIER_SET` (hex
field mask; default 0x178 = designedusc set incl. usc bit 3). Built release
in the dg-alarm-py314:sep23 chroot (gcc 16.1.1, LLVM 22.1.8 + spirv-llvm-
translator 22.1.6 provisioned via pacman; image's pristine ALARM root lacks
meson/LLVM — my container `dg-uscstudy` provisions them). Build sha256
`f6b7909b05666325...`; commit 549ddbb8a7d = 4 files, +49 lines, perftest-
only and inert without the env.

Build/machinery validation (window3d, all 3-pass): installed no-env
68.52 `bc519c03`; my build no-env 68.0 `bc519c03`; my build designedusc
function 68.51 `bc519c03`; my build mask 0x178 68.06 `bc519c03` — the mask
path emits designedusc-equivalent streams and my build is digest-faithful.

**Rare-flip discovery (digest stability battery, window3r, 12 contracts):**
the INSTALLED control flipped once — sys-r3 = `08e8a69a` (11/12
`bc519c03`). Record diff: prompt 1 output_ids first differ at token 20
(4776 vs 36609), then cascade — the documented bf16 near-tie class
(single-point divergence; corruption shows hundreds of flips instead).
Same-backend near-tie flips are rare machine-state noise on a hot box;
they hit any arm and are reported, not gated on.

### Bisection map (every arm: 3-pass contract + logits gate vs `logits-coop.json`)

| arm | SET | bits (+usc) | decode tok/s | 3-pass digest | logits |
|---|---|---|---:|---|---|
| sanity | 0x178 | {4,5,6,8} | 68.37 | `bc519c03` | 0 flips, Δ0.0 |
| drop4 | 0x168 | {5,6,8} | 67.12 | `d062385a` | **320/320, Δ26.9** |
| drop5 | 0x158 | {4,6,8} | 68.31 | `9402574b` | **19/320, Δ8.5** |
| drop6 | 0x138 | {4,5,8} | 68.73 | `046aff4d` | **320/320, Δ22.5** |
| drop8 | 0x078 | {4,5,6} | 101.29 | `5e093035` | **320/320, Δ22.5** |
| sub7 | 0x0F8 | {4,5,6,7} | 68.47 | `bc519c03` | 0 flips, Δ0.0 |
| g13g | 0x1F8 | {4,5,6,7,8} | 68.44 | `bc519c03` | 0 flips, Δ0.125 |
| lowbits | 0x00F | {0,1,2} | 102.28 | `c3a978ca` | **320/320, Δ31.25** |
| only7 | 0x088 | {7} | 67.45 | `b348c33d` | **320/320, Δ28.1** |
| usc-only | 0x008 | {} | 102.85-103.32 | 3 distinct | **320/320, Δ28.1** |

Findings:
1. **All four designed bits are individually required.** Every single-bit
   removal corrupts (flips in the hundreds with max|Δ_top1| 8.5-31.3 —
   stale-read corruption, not rounding).
2. **unk_8 (or redundantly unk_7) is the entire cost AND the entire
   protection.** {4,5,6}+usc runs 101 tok/s (usc-class speed) and corrupts;
   adding either 8 or 7 restores correctness at designedusc speed. The
   G13G trim set {4,5,6,7,8} is clean at the same speed.
3. The ~+50% decode speed is the corruption speed. The CDM-barrier wait is
   genuinely required by MLX's storage/texture read mix on G13X; no
   bit-level configuration is both faster and bit-exact.

**Verdict: the bit-exact CDM-barrier trim on G13X is EXHAUSTED at the
installed designedusc set. No win exists in this lever → nothing to
install.** The corrupt-fast arms are documented to close the "what about
101 tok/s?" question quantitatively.

## 3. A/B (contract: 10 prompts, warmup 3, passes 3, greedy, prefill 512, 32 new; 10 interleaved triples; 10-pass digest; logits gate vs `logits-coop.json`)

No winning candidate exists (§2), so the definitive A/B quantifies the map:
ctl = installed designedusc; sub7 = the clean minimal alternative
({4,5,6,7}+usc); fast8 = the corrupt fast set ({4,5,6}+usc).

| arm | decode mean±sd | median | paired delta vs ctl | 3-pass digests |
|---|---|---:|---:|---|
| ctl | 68.42 ± 0.14 | 68.43 | — | 9/10 `bc519c03`, 1/10 `9402574b` (near-tie) |
| sub7 | 68.34 ± 0.16 | 68.34 | **−0.081 ± 0.183 (95% CI, n=10) = −0.12%** | 8/10 `bc519c03`, 2 near-tie |
| fast8 | 101.59 ± 0.25 | 101.59 | **+33.169 ± 0.210 = +48.48%** — INVALID | 3 distinct (corrupt) |

- 10-pass digest: ctl **`dbf70497` @ 68.43 tok/s** — the documented pin
  reproduced exactly on the restored venv; sub7 `fa46db81` @ 68.44 (one
  near-tie flip inside 10 passes; logits gate below is the sharp check).
- Logits gate: ctl 0 flips, Δ0.0; sub7 **0 token flips**, max|Δ_top1|
  0.125 (value noise on one step, argmax unchanged); fast8 320/320 (§2).
- ctx1024 KV-stream leg: ctl vs sub7 — digest `ee718419` identical in
  10/10 runs; decode 60.3-60.8 tok/s both arms (paired deltas sub-noise).
- Conclusion: the only faster configuration (+48.5%) is corrupt; every
  bit-exact configuration is inside ±0.2 tok/s of the installed default.

## 4. Install state

**NOTHING INSTALLED — no arm beat the installed build bit-exactly.** The
installed `/usr/local/lib/libvulkan_asahi.so.d3fa18e` (designedusc) is the
bit-exact optimum of this lever and remains the system default. The
uscstudy build (`f6b7909b05666325`, perftest-only mask arm) stays staged at
`t6001-host:/var/tmp/uscstudy/drv/` behind an explicit ICD + env; it is inert
for anything that does not opt in.

State repair retained: `v072-venv-fused` holds release aae4dfc9 (verified
by the `dbf70497`/`bc519c03` pins above).

## 5. Restore

llm-inference.service stopped for 7 windows (profile, flip-probe,
discriminator, stability battery, bisection, substitution, A/B) and
restored by trap after each; final state `active`, `/health`
`{"status":"ok"}`, real completion probe answered after every window
(API-key file auth untouched, no boot writes, no reboots).

## 6. Remaining gap (68.4 vs macOS 179.5)

1. **Barrier wait ~4.9 ms/tok is hardware dependency cost, not waste** —
   the corrupt arms prove the wait protects genuine read-after-write
   coherence (dropping it = stale reads). Bypassing it requires semantics
   changes upstream of the driver: MLX kernels reading activations through
   the L2-coherent storage path instead of textures, or a compute graph
   that exposes independent dispatches — new lanes, not bit tuning.
2. **GEMV family ~34% of kernel time** at the ~160 GB/s dispatch-geometry
   pattern ceiling; reopen path = split-K concurrency at 131k subgroups
   (decode-kernels handoff), needs on-device measurement.
3. **Micro-kernel swarm ~48% of kernel time** — fusion measured neutral on
   T6001 (T6001Decode §5); next lever is chain-aware extension or dispatch
   coalescing, both below the barrier cost just closed.
4. Rare same-backend bf16 near-tie flips (documented here: ~1/12 hot-box
   contract runs, single-point divergence; logits argmax unaffected) —
   explains occasional single-digest outliers in future lanes' batteries;
   the sharp gate is the logits flip count, not the 3-pass digest alone.

## Artifacts

- t6001-host `/var/tmp/uscstudy/`: window{1,1b,3,3c,3d,3r,2f} scripts + logs,
  `out/` (all contract JSONs, logits JSONs), `prof/` (prof-p0.ndjson +
  markers), `drv/` (uscstudy .so f6b7909b + ICD), `phase_kernels.py`,
  `analyze3.py`.
- build-host: `~/src/mesa-uscstudy-out.so` (build output), container
  `dg-uscstudy` (provisioned chroot: meson/LLVM 22.1.8/spirv-llvm-
  translator 22.1.6), `~/src/build-uscstudy2.sh` + `usc-inner.sh`.
- mesa-1 branch `usc-barrier-study` @ 549ddbb8a7d (worktree
  `~/src/mesa-1-uscstudy` on the workstation; origin = joshuaswarren/mesa-1).
- this repo: `.local/uscstudy/` (all scripts), this receipt.
