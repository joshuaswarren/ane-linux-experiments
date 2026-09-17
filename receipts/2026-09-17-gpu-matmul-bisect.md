# FINDING: the "2.8x GPU matmul regression" is a mislabeled island-round cost — the mechanism is the ConvF32 kernel-selection fix `e55c1fae`; no published wheel ships the slow path (2026-09-17, GpuMatmulBisect)

## Verdict in three lines

1. The per-statement "matmul" walls (90→260 ms, +3.9 s/pass) are NOT
   matmul compute: the matmul at the anchor shape runs in 0.6-0.8 ms bare.
   They are island-round walls whose marshal stage forces `mx.eval` of the
   pending GPU span — the 24-layer fp32 pointwise-conv stack executed on
   the generic Conv kernel instead of the MatmulF32 GEMM.
2. The flip is `e55c1fae` (Sep 14 15:32, "omarchy: unit-window 1x1 ConvF32
   dispatches ordered MatmulF32"): the only code delta (+51 lines,
   `primitives.cpp`) between the measured-SLOW tree `af91f3d6` (3 354.5 ms)
   and trees measuring FAST (903.5 ms, byte-identical libmlx `ada4cf29`).
3. **No published wheel ships the slow path.** All five shipped wheels
   (v0.6.1/3/4/5/6) measure FAST class on the same classifier. The slow
   build exists only as the Sep 14 dev build `05015a76` in both hosts'
   shared venv-cache.

## 1. The mislabel (measurement mechanics)

- MIL statement 347 = `attention_scores_7_cast_fp16`, shape (1,8,375,749),
  ~0.3 GFLOP — an island-A member. Its per-statement wall is the island
  round: marshal (mx.eval of the pending GPU span + readback) + worker
  round + back.
- Bare microbenchmark, runner semantics (f16 in → f32 cast → transpose →
  f32 matmul → f16 cast), SLOW build: **0.605-0.805 ms median**. The
  matmul kernel is not the cost.
- Instrumented split (resident ABC, 2 passes, main-tip runner): marshal
  fast 2 741 ms vs slow 13 158 ms; inside marshal, GPU-span `mx.eval`
  2 517 vs 13 035 ms and readback 207 vs 110 ms. Island-A median span
  eval 35.0 ms (fast) vs 224.2 ms (slow).
- GPU-side counters are IDENTICAL across arms: 5 719
  gpu_primitive_dispatches, 16 vk_submissions, 3 269 vk_compute_dispatches,
  101 fills; enqueue-side op-wall sums equal (232 vs 233 ms). ANE exec is
  not inflated on the slow build (2 419→1 721 ms resident) — matches the
  original receipt.

## 2. Bisect result

Topology: the slow wheel `05015a76` (Sep 14 11:25) and fast reference
`044f297f` (Sep 17 04:30) diverged at `b79a4b68` (Sep 14 11:12); the slow
line carries exactly one unique commit (the custom-kernel SPIR-V disk
cache — first-call compile cost only). The fix is on the fast line.

Inverted-label bisect (good=slow `deb9c72b`, bad=fast `044f297f`; "bad"
= fast), jw16, per-step incremental builds of libmlx from source with
sha256-asserted identity and the `--no-ane` 2-pass classifier:

| step | commit | tree note | warm pass wall | class |
|---|---|---|---:|---|
| 0 | 044f297f | fast tip | 931.1 ms | fast |
| m | 0a1a1f9f | | 889.8 ms | fast |
| m | a5a44906 | | 903.5 ms | fast |
| m | c90e82a9 | receipts-only, libmlx byte-identical to a5a44906 (`ada4cf29`) | not re-run | fast |
| m | af91f3d6 | | 3 354.5 ms | **slow** |
| m | 4188ba95 | libmlx byte-identical to a5a44906 | not re-run | fast |
| flip | **e55c1fae** | **unit-window 1x1 ConvF32 → ordered MatmulF32 (+51, primitives.cpp)** | **libmlx byte-identical `ada4cf29` → FAST class** | **fix** |

Bracket proof: `git diff af91f3d6 e55c1fae -- overlay/ patches/` =
`overlay/mlx/backend/omarchy/primitives.cpp | 51 ++++++` and nothing else.
`ada4cf29` was measured FAST (903.5 ms); `c272f718` (= af91f3d6, the same
tree minus the conv change) measured SLOW (3 354.5 ms). Digests
`e832110d…` (--no-ane) and `38c73261…` (ABC runs) held on every pass of
every arm; libmlx sha256 identity asserted per run.

Mechanism, named: **kernel selection, not tiling/occupancy.** Before
`e55c1fae`, `Convolution::eval_gpu` dispatched the encoder's unit-window
(stride-1, dilation-1, 1x1) f32 pointwise convs to the generic Conv
kernel; after it, they dispatch as ordered MatmulF32 GEMM via
`select_float_kernel(MatmulF32, MatmulF16, MatmulBF16)`. The repo's own
receipt of the era (`3cd2e93f`: "encoder GPU leftover owner is ConvF32
(1,2048,375)×24 = 4.15 s") prices the slow path at ~173 ms/layer — the
exact per-layer delta of the original observation. The MIL convs are
fp16, but the runner evaluates convs in fp32 (cast-up, same datapath as
its f32 matmul statements), so the slow generic-conv path is f32.

Not the mechanism (checked and excluded): qmm occupancy tile `45b71465`
(encoder has no quantized ops), the custom-kernel SPIR-V disk cache
`05015a76` (first-call cost only; the fast line carries the same change),
`cached_translation` `deb9c72b` (measured SLOW at 3 295.8 ms — translation
caching is real but is not this flip), decode-side qmm_vec/fast_trio
(only SPIR-V blobs that differ; not in the encoder path), ANE
worker/bundle changes (constant worker binary in the A/B; --no-ane
reproduces the full delta with zero ANE involvement).

## 3. Shipped-wheel verdicts (from the shipped binaries, not git)

Classifier: encoder runner `--no-ane`, 2 passes, warm pass-2 wall; fast ≈
0.9 s, slow (05015a76) ≈ 3.3-3.4 s; hidden digest `e832110d…` held every
pass; loaded-libmlx sha256 asserted per run. Wheels are the GitHub
release assets, extracted in full.

| release | tag commit | shipped libmlx sha256 | warm wall | verdict |
|---|---|---|---:|---|
| v0.6.1 | b8e5300 | `9a72c3b84c74e7b3…` | 908.4 ms | **FAST** |
| v0.6.3 | 1ed1dab6 | `a10cebf540565ccf…` | 869.5 ms | **FAST** |
| v0.6.4 | 112c32c4 | `224a9597cf938424…` | 917.3 ms | **FAST** |
| v0.6.5 | 7b05e936 | `1a9a9206bcee4f21…` | 913.0 ms | **FAST** |
| v0.6.6 | 2f58ead9 | `06e43c203e85a16a…` | 908.4 ms | **FAST** |

**No published wheel ships the slow path — no shipping defect.** The
published GPU parity tables were measured on these same wheels in
dedicated venvs, so users get exactly the published numbers. Corroborating
history (not the evidence): all of v0.6.1-v0.6.6 contains the fast-line
GPU commits; none contains `16835c0f`/`0986add5` (hardware SHA-256 bundle
verify — a separate later landing, absent from every published wheel).
Reference binaries: slow `05015a76` wheel libmlx `65a641e4…`; landed
16835c0f lib `b2de6602…`.

## 4. Published-numbers audit (Sep 14-17)

- jwm1 GPU parity refresh (117.34 / 105.68 tok/s = 77.93% / 75.28%):
  measured ON the v0.6.3 release asset (`dcb84f7b…` wheel) in
  `/var/tmp/V063REL-venv`, provenance verified=match. Clean.
- jw16 GPU parity refresh (190.63 / 130.70 tok/s = 66.43% / 46.06%):
  measured ON the v0.6.1 wheel (`b8e5300`, libmlx `9a72c3b8` matches this
  audit's extraction) in a dedicated venv. Clean.
- 2026-09-16-parakeet-e2e-both-hosts: own E2EREV/site wheels (f43ab71),
  provenance verified. Clean. 2026-09-16-parakeet-100-run: own
  V051E2E/site (v0.5.1 wheel). Clean.
- **Contaminated**: any run resolving libmlx through the shared fallback
  cache between Sep 14 12:06 and now. Both hosts carry the slow build:
  `/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages/mlx/lib/libmlx.so`
  (sha256 `65a641e4a9e6973734a6f25f810e62c7d9e60c4a4a0e44e4490fd9518a25f2e4`,
  wheel `mlx_omarchy-0.32.2.dev202609141626+05015a76`) on jw16 AND jwm1
  (identical bytes and mtime Sep 14 12:06). Confirmed casualty: the 12:02
  jw16 out-cx-* table (superseded in 2026-09-17-libmlx-identity-shadowing.md).
  No other published Sep 14-17 number was found resolving through the cache.
- **Action (not executed by this lane — owner call)**: remove or refresh
  the `05015a76` wheel in BOTH hosts' venv-cache paths above, and set
  `MLX_OMARCHY_EXPECTED_LIBMLX_SHA256` in every harness whose
  `PYTHONPATH` can fall through to them.

## Provenance and hygiene

- Hosts: jw16 (`jw16mbp1-linux`, M1 Max T6001, Honeykrisp) for all
  measurements; lock `/tmp/m1-gpu.lock` inode 12, flock-held, never
  stolen/unlinked; every window announced TAKE/RELEASE with service
  restore + CONFIRM ACTIVE (`is-active=active`, holder = the service's
  llama-server flock PID). jwm1 only touched read-only (venv-cache sha256).
- Identifiers: transcript pin `db501a8c…`, ABC hidden `38c73261…`,
  no-ANE hidden `e832110d…`, `cpu_tensor_events=0`, 104/104 emissions on
  the full-E2E runs; `63c1d3cf` is not an ancestor of any pushed mlx-omarchy
  ref (no mlx-omarchy code was changed by this lane).
- jw16 host-hygiene note for the record: the 13:40 stray llama-server was
  a post-restore detach (V066Release's unit restart recorded active at
  13:40:19; FfnChainFusion's 13:51-13:52 stop/restart window left the
  cgroup detached; unit showed "not loaded" at ~14:00). Not a failed
  hand-back. Restored via `sudo systemctl stop llm-inference.service`;
  the queued lanes restored + confirmed ACTIVE afterward.
- Bisect build pipeline: `prepare-mlx.sh` + checksum-rsync into a
  persistent tree + ninja incremental build with `-DBUILD_SHARED_LIBS=ON`
  (the wheel's libmlx.so/core split needs it), per-commit omarchy-ane pin
  (`f261a6cb` old / `6fa243a` new) checked out from `~/src/omarchy-ane`.
  Artifacts and logs under `/var/tmp/gmb16/` on jw16.
