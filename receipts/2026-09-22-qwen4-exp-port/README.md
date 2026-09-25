# 2026-09-22 — qwen4_exp (Qwen3.8-Flash-Next) loader port + synthetic tiny checkpoint

Lane: Qwen4ExpPort. Local CPU proof complete; GPU smoke on gpu-box staged but
NOT run (see §7). Local commits only, no pushes.

## 1. What landed

- `mlx_lm/models/qwen4_exp.py` — drop-in model file for mlx-lm 0.31.3,
  ported from the transformers 5.8.0.dev0 reference
  (`modeling_qwen4_exp.py` text stack, fetched from HF main). New components
  implemented in composed MLX ops (no fused kernels, per scope):
  - QSA block-indexer (`QSAIndexer`): pooled key blocks (mean over
    `indexer_compress_ratio` tokens) → k-layernorm → rope at absolute
    block-start positions → per-head relu-dot scores → top-k blocks +
    per-query tail → additive float mask.
  - Gated residual / hyper-connections (`GatedResidual`): hc_count streams,
    lowrank input mixer, 2·sigmoid injection weights.
  - PLE (`NGramEmbedding` + `PLELayer`): splitmix64-derived per-layer hash
    multipliers (exact int64), prime per-head vocabularies, eos-aware
    shift-right, dilated depthwise short conv (channels-last; state kept in
    the layer's ArraysCache slot 2, token history in slot 3).
  - Zero-centered RMSNorm (1+w) mapped to plain MLX RMSNorm via `sanitize`
    adding 1.0 to the stored weight (same trick as qwen3_5); GDN gated norm
    is plain-weight sigmoid gate (`output_gate_type=sigmoid`).
  - GDN reuses mlx-lm `gated_delta_update` (composed ops path,
    `use_kernel=False`); q/k fold HF l2norm (eps=1e-6 on the sum) + Dk^-0.5
    readout scale exactly.
  - f32 SSM state contract preserved for f32/f16 checkpoints (state dtype
    follows activations only in f64 mode, used by the CPU reference gate).
- Vision tower and MTP head dropped (same policy as qwen3_5; `_keys_to_ignore`).
- HF 3D expert weights (`experts.gate_up_proj [E,2I,H]`) split into
  `switch_mlp.gate/up_proj` in `sanitize`; conv1d HF `[C,1,K]` → MLX
  `[C,K,1]`.
- Registration is automatic: `mlx_lm.utils` imports `mlx_lm.models.<model_type>`.
- Synthetic tiny checkpoint: `.work/qwen4exp-port/build_synthetic.py` →
  `tiny-qwen4exp/` (108 tensors, fp32, seeded). Preserves structure at toy
  scale: 4 layers in the 3 GDN : 1 QSA pattern, 8-expert top-2 MoE + gated
  shared expert, hc_count=4 lowrank hyper-connections, QSA indexer
  (budget 4 / compress 2), PLE on one-indexed layer 2, partial mrope
  interleaved, Hv:Hk = 12:4 (mirrors 48:16).
- Numpy fp64 reference: `.work/qwen4exp-port/reference.py` — line-for-line
  port of the HF torch math (chunked + recurrent gated delta rule with
  forward-substitution UT solve, causal conv, indexer per-query loop, MoE,
  gated residual, n-gram hashing, PLE dilated conv, mrope recomposition).

## 2. Correctness results (CPU, `.work/qwen4exp-port/results.json`)

Gate: `test_correctness.py`. **9/11 checks pass.**

| check | result | detail |
|---|---|---|
| weight-coverage | PASS | 0 missing, 0 extra tensors vs module tree |
| mrope (interleaved recomposition) | PASS | max\|dcos\| = 2.9e-8 vs fp64 ref |
| gdn-chunk (T=40, chunked scan) | PASS | max\|dout\| = 9.5e-8 |
| gdn-state | PASS | max\|dstate\| = 1.5e-7 (mlx state is [B,Hv,Dv,Dk], ref [B,Hv,Dk,Dv] — layout-transposed) |
| gdn-recurrent-decode (T=1 + state) | PASS | max\|dout\| = 7.6e-8 |
| ngram-multipliers | PASS | splitmix64 mults bit-exact vs python-int reference |
| forward-prefill-f64 (stage-capture) | PASS | all 4 layers' MoE in/out vs fp64 chain ≤ 2.3e-6; 0 argmax flips over 16 positions; max\|dlogits\| = 1.0e-6 at logit mag 0.70; top-8 identical |
| decode-4-steps-f64 | **FAIL (open)** | step 0 \|d\| = 6.4e-1 — see §3 |
| forward-prefill-f32 | PASS (informational) | f32 vs f64: max\|d\| = 0.85 on a 4-layer toy whose top-2 logit gap is 0.003 — toy-scale logit magnitudes make flip-count uninformative at f32; the f64 gate is the identity bar |

Bugs found and fixed during bring-up (each was a real semantic error the
gate caught): missing PLE short-conv state write-back, per-query indexer
tail selection (global tail vs per-query tail), q/k l2norm eps fold,
zero-centered norm weight mapping, grouped-RMSNorm weight broadcast.

## 3. Open item — decode-path f64 divergence

`decode-4-steps-f64` still diverges (max\|d\| ~ 0.6/step). Localization so
far: with per-stage host-forcing (capturing MoE inputs/outputs), the
**prefill** end-to-end matches the fp64 reference to 1e-6, and an isolated
GDN decode step against the post-prefill state matches to 1.2e-7. The
remaining step-0 decode mismatch arises from the handoff of the stored PLE
short-conv state / stage boundaries between the lazy prefill graph and the
decode step: fully-lazy f64 CPU graphs in this model are
**evaluation-order sensitive** (the same model call yields logits differing
by ~0.75 depending on where host syncs land; `mx.eval` at layer boundaries
does NOT reproduce the host-sync result — only numpy materialization does).
This is recorded as a suspected MLX 0.32.2 f64-CPU runtime hazard and is the
top item to close before GPU work: it must be either root-caused in the f64
backend or sidestepped by forcing stage evaluation in `DecoderLayer`/PLE
(exactly what the passing stage-capture gate does).

## 4. Hv=48 head-count audit (fused-path binding)

- Composed path: correct for Hv=48/Hk=16 — `gated_delta_ops` repeats q/k by
  `Hv//Hk=3` before the step loop (`gated_delta.py:242`), and the packed
  Metal kernel is documented "generic in B, Hk, Hv" (Dk=128, Dv%8==0).
- Our omarchy Vulkan backend: `GatedDeltaUpdate::use_fallback`
  (`overlay/mlx/backend/omarchy/primitives.cpp:10379`) falls back to
  composed ops unless `Dk==128 && Dv==128 && Hk==Hv`. With the Next-Flash
  ratio (Hk=16, Hv=48) the fused decode kernel will therefore NEVER engage —
  every GDN layer runs the composed fallback. Correct but unfused.
- Verdict: **needs a shape fix to bind**. Either (a) the loader materializes
  the q/k repeat before the primitive call (Hk==Hv==48; triples q/k memory),
  or (b) the guard is relaxed to accept `Hv = ratio·Hk` with head indexing
  `v_idx % Hk`, mirroring the mlx-lm Metal kernel. (b) is the right fix;
  measured Qwen3.8-2B (Hv==Hk==16?) unaffected. Record: also verify against
  the 2B config's actual Hv/Hk before quoting (our receipt table lists 2B
  GDN as its own shape).

## 5. Kernel engagement table (expected on gpu-box GPU, from source)

| component | path on this port | engaged fused kernel? |
|---|---|---|
| GDN prefill | composed ops (`use_kernel=False` in this port) | NO — composed by choice (correctness-first); omarchy fused prefill not wired for this model yet |
| GDN decode | composed ops | NO — `Hk != Hv` fallback guard (primitives.cpp:10379) with Hv=48/Hk=16 |
| QSA indexer | composed (matmul/relu/argpartition/mask) | NO kernel exists (expected) |
| attention SDPA | `mx.fast.scaled_dot_product_attention` (fused, additive float mask) | YES where mask shapes allow; composed fallback for the per-query indexer mask |
| rope (partial mrope) | `initialize_rope` fused fast_rope + composed interleaved recomposition | PARTIAL (recomposition is composed) |
| MoE experts | `SwitchGLU` → `gather_mm`/`gather_qmm` | YES (unexercised at 512 experts; toy is 8) |
| PLE / hyper-connections | composed elementwise + depthwise conv1d | NO kernel (none expected) |
| dispatch counts | not yet instrumented on GPU (smoke pending) | — |

## 6. Remaining work before a real Qwen4-class checkpoint

1. Close the decode f64 divergence (§3) and re-run the full gate green.
2. GPU smoke on gpu-box: load `tiny-qwen4exp` on device, prefill+decode vs this
   CPU reference under `flock -w 900 /tmp/m1-gpu.lock` (llm-inference
   stop/restart + /health receipt). Queued; gpu-box availability coordinated
   through Main.
3. Wire GDN to `mx.fast.gated_delta_update` (`use_kernel=True`) after the
   Hv=48 guard decision (§4); equivalence-check fused vs composed on device.
4. Wire the QSA path to the fused SDPA with additive mask and measure the
   indexer's cost at 262K context (per-query top-k over 4096 blocks).
5. Quantization pass (qmm family) + `quant_predicate` sanity on real weight
   shapes; MoE gather at 512 experts / top-10 correctness receipt.
6. MTP head: dropped by design (matches qwen3_5); revisit only for
   speculative decode.
7. mlx-lm server/generate integration test (tokenizer, cache_prompt) — the
   port implements `make_cache`/`sanitize`/`quant_predicate` but has only
   been exercised through direct model calls.

## 7. Environment / constraints receipts

- gpu-box was unreachable at lane start (kernel-lane experiment, no network);
  Main authorized local CPU work, then a reboot window (GpuTlpLatency), then
  a full stop while the user was at the console, then cleared GPU work.
  GPU smoke has NOT run; llm-inference on gpu-box untouched by this lane.
- Artifacts: `.work/qwen4exp-port/{qwen4_exp.py, reference.py,
  build_synthetic.py, test_correctness.py, results.json, tiny-qwen4exp/,
  debug_layers.py}`; venv `.work/qwen4exp-venv` (mlx 0.32.2 CPU, mlx-lm 0.31.3).
- Reference sources: transformers main `models/qwen4_exp/{modeling,
  configuration}_qwen4_exp.py` (fetched 2026-09-22); mlx-lm 0.31.3 + main
  `gated_delta.py`; mlx-omarchy `overlay/mlx/backend/omarchy/primitives.cpp`.
