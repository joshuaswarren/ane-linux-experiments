# 2026-09-22 — Prefill-512 per-kernel profile + top-bucket attack (m1max-host, m1-host)

Lane: PrefillProfileAttack. Baseline wheels: m1max-host `d03a7148` (integ-bisect-a),
m1-host `dc7ca4a0` (integration/qwen38-2026-09-22) — Main confirmed kernel
content identical to main `04bb49acc` for landing. Protocol: per-kernel GPU
profile via `MLX_OMARCHY_GPU_PROFILE` NDJSON + `profile_analyze.py`
(diagnostics wheels built with `scripts/build-wheel.sh --diagnostics` at the
exact baseline/candidate commits), cadence = `qwen38-mlx-bench.py` greedy
10 prompts × 3 passes, warmup 2, prefill leg 512, all under
`/tmp/m1-gpu.lock`. Correctness gate = teacher-forced top-8 logits
(`/tmp/q38c/logits.py`) + ordered-records digest.

## 1. Ranked prefill-512 profiles (BEFORE)

m1max-host (M1 Max, wall 2.12 s/pass, GPU busy 97.7%):

| kernel | n (2 passes) | total ms | share | mean |
|---|---:|---:|---:|---:|
| GatedDeltaPrefillBF16 (prefix pass, gx=16) | 36 | 2134.1 | — | 59.3 ms |
| GatedDeltaPrefillBF16 (output pass, gy=8 chunks) | 36 | 671.5 | — | 18.7 ms |
| **GDN prefill total** | 72 | **2805.6** | **68.6%** | 39.0 ms |
| QmmPrefillCoopmatBF16 | 302 | 1087.7 | 26.6% | 3.60 ms |
| ConvBF16 / ElementwiseBF16 / Copy / RMSNorm / casts | — | ~120 | ~3% | — |

m1-host (M1, stock mesa 26.2.3 asahi, wall 15.54 s/pass, GPU busy 99.5%):

| kernel | total ms | share |
|---|---:|---:|
| **QmmTileBF16 (scalar fallback — no coopmat)** | 26241 | **85.1%** |
| GatedDeltaPrefillBF16 | 3995 | 13.0% |
| everything else | ~580 | ~1.9% |

Host gaps are negligible on both (intra-submission p50 ≈ 30 µs, total ≈ 5% of
wall; one 45–50 ms inter-submission gap per prefill = final logits sync).

## 2. Landed deltas

### 2a. m1-host: fork Vulkan driver (was the #1 bucket, 85.1%)

Stock mesa 26.2.3 asahi has no cooperative-matrix, so the bf16 coopmat
prefill GEMM never dispatches and QMM falls to `QmmTileBF16` (~570 GFLOP/s
class) — this, not the GPU, was the 32.9 tok/s. Main authorized the fork.
`/var/tmp/mesa-e167-m1-host/tip.so` is exactly Honeykrisp
`git-7faf04c065`; installed as the SYSTEM default ICD
(`/usr/share/vulkan/icd.d/asahi_icd.json` →
`/usr/local/lib/libvulkan_asahi.so.7faf04c`; stock config preserved at
`asahi_icd.json.stock-mesa-2623.bak`). No `VK_DRIVER_FILES` needed after
install.

| m1-host | prefill-512 | decode | ttft | digest |
|---|---:|---:|---:|---|
| stock mesa 26.2.3 | 32.91 | 27.6* | 25.1 | `e173e037…` |
| fork 7faf04c, system default | **121.36** | **34.25** | 45.2 | **`ac1b2695…` = m1max-host exactly** |

*decode 27.6 from the gdn-hostfix receipt; 34.25 measured this session.

**`ac1b269553a220ee66d59011decad4740c90f7027ff42deca5b4c4484e2b48f1` is the
m1max-host healthy reference — cross-host identity now HOLDS.** The old
"cross-host divergence is a platform bf16 property" finding is refuted: it was
the driver stack. Worse, teacher-forced logits (top-8/step, 10 prompts × 32
steps) show stock-mesa m1-host vs fork-driver m1-host: **26 argmax flips, max
|Δ top-1 logit| = 10.6** — the stock driver was NOT numerically equivalent,
only coherent. The published M1 cell (32.88) and the correctness README's
platform-property paragraph need re-issue (MlxOmarchyRelease + Qwen38Correctness
notified).

Post-fork m1-host profile: GDN prefill 48.0%, QmmPrefillCoopmatBF16 44.9%
(12.6 ms mean) — the same shape as m1max-host.

### 2b. GDN prefill kernel (top bucket on m1max-host, 68.6%)

Commit `60c4903f` (m1max-host, branch `ppa-gdn-prefill-shader` in
`/var/tmp/ppa-wt`; cherry `2cc30673` on m1-host) — `gated_delta_prefill.comp`
only:

1. Prefix pass computed the `ns*q` output dot it never reads — now skipped
   (state arithmetic untouched).
2. k/q/g were staged through shared memory by thread 0 alone, serially — now
   spread across the workgroup (thread i stages element i).
3. Two barriers per token → one, via double-buffered k/q/g slots (slot reuse
   at t+2 is ordered by the t+1 barrier).

All per-token `precise` rounding is byte-for-byte unchanged, and only unused
values/loading order changed, so outputs are unchanged by construction.

| host | wheel | prefill-512 | digest | teacher-forced vs same-host baseline |
|---|---|---:|---|---|
| m1max-host | d03a7148 baseline | 245.5 | `ac1b2695…` | — |
| m1max-host | 60c4903 candidate | **274.3 (+11.7%)** | `ac1b2695…` IDENTICAL | **0 flips / 320 steps, max Δlogit 0.0** |
| m1-host | dc7ca4a0 sysfork | 121.4 | `ac1b2695…` | — |
| m1-host | 2cc3067 candidate | **128.8 (+6.1%)** | `ac1b2695…` IDENTICAL | bit-identical to m1max-host candidate (0 flips, Δ 0.0) |

m1max-host GDN kernel time 2805.6 → 2333.1 ms (−16.8%); m1-host 4080.6 → 3393.3 ms
(−16.8%). Candidate ranked profile m1max-host: GDN 64.6%, QMM coopmat 30.0%;
m1-host: QMM 48.4%, GDN 43.8%. Decode unaffected (decode leg uses
`gated_delta_decode.comp`; m1max-host decode 53.0 → 52.4 median, within noise).
m1-host decode 30.2 median on the candidate run has stdev 2.3 and the host
rebooted twice mid-session — noise, not a regression mechanism.

Net prefill-512: m1max-host 245.5 → 274.3 (+11.7%); m1-host 32.9 → 128.8 (+291%),
of which +268% driver, +6.1% shader.

## 3. QMM coopmat (remaining top bucket, ~30/48%)

Microbench (`qmm_prefill_bench.py`, m=512, this session): gate/up/qkv
3.33–3.34 TFLOP/s, z/out 2.24–2.49, down 2.91 — at the level the
2026-09-21-bf16-prefill-coopmat receipt already established; tile
occupancy was tuned by 2026-09-14-qmm-occupancy-tilem. No safe further
change landed this lane; next lever would be a bigger MAC tile/STEP_K
redesign (k-chain-order-preserving to keep the digest).

## 4. Notes

- `04bb49acc` does not exist on any host clone reachable from here (fetch
  fails; `origin/main` is `9f75c1eab`); Main directed baseline = installed
  wheels, branch base = origin/main for landing. My commits sit on top of the
  integration tips (`d03a7148` / `dc7ca4a0`); Main should merge the one-file
  shader commit into the main-based integration.
- m1-host system driver change documented above; reboot of m1-host at ~07:59Z was
  done by M2ProxyLive (USB wedge), not this lane.
- The m1-host fork numbers Main/Release should publish are the SYSTEM-default
  run (`baseline-m1-host-sysfork.json`, 121.36) plus candidate (128.84) once the
  shader commit merges.

## Artifacts

- This dir: per-host profile NDJSON (before/after), cadence JSONs, logits
  JSONs, `60c4903f.patch`.
- m1max-host `/var/tmp/ppa/`: analyze outputs, build logs (`build-diag.log`,
  `build-cand.log`), diag wheels in `/var/tmp/ppa-wt/dist`.
- m1-host `/var/tmp/ppa/`: same layout; driver install script
  `/var/tmp/ppa/ppa_install_fork.sh`; worktree `/var/tmp/ppa-wt` branch
  `ppa-gdn-prefill-shader`.
