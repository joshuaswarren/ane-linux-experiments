# 2026-09-22 — Qwen3.8-2B integrated-wheel serving: m1-host smoke completion, packaging vendoring, serve bench

Lane: ServingIntegrationSmoke. Wheel: integration/qwen38-2026-09-22 @ dc7ca4a0
(`mlx_omarchy-0.32.3.dev2026092210{25,28}+dc7ca4a0`, sha256s in
`receipts/2026-09-22-qwen38-integration/README.md`); venvs `/var/tmp/integ-venv`
on both hosts. Host names below use repo aliases m1-host / m1max-host.
No pushes (publication freeze); raw JSON in this directory.

## 1. m1-host serving smoke — now PASS

The integration-lane smoke never confirmed readiness and was left open. Rerun
with a 300 s readiness poll (2 s interval against `/v1/models`):

- **ready_after_s = 4** on BOTH hosts (m1-host: ready-m1-host-before.txt;
  m1max-host: ready-m1max-host-before.txt). Server startup latency was never the
  problem — the original smoke's wait budget was not the failure.
- Root cause of the original red flag: `mlx_lm.server` 0.31.3 `/v1/models`
  lists **every model in the local HF cache** (it answered with
  `lmstudio-community/gemma-4-E4B-it-MLX-4bit` and other cache entries on
  m1max-host). Any client that resolves the served model via
  `--model auto` (first `/v1/models` id) targets a model that is not loaded
  and gets 404s — which presents exactly as "the smoke never became ready".
  Fix used here: pass the explicit model id
  `SiddhJagani/Qwen3.8-2B-mlx-4Bit` in every request; snapshot
  `0867d98bfb174b042d88461c0e7c97b86b34b381`.
- Result: 10 prompts x 3 passes, 30/30 streaming chat completions 200 OK,
  `usage_verified: True` on both arms, per-host output digests identical
  before/after (`fd65b5b93df203ce` first prompt … `c14a6f86bd9311b0` last),
  and digests agree ACROSS hosts (m1-host == m1max-host on all 10 prompts).
  Servers killed after each arm; `/tmp/m1-gpu.lock` held throughout; neither
  host's other services touched.

## 2. Vendored mlx-lm serve patches — mlx-omarchy `serving/serve-packaging-20260922` (local, @ 8c67e167f)

- `patches/mlx-lm-gated-delta-fast-route.patch` — routes gated-delta updates
  to `mx.fast.gated_delta_update` (provided by the mlx-omarchy wheel); falls
  back to the upstream kernel when absent. Default ON.
- `patches/mlx-lm-convring.patch` — preallocated rolling conv-state ring for
  GDN decode. Default **OFF**; enabled with `MLX_OMARCHY_CONV_RING=1`.
- `scripts/patch-mlx-lm-gdn.py`, `scripts/patch-mlx-lm-convring.py` — the
  idempotent venv patchers (vendored from ane-linux-experiments/scripts).
- `scripts/apply-mlx-lm-patches.sh` — applies both to a venv's mlx_lm tree;
  idempotent (already-applied detected via reverse dry-run); fails loudly on
  mlx-lm version drift. Both patch files generated against pristine
  mlx-lm 0.31.3 (gated_delta.py sha256 79c8376a… verified against the wheel).
- `install.sh` step 4b fetches the script + patches at the pinned release tag
  and applies them to the install venv, so `mlx-omarchy serve` (the
  catalog-v3 managed serve path runs `mlx_lm.server` from that same venv)
  picks the patches up with no manual venv patching.
- Note: `scripts/prepare-mlx.sh` stages the pinned C++ mlx tree only; mlx-lm
  is a separate pip install, so the patch hook lives in the installer/apply
  script, not in prepare-mlx.sh.
- Verified locally (synthetic venv, python 3.11, mlx-lm 0.31.3 from PyPI):
  default arm applies gdn only; idempotent re-run reports already-applied;
  `MLX_OMARCHY_CONV_RING=1` adds the ring patch; both patched files parse
  (ast.parse) clean.

## 3. Serve bench before/after (benchmarks/qwen38-serve-bench.py)

Protocol: 10 prompts x 3 passes, greedy, 32 new tokens, warmup 2, streaming,
usage-verified (`token_rate_completion = (usage.completion_tokens - 1)/(total
- ttft)`). `before` = same venv family with the GDN fast-route patch reverted
(`/var/tmp/serve-venv-base`, gated_delta.py byte-identical to pristine
0.31.3, sha256 79c8376a…); `after` = `/var/tmp/integ-venv` (patch applied).
Port 8955, GPU flock held, servers killed after each arm.

| host | arm | TTFT median (s) | decode tok/s median | output digests |
|---|---|---:|---:|---|
| m1max-host (M1 Max) | before | 0.89 | 9.05 | fd65b5b9… c14a6f86… |
| m1max-host (M1 Max) | after-gdn | **0.59** | **13.56** | identical to before |
| m1-host (M1) | before | 1.79 | 8.29 | fd65b5b9… c14a6f86… |
| m1-host (M1) | after-gdn | **1.32** | **10.78** | identical to before |

Deltas: m1max-host TTFT -34%, decode +50%; m1-host TTFT -26%, decode +30%.
Output identity exact per host (before == after) and across hosts.

Bench robustness fix landed with this receipt
(ane-linux-experiments `benchmarks/qwen38-serve-bench.py`): count
`delta.reasoning` chunks — Qwen3.8 streams thinking output there, and the
previous content-only accounting recorded zero tokens (out sha
e3b0c442… = empty string) despite HTTP 200s.

Raw JSON: `serve-m1-host-*.json`, `serve-m1max-host-*.json`, `ready-*.txt` in this
directory (renamed copies of the hosts' /var/tmp/serve-bench outputs).
