# Current-Gen Loader Feasibility — qwen3_5 / gemma4 / prism_hadamard_qwen35

Date: 2026-09-18 · Box: ane-linux (EPYC 7443P, llvmpipe via `MLX_OMARCHY_ALLOW_NON_APPLE=1`) · Lane: feasibility + prototype, no performance claims.

## Stack under test

- Prepared MLX source: `~/src/mlx-omarchy`, `mlx.lock` pins MLX **0.32.2.dev**, commit `1f8e74e3` (omarchy Vulkan/Honeykrisp backend). Certified venvs untouched.
- Scratch venv `/tmp/fease-venv` (py3.11): wheel `dist/mlx_omarchy-0.32.2.dev202609171444+112c32c-cp311-cp311-linux_x86_64.whl` + `mlx-lm==0.31.3 --no-deps` (installer pin).
- Scratch venv `/tmp/fease2-venv` (py3.11): same wheel + `mlx-lm @ 872ae88d1fac77350db23c8c04fe8dd372a9e3e8` (mlx-lm git main, the commit oMLX main pins) + mlx-vlm 0.7.1.
- HF cache `/tmp/hf` (~40 GB). Env guard: `MLX_OMARCHY_ALLOW_NON_APPLE=1` required on llvmpipe.

## Version boundary (headline)

- **PyPI max mlx-lm = 0.31.3** — there is no newer release; the installer pin equals latest-released.
- **mlx-lm git main @ `872ae88` imports and loads models on our 0.32.2 prepared source with zero new core ops.** The next API consumer, oMLX 0.7.0.dev4, requires exactly this commit: `from mlx_lm.generate import StopSequences` (plus "full cache state / per-stream stop matchers", per its pyproject comment "mlx-lm 0.32.0: …") — **ImportError under 0.31.3**. That is the exact API break.
- oMLX 0.6.4 release pyproject pins `mlx==0.32.2` — same major/minor as our source; nothing in the currentgen model set required an MLX core op newer than 0.32.2. **Bumping the prepared source is NOT required for any model in this matrix**; it is only interesting for staying on mlx-lm main.
- mlx-vlm newest PyPI = 0.7.1; installed --no-deps for oMLX's import chain; no VLM load probed (out of matrix scope).

## Load matrix (mlx-lm 0.31.3 on prepared source unless noted)

| # | Model / repo | Arch | Verdict |
|---|---|---|---|
| 1 | `mlx-community/Qwen3.6-27B-mxfp4` | qwen3_5 (hybrid GDN + full attn), mxfp4 | **LOADED** (14 files; weights+graph built). Token-generation smoke unproven on llvmpipe CPU (1700 s budget elapsed without completing a forward eval — 27B on CPU, not an error). jw16 GPU smoke closes this. |
| 2 | `lmstudio-community/gemma-4-E4B-it-MLX-4bit` | gemma4_text, kv-shared (18 of 42), per-layer-input 256 | **NOT-LOADED** on 0.31.3 — strict `ValueError: Received 126 parameters not in model`: checkpoint ships `layers.{24..41}.self_attn.{k_proj,v_proj}.weight+scales/biases` and `k_norm.weight`; loader marks those layers KV-shared (`has_kv = idx < num_layers − num_kv_shared_layers`) and has no such params. ~~mlx-lm git main line 185 has identical logic → fails there too~~ **CORRECTED same day:** git main @ 872ae88 **loads** — it includes upstream fix `df1d3f3c` (#1240, 2026-05-04, tracking #1242), whose sanitize drops the shared-layer params; 0.31.3 predates it. Bug is release-only. See `2026-09-18-gemma4-e4b-upstream-bug.md`. Canonical layout (Google's own checkpoint ships those tensors), **not** a core-op gap. |
| 3 | `mlx-community/gemma-4-31b-it-4bit` | gemma4 (mm, affine 4-bit g64) | **LOADED** (11 files) |
| 4 | `prism-ml/Ternary-Bonsai-8B-mlx-2bit` | plain `qwen3`, affine 2-bit g128 | **LOADED** — stock path, no runtime/ loader, no Hadamard (gen-1 pack). Also **LOADED** on mlx-lm@872ae88. |
| 5 | `prism-ml/Ternary-Bonsai-2-27B-mlx-2bit` | prism_hadamard_qwen35 | **PRIMITIVES VERIFIED, pack load deferred to jw16** — needs bundled runtime (below); base repo `prism-ml/Ternary-Bonsai-2-27B` is gated (401), public `-mlx-2bit` pack has everything. |

Not probed (RuntimeModernize owns): gemma-4-E2B, 12B (`gemma4_unified`), 26B-A4B-QAT, `mlx-community/Ministral-3-8B-Instruct-2512-4bit` (mistral3 — `mistral3.py`/`ministral3.py` both present in 0.31.3), `phi3` (Phi-4-mini — `phi3.py` present in 0.31.3, expected loads-today).

## Bonsai gen-2 (27B) Hadamard runtime assessment

`PACK-RUNTIME.md` + `runtime/runtime.py`/`artifact.py` (bundled in the pack):

- Pure-Python, `sys.path`-insert; builds `mlx_lm.models.qwen3_5.TextModel` (same class as row 1), then swaps every Linear/Embedding in `hadamard.json` for a `Packed` module. **No fork kernels, no compiled extensions.**
- Required ops, all probed PASSING on our prepared wheel (CPU): `mx.hadamard_transform` (normalized Sylvester-Walsh, block 1024); `mx.quantized_matmul(..., group_size=128, bits=2)` affine per-group scale+bias decode (ternary {−s,0,+s} encoded as affine 2-bit — card claim verified); `mx.dequantize(..., bits=2)` for the inverse-embedding path (gather by index → dequantize → inverse FWHT).
- Port friction: near zero for text-only. Untested surface: `hadamard_transform` on Honeykrisp Vulkan (CPU proven only).

## Serving engines (oMLX vs mlx_lm.server), Bonsai-8B, this host

| | oMLX 0.7.0.dev4 (git main, source run) | mlx_lm.server @ 872ae88 |
|---|---|---|
| Server start | **YES** — uvicorn binds 8321, `Application startup complete`, `/v1/models` answers (auto-discovers cached models) | **YES** — binds 8323, model loads |
| `/v1/chat/completions` | Accepted (HTTP 200), engine loads model, **generation FAILS**: `RuntimeError: [omarchy] Vulkan timeline counter failed to advance for 10000 ms (last observed=0, target=1). The device may be hung; no CPU fallback is available.` — omarchy backend on llvmpipe, not an oMLX bug | **Identical error** in its generation thread at first `mx.eval(prompt_cache)` |
| Conclusion | Both engines are gated by the same llvmpipe Vulkan limitation; **generation comparison requires jw16 (real GPU)**. Load/import parity: oMLX needs mlx-lm@872ae88; with it, feature parity of the stack is intact. |

oMLX run receipts: `/tmp/omlx-serve.log`, oMLX settings `~/.omlx/settings.json` (written by test runs; source-tree run only, nothing installed system-wide).

## Minimum change list

1. **qwen3_5 (row 1): none.** Ships in mlx-lm 0.31.3; pure composite ops.
2. **gemma4 dense (row 3): none.** E4B-class kv-shared checkpoints (row 2): already fixed upstream (`df1d3f3c`/#1240, in 872ae88); release users on 0.31.3 need the fix ported — done as an installer shim in mlx-omarchy `install.sh` (`161419f5`), see `2026-09-18-gemma4-e4b-upstream-bug.md`.
3. **Bonsai 27B gen-2:** none in MLX source. Adopt pack's `runtime/`+`artifact.py` loader (text-only), add 2-bit affine g128 as first-class quant mode in docs/packaging, and prove `hadamard_transform` on Honeykrisp (jw16).
4. **Pin policy (recommendation only — Joshua decides):**
   - Keep installer mlx-lm pin at **0.31.3** while consumers only use `mlx_lm.load`/text LM serving: it is latest-released, and everything in the matrix that loads, loads on it.
   - If we adopt oMLX (or any mlx-lm-main consumer: `StopSequences`, full cache state), pin **`mlx-lm @ 872ae88d1fac77350db23c8c04fe8dd372a9e3e8`** — verified import+load on our 0.32.2 source; no source bump needed. Pin by commit, not branch, until a post-0.31.3 release lands on PyPI.
   - Either way the MLX source stays 0.32.2: no arch in scope needs newer core ops.
5. **Runtime (env, not stack):** llvmpipe cannot run generation on this backend (timeline-semaphore watchdog, both engines). Any token-level acceptance must run on jw16.

## Receipts

- Scratch venvs `/tmp/fease-venv`, `/tmp/fease2-venv`; HF cache `/tmp/hf`.
- oMLX source `/tmp/omlx-src` (jundot/omlx, 0.7.0.dev4); mlx-lm main `/tmp/mlxlm-main`; Bonsai runtime `/tmp/bonsai`.
- Supervised processes `omlx-feasibility` (port 8321), `mlxlmsrv2` (port 8323) — stopped after capture.
