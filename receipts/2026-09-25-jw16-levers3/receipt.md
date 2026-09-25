# 2026-09-25 — t6001-host (M1 Max) levers 3: launch-fusion merged to mlx-omarchy main; the 10x10 no-split battery FAILS (12/1000 records vs 1/1000 control); omarchy-ane 5a22ee3 (ane_boost) installed on T6001

Lane: Jw16Levers3 (successor of Jw16Levers2, receipt 124516a / dcbbb82).
Host: t6001-host (M1 Max T6001/G13C, Omarchy, kernel 7.1.6-1-1-ARCH),
single GPU owner; every GPU leg under `/tmp/m1-gpu.lock` with
`llm-inference.service` stopped and restored by the window trap with a
real completion (`artifacts/*/window-*.log`, `completion-*.json`).
Driver throughout: `/usr/local/lib/libvulkan_asahi.so.d3fa18e`
(sha `1e912d3e…`), system ICD unchanged. Serving venv
`/var/tmp/v072-venv-fused`: wheel `0.32.3.dev202609252013+1faf7f00`
(levers2 stack: 4-weight GEMV group + swiglu-eager + qgate-split, census
405 dispatches/token). Model `SiddhJagani/Qwen3.8-2B-mlx-4Bit`
@0867d98b; contract = 10 prompts, warmup 3, greedy, 32 new tokens,
prefill 512 (`~/bench-scripts/qwen38-mlx-bench.py`). Denominator (same
laptop, macOS, launch-sink2 row): decode 180.38 tok/s, prefill 1326.05,
TTFT 359.98, e2e 0.2081 s.

## 1. Step 1 — merge + the 10x10 interleaved battery

### 1.1 Battery (launched by Levers2, read here): no-split does NOT qualify

`artifacts/battery-10x10/contract-bat-{ctl,nosplit}-p10-{1..10}.json`,
each 10 passes x 10 prompts = 100 records, interleaved ctl/nosplit on
the installed candC stack. ctl = system ICD d3fa18e (a compute batch
split at every `vkCmdPipelineBarrier`, per-launch CDM barrier set
0x178). nosplit = mesa-1 41ccf96cc59 via `VK_DRIVER_FILES` (same
barrier set, the batch is kept open across barriers).

| arm | 10-pass legs | `dbf70497` pin | diverged legs | diverged records / 1000 | decode tok/s (median of legs) |
|---|---:|---:|---:|---:|---:|
| ctl (d3fa18e) | 10 | 9 | 1 | **1** | 78.6 (82.33 on leg 1 with the tests compile beside it) |
| nosplit (41ccf96) | 10 | 4 | 6 | **12** | 81.1 (+3.2%) |

Divergence positions (`artifacts/flips.py`, vs `bat-ctl-p10-1`):

- ctl: p10-10 `f7de0094` — pass 0 prompt 1 token 14 (18 positions).
- nosplit: p10-2 `454adf43` — pass 0 prompt 7 token 19 (13), pass 4
  prompt 8 token 5 (21), pass 7 prompt 8 token 14 (18); p10-4
  `d283c30f` — pass 5 prompt 8 token 0 (32); p10-6 `da67ca57` — pass 0
  prompt 4 token 25 (7), pass 0 prompt 7 token 15 (17), pass 4 prompt 8
  token 5 (21); p10-7 `3959e2ac` — pass 2 and pass 9 prompt 8 token 5
  (21 each); p10-8 `15526a5d` — pass 4 prompt 8 token 0 (32); p10-10
  `6e0a42f4` — pass 1 prompt 7 token 15 (5), pass 3 prompt 8 token 6
  (26).

Reading: the no-split driver multiplies the stack's divergence rate by
~12 and its dominant fingerprint — **prompt 8 from token 5, 21
positions** (4 of 12 records) — is exactly the 09-24 dep-skip lever's
fingerprint (launch-sink receipt §2.3: "pass 0/3, prompt 8, token 5, 21
positions"). The flips are not confined to pass 0 or prompt 7, so the
"pre-existing pass-0 prompt-7 near-tie" framing of the levers2 receipt
does not cover them; the installed driver's own 1/1000 (prompt 1 token
14) and the earlier c12461f2/a483d947 (prompt 7 tokens 15/19) are the
same population at a lower rate. Both levers that removed the
per-barrier batch split (no-split keeps every per-launch CDM barrier;
dep-skip also dropped barriers between unordered launches) land on the
same fingerprint, so the split's stream link + fresh chunk is doing
work the per-launch barrier set 0x178 does not do. Section 4 (step 4)
takes this apart with a logit-level pin instead of the token digest.

Verdict for the assignment's no-split candidate: **not installable**
(12 > 1). The +3.2% stays on the branch.

### 1.2 Standing omarchy battery on the installed ICD, then the merge

Tests built from the on-device worktree `/var/tmp/levers/mlx` @
152a41cd (`cmake --build .work/build-tests -j8 -- -k`; the
`omarchy_ane_runtime_tests` link (`AneRuntime::load` undefined) is a
pre-existing ANE-surface build gap, excluded). Window
`artifacts/tests/window-20260925T210406Z.log`: 31 suites PASS, 0
failed (matmul_family 82,940,463 assertions, fast_ops 1,104,350,
fused_chain, sdpa_decode_fused, sdpa_causal_ragged, primitive 103
cases, runtime 41, ane_bundle 34, …); capability_sim profiles
m1-honeykrisp-fork, m1-stock-no-coopmat, subgroup-size-64,
small-shared-memory, no-cooperative-matrix all PASS (2460-2462
assertions each). The one "FAIL" row is the capability_sim binary run
without a profile argument (usage exit 2), not a test failure
(`artifacts/tests/suite-tails.txt`).

Merged: **mlx-omarchy main `bfe2ddc6d`** = merge of
`agent/jw16-levers2` @ 152a41cdb onto 27aba5211 (Jwm1Parity7's small-M
coopmat tile, primitives.cpp only, no overlap; pushed). Pins carried
into the merge message: bc519c03 3-pass, dbf70497 10-pass 9/10 with
the 1/1000 record above named.

## 2. ANE step (Main directive): omarchy-ane 5a22ee3 on T6001

- Built on the device from `/var/tmp/levers3/omarchy-ane` (worktree of
  the device clone at 5a22ee388e43…, `make` in `ane/`, 3 s):
  `ane.ko` version `v0.1.0-605-g5a22ee3`, sha `cf1d4bf135da7b03`,
  `parm: boost_idle_ms` present. Installed persistently at
  `/usr/lib/modules/7.1.6-1-1-ARCH/updates/ane.ko` (previous
  `v0.1.0-593-ga9a5f60` kept as `ane.ko.a9a5f60`), `depmod -a`, reloaded
  (`rmmod`/`modprobe`): `/sys/module/ane/version` = g5a22ee3,
  `boost_idle_ms=100`, `map_mode=3`, `dart_contain=Y`
  (`artifacts/ane/install-killrace.log`).
- **kill-race battery**: `test/kill-race/main.out 10` → `KILL-RACE:
  PASS (10 iterations, no poisoned ranges)`, 10/10 "ok kill + reopen +
  bo_init", 84 s (`artifacts/ane/kill-race.log`).
- Guard check (`test/guard make check`): the verdict-vector half passes
  ("all power-guard checks passed"); the awk source-anchor half fails
  identically on a9a5f60 (the previously installed tree) — a stale test
  anchor, not a 5a22ee3 regression.
- As df23ca9's own validation order says, a T6001 kill-race leaves the
  TM parked (dmesg: "recovery failed; preserving resources until
  module reload or reboot", then "out of ANE space: -28" for every
  later open): the first Parakeet contract attempt right after the
  battery failed at its first island submit (`ane_exec failed for
  program 0`, `artifacts/ane/parakeet-contract-wedged.out`). Module
  reload (`rmmod`/`modprobe`, no reboot) revived it: whole-encoder
  worker 2 iterations status=0, hidden16 `fca96f1355485ec3` (the
  certified-capture anchor). The contract and the boost A/B were then
  run on the reloaded module (§2.1, §2.2).

### 2.1 Full Parakeet const-cache contract on the reloaded 5a22ee3 (boost_idle_ms=100)

`/var/tmp/parakeet-recover/run-contract.sh` (own service stop/restore,
flock, smoke + 3 measurements; `artifacts/ane/contract/`):
**all_green: True** — mel `5b54f4a9`, hidden `38c73261`, transcript
`db501a8c` bit-exact on all four runs, status match,
matching_prefix_length 104. Stage medians (ms): mel_frontend 140.3,
encoder_ane 1440.4, decoder_load 55.0, tdt_decode 555.9, detokenize
49.9, total 2248.2 — against the last a9a5f60 battery on this box
(12:21 CDT, no boost): encoder_ane 1614.4, decoder_load 76.5, total
2427.5 (uncontrolled comparison; the controlled one is §2.2).

### 2.2 boost_idle_ms=100 vs 0, interleaved 3 reps (`artifacts/ane-ab/`)

Inside one window (service stopped, lock held), the parameter toggled
through `/sys/module/ane/parameters/boost_idle_ms` between legs;
`scaling_cur_freq` of the three cpufreq policies sampled every 50 ms
during every leg (`freq-*.txt`); every leg's outputs gate-checked
(`gates.txt`: all six pipeline runs bit-exact, prefix 104; every
encoder leg hidden16 `fca96f1355485ec3`).

| leg | boost 100 | boost 0 |
|---|---|---|
| whole-encoder single submit, slope (n32 - n1)/31 ms/iter | 439.8 / 440.8 / 441.4 | 441.0 / 440.7 / 441.0 |
| P-cluster clock during the n32 leg (share of samples at 3036 MHz / median MHz) | 25-50% / 1980-3036 | 1-4% / 1056 |
| pipeline encoder_ane ms | 1439.5 / 1438.3 / 1437.5 | 1768.0 / 1644.0 / 1640.3 |
| pipeline decoder_load ms | 54.3 / 52.6 / 53.1 | 76.7 / 76.3 / 80.8 |
| pipeline tdt_decode ms | 565.0 / 549.2 / 552.8 | 573.5 / 549.9 / 564.7 |
| pipeline total ms | 2249.9 / 2226.7 / 2234.6 | 2611.8 / 2465.9 / 2475.0 |
| P-cluster clock during the pipeline leg | 55% at 3036 / median 3036 | 2% / ~1056 |

- The M1 Max whole-encoder single submit does **not** move: 440 ms/iter
  either way (vs macOS 158; the 2.8x gap stays open and is not a CPU
  clock effect). Mechanism, from the driver: `ane_boost_kick` runs at
  submit, so one 14.7 s submit is boosted for `boost_idle_ms` (100 ms)
  and the QoS is dropped while the engine is still busy — the sampler
  shows the clusters back at low p-states for most of the leg. And the
  encoder is compute-bound, as on T8103.
- The submit-dense Parakeet pipeline moves: encoder stage **1640 → 1438
  ms (-12.4%)**, decoder_load 77 → 53, total **2475 → 2235 ms (-9.5%)**,
  medians, all six runs bit-exact. This is the T8103 mechanism (island
  submits stalled by cluster p-states) on T6001.
- Sent to AneDocKeeper (folded into omarchy-ane main 19dfcd8, section 19).
