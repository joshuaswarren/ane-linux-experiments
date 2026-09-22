# 2026-09-22 — Qwen3.8-2B kernel publish prep (publish/qwen38-kernels, local only)

Lane: Qwen38PublishPrep. **No pushes anywhere; everything local.** Prepares
the verified `integration/qwen38-2026-09-22` kernel work for the public merge
into mlx-omarchy main.

## Branch

`mlx-omarchy` local branch **`publish/qwen38-kernels` @ `15b394482`**
(two commits on `origin/main` @ `9ca4cfeb4`):

- `8d9aaa2db` kernels: replay of the qwen38-2026-09-22 verified kernel work
  (GDN decode/prefill fused kernels + mask path, bf16 coopmat qmm prefill,
  bf16-scale qmm prefill variants, fused-chain stride-guard fixes, q4 gemv
  xpack bench + `--bf16eq`/`--2b`), the mlx-lm GDN fast-route packaging from
  `serving/serve-packaging-20260922` @ `8c67e167f` (patches/ +
  apply-mlx-lm-patches.sh + install.sh hunk; conv-ring default OFF), and the
  catalog-v3 qwen3.8-2b-4bit entry (`e03713bd8`, 3-way applied, JSON valid).
- `15b394482` docs: README performance matrix to the integrated-wheel
  cadence + `docs/kernel-flags.md` (env flags incl. conv-ring OFF default;
  `MLX_OMARCHY_FUSED_AB` documented as ANE-side/ignore).

Topology note: `integration/qwen38-2026-09-22` (dc7ca4a0) sits on an
unrelated history root — a literal merge is impossible (`refusing to merge
unrelated histories`, merge-base empty). The branch was therefore replayed
as the tree delta restricted to the kernel/packaging paths; install.sh got
ONLY the 13-line vendoring hunk (main's newer serve-CLI install work kept).
Verification of completeness: diff of publish vs integration on
`overlay/mlx/backend/omarchy`, `tools/q4-bw-bench`, `patches/` is empty for
every path the kernel work touches.

## Build + verification (m1-host, all under `/tmp/m1-gpu.lock`)

Wheel: `mlx_omarchy-0.32.3.dev202609221147+8d9aaa2-cp314-cp314-linux_aarch64.whl`
(8,411,881 B, sha256 `e330e5ead4162c7cac229b06f2f625b77b9a3aa5cca8aa341db19d7ec5121636`),
built from `publish/qwen38-kernels` @ `8d9aaa2db` in `/var/tmp/publish-wt`
via `scripts/build-wheel.sh`. Build log: m1-host
`/var/tmp/publish-prep-build.log`; tests build `/var/tmp/publish-tests-build.log`;
unit run `/var/tmp/publish-unit-tests.log`; bf16eq `/var/tmp/publish-bf16eq.ndjson`;
identity JSONs `/var/tmp/publish-identity-{ops,fused}.json`.

| gate | result |
| --- | --- |
| backend unit tests (ctest, tests-ON build of the same staging tree) | `omarchy_fast_ops_tests` (qmm/rope/GDN fast ops) Passed 42.1 s; `omarchy_fused_chain_tests` Passed; `omarchy_compiled_tape_tests` Passed; `omarchy_matmul_family_tests` Passed 241.9 s; `omarchy_fast_regression_tests` Passed — 0 failures |
| `q4-bw-bench --bf16eq --2b` | 28/28 rows, `bit_mismatches: 0` on every row |
| tokid identity probe (3 cases, greedy 32, pinned 0867d98b snapshot) | fused route == composed-ops route, True/True/True; streams healthy (case1 `760 1156 369 3154 264 4952…` = the healthy family; NOT the degenerate `5e093035` zero stream). Probe script `/var/tmp/publish-identity-probe2.py`; note: the old `identity_probe.py`'s `GD_FORCE_OPS` env matches nothing in any wheel — the real fused/ops toggle is the mlx-lm routing patch, so the probe was rerun unpatched-venv vs patched-venv |

## Privacy scan

`scripts/privacy_check.py` (v5) with `PRIVACY_REPO=<repo>`:
`origin/main..HEAD` (full branch diff incl. catalog entry + vendored
patches): **clean**. Commit messages of both commits: **clean**. The
conservative full-history single-rev scan flags pre-existing test fixtures
(`scripts/test_collect*.py`, wheel-pin tests, community-data pii test) that
are unchanged from origin/main — out of scope for this branch. Pre-commit
privacy hook passed on every commit.

## README

Performance section updated: M1 Max Omarchy row 61.89 / 238.32 / 57.59,
M1 row 25.12 / 32.88 / 34.30 (ttft / prefill-512 / decode tok/s) on wheel
`…+8d9aaa2`; build id + sha256 cited; macOS rows unchanged; the
"Linux cells byte-identical across hosts" invariant replaced by the
qualified per-host-determinism / bf16 near-tie statement citing
receipts/2026-09-22-qwen38-correctness. Diff:
`receipts/2026-09-22-qwen38-publish-prep/README-diff.patch`.

## ane-linux-experiments

`147f475` — re-issued digest/acceptance sections of
`receipts/2026-09-22-gdn-prefill-host` and `receipts/2026-09-21-gdn-prefill-exact`:
`5e093035…` void (degenerate-output hash), healthy per-host references
`ac1b2695…` / `e173e037…` per the correctness receipt; wall numbers stand.

## Status

AWAITING AUTHORIZATION. No push of `publish/qwen38-kernels`, no push of the
ane-linux-experiments receipt commit, no release action taken.
