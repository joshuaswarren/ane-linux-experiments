# 2026-09-22 — Qwen3.8 "Next-Flash" format: facts, gap analysis, feasibility plan

Lane: Qwen3NextFormat (research-first). No kernels written. No GPU lock taken,
the GPU box untouched. Local commit only.

**Scope correction honored (Main, 2026-09-22):** Next-Flash is analyzed on its
own terms as a DIFFERENT format from the Qwen3.8 (`qwen3_5`) we already run.
Every shared component below is proven from configs, not assumed.

## 1. What "Next-Flash" actually is (primary sources)

**Qwen3.8-Flash-Next** (`Qwen/Qwen3.8-Flash-Next`, HF, license
qwen-community-1.0, pipeline image-text-to-text):

- config: `model_type: "qwen4_exp"` (text: `qwen4_exp_text`),
  `architectures: ["Qwen4ExpForConditionalGeneration"]`,
  `transformers_version: "5.8.0.dev0"`
  — https://huggingface.co/Qwen/Qwen3.8-Flash-Next/raw/main/config.json
- Model card states verbatim: *"This experimental preview of the architecture
  that will underpin Qwen4"* —
  https://huggingface.co/Qwen/Qwen3.8-Flash-Next/blob/main/README.md
- Scale: 125B LM params / 6B activated, plus 51B n-gram embedding + 4B MTP;
  hidden 2560; 48 layers as 12 × (3 × (Gated DeltaNet → MoE) → 1 ×
  (Qwen Sparse Attention → MoE)); context 262K native, 1M extensible.

"Flash" here is the **model-name tier** (like Qwen3.8-Flash, the managed API
variant with 1M context), NOT flash-attention kernels and NOT the
flash-linear-attention (fla) library. There is no separate "Next flash
checkpoint format": the checkpoint is a standard HF safetensors layout with a
`qwen4_exp` config (bf16 master weights; community quantization expected).

### How it differs from plain Qwen3.8 (config-proven, side by side)

Our existing Qwen3.8-2B: `SiddhJagani/Qwen3.8-2B-mlx-4Bit`, `model_type:
"qwen3_5"` / `Qwen3_5ForConditionalGeneration` (config read 2026-09-22).

| component | Qwen3.8 (`qwen3_5`, our 2B) | Next-Flash (`qwen4_exp`) | same? |
|---|---|---|---|
| hybrid pattern | 3 linear_attention : 1 full_attention, 24 layers | same 3:1, 48 layers | YES (both configs list `layer_types` explicitly) |
| Gated DeltaNet | Hv=16, Hk=16, Dk=Dv=128, conv 4, `mamba_ssm_dtype: float32` | Hv=48, Hk=16, Dk=Dv=128, conv 4, `mamba_ssm_dtype: float32` | YES mechanically; head count differs |
| full-attention layer | Gated Attention, head_dim 256, 8 Q / 2 KV heads | **Qwen Sparse Attention (QSA)**: 24 Q / 2 KV, head_dim 256, rotary dim 64, plus a block-selection **indexer** (MQA, 4 Q heads / 1 shared K, head_dim 128, budget 512 blocks / 2048 tokens, compress ratio 4) | NO — QSA is new |
| MoE | none in 2B (dense MLP, intermediate 6144) | 512 experts, top-10 + 1 shared, expert intermediate 640 | NO — Next-Flash is high-sparsity MoE |
| Gated Residual | absent from config | `hc_count: 4`, `hc_lowrank: 320`, `output_gate_type: "sigmoid"` — per-branch write gate + data-dependent read gate over widened residual | NO — new module |
| N-gram embedding | absent | 20M bigram/trigram embeddings (~51B params), PLE at layer 2 (`ple_layer_ids: [2]`, `ple_embed_dim: 2560`, conv kernel 4), `split_ngram_parts: 128`, `heads_per_ngram: 8` | NO — new |
| MTP | `mtp_num_hidden_layers: 1`, no dedicated embeddings | 1 layer, **hybrid: true, full_attention**, multi-step trained | partially (config differs) |
| rotary | partial 0.25, theta 1e7, mrope interleaved, section [11,11,10] | identical (`rope_parameters` equal in both configs) | YES (proven) |
| RMSNorm | eps 1e-6 | eps 1e-6; zero-centered/weight-decayed norm is a training-recipe item (model card) | YES for inference math |
| tokenizer | vocab 248320 padded, eos 248044 | vocab 248320 padded, bos/eos 248044 | YES, same family |
| vision tower | Qwen3.5 VL tower, out of our text lane | 27-layer ViT (1152 hidden), out of scope likewise | n/a |
| dtype | bf16 + 4-bit MLX quant | bf16 master; community quants (mxfp4 etc. exist for the older Qwen3-Next) | quantizable by our qmm family |

Note the name trap: **Qwen3-Next-80B-A3B** (Sep 2025, `model_type:
qwen3_next`) is a DIFFERENT, older architecture — GDN + *gated full attention*
(3:1), no QSA, no gated residual, no n-gram embeddings
(https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Instruct-FP8 config read;
transformers doc
https://github.com/huggingface/transformers/blob/main/docs/source/en/model_doc/qwen3_next.md).
It already has an mlx-lm model file; Next-Flash does not (below).

### Premise verdict ("Next flash is what Qwen4 will need")

**VERIFIED by Qwen's own words, with one caveat.** The model card explicitly
calls Qwen3.8-Flash-Next the *experimental preview of the architecture that
will underpin Qwen4*. Caveats, stated plainly: (a) it is labeled experimental —
Qwen4's final architecture may drop or change pieces (QSA budget, n-gram
scale); (b) what transfers most robustly from our existing work is the GDN
half, which Next-Flash keeps byte-for-byte in its config contract; the new
QSA/gated-residual/n-gram pieces are Qwen's actual bets for Qwen4.

### Loader availability today

- Upstream mlx-lm (main AND pinned v0.31.3) model files, verified via GitHub
  contents API 2026-09-22: `qwen3_5.py`, `qwen3_5_moe.py`, `qwen3_next.py`
  exist; **there is no `qwen4_exp.py` anywhere in mlx-lm**. Next-Flash has no
  MLX loader at all. transformers (5.8.0.dev0) has the reference
  implementation; the config's `transformers_version` proves it.
- Older Qwen3-Next IS loadable via mlx-lm `qwen3_next.py` — irrelevant to
  Next-Flash but useful as a MoE-hybrid reference implementation.

## 2. Gap analysis: Next-Flash components vs the omarchy Vulkan backend

File-level, against `mlx-omarchy repo/overlay/mlx/backend/omarchy/`.

| Next-Flash component | backend status | evidence |
|---|---|---|
| GDN decode (Hv=48, Dk=Dv=128, bf16 acts, f32 state) | **COVERED** — fused kernel, dispatch parameterized by Hv workgroup count | `primitives.cpp:10393` `GatedDeltaUpdate::eval_gpu` → `compute.cpp:1237` `GatedDeltaDecodeBF16` → `shaders/gated_delta_decode.comp`; `use_fallback` guard at `primitives.cpp:10379` needs head-count/shape audit for Hv=48 (48 vs 16 is a config value, not a kernel shape constant) |
| GDN prefill scan | **COVERED** — fused two-pass chunked kernel | `shaders/gated_delta_prefill.comp`, `compute.cpp:1240` `GatedDeltaPrefillBF16`; raw-gates prologue fusion + KV-window handling from the Qwen3.8 receipts |
| GDN prologue (in_proj, conv1d k=4, gates, output norm) | **COVERED** | 2B uses the identical op chain (`linear_conv_kernel_dim: 4` in both configs); `scripts/patch-mlx-lm-gdn.py` routes `mx.fast.gated_delta_update` on GPU |
| partial rotary + mrope interleaved, theta 1e7 | **COVERED** | `shaders/fast_rope.comp` + rope-pair bf16; `rope_parameters` byte-equal in both configs |
| full-attention QSA *math* on selected tokens (SDPA, head_dim 256, partial rope, q/k norm) | **COVERED** per-token | `shaders/sdpa_decode_native*.comp`, qmm coopmat prefill; attention head counts differ but are runtime dims |
| QSA **indexer / block top-k selection** (compress ratio 4, 512-block budget, MQA indexer) | **NOT SUPPORTED as a kernel** — must be composed from generic ops (topk/sort/gather/reduce all exist) | no corresponding primitive in `compute.h`; nothing in `shaders/` selects block indices |
| MoE 512 experts, top-10 + shared | **COVERED structurally, unexercised at this scale** | `shaders/gather_mm.comp` (+f16/bf16 variants, `CMakeLists.txt:465-467`), `shaders/gather_qmm.comp` for quantized experts, `shaders/segmented_mm.comp`; our 2B is dense, so the quantized-expert gather path has no correctness receipt yet |
| Gated Residual (4 branches, lowrank 320, sigmoid gates) | **COVERED by composed ops** — elementwise + small GEMMs, no kernel required | generic `binary_vec.comp`, `matmul*` primitives |
| N-gram embedding (20M rows, PLE layer 2) | **COVERED by generic gather/take; loader work only** | `gather_take`/gather primitives; backend has no concept of n-gram vocab — all in the mlx-lm model file |
| MTP layer | **OPTIONAL** — ignored in single-stream teacher-forced/decode | config-driven; mlx-lm generates without MTP head unless spec-decode is wired |
| 4-bit quantization of weights | **COVERED** | qmm family (`qmm_vec`, `qmm_coopmat`, `qmm_tile`), `tools/qwen38_distill_quant.py` as the quantize-recipe pattern |
| f32 SSM state contract | **COVERED** | `mamba_ssm_dtype: float32` matches the kernel contract ("bf16 activations, f32 state", `compute.h:650`) |

Net: the linear-attention half and all generic machinery transfer with config
audits only. The genuinely new GPU work is one composed-path item (QSA
indexer) and one unreceipted path (quantized MoE gather at 512 experts).

## 3. Ordered feasibility plan (effort / risk)

0. **Hard feasibility fact first:** full Next-Flash is ~180B params (125 LM +
   51 n-gram + 4 MTP + vision). At 4-bit ≈ 95 GB; even ~2.5-bit ≈ 60 GB +
   runtime state/KV. **It does not fit the GPU box's 64 GB M1 Max in any quantization.**
   Real-checkpoint generation on our hardware is OUT; only scaled-down configs
   are testable. (the other fleet hosts off-limits this lane; noted, not re-opened.)
1. **Port `mlx_lm/models/qwen4_exp.py`** from the transformers 5.8.0.dev0
   implementation: reuse `qwen3_5.py` GDN path, `qwen3_5_moe.py` experts,
   implement QSA composed (topk/gather over block scores), gated residual,
   n-gram embedding lookup, PLE. Effort 1–2 days. Risk medium (new model code,
   not new kernels).
2. **Synthetic tiny `qwen4_exp` checkpoint probe** (2–4 layers, hidden 256,
   ngram vocab shrunk, random weights): load-only + teacher-forced 32-step
   decode on the GPU box under `flock -w 900 /tmp/m1-gpu.lock` with llm-inference
   stopped and restored. Cheap gate that the loader + every backend op
   compose. Effort ~0.5 day after step 1. **Not run in this lane** — it
   requires the step-1 model file (a full work item, not a cheap step), and a
   real-checkpoint probe is impossible per fact 0. Not half-done; recorded.
3. **Identity gate:** extend the accepted equivalence class from
   `receipts/2026-09-22-qwen38-correctness` — teacher-forced argmax flips vs a
   CPU transformers reference on the tiny config, bf16 quantum margins
   (≤0.25 logit at operating magnitude), per-host digest on a pinned driver
   stack. No new protocol needed; reuse logits top-8 capture.
4. **QSA fast kernel** (block-score compress + top-k + gathered SDPA),
   composed path first as the arithmetic reference, fused kernel only after
   identity is proven. Effort 1–2 weeks, highest risk item. Only justified if
   Qwen4 ships.
5. **MoE gather correctness receipt** on 512-expert shapes (quantized
   gather_qmm vs composed reference) — medium value now, blocks nothing.

## 4. Probe results

None. Justification: per §3.0/§3.2 — no Next-Flash checkpoint fits the GPU box, and
the only meaningful probe is gated on the step-1 loader port. the GPU box lock was
never taken; llm-inference untouched.

## 5. Citations

- https://huggingface.co/Qwen/Qwen3.8-Flash-Next/blob/main/README.md (model
  card: "experimental preview of the architecture that will underpin Qwen4";
  full spec table; Flash tier note)
- https://huggingface.co/Qwen/Qwen3.8-Flash-Next/raw/main/config.json
  (qwen4_exp config: layer_types, hc_count/hc_lowrank, indexer_*, ngram_*, ple_*,
  mtp{hybrid}, rope_parameters, moe dims)
- https://huggingface.co/SiddhJagani/Qwen3.8-2B-mlx-4Bit/raw/main/config.json
  (our qwen3_5 config for the side-by-side)
- https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Instruct-FP8/raw/main/config.json
  (older qwen3_next; name-disambiguation)
- https://github.com/huggingface/transformers/blob/main/docs/source/en/model_doc/qwen3_next.md
  (Qwen3-Next overview; contributed 2025-09-10)
- mlx-lm model inventory, GitHub contents API, refs `main` and `v0.31.3`
  (2026-09-22): `qwen3_5.py`, `qwen3_5_moe.py`, `qwen3_next.py` present; no
  `qwen4_exp.py`
- Local: `receipts/2026-09-22-qwen38-correctness/README.md` (identity
  protocol), `scripts/patch-mlx-lm-gdn.py`, backend sources listed in §2
