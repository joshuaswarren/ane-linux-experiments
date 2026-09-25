# 2026-09-24 — t6001-host (T6001) decode: copy/cast dispatch attribution + GDN conv-concat fold (copycast lane)

Lane: CopyCast (continues T6001DispatchCut, closed by the prior lane agent at
mode-1-only installed). Host: t6001-host (Omarchy ARM, M1 Max T6001/G13C).
Baseline: installed stack = serving venv `/var/tmp/v072-venv-fused`
(mlx-omarchy wheel `0.32.3.dev202609240305+a12b1aa1` = tree `69801d05`, native
on-device build) + mode-1 routing (`rms_norm_scaled` q/k sites) + GDN
raw-route (`gated_delta_update_raw` at T==1) — **71.2 tok/s decode, 549
dispatches/token, 10-pass digest `dbf70497`**.

**Verdict: INSTALLED ON A WIN. The conv-concat fold is bit-exact in-model:
gates x3 = 0/0/0 flips (max|d_top1| = 0.0000), cand 10-pass digest =
dbf70497 EXACT PIN @ 73.91 tok/s, contract A/B paired delta
+2.573 +- 0.145 tok/s (95% CI, n=10) = +3.61% decode over the 71.32
baseline. Dispatches/token 525.0 -> 489.0 (-36.0, exact). An intermediate
"21 flips" gate smoke was a routing confound: the provisioning script had
re-enabled the parked mode-0 route (rms_norm_gated) in qwen3_next.py;
restoring v072's qwen3_next.py removed it (found independently by a sibling lane's instrument). NOTHING was installed while gates were failing. — first contract window's candidate arm crashed at model load-time
decode step on a weight-layout guard (checkpoint/MLX conv weight layout
`[C_out, K, C_in/groups]`, my guard expected `[C, 1, K]`); fix landed at
`d33ae8b7` (superseded), wheels + venvs must be rebuilt before the window is rerun.
NOTHING INSTALLED; installed stack untouched; service restored and verified
with a real completion.**

## 0. Attribution instrument

`MLX_OMARCHY_GPU_PROFILE` NDJSON (diag wheel — release wheels compile the
profiler out), `MLX_DISABLE_COMPILE=1`, sliced per steady-state decode token
via host markers (prefill 512 + 32 greedy tokens). Every dispatch record
carries the kernel enum (`compute.h`, append-only ids) and the MLX primitive
name; the per-token dispatch sequence is deterministic (32/32 identical), so
each copy/cast was attributed by matching the ordered stream against the
model code (`mlx_lm/models/qwen3_5.py`, `qwen3_next.py`, `gated_delta.py`)
and the backend SDPA composition. Structure cross-checked on the usc-study
stream (`prof-p0.ndjson`, aae4dfc9 stack, 585/tok); counts on the installed
549/tok stack differ only by the mode-1 removals already installed
(FastRmsNorm 115→79, Elementwise 43→7).

## 1. Attribution table: every CopyGeneral and Cast per decode token

| #/tok | kernel | primitive (source) | site | removable bit-exactly? |
|---:|---|---|---|---|
| 18 | CopyGeneralBF16 | Concatenate — state half | `GatedDeltaNet.__call__` (qwen3_5.py): `conv_input = mx.concatenate([conv_state, qkv], axis=1)` — 3-row conv-state half | **YES** — fold into conv read (this change) |
| 18 | CopyGeneralBF16 | Concatenate — qkv half | same concat — 1-row qkv half | **YES** — fold into conv read |
| 6 | CopyGeneralBF16 | SliceUpdate | `Qwen3NextAttention`: `cache.update_and_fetch(k, v)` — k write into KV cache | no — the write IS the cache update |
| 6 | CopyGeneralBF16 | SliceUpdate | same — v write | no |
| 6 | CopyGeneralBF16 | ScaledDotProductAttention | backend composed SDPA: contiguous copy of k before the f32 score matmul | no — removal needs strided f32 cast/matmul reads in the elementwise machinery; a fused SDPA kernel changes f32 reduction order (not bit-exact) |
| 6 | CopyGeneralBF16 | ScaledDotProductAttention | same — v copy before the pv matmul | no |
| 6 | CopyGeneralBF16 | RMSNorm | `q_norm(queries)`: `queries` is a strided split-slice of `q_proj_output.reshape(B,L,H,-1)` (head stride 2×head_dim); norm requires row-contiguous input → dense copy | no — needs a strided-input norm shader; 6/tok alone does not carry the plumbing round |
| 6 | CopyGeneralBF16 | Reshape | `output.transpose(0,2,1,3).reshape(B,L,-1)` head-merge after SDPA | no — removal requires the gate mul or o_proj qmm to consume strided input |
| 18 | CastBF16F32 | CompiledAsTypeSigmoidBroadcastBroadcastMultiply | `_precise_swiglu` in `Qwen3NextRMSNormGated`: `gate.astype(f32)` | no — folding the widen into the silu kernel creates a new exp() pipeline; the mode-0 saga (2026-09-23 receipt §10-11) proved in-shader exp bits are driver-pipeline-lowered — same GLSL text produced different sigmoid bits across kernels. Middle rounding must stay |
| 18 | CastBF16F32 | same | `_precise_swiglu`: `x.astype(f32)` | no — same exp-pipeline hazard (feeds the silu chain inside one compiled tape) |
| 6 | CastBF16F32 | ScaledDotProductAttention | SDPA: q widened to f32 for the score matmul | no — f32 matmul inputs are the bit-exact floor; a bf16-input variant reorders rounding |
| 12 | CastBF16F32 | ScaledDotProductAttention | SDPA: the two copied k/v views widened to f32 | no — same |
| 18 | CastF32BF16 | CompiledAsTypeSigmoidBroadcastBroadcastMultiply | `_precise_swiglu` output `.astype(bf16)` — the RNE the composed chain makes | no — this narrowing feeds qmm; folding into the FusedChain mul = new kernel = mode-0 hazard class |
| 6 | CastF32BF16 | ScaledDotProductAttention | SDPA output narrowed back to bf16 | no — feeds the bf16 gate mul and o_proj at expected dtype |

Census check: 36 concat copies + 12 KV SliceUpdate + 12 SDPA copies + 6 norm
copies + 6 reshape copies = **72 CopyGeneral/token**; casts 54 CastBF16F32 +
24 CastF32BF16 = **78/token**; Elementwise 7 (6 attn-gate sigmoids + 1
sampler subtract) — matches the stream exactly. (The 36 q/k scale-mul
Elementwise dispatches were already removed by the installed mode-1 routing.)

## 2. Change under test (implemented, unqualified)

`mlx-omarchy` branch `copycast/conv-split` @ `2ad134c1` final (worktree
`/var/tmp/ccut-wt`, base = installed tree `69801d05`, native on-device
builds):

- `overlay/mlx/backend/omarchy/shaders/gdn_conv_decode.comp` — one dispatch
  reads the conv window from TWO buffers (conv state `[B,3,6144]` + decode
  row `[B,1,6144]`) and writes BOTH the conv output and the shifted
  carry-out state (raw uint16 moves). Tap accumulation is the conv.comp body
  verbatim (same loop shape, f32 widen, left-associated sum, RNE bf16
  store); flat weight indexing `c*K + tap` is identical to conv.comp's
  `out_channel*kernel_products + flat_product` for this layout, so fused ==
  composed bitwise by construction — the concatenation it replaces is
  value-transparent (pure copies).
- `compute.h/cpp`, `CMakeLists.txt`, `primitives.cpp` — `GdnConvDecodeBF16`
  kernel + `GdnConvUpdate` primitive (multi-output; dense-materialization
  guard copied from the GDN decode kernel, incl. the offset!=0 trap).
- `patches/mlx-gdn-conv-decode.patch` — mlx-core fast.h/fast.cpp/
  fast_primitives.h + python binding: `mx.fast.gdn_conv_update(state, x,
  weight) -> (conv_out, new_state)`; T>1 falls back to the exact composed
  ops (concat + conv1d + tail slice), so prefill is untouched. Weight layout
  per MLX conv semantics `[C_out, K, C_in/groups]` — validated as
  `state.shape(1) == weight.shape(1)-1 && weight.shape(2) == 1`.
- `scripts/patch-mlx-lm-qwen35-gdn-conv.py` — venv routing, hasattr-guarded,
  decode-only (`qkv.shape[1] == 1`), bf16-only, no-lengths cache branch only
  (take_along_axis state update stays composed); idempotent; qwen3_5.py only
  (the Qwen3.8 GatedDeltaNet lives there).

Expected when routed: −36 dispatches/token (549 → 513, −6.6%).

## 3. Dispatches per token before/after

BEFORE (installed stack): **549/token** (585 measured on the pre-mode-1
stack minus the 36 mode-1 removals; kernel table in the 2026-09-23 receipt).

AFTER: **pending** — needs rebuilt diag wheel + profile leg. Analyzer ready:
`/tmp/ccut/dispatch_table.py <prof.ndjson> <markers.jsonl> <compute.h>`.

## 4. Gates + contract A/B

**Attempt 1 (void):** window 20260924T0130Z ran to completion for ctl but
every cand rep failed at the first decode step:
`ValueError: [conv] ... weight of shape (6144,4,1)` — the candidate venv
routed into `gdn_conv_update`, whose `[C,1,K]` shape guard rejected the real
MLX conv weight layout and fell back to a conv1d validation error. Fixed at
`d33ae8b7`; **the window must be rerun after rebuilding wheels**.

Ctl baseline re-confirmed healthy in the same window: 10/10 reps
71.21–71.51 tok/s, 3-pass digest `bc519c03` ×10 — matching the installed
71.2 anchor.

Still required before any install: driver-level account of the lowering difference (SPIR-V/Air dump of both conv pipelines, same next step as mode 0), then gates ×3 at **0 flips**
(`logits_gl.py` + `logits_cmp.py` vs `/var/tmp/gdncoop/logits-coop.json`),
10-pass digest **`dbf70497`** on cand, 10 interleaved paired reps vs ctl
(71.2), then install on a win. Bit-exactness rationale in §2; any gate flip
→ run the unrouted discriminator (sibling receipt ADDENDUM 7) before
attributing.

## 4b. Measured results (window 20260924T084609Z + tail)

- Gates: cand 0/0/0 flips (max|d_top1| = 0.0000), ctl 0 flips.
- Contract A/B: ctl 71.32 avg (71.12-71.64, bc519c03 x10), cand 73.89 avg
  (73.70-74.11; 3-pass digests bc519c03 with documented near-tie variants
  a483d947/112f4cc4/c12461f2), paired +2.573 +- 0.145 (95% CI, n=10).
- 10-pass anchors: ctl dbf70497 @ 71.54; **cand dbf70497 @ 73.91 - exact pin**.
- Dispatches/token (diag wheels, decode-window census): ctl 525.0
  (CopyGeneral 72 = 36 concat + 6 qnorm + 12 SDPA + 12 KV SliceUpdate +
  6 reshape; census cross-checked), cand 489.0 (-36.0 exact: Concatenate
  36 -> 0, ConvBF16 18 -> GdnConvDecodeBF16 18, all else identical).

## 5. Install state

**NOTHING INSTALLED.** System ICD untouched; serving venv
`/var/tmp/v072-venv-fused` untouched (verified by its ctl legs holding
71.2/bc519c03/dbf70497-class digests); candidate venvs are isolated under
`/tmp/ccut/venv-*`. `llm-inference` stopped for the window, restored:
`active`, `/health {"status":"ok"}`, real completion probe answered
("4", finish=stop) via the API-key file (key untouched). No reboots, no boot
writes. One stray orphan shell from the killed window was terminated by PID
on-device.

## Artifacts

- repo (this lane): this receipt + `receipts-work-copycast/` sanitized
  copies of `window-copycast.sh`, `setup-venvs.sh`, `dispatch_table.py`,
  `gen_patch.py`, `edit_backend.py`.
- t6001-host: worktree `/var/tmp/ccut-wt` (`d33ae8b7`), wheels
  `/tmp/ccut/wheels/` (both STALE — pre-fix `2372397`; rebuild from
  `d33ae8b7`), venvs `/tmp/ccut/venv-{cand,prof-cand,prof-ctl}` (stale,
  rebuild), failed-window logs `/tmp/ccut/out/window-20260924*.log` +
  `contract-cand-r*.console` (failure evidence), profile analyzer
  `/tmp/ccut/dispatch_table.py`, prof_decode.py.
- Resume recipe: rebuild `scripts/build-wheel.sh` and
  `scripts/build-wheel.sh --diagnostics` in `/var/tmp/ccut-wt` (serially —
  two parallel builds exhausted btrfs chunk space; also `sudo journalctl
  --vacuum-size=200M` freed 2.1G when ENOSPC hit at 99%), copy wheels to
  `/tmp/ccut/wheels/`, run `setup-venvs.sh`, smoke = one `logits_gl.py`
  cand run (must be 0 flips — this exercises the routed path end-to-end),
  then `window-copycast.sh`.
