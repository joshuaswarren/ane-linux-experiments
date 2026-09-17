# FINDING: silent libmlx identity shadowing in the measurement harness (2026-09-17, Sha256CryptoMatrix)

## The defect

The e2e encoder harness resolves `libmlx.so` through the dynamic linker,
not through any explicit pin. With the new wheel deployed and no
`LD_LIBRARY_PATH`, the runner (fused_e2e python on jw16) silently loaded
the venv-cache `05015a76` build instead of the intended `044f297f` build.
No error, no warning, no field in the report identifies which GPU backend
build ran.

Measured consequence (statement-level instrumentation, jw16, ABC resident,
same runner file, same everything except the loaded libmlx):

- stmt 347 matmul: 90 → 260 ms per statement, repeated across all 24
  encoder layers ≈ **+3.9 s of encoder wall**, ~2.8× per statement.
- Session ABC resident wall: ~5 100 → ~9 190 ms, fully reproducible
  interleaved (5 330.4 / 9 170.8 / 5 337.7 / 9 204.4), `flock` held,
  llama stopped.

A harness that can load the wrong binary without telling you produces
confident wrong numbers, which is worse than crashing.

## Guard (landed)

`overlay/tools/coreml/vulkan_encoder.py` `assert_mlx_binary_identity()`
(mlx-omarchy main @ `88a0bc71`): the runner resolves the libmlx actually
mapped into the process from `/proc/self/maps`, records
`{loaded_libmlx_path, loaded_libmlx_sha256, dist_version}`, and
**hard-fails** when `MLX_OMARCHY_EXPECTED_LIBMLX_SHA256` or
`MLX_OMARCHY_EXPECTED_LIBMLX_PATH` disagrees. Set the env var whenever a
measurement's provenance matters. The same assert is applied to the
scratch runners on jwm1 (`vk_resid.py`) and jw16 (`vk_erev_o.py`).

## Contamination scope — which of today's numbers are affected

| measurement | runner libmlx | verdict |
|---|---|---|
| 2026-09-17-ffn-placement (both hosts, gpu_ops 1206) | jw16 arms: `E2EREV/site` → wheel `f43ab71` (Sep 16) — empirically verified resolution; NOT the slow `05015a76` path (its walls sit in the fast class, ~4.8 s) | absolute walls are on a third build — cross-receipt comparison to `044f297f`/`16835c0f` walls is NOT valid; the ABCF-vs-ABC net-loss verdict is within-one-harness/one-session and stands |
| v0.6.2 release receipt (jw16 ABC/ABCO resident 4 922/5 649) | unverified; resolution path would be `venv-cache 05015a76` today, but the walls sit in the fast class, so the run predates the shadow or used a site that existed then | treat cross-receipt absolute walls as unprovenanced; relative deltas within the receipt are sound |
| this lane's first jw16 table (12:02, out-cx-*) | `venv-cache 05015a76` — the SLOW path | **superseded**: absolute walls inflated ~+4 s; relative within-table comparisons internally consistent. Use the runner-pinned split A/B below instead |
| this lane's jwm1 matrix (out-resid-*) | runner imports via `ParakeetE2ECurrentWheel/site` — different resolution chain, unaffected; jwm1 walls consistent with prior receipts | valid as published |
| this lane's jw16 split A/B (out-cln-, out-split-, out-diag-*) | runner pinned `044f297f` via `LD_LIBRARY_PATH`, worker resolves its own wheel lib (child env stripped) | valid; the before/after numbers of record |

## Numbers of record for jw16 ABC (runner pinned `044f297f`, llama stopped, `flock -w 900`, pins `38c73261` / `db501a8c` EXACT on every run)

| arm | worker+lib | wall | exec | subs |
|---|---|---|---|---|
| launch | OLD scalar | 6 001.4 | 2 553.0 | 72 |
| launch | NEW crypto | 6 010.3 | 2 557.3 | 72 |
| resident | OLD scalar | 5 075.4 | 2 442.5 | 1 |
| resident | NEW crypto | 4 714.6 | 2 210.3 | 1 |

Rule going forward: every e2e report should carry the loaded-libmlx
identity; a wall quoted without it is unprovenanced. Cross-receipt wall
comparisons are only valid when both runs assert the same loaded sha256.
