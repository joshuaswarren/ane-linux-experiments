# jw16 step 1 — corrected CDM-barrier flush set + dep-skip: 10x10 battery PASS, installed (2026-09-25)

Owner: Jw16Levers5 (resumed Jw16Levers4, which died mid-battery on a model-quota
error; its orphaned battery process turned out to be still alive on jw16 and was
allowed to finish — window.sh pids 3660/3679 survived, flock held, correct venv
`/var/tmp/v072-venv-fused`).

## What was installed (and why)

The previously installed ICD driver `d3fa18e8dd0` carried a per-launch CDM
barrier trim of `0x178`: flush bits 0-2 (PBE/texture) and 13-15 dropped. The
09-24 stock driver's stream splits masked the missing flush; under no-split or
dep-skip scheduling, prefill of prompts 7/8 produces stale reads (logit deltas
0.125-0.25) that cascade into the argmax token-tie at prompt 8 token 5 (the
09-24 dep-skip fingerprint; root cause per receipts/2026-09-25-jw16-levers3,
step 4, logitpin.py).

Candidate = branch `agent/jw16-flush17f-depskip` (joshuaswarren/mesa-1), tip
`2a9762ef6ec`, two commits on the no-split base `2aefdd576f0`:

- `5a520cf3d35` asahi: dependency-track the per-launch CDM barrier on the
  Vulkan path (dep-skip lever; default path, keyed on vkCmdPipelineBarrier2)
- `2a9762ef6ec` asahi: restore bits 0-2 (0x17f) in per-launch CDM barrier for
  G13X (designed set {0,1,2,4,5,6,8} + USC cache invalidate)

Diff vs installed: 6 files, +86/-17 (`artifacts/step1/flush17f-depskip.diff`).
Build: `/var/tmp/levers/mesa-nosplit` build-rel,
`libvulkan_asahi.so` sha256 `bcbf6cbb2809fa7af8cb39edd2cddf142a99b44b53efcf93a3c0dd3f168e5ab0`.

## Battery: interleaved 10x10-pass, ctl (installed d3fa18e) vs candidate+env

10 interleaved pairs, each contract = 10 passes x 10 prompts = 100 records,
greedy, 32 new tokens, 512-token prefill (`qwen38-mlx-bench.py`).

**Result: 20/20 contracts digest `dbf70497`, diverged=0 everywhere
(`artifacts/step1/flips-summary.txt`).** The candidate holds bit-exact with 0
extra divergences vs control.

| arm | decode tok/s (range) | e2e_med s (range) | digest |
|---|---|---|---|
| ctl (d3fa18e, no env) | 80.88 - 81.18 (12.32-12.36 ms/tok) | 0.5418 - 0.5462 | dbf70497 x10 |
| flush17f+depskip (env) | 83.55 - 83.77 (11.94-11.97 ms/tok) | 0.5326 - 0.5412 | dbf70497 x10 |

Median decode +3.2% (83.6 vs 81.0 tok/s); prefill 739-759 vs 733-752 tok/s
(within noise); ttft 77.7-82.1 vs 79.2-81.6.

Part 2, standing omarchy battery on the candidate ICD: **31 suites + 5 capsim
profiles PASS (35 PASS lines)**. The single `battery omarchy_capability_sim_tests:
FAIL rc=2` is the harness invoking the capsim runner without a profile argument
(usage error rc=2, artifact of `body-step1-battery.sh`'s loop; all 5 real capsim
profiles — m1-honeykrisp-fork, m1-stock-no-coopmat, subgroup-size-64,
small-shared-memory, no-cooperative-matrix — PASS). Same artifact existed in the
aborted first window run; not a driver failure.

Note: the first battery window (22:04:54Z) ran Part 1 with a stale VENV (bench
produced no JSONs — the FileNotFoundError spam in
`window-20260925T220454Z.log`), was fixed by pointing VENV at
`/var/tmp/v072-venv-fused`, and its Part 2 on the candidate ICD had already read
pass=35 fail=1 (same capsim artifact). The authoritative run is
`window-20260925T220722Z.log`.

## Install (verified)

- `install-flush17f.sh`: ICD `/usr/share/vulkan/icd.d/asahi_icd.aarch64.json`
  `library_path` now `/usr/local/lib/libvulkan_asahi.so.flush17f-2a9762e`.
- Installed binary sha256 `5df98d0c3ac505adbfcb35e70141bb8cd6947662c1b32e73c5f671425aa76ebe`
  (rebuild after the identifier scrub below; the battery-era bytes were
  `bcbf6cbb…`). Mesa's link is non-deterministic: two rebuilds of the identical
  source tree produced different .so hashes (`5df98d0c…`, `522d90e3…`), so the
  pinning chain is source tree (git sha) + behavioral contract
  (`dbf70497` in both env modes), verified on two independent builds — the 20/20
  battery on the `bcbf6cbb…` build and the post-scrub smoke on `5df98d0c…`.
  Prior control `/usr/local/lib/libvulkan_asahi.so.d3fa18e` (sha `1e912d3e…`)
  left on disk for revert (rewrite the ICD library_path back).
- Post-install smoke on the SYSTEM ICD (no VK_DRIVER_FILES override), 10 passes:
  - no env: digest `dbf704971617fdfcf693c4287b9f0403ee24a2b2c5d3a9fb4d2a032d613c9596`,
    decode 80.66 tok/s — PASS
  - MLX_OMARCHY_GATED_BARRIERS=1: digest `dbf70497…`, decode 82.38 tok/s — PASS
  Both serving modes of the installed driver are bit-exact. The +3% decode is
  realized with the gated-barriers env set (the mlx-side lever); the default
  path ≈ control speed, bit-exact.

## Push (privacy-hook compliant)

The candidate commits originally carried fleet identifiers (the `5a520cf3d35`
message cited the private `2026-09-23-jw16-usc-cdm-barrier-bisect` receipt, and
`libagx_dgc.h` line 400 said "decode on jwm1"). Scrubbed via rebase: message
now reads "(measured: …)", the comment "on the reference M1". Scrubbed lineage:
`745084fc6ea` (dep-skip) → `8d4e214b2d79` (0x17f).

Per Main's directive (route b, as Jw16GpuLevers), the push went as a
**fast-forward of the existing origin ref** `jw16/usc-barrier-study`
(41ccf96cc59 — the origin-side copy of the no-split base), avoiding the new-ref
full-history hook scan (which on mesa is ~200k commits and fail-closed). The
origin branch carried a parallel `maskcdmbarrier` knob (549ddbb8a7d) not
present in the battery-verified tree; the FF branch cherry-picks the two
scrubbed commits and drops that knob (c32ffddc8bb), making its tree
byte-identical to `8d4e214b2d79` (verified: `git diff` empty). The hook's range
scan `41ccf96cc59..c32ffddc8bb` returned **clean** before the push.

- **Pushed: joshuaswarren/mesa-1 `jw16/usc-barrier-study` 41ccf96cc59 →
  `c32ffddc8bb`** (3 commits: dep-skip, 0x17f restore, knob removal).

## Service state

window.sh cleanup restored llm-inference at 17:29:04 (poll #2: 8002 ok,
completion probe finish_reason=length, `service healthy=1`).

## Artifacts

`artifacts/step1/`: `contracts.txt` (20 rows + battery summary),
`flips-summary.txt` (20 legs, diverged=0), `window-20260925T220722Z.log`
(authoritative), `window-20260925T220454Z.log` (aborted first window),
`contract-bat-ctl-p10-1.json`, `contract-bat-flush17f-p10-1.json`,
`contract-bat-flush17f-p10-10.json`, `flush17f-depskip.diff`,
`flush17f-commits.txt`, `icd-after.json`. Raw dirs on jw16:
`/var/tmp/levers3/step1-battery/`, `/var/tmp/levers5-install/`.
