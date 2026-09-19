# hk/agx-wait-batching-clean screened on jw16 against e1677564284 — digest-clean, perf-neutral: NO-LAND, left unmerged

Date: 2026-09-19. Lane: MesaWaitBatchScreen. Host: jw16mbp1-linux (Apple M1 Max T6001, G13C C0).
Repo: `github.com/joshuaswarren/mesa-1`. Box left in normal steady state (see §Steady state).

## Verdict: NO-LAND

The cleaned wait-batching series passes every correctness gate and moves
nothing: short decode +0.23% (inside noise), ctx1024 decode −3.57%
(inside the leg's ±5–10% wander band, driven by two low rows, not a
systematic shift), ctx prefill −0.15%, short prefill −0.11%. Gate leg
(short) passes; ctx1024 leg passes its floor (138.49 ≥ 134) but shows no
win. The land rule requires a measured win, so `hk/agx-wait-batching-clean`
stays unmerged. The branch is safe to revisit (digest-clean, test suite
intact).

## What was screened

- Baseline: `honeykrisp-omarchy` @ `e1677564284be72c663a65afeb6fd1d22cf45c17`
  (= SIMDMAT default-on restore + FTZ-pair reverts; the merged tip from the
  regression-decomposition lane).
- Candidate: baseline + the cleaned wait-batching series, cherry-picked
  byte-identical onto the baseline (content diff of the three series files
  vs `13d0bc50062628c64e17a2912d514ee06fad093b` is empty, 0 lines):
  `62b089eb844` (functional: region walk, lazy if/else merge, clamp-merge
  accounting, pop_exec close, drain elision, 2 slots) + `28c020a48a0`
  (4-test gtest suite + meson registration). Screen branch
  `hk/wb-screen-e1677564` @ `28c020a48a085166442db67f4a4e90176f9e26b6`
  (pushed), so the ONLY delta vs baseline is the wait-batching series.
- The pre-existing cleaned branch `hk/agx-wait-batching-clean` @
  `13d0bc50062628c64e17a2912d514ee06fad093b` (based on `d8d4e1c500b`) was
  NOT rebuilt directly: it predates the SIMDMAT restore + FTZ reverts, so a
  direct screen would have re-measured the −26% SIMDMAT cliff and the −8.6%
  FTZ residual instead of the series. The cherry-pick preserves the series
  content exactly while holding the tree at the current integration tip.
- Packages: `mesa-honeykrisp-omarchy 26.3.0.devel.hke167756-1` (prebuilt,
  source commit verified `e1677564284…`) vs
  `mesa-honeykrisp-omarchy 26.3.0.devel.hk28c020a-1` (built this lane on
  jw16, `makepkg -s -C -f`, source commit verified `28c020a48a0…`).
  Extracted ICD arms `/var/tmp/cb/pkg-base176` (`libvulkan_asahi.so`
  sha256 `0ffd1aa2…`) vs `/var/tmp/cb/pkg-wb28` (`a901780c…`).

## Test-suite presence check (the flagged risk)

The cleanup receipt flagged that the raw series had once REPLACED
`test-lower-parallel-copy.cpp` with `test-insert-waits.cpp` in
`meson.build`, silently dropping trunk's parallel-copy suite. Verified
restored in the screen tip:

- `meson.build` registers BOTH `test/test-lower-parallel-copy.cpp` AND
  `test/test-insert-waits.cpp`.
- `agx_tests` built clean and ran **58/58 PASSED** (8 suites): 4/4
  `InsertWaits.*` (RawHazardWaitsAtUse, SlotCapacityWaitsBeforeIssue,
  DivergentWawWaitsInElseArm, MergeReaderSeesCarriedPending) and 10/10
  `LowerParallelCopy.*` all `[ OK ]`.
- Had the suite still been missing, this would have been an automatic
  NO-LAND per the assignment. It is present. No stop was needed.

## Battery (interleaved A/B, one wheel pinned)

- Harness: `/var/tmp/cb/cb_ab_1deb.py` (derived from `cb_ab.py` with the
  libmlx pin updated `df3d4e74→6d61d44a` for the `1deb70f1` wheel and a
  `--wheel` provenance arg added), `bench_decode.py` sha
  `f5062d88f34b0845c1e59b0b35d2e33ae02180f636a0f65c543a4366ec2bef7f`,
  Qwen2.5-0.5B-Instruct-4bit @ `a5339a4131f135d0fdc6a5c8b5bbed2753bbe0f3`,
  wheel `mlx_omarchy-0.32.2.dev202609152131+1deb70f1`, 6 interleaved rounds
  per arm (alternating order), 32-token greedy legs, digest + libmlx pins
  fatal on every run. Trunk default `AGX_SIMDMAT=on`; no env override.
- Warmup digest gates 4/4 clean (both arms × both legs hit
  `7fd25a869ff21678` short 30/32 / `7da83f06ec9f001d` ctx1024 1053/32),
  and all 24 battery rows digest-clean (`rc=0`; any mismatch exits).
- One `/tmp/m1-gpu.lock` hold (inode 12); llm-inference stopped before,
  restarted after (see §Steady state).

| arm | short decode med (tok/s) | ctx1024 decode med (tok/s) | ctx prefill med (tok/s) | short prefill med (tok/s) |
| --- | ---: | ---: | ---: | ---: |
| base176 (`e1677564`) | 179.97 [175.64–180.29] | 143.61 [137.00–150.99] | 3872 [3553–3916] | 455.6 [451.0–456.2] |
| wb28 (`e1677564`+waits) | 180.39 (+0.23%) [177.49–181.09] | 138.49 (−3.57%) [127.14–144.90] | 3866 (−0.15%) [3822–3892] | 455.1 (−0.11%) [415.1–456.6] |

- Gate (short ≥ 175 AND ctx1024 ≥ 134 on the `1deb70f1` protocol): short
  PASS both arms (179.97 / 180.39); ctx1024 PASS both arms (143.61 /
  138.49). The candidate clears both floors — but clearing floors is not
  landing; there is no win on any leg.
- Prefill (the leg most likely to show submit-overhead movement): no
  movement (−0.15% ctx, −0.11% short, both inside noise).
- The ctx1024 −3.57% is not a systematic regression: the leg's round spread
  is ±5–10% on this box (the decomposition lane documents 134.2–144.0
  spreads and a 135.62 low draw on the same driver+wheel), and the wb28
  median is carried by two low rows (127.14, 131.37) against four rows
  ≥136.4. Drop either low row and the wb28 median rises to 140.56
  (−2.1%, still noise). The base arm's own rows span 137.0–151.0. A
  negative result cleanly proven is a success; no re-run is warranted
  (re-running until the wander favors you is p-hacking, and the prior raw
  series already read perf-neutral twice: +0.2% coopmat-off, −0.15%/+0.47%
  coopmat-on).

## Why NO-LAND rather than "neutral, land anyway"

Same rule that rejected device-load-coh7, fma-ceiling-unroll, and the raw
series: the land rule requires a measured win. A compiler change that
touches every shader's wait placement with zero measured benefit is risk
without return. Left unmerged; the branch stays screenable for a future
driver generation where barrier/wait economics change.

## Coordination

Shared jw16 with AneEncoderCoverage (ANE-side, queued next), plus
Bf16CompiledTape-2 (queued after) and F7GdnCorrectness-2 (no GPU need).
Order agreed over hub (me → AneEncoderCoverage → Bf16CompiledTape-2):
TAKE/RELEASE announced to all; both peers acked. First TAKE attempt failed
cleanly (service still held the lock; waiter killed, no state touched);
second TAKE succeeded after a verified `systemctl stop`. No lock stolen or
unlinked at any point. No `upstream/correctness*` touched. No jwm1/jw14m2
contact.

## Steady state (verified)

- `llm-inference.service` **active**; `/tmp/m1-gpu.lock` (inode 12) held
  only by the service's own ExecStart (`flock --nonblock` PIDs
  526821/526822, `llama-server`).
- Real completion verified post-restore: `chatcmpl-5XkV15mf5oZNnIeKFz2sw0BLIGBWCDEc`,
  16 completion tokens, qwen3.8-27b @ :8002.
- Installed driver untouched: `mesa-honeykrisp-omarchy
  26.3.0.devel.hk5deac1c-2` (packages were extracted to ICD arms, never
  installed; `pacman -Q` confirms).

## Artifacts

- jw16: `/var/tmp/cb/window-wb3.sh`, `/var/tmp/cb/window-wb3.log`
  (full 24-row battery + warmup gates), `/var/tmp/cb/ab-wb3.json`
  (rows+medians), `/var/tmp/cb/cb_ab_1deb.py`, `/var/tmp/cb/pkg-base176/`,
  `/var/tmp/cb/pkg-wb28/`, `~/src/mesa-pkg-jw16-waitclean-20260919/`
  (`mesa-honeykrisp-omarchy-26.3.0.devel.hk28c020a-1-aarch64.pkg.tar.xz`),
  `/var/tmp/cb/finished-wb3.txt`.
- mesa-1: `hk/wb-screen-e1677564` @ `28c020a48a0` (pushed; screen tip),
  `hk/agx-wait-batching-clean` @ `13d0bc50062` untouched,
  `honeykrisp-omarchy` @ `e1677564284` untouched (no merge — NO-LAND).
- Dev box: `/tmp/wt-wbscreen` (worktree) + `/tmp/wt-wbscreen-build`
  (compiler-only `agx_tests` build; disposable).
