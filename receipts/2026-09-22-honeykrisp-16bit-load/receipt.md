# 2026-09-22: Honeykrisp 16-bit storage buffer loads (Q4 xpack blocker)

Lane: Honeykrisp16bitLoad. Question: do 32-bit loads (uvec4/uint) from a
buffer holding 16-bit (bf16) storage return wrong data on the local
honeykrisp-omarchy Mesa tip, blocking the +37% Q4 decode GEMV xpack win?
Host/path details: `private/hosts.md` (untracked).

## VERDICT: NOT a driver bug. Two real defects found, both in the xpack lane's own code.

### 1. Driver exonerated — standalone minimal repro, both driver arms

Minimal standalone compute shader (`lo16_scalar.comp`, `lo16_vec.comp` +
`runner16.cpp`; 16-bit-storage feature enabled; the same VkBuffer bound to a
`uint16_t[]` view and a `uvec4[]`/uint view), 64/128 KiB known pattern, 3
rounds per arm. Zero bit mismatches on every arm of the matrix:

| driver arm | scalar-16 view | uvec4 view |
| --- | --- | --- |
| honeykrisp tip (7faf04c065c build) | 0 / 32768 wrong | 0 / 32768 wrong |
| upstream correctness base (728fe700bc0) | 0 / 32768 wrong | 0 / 32768 wrong |

Artifacts: `lo16/` scratch dirs on both hosts (shader, runner source, spvs,
pattern input, output dumps, run script). Reproduced identically on both M1
hosts' toolchains; the both-driver matrix ran on the M1 Max.

In-situ proof: instrumented the real q4-bw-bench xpack shader to XOR the
uvec4-loaded x words against scalar-16 loads of the same elements — dbg == 0
for every output element on the tip driver. The 32-bit loads return
bit-identical data inside the production-shaped kernel.

`q4-bw-bench --bf16eq` bit_mismatches are identical on tip and upbase
(896/896, 128/128, ...) — no driver dependence.

### 2. Defect A (confirmed, in the bench): `--bf16eq` is an invalid instrument for bf16

`bench.cpp` compiles the base arm with `-DUSE_BF16=1 ...`, but
`qmm_vec_base.comp` gates the native Q4_WORD path on
`#if defined(USE_FP16) && defined(QMM_VEC_Q4_WORD)`. Under bf16 the base
therefore runs the old generic scalar path while xpack runs the Q4_WORD path —
different accumulation/rounding structure, so 100% bit "mismatch" is expected
even with perfect loads. f16 passed only because both sides ran Q4_WORD there.
With the base and unroll gates opened to `(USE_FP16 || USE_BF16)`, the
scalar-load unroll twin is bit-exact vs base (0 mismatches) and the instrument
becomes meaningful.

### 3. Defect B (production, root cause NOT yet found): the lost branch's bf16 q4_word kernel computes garbage

The branch `agent/q4-gemv-bandwidth` (tip 1b72eb4d3) is lost — absent from
both hosts' clones and the remote. Its wheel and source tree survive in the
Q4GemvBw lane scratch dirs (see private/hosts.md).

Repro: bf16 quantized_matmul, K=64 N=8, vs exact float64 dequant reference →
rel err ~200x; the f16 kernel on the identical path is correct (rounding
level). Disabling the q4-word route restores correct output. Driver-independent
(same garbage on tip and upstream base on the M1 Max).

In-shader instrumentation (incremental rebuilds of the lane's build tree)
proved the shader reads the correct weight word, scale, bias, and x bits (diag
dump through the output buffer matched host expectations exactly), and
replacing the uvec4 x load with scalar 16-bit loads changes nothing
(bit-identical wrong output). Basis-vector probes produce quantized junk
(0, ±2) instead of scale*nibble. The corruption is in the bf16-specific
arithmetic/epilogue of the non-MULTI compile — exact line NOT identified. The
bench MULTI+SUBGROUP compile of the same source is numerically correct (~2e-3
vs float64 reference), confining the defect to the production non-MULTI bf16
compile. This explains the lane's model tokid failure (degenerate 760 12 12
12 stream).

The committed bf16 unpack also takes the HIGH half first (`x0 = lo >> 16u`)
while its own comment and the f16 `unpackFloat2x16(lo).x` mapping say
low-half-first — fixed to low-first in test copies, but masked by Defect B
(it cannot be validated until B is found).

## Unblock path for the +37% win

1. Reconstruct the branch (production diff recoverable: qmm_vec.comp 3 hunks +
   primitives.cpp `packed_q4_x` bf16 gate), then root-cause Defect B by
   bisection inside the bf16 non-multi q4_word path; the instrumentation loop
   (edit shader → make → swap libmlx.so → probe) is set up and costs ~10 s per
   iteration.
2. Land Defect A's gate fix plus the low-half-first unpack with it.
3. Re-run the tokid identity gate, then decode tok/s cadence on both hosts.

## Housekeeping

- M1 Max worktree: bench.cpp restored clean vs HEAD; qmm_vec_base.comp
  retains the pre-existing uncommitted SwiGLU-fold work of the GDN lane (my
  intermediate copies are in the local stash `lo16 lane temp edits`);
  xpack shader candidates restored to their pre-lane saved state.
- M1 Max llama-server: stopped for GPU work, restored degraded, health ok.
- M1 host: lane scratch venvs/probes only; other venvs untouched; no
  llama-server there. No other machines were touched.
