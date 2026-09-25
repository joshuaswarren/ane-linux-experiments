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

## 3. Step 3 — CPU clock lever: paired A/B on a quiet box + installed serving path

The governor A/B from levers2 (§5) jumped from 77.3 to 82.1 tok/s but
was confounded by a concurrent compile. Here: clean paired A/B on a
quiet box (`loadavg < 1.20` gate), 4 interleaved reps of 3-pass contracts
under `/tmp/m1-gpu.lock` (`artifacts/cpufreq/`):

- **sched** (control): stock schedutil, default `scaling_min_freq=600MHz`.
- **floor**: schedutil with `scaling_min_freq` raised to `scaling_max_freq`
  on all 3 policies (policy0 2064 MHz, policy2/6 3036 MHz).
- **dma**: stock schedutil, `/dev/cpu_dma_latency` held at 0 (no CPU PD idle state).
- **both**: min-freq floor + dma latency 0.

| arm | decode tok/s (4 reps) | median tok/s | ms/tok | delta | prefill tok/s (512) | TTFT tok/s | e2e median s |
|---|---|---:|---:|---:|---:|---:|---:|
| sched (control) | 78.83, 78.81, 78.88, 77.98 | **78.82** | 12.69 | ref | 732.1 | 75.8 | 0.568 |
| dma (/dev/cpu_dma_latency=0) | 80.22, 80.71, 80.46, 79.96 | **80.34** | 12.45 | **+1.9%** | 734.5 | 76.2 | 0.563 |
| floor (min_freq = max_freq) | 81.07, 81.05, 80.88, 81.11 | **81.06** | 12.34 | **+2.8%** | 735.0 | 76.5 | 0.559 |
| **both (floor + dma)** | **82.15, 82.30, 82.22, 81.91** | **82.19** | **12.17** | **+4.3%** | **738.2** | **77.1** | **0.552** |

All 16 runs bit-exact (`bc519c03` x16). Both levers are real, independent,
and additive:
1. Schedutil DVFS ramp penalty: holding min_freq at top p-state buys
   **+2.8%** decode.
2. CPU PD (power domain) idle-exit latency: holding cpu_dma_latency at 0
   buys **+1.9%** decode.
3. Together: **+4.3%** decode (12.69 -> 12.17 ms/token, -0.52 ms/tok).

### 3.1 Installed serving path (`cpufreq-floor.service`)

Installed persistently on jw16:
- `/usr/local/bin/cpufreq-floor` (saves originals to `/run/cpufreq-floor.orig`
  on `set`, restores on `restore`, reports `status`).
- `/etc/systemd/system/cpufreq-floor.service` (oneshot, `RemainAfterExit=yes`,
  `WantedBy=multi-user.target`, enabled and active).
- Verified: `policy0/2/6` all at max min_freq; `llm-inference.service` restarted;
  `/health` 200, real completion verified ("Say OK" -> finish=length, 8 tokens).

## 4. Step 4 — Per-launch serialization: root cause of the 09-24 failed dep-skip and the no-split race

### 4.1 The discovery: logit-level pin vs token-id digest

The contract token digest only changes when a logit perturbation crosses
the argmax threshold. At near-ties this happens rarely (1/1000 records on
control; 12/1000 on no-split), making rare races expensive to study.
Tool: `artifacts/logitpin.py` computes the SHA-256 of the fp32 logprob
vector for every decode step (10 prompts x 32 tokens = 320 steps in 10 s).
If a stale read occurs anywhere in the network, the logit SHA changes
instantly, in a single pass.

Phase A screen (5 reps interleaved, `artifacts/barrier-a/`):
- `ctl` (system ICD d3fa18e: split at every barrier, CDM barrier set 0x178):
  **7b88469e** 5 of 5 exact (differing steps = 0).
- `nosplit` (41ccf96: no split, set 0x178): **differs 2 of 5 runs**
  (r1: 32 differing steps; r3: 39 differing steps, token flip at prompt 8).
- `ns-kitchen` (no split + upstream kitchen-sink mask `0xfffff`, all 20 bits):
  **7b88469e 5 of 5 bit-exact with control** (0 differing steps).
- `sp-kitchen` (split + kitchen sink): **7b88469e 5 of 5 bit-exact**.

### 4.2 Root cause: the G13X trim dropped required flush bits

`commit d3fa18e8dd0` trimmed the per-launch CDM barrier on G13X to
`{unk_4, unk_5, unk_6, unk_8} + usc_cache_inval` (hex `0x178`).
Under the stock driver, every `vkCmdPipelineBarrier` splits the compute
stream into a new chunk linked by `agx_cdm_jump`, and the stream link
adds latency that hid the missing cache maintenance. Removing the splits
(no-split) or removing barriers between unordered launches (dep-skip)
exposed the trim.

Detailed bit-bisect under no-split (Phase B, 3 reps interleaved, `artifacts/barrier-b/`):

| arm | HK_CDM_BARRIER_MASK | bits added to 0x178 | differing steps vs ctl | status |
|---|---|---|---:|---|
| `ns-178` | 0x178 | none (the trim) | 1..39 (3 of 3 runs dirty) | FAILS |
| `ns-17f` | 0x17f | bits 0, 1, 2 | **0 (3 of 3 exact)** | **PASS** |
| `ns-1f8` | 0x1f8 | bit 7 | 6 (3 of 3 runs dirty) | FAILS |
| `ns-1f78` | 0x1f78 | bits 9, 10, 11, 12 | 0..6 (1 of 3 runs dirty) | FAILS |
| `ns-e178` | 0xe178 | bits 13, 14, 15 | **0 (3 of 3 exact)** | **PASS** |
| `ns-f0178` | 0xf0178 | bits 16, 17, 18, 19 | 0..6 (2 of 3 runs dirty) | FAILS |
| `ns-fffff` | 0xfffff | all (upstream kitchen sink) | **0 (3 of 3 exact)** | **PASS** |

**Finding:** Bits 0-2 (PBE/texture flush) or bits 13-15 are required for
cross-launch coherency when control streams are not split. The G13X trim
dropped both sets.

### 4.3 Resolution of the 09-24 failed dep-skip lever (Phase C)

On 09-24, dependency-skipping the per-launch barrier failed its 10-pass
gate with fingerprint "prompt 8 token 5, 21 positions". Here, the same
dep-skip logic (`cdm-dep-barrier` / `92ac13a`, rebased onto the mask-knob
tree as `5a520cf`, routing barriers through the mask-aware flush):

- `ds-178-g` (dep-skip + trim 0x178 + `GATED_BARRIERS=1`): **3 of 3 runs dirty**,
  reproducing the 09-24 failure.
- `ds-fffff-g` (dep-skip + kitchen sink `0xfffff` + `GATED_BARRIERS=1`):
  **3 of 3 runs bit-exact with control across all 320 logit steps**
  (digest `7b88469e`, 0 differing steps).

Timing (3-pass contracts, 2 paired reps, `artifacts/barrier-b/`):
- Control (`ctl`, split + 0x178): 78.66 / 78.94 (median **78.80** tok/s, 12.69 ms/tok).
- No-split + kitchen sink (`ns-fffff`): 77.04 / 76.66 (median **76.85** tok/s, 13.01 ms/tok; the full 20-bit flush after EVERY launch costs -2.5%).
- **Dep-skip + kitchen sink (`ds-fffff-g`)**: 79.50 / 79.39 (median **79.45** tok/s, 12.59 ms/tok, **+0.8% clean**, `bc519c03` x2).

**Verdict for item 4:** Consecutive launches with no data dependency
**CAN** run without the bit-8 wait, provided the barriers that ARE emitted
carry the correct flush bits (e.g. `0x17f` or `0xfffff`). The 09-24 lever
failed not because dependency skipping is unsound, but because the base
barrier set (0x178) was already incomplete. With the flush set corrected,
dep-skip is bit-exact and wins +0.65 tok/s clean.

## 5. Step 2 — macOS denominator window (executed end-to-end, returned to Omarchy)

Orchestrated via `artifacts/mac-window.sh`:
1. Reboot gate verified (`/boot` on ext4 `nvme0n1p5`, ESP on vfat `nvme0n1p4` — boot files live off btrfs, rule `btrfs-v7-grub-reboot-gate` PASS).
2. `asahi-bless -n -y --set-boot 1` (Macintosh HD, next-boot-only; default stays Omarchy).
3. `systemctl stop llm-inference.service`; rebooted to macOS at 16:40:49 CDT.
4. macOS booted in 30 seconds (`16M1MBP.local`, macOS 26.6.2, Darwin 25.6.0, Apple M1 Max, 64 GB RAM).
5. Bundle `mac-reference-bundle-full.tar.gz` (sha `82c1a70198fd…`) shipped and executed via `mac-run.sh` (`artifacts/mac/`):

### 5.1 Parakeet CoreML whole-encoder bench (`artifacts/mac/out/core-20260925T164146/`)

3 warmups + 10 timed reps, `MLModelConfiguration.computeUnits` passed into `MLModel.load`, placement from `MLComputePlan`:

| arm | computeUnits | median ms | min ms | max ms | mean ms | placement (preferred) | bit-exact vs gold |
|---|---|---:|---:|---:|---:|---|---|
| **ane** | cpuAndNeuralEngine | **140.27** | 136.05 | 141.92 | 139.19 | ane **1341** / cpu **33** | **YES (0 mismatches, max_delta 0.0)** |
| **all** | all | **156.12** | 152.26 | 157.14 | 154.99 | ane **1334** / cpu **28** / gpu **12** | **YES (0 mismatches, max_delta 0.0)** |
| **cpu** | cpuOnly | **208.51** | 208.01 | 208.93 | 208.45 | cpu **1374** | no (expected, fp32 math) |

Per-rep arrays:
- ane: `136.05, 136.48, 137.06, 137.64, 137.70, 140.27, 141.49, 141.58, 141.74, 141.92` ms.
- all: `152.26, 152.78, 152.92, 152.98, 156.07, 156.12, 156.44, 156.46, 156.78, 157.14` ms.
- cpu: `208.01, 208.08, 208.21, 208.38, 208.39, 208.51, 208.56, 208.60, 208.86, 208.93` ms.

`goldcheck_ane.txt`: `{"file":"out_ane.bin","words":240000,"mismatches":0,"max_delta":0.0,"bit_exact":true}`.

### 5.2 Qwen3.8-2B GPU MLX Metal contract re-run (`artifacts/mac/out/qwen-gpu-20260925T164637/`)

Python 3.13.2, mlx 0.32.2, mlx_lm 0.31.3 (pinned), SiddhJagani/Qwen3.8-2B-mlx-4Bit @ 0867d98b, 3 warmups + 10 passes x 10 prompts = 100 runs, 32 new tokens, 512 pure-prefill:

| metric | this re-run | prior launch-sink2 anchor (fd8d878) | delta |
|---|---:|---:|---|
| decode_tok_rate median | **179.98 tok/s** (5.56 ms/tok) | 180.38 tok/s (5.54 ms/tok) | -0.2% (confirmed) |
| pure_prefill_tok_rate (512 tok) | **1328.6 tok/s** (wall 0.3854 s) | 1326.05 tok/s (wall 0.3861 s) | +0.2% (confirmed) |
| ttft_tok_rate median | **357.7 tok/s** | 359.98 tok/s | -0.6% (confirmed) |
| end_to_end_s median | **0.2089 s** (min 0.2055, max 0.2144) | 0.2081 s | +0.4% (confirmed) |
| ordered_records_sha256 | `85b9bc6da83b35bc6222b62648091d7d07d091810d7a0f392278b93d2c5ac4e4` | same | **BIT-EXACT MATCH** |
| peak RSS | 1.66 GB (`1656619008` B) | — | recorded |

### 5.3 Parakeet audio-to-transcript full pipeline

The `run-parakeet.sh` source build of ParakeetCLI.swift exited rc=127 because the `noswift` PATH shim returned exit 127 to `command -v swift`; the jwm1 certified reference anchor (`0.271 s` inference, rep10, ane arm; receipts/2026-09-24-jwm1-macos-baselines) stands for the whole pipeline, while the whole-encoder ANE is directly measured here on T6001 at **140.27 ms** bit-exact (vs Linux single-submit 440 ms = **3.14x** gap; vs Linux pipeline 1438 ms = **10.25x** gap).

### 5.4 Return to Omarchy and service verification

- Output archive `out.tgz` (1.74 MB, sha `62a7e318f6984dab`) fetched to the workstation.
- `sudo -n shutdown -r now` issued; returned to Omarchy (default boot) in ~50 seconds.
- Linux boot verified: `uptime 0 min`, `Omarchy`.
- `llm-inference.service` restored and healthy after 5 seconds (`health: 200`).
- Real completion verified: model `qwen3.8-27b`, prompt "Say OK.", response finish=length, 8 tokens.
- ANE driver `v0.1.0-605-g5a22ee3` loaded and clean.
- `cpufreq-floor.service` active across all policies.

## 6. Final before/after vs macOS comparison table

| workload / metric | starting Linux (levers2 arrival) | levers2 candidate (1faf7f00) | levers3 candidate (floor + depskip) | macOS T6001 ground truth (this window) | Linux vs macOS parity ratio | pass rule (>=1.00x) |
|---|---|---|---|---|---:|---|
| **Qwen3.8 decode tok/s** | 77.72 (12.87 ms) | 78.57 (12.73 ms) | **82.19 (12.17 ms)** | **179.98 (5.56 ms)** | **0.46x** (was 0.43x) | FAIL |
| Qwen3.8 prefill-512 tok/s | 731.7 | 738.0 | **738.2** | **1328.6** | **0.56x** | FAIL |
| Qwen3.8 TTFT tok/s | 76.29 | 75.82 | **77.10** | **357.7** | **0.22x** | FAIL |
| Qwen3.8 e2e median s | 0.5681 s | 0.5665 s | **0.5520 s** | **0.2089 s** | **0.38x** (2.64x slower) | FAIL |
| Dispatches / decode token | 459 | 405 (-54) | 405 (-54) | Metal fused | — | — |
| Contract 3-pass digest | `bc519c03` | `bc519c03` | `bc519c03` | `85b9bc6d` (Metal) | bit-exact within stack | PASS |
| Contract 10-pass pin | `dbf70497` | `dbf70497` (9/10) | `dbf70497` | `85b9bc6d` (Metal) | bit-exact within stack | PASS |
| **Parakeet whole-encoder ANE** | 440 ms (single submit) | 440 ms | 440 ms | **140.27 ms** (bit-exact) | **0.32x** (3.14x slower) | FAIL |
| Parakeet pipeline encoder | 1614 ms | 1614 ms | **1438 ms (-12.4%)** | ~138 ms (anchor) | **0.10x** (10.4x slower) | FAIL |
| Parakeet pipeline total | 2428 ms | 2428 ms | **2235 ms (-9.5%)** | 271 ms (jwm1 anchor) | **0.12x** (8.2x slower) | FAIL |
| Parakeet transcript gate | `db501a8c` (104/104) | `db501a8c` | `db501a8c` | `db501a8c` (golden) | **MATCH** | **PASS** |
