# Gemma-4-E4B KV-Shared Loader Bug — Upstream Certification + Interim Shim

Date: 2026-09-18 · Lane: upstream cert + overlay shim · Follows: `2026-09-18-currentgen-loader-feasibility.md` row 2.

## Verdict

**Real loader bug, already tracked and fixed upstream.** mlx-lm 0.31.3 (latest PyPI, 2026-04-22) rejects canonical Gemma 4 checkpoints with the strict `ValueError: Received 126 parameters not in model`. Upstream issue **[ml-explore/mlx-lm#1242](https://github.com/ml-explore/mlx-lm/issues/1242)** (open, 2026-05-03, multiple 0.31.3 reporters) and fix **#1240** (merged 2026-05-04, commit `df1d3f3c`, 13-line sanitize drop). **No new issue or PR filed** — both would duplicate #1242/#1240. Cross-link comment posted with independent evidence: [#1242 comment](https://github.com/ml-explore/mlx-lm/issues/1242#issuecomment-5731014742).

**Correction to the feasibility receipt:** row 2's "mlx-lm git main line 185 has identical logic → fails there too" is wrong. Git main @ `872ae88` (the oMLX pin) **contains** `df1d3f3c` and **loads E4B** (verified below, 23 s CPU). The failure is release-only: 0.31.3 predates the fix by 12 days and nothing newer has shipped to PyPI.

## Certainty evidence

**(a) KV-sharing is intentional in the checkpoint — canonical layout, not converter damage.**
- lmstudio-community card: 4-bit conversion of `google/gemma-4-E4B-it` via mlx_vlm.
- Google's own single-file `google/gemma-4-E4B-it` `model.safetensors` header scan (range request): `model.language_model.layers.24.self_attn.{k_norm,k_proj,v_proj}.weight` present; k_proj in L23 and L24 both true. Google ships the shared-layer tensors; transformers drops them on load via `_keys_to_ignore_on_load_unexpected` (modular_gemma4.py ~L1346: "drop all k/v proj and norms for the shared layers"), and does not even create the modules for shared layers (~L1040: `if not self.is_kv_shared_layer: self.k_proj = ...`).

**(b) Config fields match the loader — not a config-naming gap.**
Checkpoint `text_config`: `num_hidden_layers: 42`, `num_kv_shared_layers: 18`, `num_key_value_heads: 2`, `model_type: gemma4_text`. Loader `has_kv = idx < 42 - 18` → layers 0–23 own KV, 24–41 shared. The checkpoint ships per-layer `k_proj.{weight,scales,biases}` for all 42 layers plus `k_norm.weight`/`v_proj.{weight,scales,biases}` on 24–41 → 18 × 7 = **126** unexpected params, exactly the error count.

**(c) Fresh-venv repro (this host, CPU, prepared `mlx_omarchy` wheel + `mlx-lm==0.31.3 --no-deps`).**
- Unpatched 0.31.3: `ValueError: Received 126 parameters not in model: language_model.model.layers.24...` through `layers.41...v_proj.weight` (list ends at L41 = last shared layer).
- + `df1d3f3c` patch: `LOAD OK`.
- Control revert (patch -R): failure returns. `/tmp/g4-repro-venv`.
- mlx-lm @ 872ae88 (fease2-venv): `LOAD OK` (23 s).

## Interim shim (our overlay)

mlx-omarchy `install.sh` (commit `161419f5`, branch `e2e-kind`, **local only — not pushed**): embedded patch block applied to the venv's `mlx_lm/models/gemma4_text.py` right after the `mlx-lm==$MLX_LM_VERSION` install. It is the verbatim upstream `df1d3f3c` diff, marked with #1240/#1242. Self-expiring: skipped when the installed mlx-lm already carries the fix; `die`s loudly if the hunk stops applying. Drop the block when `MLX_LM_VERSION` includes `df1d3f3c`.

Block verification (extracted verbatim, `/tmp/patchblock.sh`, on `/tmp/g4-repro-venv`): already-fixed → skip message, exit 0, no `.rej` litter; pure 0.31.3 → applies, exit 0, E4B `LOAD OK`.

### jw16 (16" M1 MBP, Honeykrisp Vulkan) — GPU window via RuntimeModernize

Procedure honored: `sudo systemctl stop llm-inference` → `flock /tmp/m1-gpu.lock` → smoke → baseline restore → restart → `/health` 200 attempt.

**jw16 result: shim verified for LOAD, generation blocked by a separate backend issue (not the shim).**
- Load: clean on device — no 126-param error, full weights+graph build with the shim on mlx-lm 0.31.3.
- Generate, attempt 1 (compiled path): refused by the backend's own guard — `RuntimeError: [omarchy] Compiled tape bfloat16 is refused: bf16 fragments corrupt nondeterministically on Honeykrisp. Re-run with MLX_DISABLE_COMPILE=1.` (bf16 is E4B's dtype; any bf16 model hits this.)
- Generate, attempt 2 (`MLX_DISABLE_COMPILE=1`, eager): `RuntimeError: [omarchy] Vulkan timeline counter failed to advance for 10000 ms (last observed=0, target=1). The device may be hung; no CPU fallback is available.` — same failure class as the feasibility receipt's row-1 pending item (Qwen3.6-27B gen smoke, "jw16 GPU smoke closes this"). E4B prefill hangs the omarchy Vulkan backend in eager bf16; this is RuntimeModernize's active lane (Select/Take kernel fixes + wheel rebuild), not a KV-shared-loader issue.
- Baseline restored: `/tmp/venv-base` shim applied then reverted, `grep -c "KV-shared layers reuse K/V"` → 0. `llm-inference` handed back to RuntimeModernize (their round-4 runner holds the lock; service flapping during handoff is a lock-collision artifact their in-window stop/restart clears).

## Upstream receipts

- Issue: https://github.com/ml-explore/mlx-lm/issues/1242 (existing, open — the tracking thread)
- Fix PR: https://github.com/ml-explore/mlx-lm/pull/1240 (merged 2026-05-04, `df1d3f3c`); closed duplicate PR #1205
- Our comment: https://github.com/ml-explore/mlx-lm/issues/1242#issuecomment-5731014742
- No PR opened from us: the fix already exists upstream; porting it here is the shim above.

## Scratch

`/tmp/g4-repro-venv` (repro A/B), `/tmp/df1d3f3c.patch` (upstream diff), `/tmp/jw16-e4b-smoke.sh` + jw16 copy (GPU smoke), `/tmp/hf` (checkpoint cache).
