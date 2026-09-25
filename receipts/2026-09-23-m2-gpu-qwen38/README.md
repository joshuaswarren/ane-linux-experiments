# 2026-09-23 — M2 Max (T6021) Qwen3.8-2B GPU contract cell on Linux (m2-host)

Lane: M2Gpu. Fills the GPU-inference matrix cell for the M2 Max under Omarchy/Asahi
Linux, with the M1-laptop qualified stack and byte-level parity against the M1
contract cells. **Verdict: QUALIFIED — logits byte-exact vs the T6001 reference
(0 flips / 0.0 max |Δtop1| over 320 steps), contract records digest identical to
the cross-host pin, and T6021 is 1.14× T6001 on paired decode.**

## 1. Inventory (read-only, pre-install)

- Host: `m2-host` — "Apple MacBook Pro (14-inch, M2 Max, 2023)", kernel
  `7.1.13-3-1-ARCH` (linux-asahi 7.1.13.asahi3-1), Python 3.14.7, openblas
  0.3.34-1 already present (no pacman changes needed).
- Stock graphics stack: mesa 1:26.2.3-1 + vulkan-asahi 1:26.2.3-1. vulkaninfo
  device `Apple M2 Max (G14C B1)`, driver `Honeykrisp` — but **stock 26.2.3
  exposes NO VK_KHR_cooperative_matrix on the Apple GPU** (the single
  `vulkaninfo | grep -c` hit is llvmpipe, which always exposes it — a per-device
  JSON/awk check is required; the text summary greps lie).
- Pre-existing state: `/var/tmp/venv-q38-m2` — a stale hand-staged dev venv
  (`0.32.3.dev202609221154+dc7ca4a0`) from an earlier lane. **Not used**; this
  cell installs through the packaging path instead. HF cache already held the
  pinned model snapshot (paths identical to m1-host/t6001-host:
  `~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/0867d98b…/`,
  safetensors sha256 `b0d5de68…` — verified on-box).

## 2. Qualified stack (installed via the packaging path, nothing hand-patched)

| artifact | identity |
| --- | --- |
| mlx-omarchy wheel | `0.32.3.dev202609230705+aae4dfc9` cp314 aarch64, sha256 `7db9914feeacf9c34da1a91496f7a545bfb4e7fe1ee7f6d4fe696071cbb7ecf2` (the T6001 gdncoop lane owner-designated qualified bit-stream from `t6001-host:/var/tmp/gdncoop/wheels/`) |
| venv | `~/.local/share/mlx-omarchy/venv` (installer layout), mlx-lm 0.31.3 (`--no-deps`), transformers 5.16.1, numpy/protobuf/pyyaml/jinja2/huggingface_hub |
| mlx-lm patches | `apply-mlx-lm-patches.sh` @ aae4dfc9 (GDN fast route ON, conv-ring OFF) + in-repo `scripts/patch-mlx-lm-gdn-raw.py` @ a12b1aa1 (sha `5c4c9be3…`, the canonical raw-route script per the T6001 gdncoop lane owner). Post-state verified byte-matching the qualified `venv-rel`: `gated_delta_update_raw` count 2, `q.shape[1] == 1` branch at line 284, metal gate gone from the use_kernel line. NO greedy-prune (matches the qualified-cell era; venv-rel grep clean). |
| driver | Honeykrisp fork tip `git-7faf04c065` (`joshuaswarren/mesa-1` `honeykrisp-omarchy`), `.so` sha256 `09e3527dee4a365ee29085637c266291396666afb0039a6932b5be9dc7dd6a80` — **byte-identical to m1-host's system `libvulkan_asahi.so.7faf04c`** that ran the v0.7.2 qualified battery. Staged at `/var/tmp/mesa-fork-m2/` + icd.json, selected per-run via `VK_DRIVER_FILES` (no system ICD mutation on this box). vulkaninfo under the fork: `Apple M2 Max (G14C B1)`, `Mesa 26.3.0-devel (git-7faf04c065)`, **VK_KHR_cooperative_matrix revision 2**. |

Notes for the packaging lane: release v0.7.2 (fa103c86) predates GDN coopmat
dispatch and would not have been comparable to the M1 contract cells (the T6001 gdncoop lane owner).
The raw route is now packaged default-on in `6017b8469` (agent/batch-flush-rootcause,
`patches/mlx-lm-gated-delta-raw.patch` after the fast-route patch); that branch
was not on the remote when this cell installed, so the in-repo script was used —
same inserted branch, verified verbatim by the T6001 gdncoop lane owner against v072.

## 3. Contract run (protocol = benchmarks/qwen38-2b-contract.json)

3 warmups × 10 passes × 10 prompts, 32 new tokens, greedy, pure-prefill 512 leg.
Correctness first, and the logits gate used the SAME tool as the qualified lane
(`logits_gl.py`, teacher-forced top-8, sha `064adf0f…`) compared against the
T6001 reference capture (`logits-coop.json`, sha `d8f96153…`, from
`t6001-host:/var/tmp/gdncoop/`).

**Correctness: PASS (byte-exact class).**

- Logits gate vs T6001: `steps=320 flips=0 max|d_top1|=0.0000` — every top-1
  token matches, zero logit delta. Contract thresholds (top1 all 32 tokens every
  prompt; max |Δlogit| ≤ 0.25; mean ≤ 0.02; rel-L2 ≤ 0.01; top10 overlap ≥ 0.9)
  all satisfied with margin: the two hosts are numerically IDENTICAL on this
  stack, not merely within threshold.
- Records digest: `dbf704971617fdfcf693c4287b9f0403ee24a2b2c5d3a9fb4d2a032d613c9596`
  — **identical to the T6001 gdncoop contract cell AND the m1-host denominator
  run** (cross-silicon byte identity: T6021 = T6001 = T8103 on the pinned stack).
- Determinism: second full 10×10 pass reproduced the digest exactly (both runs
  in raw/, shas `8267968c…` / `984e49c8…`).

**Performance (n=100 records, bootstrap 95% CI, 10k resamples, seed 0):**

| metric | T6021 (this cell) | T6001 ref (gdncoop cell) | paired ratio M2/T6001 |
| --- | --- | --- | --- |
| decode tok/s (median) | **72.58** [72.55, 72.62] | 63.63 | **1.141×** [1.139, 1.143] |
| ttft tok rate (median) | 85.59 [81.99, 87.58] | 74.0 median | — |
| end-to-end tok/s (median) | 75.98 [75.20, 76.38] | — | 1.153× [1.143, 1.159] |
| pure prefill-512 tok/s | **906.84** (wall 0.5646 s) | 843.83 (wall 0.6068 s) | 1.075× |

- Peak RSS 553,488 KB (~540 MB). Thermal 27.6 °C at run end (cool box; thermal
  zones in raw/env.txt). Power: Asahi Linux exposes no GPU power rail
  (no powermetrics equivalent; the drm `gpu_busy_percent` node is absent on this
  kernel — the bench's busy sampler recorded no samples). GPU execution is
  proven by device/driver identity + `[rtmod] SUBMIT` traces in the logs, not by
  a busy% counter.
- Artifact identity: wheel `7db9914f…`, driver `.so` `09e3527d…`, model
  safetensors `b0d5de68…` @ `0867d98b`, corpus `9299a3b2…` (verified on-box
  pre-run), logits ref `d8f96153…`. Raw: `raw/` (contract-m2.json,
  contract-m2-r2.json, logits-m2.json, logits-verdict-m2.txt, env.txt,
  summary-m2.txt, ci-compare.json, logs, SHA256SUMS).

## 4. Decode-step profile on T6021 (diag wheel `diag.aae4dfc9`, sha `df19ba7f…`)

Instrument: receipt 934cae7 stack — `prof_decode.py` + `MLX_OMARCHY_GPU_PROFILE`
NDJSON + `profile_analyze.py` + `phase_kernels.py` (per-kernel enum names from
compute.h @ aae4dfc9). Patched route active in the profile venv (fast + raw);
all output file-redirected. Raw: `raw/profile/` (prof-m2.ndjson 5.3 MB,
markers.jsonl, analyze.txt, phases.txt, prof.log).

Whole capture: 20,429 dispatches / 104 submissions, GPU busy 70.0%. Decode
window: **604.5 dispatches/token, 3.1 submissions/token** (t6001 934cae7: 580
and 3.1 — same shape). 7.47 ms/tok profiled (diag wheel ≈1.74× release plus
instrumentation: shares below, absolutes not comparable — release decode is
72.58 tok/s).

**Top costs per decode token (share of decode-window GPU time):**

| rank | kernel family | n/tok | ms/tok | share |
| --- | --- | ---: | ---: | ---: |
| 1 | QmmVecQ4 GEMV xpack (MultiSubgroup 23.8% + WordSubgroup 8.5%) | 38.3 | 2.415 | **32.3%** |
| 2 | Norm/elementwise/copy/cast swarm (FastRmsNorm 13.0, Elementwise 7.0, CopyGeneral 6.8, Casts 7.0, Swiglu 2.0) | ~107 | ~2.5 | **~33%** |
| 3 | GDN core (GatedDeltaDecodeBF16) | 6.0 | 0.577 | **7.7%** |

- The GEMV family is weight-streaming at batch-1; on M1 Max the same family was
  measured AT its dispatch-geometry ceiling (2026-09-22-decode-m1max-occupancy:
  160 GB/s in-model; remaining lever = a honeykrisp occupancy-policy feature,
  not kernel tweaks). The WordSubgroup variant runs ~2× the MultiSubgroup mean
  (100.7 vs 55.5 µs) on its 6.3 dispatches/token — the one visible inefficiency
  inside the family.
- The norm/elementwise swarm is 107+ small memory-bound dispatches/token
  (means 19–36 µs) — dispatch/launch overhead dominates per-kernel work; the
  rtmod hot-path print gate and fusion work (gdn-fuse lane) target exactly this.
- GDN core is small (7.7%); inter-submission gaps (3.1 submits/token, p50
  311.6 µs) account for ~80.5 ms of the 933.5 ms profiled decode (~8.6%).
- Barrier discipline clean: 0/20,429 dispatch barriers skipped.

Structure matches the T6001 raw-route profile (GEMV ~34%, swarm ~39%, GDN
7.5%) — T6021 inherits the same lever list: occupancy policy for GEMV,
dispatch-count reduction for the swarm; nothing GDN-specific.

## 5. Addendum (same day): driver installed as system default — cell re-verified

Main's acceptance condition: the VK_DRIVER_FILES staging was not the normal
install. The canonical m1-host install (no package exists; verified on-box) is
the system ICD swap: the fork `.so` at
`/usr/local/lib/libvulkan_asahi.so.7faf04c` with
`/usr/share/vulkan/icd.d/asahi_icd.json` pointing at it (api_version 1.4.359)
and stock mesa parked as `asahi_icd.json.stock-mesa-2623.bak`. Replicated
exactly on m2-host:

- `/usr/local/lib/libvulkan_asahi.so.7faf04c` sha256 `09e3527d…` (the qualified
  bit-stream, unchanged from the staged copy), stock ICD parked as `.bak`,
  `asahi_icd.json` rewritten identically to m1-host's.
- Plain environment (VK_DRIVER_FILES unset) vulkaninfo: GPU0 `Apple M2 Max
  (G14C B1)` / Honeykrisp / `Mesa 26.3.0-devel (git-7faf04c065)`,
  VK_KHR_cooperative_matrix rev 2.

Re-verification through the normal environment (`raw/sysinstall-artifacts/`):

- Logits gate vs the T6001 reference: `steps=320 flips=0 max|d_top1|=0.0000` —
  byte-exact again.
- One decode rep (warmup 3 × 1 pass × 10 prompts): decode median 72.22 tok/s,
  ttft 85.91, prefill-512 948.04 tok/s. The 1-pass records digest
  (`486872c4…`) differs from the 10-pass pin (`dbf70497…`) only because
  `ordered_records_hash` canonically includes the pass index — a 1-pass run
  hashes a 10-record set, not a 100-record one. Token-level check: pass-0
  `output_ids` are IDENTICAL to the accepted 10-pass run for all 10 prompts
  (0 mismatches). The cell stands as accepted.

## 6. M2 macOS denominator (handed to Main)

Spec sent to Main 2026-09-23: reuse `mac-reference-bundle-full.tar.gz`
(sha256 `82c1a70198fd…`, the same bundle as the M1 denominators), leg
`run-qwen-gpu.sh` (upstream mlx 0.32.2 Metal, pinned model/corpus, 3 warmups ×
10 passes, peak RSS, ordered_records_sha256), run under `caffeinate -dimsu`
with python ≥ 3.10 (CLT 3.9 insufficient). Comparators: M1 macOS 47.05 tok/s
decode / 343.73 prefill; M1 Max macOS 179.47 decode. The macOS records sha is a
within-OS determinism pin only — Metal vs Vulkan round differently (established
m1-mac-denominator). Main owns the reboot scheduling; this lane does not boot
the M2 into macOS.
