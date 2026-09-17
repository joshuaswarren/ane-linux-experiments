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

---

# Appendix: re-measured matrix with the ARMv8 SHA-256 crypto fix (2026-09-17, Sha256CryptoMatrix)

## Deployed provenance

- Wheel built on jwm1 in `~/src/mlx-omarchy-resid` @ `16835c0f`
  (`/tmp/resid-build.log`: "source commit: 16835c0"; wheel sha256
  `14424d7f96a3305c93b52e4e84b396b5f5b7b6e1fbfc09b857a4339d301f48e3`).
- Deployed on BOTH hosts: full wheel tree over `/var/tmp/r4-wheelx/mlx/`
  (old `libmlx.so` + worker preserved as `*.pre16835c0f`); launch-path
  worker `/var/tmp/{jwm1,jw16}-oproj-place/mlx-omarchy-ane-worker` is a
  symlink to the r4-wheelx binary (RUNPATH `$ORIGIN/../lib` resolves to the
  NEW `libmlx.so` — deploying the binary alone was measured first and did
  nothing: open stayed ~7.4 s because the old scalar `.so` was still loaded).
- Provenance is pure `16835c0f`: the only other change on the branch,
  `b284e7fb` (+0/−13, test file only), landed after the wheel was built and
  touches no C++.

## KATs against the DEPLOYED binary (not the build tree)

`/tmp/kat.cpp` (13 FIPS 180-4 vectors verbatim from `test_bundle.cpp`)
compiled and linked against the DEPLOYED `libmlx.so` (`-L<r4-wheelx>/lib`,
rpath to it) on each host:

- jwm1: 13/13 PASS (`/tmp/kat_deployed`, rc=0)
- jw16: 13/13 PASS (`/tmp/kat_deployed`, rc=0)

Crypto path confirmed ACTIVE on both hosts via a C `getauxval(AT_HWCAP)`
probe: jwm1 hwcap `0xffb3ffff` (SHA2 bit 6 set). Note: Python
`ctypes.getauxval` on jwm1 reports a bogus `0x181`; do not trust it — use
a compiled probe.

## open_probe (resident worker session open, all bundles hashed at open)

| host | bundles | payload | before (scalar) | after (crypto) | MB/s scalar → crypto |
|---|---|---|---|---|---|
| jwm1 | 96 ffn islands | 807 MB | ~7 400 ms | **1 549–1 848 ms** | 109 → 520 |
| jw16 | 28 islands | 51 MB | 461–488 ms | **128–137 ms** | 110 → 390 |

The receipt's ≤0.5 s expectation for 96 bundles was optimistic: Apple's
SHA2 extension measures ~0.4–0.5 GB/s single-threaded here, not the
≥1.6 GB/s that would put 807 MB under 0.5 s. The scalar→crypto speedup is
3.6–4.8×, consistent across hosts.

## ABC default, before vs after (the number that ships to every user)

jwm1, same-session launch-minus-resident `ane.exec_ms` gap (the launch
per-submit re-hash proxy):

| arm pair | before gap | per submit | after gap | per submit | recovered |
|---|---|---|---|---|---|
| ABC (72 submits) | 2 706 ms | ~37.6 ms | **908 ms** | **12.6 ms** | −1 798 ms (−66%) |
| ABCF (168 submits) | 12 079 ms | ~71.9 ms | **5 130 ms** | **30.5 ms** | −6 949 ms (−58%) |

Launch mode still pays ~12.6 ms/submit (ABC): per-process spawn + libane
init + device program load remain; hashing was ~2/3 of the ABC launch gap
and is gone.

## Full matrix, gates held (status match, prefix 104/104, bounds PASS, cpu_tensor_events 0)

| host | arm | subs | gpu_ops | encoder wall ms | ane exec ms | hidden | transcript |
|---|---|---|---|---|---|---|---|
| jwm1 | ABC launch | 72 | 1206 | 7998.2 | 2787.7 | `38c73261` | `db501a8c` |
| jwm1 | ABC resident | 1 | 1206 | 5501.5 | 1880.5 | `38c73261` | `db501a8c` |
| jwm1 | ABCF launch | 168 | 1158 | 11927.6 | 7867.0 | `91b0e28d` | `db501a8c` |
| jwm1 | ABCF resident | 1 | 1158 | 7243.0 | 2736.9 | `91b0e28d` | `db501a8c` |
| jwm1 | ABCFO launch | 192 | 1134 | 11707.6 | 7404.2 | `7a6d9adf` | `db501a8c` |
| jwm1 | ABCFO resident | 1 | 1134 | 6927.6 | 2528.0 | `7a6d9adf` | `db501a8c` |
| jw16 | ABC launch | 72 | 1254 | 10834.3 | 2591.8 | `38c73261` | `db501a8c` |
| jw16 | ABC resident | 1 | 1254 | 9122.2 | 1731.1 | `38c73261` | `db501a8c` |
| jw16 | ABCO launch | 96 | 1230 | 11243.5 | 2975.7 | `ef6afd13` | `db501a8c` |
| jw16 | ABCO resident | 1 | 1230 | 9221.2 | 1828.5 | `ef6afd13` | `db501a8c` |

Pins: ABC `38c73261` byte-exact both hosts/modes; ABCF `91b0e28d` and ABCFO
`7a6d9adf` match the recorded deterministic hiddens; jw16 ABCO `ef6afd13`
matches the recorded pin (receipts/2026-09-17-encoder-ane-oproj-channel-
derive.md). jwm1 ABCF resident wall 14 342 → **7 243 ms** (−7.1 s), the
predicted open recovery realized. No digest moved anywhere — the crypto
compress is digest-identical in production, as the KATs predicted.

## Disposition

**Default stays ABC; `16835c0f` should still land to main — it is a large
pure win for the shipped default.**

1. ABC (default) improvement, shippable on its own: launch-mode hashing
   overhead cut by ~2/3 (−66%, 37.6 → 12.6 ms/submit); every launch-mode
   ANE user gains ~1.8 s per 72-submit pass; open hashing on any resident
   open is 3.6–4.8× faster. No gate moved. Recommend landing `16835c0f`.
2. ABCF does NOT become viable: jwm1 resident ABCF is still +1 741 ms wall
   (+32%) over ABC resident. Residual breakdown:
   - per-utterance open: ~1.55 s (807 MB hashed at 520 MB/s inside
     `_ensure_session`), paid once per resident session;
   - per-round marginal: exec 2 736.9 − 1 880.5 = +857 ms over 96 rounds
     ≈ +8.9 ms/round (GPU contention/IPC; matches the ~8 ms/island
     submit-cost receipt);
   - launch mode is strictly worse (ABCF launch +3 930 ms over ABC launch).
3. Path to flipping ABCF, on paper: (a) digest caching — hash each bundle
   once and verify by size+mtime on later opens would delete nearly the
   whole 1.55 s open (dominant residual at crypto speed); (b) the fused
   mm1→silu→mm2 program halves rounds 96→48 and drops 7.68→1.54 MB/layer
   of traffic, worth roughly −450–700 ms of the per-round residual. Together
   they plausibly cover the +1.7 s gap; neither alone does. Fusion remains
   the structural lever; caching is now the cheap one.

## Housekeeping

- jwm1: lock inode 35 free, module `1fc2e02` map_mode 3; new worker deployed
  (old binaries `*.pre16835c0f` preserved in place); `/tmp/resid-wheel` and
  `/tmp/open_probe.py` left for reproducibility.
- jw16: llm-inference stopped before arms (lock inode 12 released, never
  stolen), restarted and **active** at hand-back holding inode 12; module
  `1fc2e02` map_mode 3. Same deployment layout; `/var/tmp/oldlib` (old
  libmlx for the before-probe) can be deleted.
- jw16 `vk_erev_o.py` `RESIDENT_BUNDLES` extended with
  `island-oproj-L00..23` — it listed only the 3 non-oproj islands, so ABCO
  resident mode had never been runnable there (first run failed
  "unknown resident bundle 'island-oproj-L00'"; after the fix it MATCHes
  with pin `ef6afd13`).
- Test fix: `b284e7fb` on `agent/ane-weight-residency` deletes the stale
  "positional channel map is refused" case; suite rebuilt and 27/27 green
  on jwm1.

## Addendum (same day): jw16 reconciliation — the SHA fix is clean; two earlier jw16 numbers were harness artifacts

Main flagged that my first jw16 table did not reconcile with the FfnPlacement
matrix. Resolution below; every claim is backed by a run in this session.

### 1. The first jw16 table was NOT comparable — and the wall regression it showed was a pre-existing harness artifact, not the fix

- Metric: I quoted `stages[stage=="encoder_ane"].wall_ms`. The FfnPlacement
  receipt quoted `total_pipeline_ms` (and used the FFN lane runner
  `vulkan_encoder.py`+F hunks; `gpu_ops` 1206 there vs 1254 for my
  `vk_erev_o.py` ABC). Different runner, different metric — not comparable.
- Same-runner-pinned A/B then showed new-pair walls ~2× old (resident
  5 331 → 9 188). Statement-level instrumentation located it: with the new
  wheel deployed WITHOUT `LD_LIBRARY_PATH`, the RUNNER (fused_e2e python)
  loaded the venv-cache libmlx `05015a76` (dev202609141626) instead of the
  `044f297f` build, and that build's GPU matmul path is ~2.8× slower per
  statement (stmt 347 matmul 90→260 ms across all 24 layers ≈ +3.9 s).
  This is independent of the SHA change — it is a runner-libmlx-version
  artifact that was silently present in the 12:02 matrix too.
- Decisive split (worker resolves its own libmlx via RUNPATH; runner pinned
  on `044f297f` via `LD_LIBRARY_PATH`, `LD_LIBRARY_PATH` stripped from the
  child env; llama stopped; `flock -w 900` held; pins `38c73261` /
  `db501a8c` EXACT on all four runs):

| jw16 ABC, runner pinned 044f297f | wall | exec | subs |
|---|---|---|---|
| worker+lib OLD (scalar SHA) | 6 001.4 | 2 553.0 | 72 |
| worker+lib NEW (crypto SHA) | 6 010.3 | 2 557.3 | 72 |
| worker+lib OLD, resident | 5 075.4 | 2 442.5 | 1 |
| worker+lib NEW, resident | 4 714.6 | 2 210.3 | 1 |

- jw16 verdict: launch neutral on ABC (its per-submit bundles are small,
  ~1.5–5 MB, so per-submit hashing was only a few ms); resident −360 ms
  wall / −232 ms exec (session-open hashing 463→131 ms plus round
  variance). Post-fix open probe (28 bundles, 51 MB): 461–488 → 128–137 ms
  (110 → 390 MB/s). The jwm1 launch win (−66% of the launch−resident gap)
  stands: those arms hash ~96 MB of FFN islands per submit-heavy pass.
- jw16 scratch runner `vk_erev_o.py` now carries two durable fixes: the
  `RESIDENT_BUNDLES` oproj extension and the `LD_LIBRARY_PATH` strip (runner
  mlx loads before children; the worker must resolve its own wheel lib).
  Final post-cleanup check: MATCH, wall 4 940, exec 2 373, `38c73261` /
  `db501a8c`.

### 2. The "+727 ms ABCO resident on jw16" published number is VALID — my "never runnable" claim was over-broad

`receipts/2026-09-17-v0.6.2-release.md` measured ABCO resident
(submissions=1, hidden `ef6afd13`) via WheelR4V062's own runner, which had a
complete resident bundle set. What had never been runnable was ABCO resident
through the `/var/tmp/ParakeetE2EJw16/vk_erev_o.py` scratch copy specifically
(its `RESIDENT_BUNDLES` listed only the 3 non-oproj islands). The +727 ms
figure stands; no correction needed. The number that DOES need a caveat is my
earlier claim in this receipt — scope corrected here.

### 3. Branch state confirmed

`agent/ane-weight-residency` tip is exactly `b284e7fb` (parent `16835c0f`);
verified via `git fetch origin` + log. The force-push incident replaced the
tip for ~40 s with a same-content commit on the wrong parent (`1a79c130`,
parent `112c32c4`); the wrong-parent commit was never referenced anywhere
else and is now unreachable. Nothing else was on the branch between
`16835c0f` and `b284e7fb` except the one test-file deletion.

### 4. Landing implication unchanged

`16835c0f` remains a pure win: jwm1 launch hashing −66%, resident open
hashing 3.6–4.8×, zero digest movement anywhere, KATs 13/13 against the
deployed libmlx on both hosts. jw16 launch-mode neutrality is expected (its
ABC per-submit payloads are small); the win there is resident-open and any
future FFN-island use, where 96×8.4 MB hashing per pass was the cost.

## Landing receipt (final)

- `16835c0f` + `b284e7fb` **landed to mlx-omarchy main**: branch
  `land-sha256-crypto` cut from current `origin/main` (`2da5e052`,
  `63c1d3cf` asserted non-ancestor), cherry-picked, plus a third commit
  `88a0bc71` "encoder: assert the loaded libmlx identity before
  measuring" (the harness guard). Pushed fast-forward
  `2da5e052..88a0bc71` on main.
- Harness guard: `assert_mlx_binary_identity()` resolves the mapped
  libmlx from `/proc/self/maps`, records path+sha256+dist version, and
  hard-fails on `MLX_OMARCHY_EXPECTED_LIBMLX_SHA256`/`_PATH` mismatch.
  Deployed to the live scratch runners too (jwm1 `vk_resid.py`, jw16
  `vk_erev_o.py` + `vk_ffn.py`); mismatch smoke test exits non-zero on
  both hosts.
- Named finding: `receipts/2026-09-17-libmlx-identity-shadowing.md`
  (defect, guard, per-receipt contamination table). Separate
  observation: `receipts/2026-09-17-05015a76-gpu-matmul-regression.md`
  (the ~2.8x matmul regression shipped in the venv-cache build).
- Housekeeping: jw16 `vk_erev_o.py` diag instrumentation removed;
  `RESIDENT_BUNDLES` fix and `LD_LIBRARY_PATH` strip retained;
  llm-inference restarted and ACTIVE holding lock inode 12; jwm1 lock
  inode 35 free; module `1fc2e02` map_mode 3 on both hosts.
