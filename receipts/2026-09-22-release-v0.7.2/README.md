# Receipt: mlx-omarchy v0.7.2 release (final)

Date: 2026-09-22. Release: https://github.com/joshuaswarren/mlx-omarchy/releases/tag/v0.7.2

## Commit / tag

- Tag `v0.7.2` (annotated `26035ec99`) → `fa103c8670dbb43d48cadd868b224b5bea072f64` (force-pushed from the earlier `04bb49acc` cut; documented `--no-verify` used only for the pre-push full-history false positive on pre-existing public fixtures). Range privacy scan of the new commits: `privacy-check: clean (04bb49acc..fa103c867)`.
- main is one docs commit ahead (`d39179d90`: README matrix re-measured on the tag build). Wheels record build commit `fa103c86`, which is what `scripts/verify-release-assets.py` pins against the tag.
- Origin of the re-cut: the first build window (08:04–08:06 local) ran from a worktree checked out at the stale tag content; `fa103c867` landed 08:08:30. All gates below were re-run on wheels built from the tag commit.

## Gate battery, tag build (per host summary in /var/tmp/v072-gates/summary.txt)

| gate | m1max-host (m1max-host) | m1-host (m1-host) |
|---|---|---|
| ctest fast_ops / fused_chain / compiled_tape / matmul_family / fast_regression | 35/35 (1,104,350 asserts), 36/36 (346,272), 12/12, 22/22 (829,404), 2/2 — all rc=0 | — (round-1 coverage) |
| q4-bw-bench --bf16eq --2b | 28 rows, 0 nonzero bit_mismatches, rc=0 | 28 rows, 0 nonzero bit_mismatches, rc=0 (re-run after /tmp wipe: bench recompiled from tag tree) |
| tokid identity (ops vs fused) | rc=0 both venvs | rc=0 |
| cadence prefill-512 (10×3, greedy, pinned digest) | ttft 62.25, pure prefill 267.7 (+12% from GDN prefill rework vs 238.3), decode 56.8, digest `ac1b269553a220ee…` | fork driver: ttft 46.68, pure prefill 128.66, decode 34.3, digest `ac1b2695…` = m1max-host, byte-identical; stock-Mesa control 46.7/128.3/34.29, same digest (fork is now m1-host system default, so both legs agree) |
| serving smoke (mlx_lm.server + OpenAI bench 10×3) | 30/30 completions rc=0 (re-run via fixup script after gates script served from a stale buffered path) | — |

README matrix rows updated to these measurements: M1 46.7/128.7/34.3 (fork driver), M1 Max 62.3/267.7/56.8.

## Assets (uploaded, clobbered over the 04bb49ac cut)

- `mlx_omarchy-0.32.3.dev202609221309+fa103c86-cp314-cp314-linux_aarch64.whl` — m1max-host build, sha256 `5dd224028975acaaa7ad27cf690e82ac53405599230ca07b5aa929e67cebff41`
- `mlx_omarchy-0.32.3.dev202609221309+fa103c8-cp311-cp311-linux_x86_64.whl` — workstation build, sha256 `1a5b48b2d621927e70d2090a0578f62743af19dffd36c22908c6c1adb829bd0c`
- `SHA256SUMS` — sha256 `243629ca53777fd5385d5c18037362c42b478ee92484d430c0f02d3a04af85d6`
- The independently built m1-host aarch64 wheel (sha256 `09e6af00e285fa050c1cda41a4cdf8c0f53a247aaef606f5ae292b39b3d651f5`) is recorded here as a cross-check only: the `m1-host-`-prefixed asset name fails the verifier's wheel-name identity check, so it is not distributed.
- Stale `04bb49ac*` assets deleted from the release.

## Verification

- `python3 scripts/verify-release-assets.py v0.7.2 --repo joshuaswarren/mlx-omarchy` → **VERIFIED: every uploaded asset matches what the release claims** (sha256, filename/dist-info/METADATA version identity, build commit = tag commit, stable-build feature strings with MLX_DISABLE_COMPILE control).
- Uploaded-asset pinned decode (fresh venv installing the release-download URL, not a local build; m1max-host): asset.whl sha256 `5dd22402…` matches the recorded hash; run rc=0, label `v072-uploaded-asset-m1max-host-fa103c86`, installed version `0.32.3.dev202609221309+fa103c86`, digest **`ac1b269553a220ee…`** (release digest family), prefill-512 274.5, decode 57.7. Evidence: `<m1max-host>:/var/tmp/v072-rel/{summary.txt,pinned-decode.json}` on m1max-host.

## Notes

- Mesa work referenced by the release notes lives in `joshuaswarren/mesa-1` (branch `honeykrisp-omarchy`), per the repo-migration rule.
- m1-host was rebooted once mid-flow (dwc3 wedge, M2 ANE priority); /tmp-derived state (bf16eq bench binary) was rebuilt from the tag tree and re-run.
