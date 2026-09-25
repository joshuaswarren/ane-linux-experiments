# 2026-09-22: QmmVecQ4* decode GEMV dequant levers — dual-row lands kernel-side, model identity gate FAILS, production flip disabled

Lane: DecodeQmmDequant. Base: `integration/qwen38-2026-09-22` @ dc7ca4a05
(= production decode base with xpack + kv-direct). Branch (local, never
pushed): mlx-omarchy `agent/decode-qmm-dequant` — tip **cbac299f8**.

## 1. AGX instruction mix (per output column, static packed-asm histogram)

Dump: `/tmp/q4-bw-bench-dq --bf16eq` under `AGX_MESA_DEBUG=shaders
MESA_SHADER_CACHE_DISABLE=true` on m1-host (stock-fork honeykrisp ppa
driver), all five MULTI+SUBGROUP+BF16 pipelines in one run; sections
identified by compile order + SPIR-V blob hashes
(`/var/tmp/qmm-dequant/out/benchdump.txt`, parser inline in transcript).

| kernel arm | total asm | fma-class | int ALU | load | store | flow | per column |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| base (pre-xpack, scalar x) | 1050 | 89 | 280 | 127 | 6 | 90 | 131.3 |
| xpack = PRODUCTION | 1428 | 144 | 386 | 186 | 6 | 119 | 178.5 |
| xpack2 (uint-word x) | 948 | 84 | 248 | 120 | 6 | 83 | 118.5 |
| wg128 (4 col/wg) | 1418 | 152 | 343 | 84 | 7 | 93 | 354.5 |
| dual (candidate) | 2866 | 320 | 696 | 148 | 19 | 169 | 179.1 |

Takeaways: (a) the x-side that dual-row shares (one uvec4 load + 8
shift/mask unpacks + quad sums per word) is only ~3% of the instruction
stream — dual saves ~4.5 instr/column of ~179, which is exactly the
measured kernel win. The family is dominated by nibble fma, address
ALU, and the per-word scale/bias loads; dequant-in-GEMM ALU is the
ceiling, not x traffic. (b) Zero barriers in any subgroup variant
(lever (c) already landed; confirmed in dump). (c) Lever (d) merge
QKV/gate-up already landed (QMM_VEC_MULTI + swiglu fold bit 16;
dispatch receipts 0640385/225eb23). (d) Lever (a) pre-permuted nibbles
would not remove ops: the unpack is already shift+and with no scatter.

## 2. Lever (b): dual-row mapping (two weight rows per lane)

Each 32-lane slot owns columns c and c+8, walking both weight rows in
lockstep so every x uvec4 load, bf16 quad unpack, and quad sum is paid
once for two output columns. Per-row arithmetic order untouched —
bit-identical per column (fma chain, input_sum chain, block finish
fma). Fold (swiglu) path and non-subgroup kernels keep the single-row
8-column mapping; host group count switches 8→16 columns only for the
subgroup multi kernels on 16-bit x dtypes.

Two bugs found and fixed on the way (both caught by the `--bf16eq`
shader-level bit-exactness gate on hardware, m1-host):
1. B-row dot accumulated against the A-row word (`wB` unused in
   `Q4_QUAD_DUAL`) — ~50% of columns wrong, exactly the B columns.
2. Dual workgroup/weight partition used the 8-column span while the
   host dispatched 16-column groups — zero rows and cross-weight
   stores. Fixed with a dual-span partition (`dg0/dg1`) inside the
   kernel.

## 3. Kernel bandwidth (m1-host, `--gap --2b`, bf16, 34,285,568 B/layer, pass-2 medians, both passes run)

| arm | iso4 | widedep (24-set stream) |
| --- | ---: | ---: |
| base | 956.9 us = 35.8 GB/s | 951.8 us = 36.0 GB/s |
| xpack (production) | 669.7 us = 51.2 GB/s | 668.9 us = 51.3 GB/s |
| **dual** | **653.5 us = 52.5 GB/s** | **651.6 us = 52.6 GB/s** |

Dual vs production: **+2.8%** (iso4 +2.5%), 90.5% of the 58.2 GB/s
copy ceiling. Raw: m1-host `/var/tmp/qmm-dequant/out/gap2b-dq-{a,b}.ndjson`.

## 4. Model-level A/B + identity — **FAILS, dual is NOT shippable**

Protocol: France x16 prompt, greedy temp 0, 96-token decode window,
2 runs/arm, MLX_DISABLE_COMPILE=1. Before wheel dc7ca4a0 diag
(m1-host `/var/tmp/cut3-base/dist/...diag.dc7ca4a`, m1max-host
`/var/tmp/mlx_omarchy-0.32.3.dev202609221028+dc7ca4a0`); after wheel
cc4ff2ad4 diag built on each host from the branch tree
(m1-host `/var/tmp/qmm-dequant/tree/dist/...diag.cc4ff2ad4`, m1max-host
`/var/tmp/qmm-dequant/tree/dist/...diag.cc4ff2ad4`).

- **Baseline identity holds on both hosts**: stream
  `16 15 15 4 314 279 854 11 1092 369 ... first=16 last=271`, matching
  the established m1-host reference — cross-host (m1-host vs m1max-host) and
  cross-run identical.
- **After (dual production flip) FAILS on both hosts**: first token
  correct (16, from prefill — prefill kernels are untouched), every
  decode step then emits token 0 (degenerate stream). m1max-host tok/s
  21.34/21.54 vs before 22.73/20.91 — invalid, not a perf claim.
- Wheel diff audit: embedded SPIR-V blob hash comparison of the two
  libmlx.so binaries shows EXACTLY the two dual kernels differ
  (`qmm_vec_q4_multi_subgroup_{f16,bf16}`) — build contamination
  ruled out.
- The shader-level eq gate passes dual 0/7 rows (plain outputs) on
  m1-host. An extended eq arm covering the addend epilogue (flags bit
  8<<d) + KV-window column map (bit 12<<d) was added to the bench
  (`eqsum` rows) but its first m1-host run used a non-bijective synthetic
  window (gap 40 > head_dim 32) leaving unwritten holes — fixed to a
  bijective map in cbac299f8 but **not yet re-run**; the eqsum gate
  therefore never validated dual on the epilogue paths.

Root cause OPEN. Working hypothesis: one of the production-only fused
paths (swiglu fold coexistence, KV-direct sum window stores, addend
epilogue) misbehaves under the dual mapping despite the code paths
being textually mirrored; the first decode step corrupting while
prefill stays correct points at the first fused MULTI dispatch with
KV-direct windows (GDN state feed). Next step: re-run the fixed eqsum
gate on m1-host/m1max-host, then bisect flags (bit8 only → +bit12 → fold) at
the bench level before touching the model again.

## 5. State / housekeeping

- Branch tip cbac299f8: production flip DISABLED (`dual_rows = false`
  with pointer to this receipt; CMakeLists DUAL define removed) —
  dc7ca4a05 behavior is bit-preserved on the tip. Dual remains
  available as the `dual` candidate arm in tools/q4-bw-bench plus the
  guarded shader code and the extended eq gate.
- m1-host: lane tree `/var/tmp/qmm-dequant/` (tree, venvs
  venv-before/venv-after with dc7ca4a/cc4ff2ad4 diag wheels, out/
  artifacts). m1-host handed to macOS per Main.
- m1max-host: same layout under `/var/tmp/qmm-dequant/`; llm-inference
  stopped for the window and restarted — `GET :8002/health` = 200
  after (receipt line in window log; llama unit was stopped via
  `systemctl stop llm-inference` after the first window script
  deadlocked waiting on the lock the service holds — fixed script
  starts/stops around the lock).
- m1max-host was dark for the first half of the lane (hostname unresolved);
  all its numbers are from the post-return window. m2-host untouched.
- No pushes; local branches only.
