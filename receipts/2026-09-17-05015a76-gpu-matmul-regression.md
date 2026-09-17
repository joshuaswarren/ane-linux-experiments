# OBSERVATION: libmlx build 05015a76 carries a ~2.8x GPU matmul regression (2026-09-17, Sha256CryptoMatrix)

## What

`/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages/mlx/lib/libmlx.so`
(wheel `mlx_omarchy-0.32.2.dev202609141626+05015a76`, dated Sep 14 12:06)
runs the encoder's per-statement GPU matmuls ~2.8x slower than the
`044f297f` build (Sep 17 10:25): statement 347 matmul 90 ms → 260 ms,
repeated across all 24 layers ≈ +3.9 s of encoder wall per pass. Same
runner file, same GPU, same SPIR-V cache dir, `flock` held, llama
stopped — the ONLY variable is which libmlx.so the runner process mapped
(verified via /proc/self/maps).

## Reproduction anchors

- jw16, ABC resident, interleaved A/B twice: wall 5 330.4 / 5 337.7 (old)
  vs 9 170.8 / 9 204.4 (05015a76). exec_ms (ANE-side) slightly FASTER on
  the slow build (2 395 vs 1 715) — the regression is purely GPU-side.
- Statement-level walls: `STMT 347 matmul 96.4ms` (old) vs
  `STMT 347 matmul 266.5ms` (05015a76); the whole per-layer matmul group
  inflates.

## Why it matters independently of measurement hygiene

That build is sitting in a shared venv cache that multiple harnesses
fall back to when their site-dir is absent (`PYTHONPATH=$RUN/site:venv-cache`
with a missing `$RUN/site`). Any run that resolves it gets the slow GPU
path silently. Something shipped it; the regression was never caught
because no harness asserted the loaded binary's identity until now
(see receipts/2026-09-17-libmlx-identity-shadowing.md).

## Suggested follow-up

1. Bisect 05015a76..044f297f for the GPU matmul fix (the fast path is
   already shipped in 044f297f and later, including landed `16835c0f`).
2. Refresh or remove the stale `05015a76` wheel from
   `/var/tmp/MelFrontendPerf/venv-cache`, or pin
   `MLX_OMARCHY_EXPECTED_LIBMLX_SHA256` in every harness that resolves
   through that cache.
3. Ask whether any published number between Sep 14 and Sep 17 was measured
   through this cache; those absolute walls carry the ~2x penalty.

## Exact binaries (jw16)

- slow: venv-cache `.../mlx/lib/libmlx.so`, sha256
  `a91880f9f17d52ed34fbad9e46f6fd29`-prefixed md5 form recorded; wheel
  dist-info `mlx_omarchy-0.32.2.dev202609141626+05015a76`
- fast reference: `/var/tmp/r4-wheelx/mlx/lib/libmlx.so.pre16835c0f`
  (044f297f wheel, md5 `52e26050d342d7c4c41cf295f236bc8e`)
- landed fix binary: `/var/tmp/r4-wheelx/mlx/lib/libmlx.so`
  (16835c0f, md5 `d587a011ecc62bdea49f073d1e9c9653`; GPU code identical
  to 044f297f, only bundle.cpp SHA dispatch differs)
