# ANE weight-residency: attribution + hardware-SHA fix (2026-09-17, jwm1 T8103; jw16 probes + service discipline)

## Status: attribution COMPLETE (numbers below), implementation LANDED (16835c0f, pushed), wheel build IN FLIGHT on jwm1, full re-measured matrix PENDING

The hypothesis under test — "placed-island weights re-stream per round; staging
them once flips ABCF from loss to break-even" — is **REFUTED as stated and
root-caused in the same pass**:

1. **Per-round weight re-staging does not exist in resident mode.** The 96
   minted mm1/mm2 anecs declare only `x` as a program input
   (`bundles-ffn/island-ffn11-L00/manifest.json`: inputs = [x 768000 B @ ch4],
   outputs = [y 3072000 B @ ch5]; the 8.4 MB of weights are inline in the
   anec). libane stages the full anec into the channel-0 BO once at
   `ane_init`; `set_btsp_and_command` runs only in `ane_chan_init` (strict-fill
   fork `ane-6fa243a-wt/libane/ane.c:209`), never per exec. Empirical probe
   (isolated resident worker, jwm1, real ffn11 bundle, 12 rounds, lock
   flock -w 900 inode 35): worker-internal elapsed 1–4 ms/round,
   stage_ms 0–1, save_ms 0–3. An 8.4 MB/round refill would show ≥4–6 ms in
   stage alone. Round walls in production are 13.6–16.6 ms (GPU-contention
   inflation, consistent with the submit-cost receipt), not weight traffic.

2. **The ~6.1–7.5 s ABCF regression is ~94% ONE-TIME worker session open.**
   Instrumented runner (per-statement wall + per-round marshal/back/ipc
   splits, gates held: db501a8c EXACT, 38c73261 / 91b0e28d / 7a6d9adf pins,
   104/104, bounds PASS, cpu_tensor_events 0, jwm1):

   | arm (jwm1 resident) | wall | exec | marshal | back | open (first placed stmt) | unexplained |
   |---|---|---|---|---|---|---|
   | ABC  | 6795 | 2416 | 3086 | 98  | ~0.15 s (3 bundles) | ~1.0 s |
   | ABCF | 14342 | 3803 | 2374 | 172 | **7097.9 ms** (stmt 169, linear_1) | ~0.9 s |
   | ABCFO| 14716 | 3810 | 2305 | ~170 | ~7.1 s (99 bundles) | ~1.2 s |

   Statement-level trace: `stmt_wall_ms 169 linear 7097.9` — the ENTIRE
   residual is the lazy `AneIsland._ensure_session()` loading all 96+3 bundles
   inside the first placed-linear statement. ABC's matmul wall 4535 → ABCF
   2341 (−2.2 s, FFN matmuls left the GPU) and marshal 3086 → 2374 partially
   offset the added open+rounds; net = the observed +7.5 s.

3. **Root cause of the open cost: the worker CLI re-verifies every payload
   with a hand-rolled scalar SHA-256 on every pass.**
   `bundle.cpp:load_bundle_snapshot` → `sha256_file` → `sha256_compress`
   (plain C, ~100 MB/s). 96 bundles × 8.4 MB ≈ 806 MB hashed per session:
   measured 6794 ms per open (open_probe, 96 bundles; coldish = warm =
   6794 ms — page cache is NOT the variable). Single-bundle splits:
   ffn11 (8.4 MB) full-open ≈ 89–116 ms, parent-only (bundle load + sha, no
   device) ≈ 73–112 ms; oproj (1.5 MB) ≈ 30–50 / 23–40 ms — the cost scales
   with payload bytes at ~8–9 ms/MB, i.e. the hash. Launch mode pays the same
   per submit: ABCF launch ane_exec 15882 ms / 168 submits ≈ 94 ms each,
   dominated by per-process load_bundle re-hashing.

## Implementation (branch agent/ane-weight-residency, commit 16835c0f, pushed)

- `overlay/mlx/backend/omarchy/ane/bundle.cpp`: `sha256_compress` dispatches
  at runtime (`getauxval(AT_HWCAP) & HWCAP_SHA256`) to
  `sha256_compress_crypto` — the canonical public-domain sequence
  (noloader/SHA-Intrinsics sha256-arm.c by Jeffrey Walton, after ARM/mbedTLS),
  transcribed verbatim; scalar path unchanged as fallback. No digest changes:
  same function, hardware executed.
- `overlay/tests/omarchy/ane/test_bundle.cpp`: FIPS 180-4 KATs through the
  ACTIVE path (empty, "abc", 1/3/55/56/63/64/65/119/120-byte boundaries,
  1000×'a', 1 MiB 0x5A) — 13/13 pass on jwm1 (crypto path). Suite: 27/28
  passing; the single failure ("positional channel map is refused") is
  PRE-EXISTING on the untouched baseline f2fd684f (verified by building the
  original bundle.cpp+test on jwm1: same single failure) — stale expectation
  from before the fb4dfa86 positional fill; not this lane's behavior change.
- Runner instrumentation (numerics-neutral, pins held on every run):
  per-round marshal_ns/back_ns/write_ns/read_ns + worker stage_ms/save_ms in
  the island log, op-wall table (`ANE_OP_WALL`), slow-statement trace
  (`ANE_STMT_WALL`), CLI report fields.
- During iteration, three wrong crypto transcriptions were caught by the KATs
  BEFORE any device use (state byte-swap not needed, hq/h2 state roles
  inverted, schedule interleave) — the pins + KATs are the guard that makes
  this fix safe to ship.

## In flight / pending (budget stop)

- jwm1: `~/src/mlx-omarchy-resid` worktree @ 16835c0f,
  `scripts/build-wheel.sh` running (started 2026-09-17 ~11:10 CDT,
  log /tmp/resid-build.log). On completion: extract wheel, deploy worker,
  re-run open_probe (expect ~6.8 s → ≤0.5 s for 96 bundles), then the full
  6-arm matrix on jwm1 with gates.
- jw16: service stop/start discipline already exercised correctly once
  (llm-inference stopped, lock inode 12 never stolen, restarted, active,
  inode 12 held again — verified). Same probe + matrix pass still to run
  there with the new wheel.
- Launch arms are expected to move the most (168 re-hashes per ABCF-launch
  pass); resident ABCF is expected to recover ~5–6 s of the 7.5 s regression,
  which changes the ABCF disposition arithmetic but does NOT by itself flip
  the default: per-round marginal stays ~+1.4 s and the open cost is
  per-utterance (real inference = one pass per process).
- Disposition on the chain route is unchanged from the placement receipt:
  the residual after this fix is per-round IPC/contention (~15 ms/island
  incl. ~8 ms GPU-contention) and the ~0.9–1.2 s GPU-drain share; the fused
  mm1→silu→mm2 program (48 rounds, 1.54 MB/layer instead of 96 rounds and
  7.68 MB) remains the structural lever, arithmetic in the placement receipt.

## Host hand-back

- jwm1: lock free (inode 35, never stolen), module 1fc2e02 map_mode 3,
  build worktree left running the wheel build, /tmp scratch cleaned of
  orphaned parakeet-gate dirs. Certified worker/libane binaries untouched.
- jw16: llm-inference active, lock inode 12 held by its own llama-server
  (PID 24986), module 1fc2e02 map_mode 3. No device state changed; probes
  planned for the next window were NOT run (budget stop before device work
  began beyond the service cycle).
