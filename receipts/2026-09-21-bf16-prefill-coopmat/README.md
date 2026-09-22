# 2026-09-21 — bf16 prefill coopmat (QmmPrefillCoopmatBF16/M16BF16)

Lane: BF16PrefillGemm. Target: the prefill GEMM gap for bf16-activation
Q4 models (pinned mlx-community Qwen3.8-2B-mlx-4Bit snapshots are
bf16-hybrid: bf16 x, bf16 scales/biases, bf16 out).

## Root cause (measured/confirmed in source)

The 8x8x8 fp32 cooperative-matrix prefill kernel (`qmm_coopmat.comp`)
is dtype-agnostic in its math; only the loads/drains were f16-typed.
Two dispatch gates in `primitives.cpp` (`coopmat_reachable` and the
tile-path block) required `out.dtype() == float16`, so bf16 prefill
fell to the scalar 16x16 `QmmTileBF16` baseline (~570 GFLOP/s effective
on the dominant shapes, not the 327 GFLOP/s earlier profile — that
figure was a different/older build).

## Change

Commits (local branch `bf16-prefill-coopmat-925cf`, also carried on
`bf16-decode-gdn` history as 7306a7ca5 and on `bf16-prefill-wheel` as
451764258):

- `8f9215801` qmm prefill: bf16-activation coopmat route
  (QmmPrefillCoopmatBF16/M16BF16). `-DX_BF16/-DOUT_BF16` variants of
  `qmm_coopmat.comp`: bf16 widening of x, RNE bfloat16 drain matching
  the elementwise store; same fp32 coopmat accumulation order as the
  f16 kernels. Same occupancy pick (`coopmat_tile_rows`). With neither
  define set the shader compiles to byte-identical SPIR-V (verified
  with glslangValidator against HEAD).
- `97c012055` qmm prefill: include the bf16 coopmat embedded-spirv
  headers (build fix).
- `823585b91` qmm prefill: bf16 variants read bf16 scales/biases — the
  pinned snapshots store qmm scales and biases in bfloat16; under
  `X_BF16` the scale/bias bindings become `uint16_t` storage widened
  exactly (mirrors shipped `QmmTileBF16` LOAD_VALUE semantics).

Eligibility after the change: bf16 transposed affine 4-bit/group-64
prefill with the fp32 cooperative matrix and subgroup 32 routes to the
new pair; without coopmat capability the shipped `QmmTileBF16` tile
path remains, unchanged.

## Results — M1Max (M1 Max, linux, exclusive GPU window, flock held)

Harness: benchmarks/qwen38-mlx-bench.py, greedy, 3 passes x 10 prompts,
prefill leg 512 tokens. Baseline wheel 0.32.3+5b18306 (deployed bench
venv); candidate wheel 0.32.3.dev202609212355+4517642.

| metric | baseline | candidate | delta |
|---|---|---|---|
| pure prefill-512 tok/s | 52.55 | 72.95 | +38.8% |
| ttft_tok_rate median | 35.71 | 40.47 | +13.3% |
| decode tok/s median | 34.28 | 34.27 | flat |
| token digest | cceba7527e064f49… | cceba7527e064f49… | IDENTICAL |

Token identity: ordered_records_sha256 equal across baseline and
candidate (greedy, 30 records, corpus sha in JSON receipts).

Kernel microbench (native mx.quantized_matmul, bf16 end to end, m=512,
20 reps, mean of 3 warm reps; `qmm_prefill_bench.py`):

| shape | baseline GFLOP/s | candidate GFLOP/s | speedup |
|---|---|---|---|
| gate/up/qkv 6144x2048 | 578.6–581.4 | 3338.2–3357.6 | 5.8x |
| z/out 2048x2048 | 552.4–552.7 | 2497.5–2509.0 | 4.5x |
| down 2048x6144 | 568.3 | 2909.7 | 5.1x |

Per-layer QMM serial time at m=512: 105.9 ms -> ~19.7 ms.

Target ">2 TFLOPS effective on M1 Max": met (3.36 TFLOP/s dominant
shape).

## Post-change attribution

Per-layer QMM (~19.7 ms x 24 layers ~ 0.47 s) is now ~7% of the 7.0 s
prefill-512 wall on the 2B. The remaining gap is non-GEMM: the GDN
(gated delta) prefill path is an f32 elementwise chain on this backend
(mlx-lm on Metal uses a fused chunked kernel), plus dequant/cast
chains. Follow-up lane: chunked GDN prefill scan kernel (BF16Decode
Kernels owns the decode recurrence; this lane owns the chunked prefill
scan — see handoff message in session log).

## Cast-to-f16-boundary variant

Skipped per Main (2026-09-21): the native bf16 coopmat route avoids the
extra cast dispatches entirely and already exceeds target; the cast
boundary would add two elementwise passes per call plus a permanent
f16 weight copy.

## Artifacts

- receipts/2026-09-21-bf16-prefill-coopmat/{baseline,candidate}.json —
  M1Max model bench receipts (full metadata + per-record tokens)
- receipts/2026-09-21-bf16-prefill-coopmat/{baseline,candidate}-qmm.txt
  — kernel microbench outputs
- receipts/2026-09-21-bf16-prefill-coopmat/qmm_prefill_bench.py,
  run_M1Max_window.sh, cast_boundary_bench.py
- M1Max: /var/tmp/bf16-prefill-wt (worktree at 451764258), candidate
  venv /var/tmp/bf16-prefill-venv

## gpu-base-host leg

Candidate wheel staged, measurement window queued in the gpu-base-host GPU
flock behind BF16DecodeKernels' GDN window (window script blocks on
the lock and runs unattended). Numbers appended below when the window
completes.

Raw model-bench JSON receipts (per-record tokens, model paths, host
metadata) contain private-infrastructure identifiers and live only in
the local `private/` subdirectory of this receipt (gitignored by the
privacy guard); the tables above are the durable record.

## Follow-up item: chunked GDN prefill scan (GatedDeltaPrefillBF16)

Commit cdb546c81/86c298621 (branch bf16-prefill-coopmat-925cf):
`gated_delta_prefill.comp` + enum/table/dispatch. One workgroup per
(b=0, v-head), one thread per Dv row, state cloned h0->hf and updated
in place (same [B,Hv,Dv,Dk] f32 layout as the decode kernel), per-token
math matches the fast.cpp fallback promoted to f32, scalar or per-Dk
decay via push-constant flag. Eligibility = decode gate extended to
T>1 (mask still falls back).

Measurements (M1Max host, T=512, H=16, Dk=Dv=128, B=1, direct
mx.fast.gated_delta_update call):

| leg | ms |
|---|---|
| composed fallback (baseline wheel 5b18306) | 446.4 |
| fused prefill scan (candidate wheel 86c2986) | 41.6 (10.7x) |

Output max abs diff vs f32 fallback: 1.4e-4 (bf16 store rounding).
Mask-free greedy model bench on the candidate wheel: digest
cceba7527e064f49... IDENTICAL to baseline; prefill 73.0 tok/s (flat,
see below).

## Why end-to-end prefill did not move, and the blocker

mlx-lm (0.31.3) `gated_delta.py` only reaches `mx.fast.
gated_delta_update` when `mx.metal.is_available()`; on Linux every
call - prefill AND decode - goes to the pure-mlx `gated_delta_ops`.
The backend primitive is dead code for the model today.

A venv-level routing patch (call the primitive on Linux, ops as
escape hatch) was measured and REJECTED: prefill regressed to
57.8 tok/s and the greedy digest flipped (5e093035... vs reference
cceba7527e064f49...) because the model's prefill passes an SSM mask,
which routes to the primitive's composed masked fallback whose
numerics differ from `gated_delta_ops`. Patch reverted; the shipped
candidate remains digest-identical.

Path to realize the 10.7x: (a) teach GatedDeltaUpdate to accept the
SSM mask (all-true mask = maskless fast path; per-token mask in the
scan kernel is one extra load), and (b) land the mlx-lm one-line
Linux routing. Both are follow-up work; contract with BF16Decode
Kernels (state layout, decay-before-kv-dot) is agreed in-session.
