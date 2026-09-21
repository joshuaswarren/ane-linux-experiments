# jw14m2-linux MLX/Vulkan decode+prefill baseline — wheel 5b18306, fixed harness, stock Honeykrisp 26.2.3 (2026-09-20)

Verdict: **BASELINE RE-ESTABLISHED (first VALID perf numbers post-invalidation).** All five legs ran under
`/tmp/jw14-bench/gpu.lock` on an otherwise idle box (load ≤0.95), ≤10-min legs, compileON==compileOFF
**bit-exact on both prompts** (ID digests), A/A deterministic. Decode/prefill numbers below are produced by
the v2 fixed harness (`8a821aba…`, summary event excluded from BOTH numerator and denominator), so they
replace the invalidated Phase A/B columns (`2026-09-20-jw14m2-phaseB-a1251-correctness-gate.md`).

## Context

- Mesa sin-FTZ fix `095cb7e1` ("agx: return a flushed signed zero from sin under DenormFlushToZero",
  landed 2026-09-20T16:31:09Z in `joshuaswarren/mesa-1`) is **NOT staged on jw14m2-linux**: no mesa build
  tree, no ICD/loader override, no honeykrisp-omarchy package — host runs stock `mesa 1:26.2.3-1` +
  `vulkan-asahi 1:26.2.3-1` (DRIVER_ID_MESA_HONEYKRISP, API 1.4.354 — the same driver/vintage as the
  2026-09-18 third-device baseline). Per delegation, the existing MLX/Vulkan baseline with exact pins was
  executed instead.
- jw14m2-linux rebooted 2026-09-20 ~16:23 (h14 first-boot fault, boot lane). The wipe took the Phase A/B
  `/tmp/jw14-bench` (venv, lock, harness copies, raw receipt JSONs — committed receipts survive). This
  session rebuilt the bench area from repo-pinned artifacts; **zero downloads, zero system installs**
  (all pip deps were pip-cache hits, `Downloading` count = 0, verified in `logs/pip-deps.log`).

## Exact pins

| item | value |
| --- | --- |
| host | jw14m2-linux, kernel `7.1.13-3-1-ARCH`, M2 Max (G14C B1), `/dev/dri/renderD128` |
| driver | stock mesa/vulkan-asahi `1:26.2.3-1`, Honeykrisp, API 1.4.354, conformance 1.4.0.0, deviceUUID `3bacad71-…` |
| wheel | `mlx_omarchy-0.32.3.dev202609201440+5b18306-cp314-cp314-linux_aarch64.whl`, sha256 `fe51534b1ed658f64f2e16f5ce4709c27cbb1c683388b50a2d04eacf6b362a01` (local worktree build; supersedes Phase B's a1251aaa) |
| installed libmlx.so | sha256 `c28a485f98b55aadf12c68ae6d373f308517177c0cf33ad3c77ea82a796e931e` — byte-equal to the wheel member (fork wheel re-seated LAST after pip pulled upstream `mlx==0.32.2` as mlx-vlm dep; the overwrite hazard is real and must be re-checked after every dep install) |
| venv | `/tmp/jw14-bench/venv` (system python 3.14.7); pins: mlx-omarchy 5b18306, mlx-lm 0.31.3, mlx-vlm 0.7.1, transformers 5.17.0, numpy 2.5.3, tokenizers 0.23.2, huggingface_hub 1.32.0, safetensors 0.8.0 (full freeze in evidence) |
| model | `mlx-community/Qwen3.8-27B-4bit` snapshot `10c35caafbb80f7dc6a7a432cdd11af10a6d4818` (HF cache, offline) |
| harness | `bench_decode_vlm.py` v2 sha256 `8a821aba9b2bb2ed4897eec54020cc7326a5a3677d45ff98a254ce86ad478b05` (repo copy `receipts/2026-09-20-final-harness-bench_decode_vlm.py`; self-test PASS: rate=(n-1)/(last-first) over real decodes, summary event excluded from ids and rate) |
| matrix | `bench_matrix.json` sha256 `df8eb9f3…` (unchanged pin); companions `caps_sim_guard.py`, `mlx_provenance.py` from `.local/ane-v064-wt/scripts/` |
| protocol | `HF_HUB_OFFLINE=1`, temp 0 seed 0, `--warmup-tokens 4`, `--stop-policy ignore-eos`, `--tokens 128`; compileON = `env -u MLX_DISABLE_COMPILE`, compileOFF = `MLX_DISABLE_COMPILE=1`; fresh process per leg; `flock -n` held on `/tmp/jw14-bench/gpu.lock` across each leg |

## Results (fixed harness — VALID; supersedes Phase A/B rate columns)

| leg | prompt | mode | decode tok/s | prefill s | prefill tok/s | prompt_tokens | ids sha256_16 (n=128) | wall |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | long (245) | compileON | 4.485 | 18.55 | 13.21 | 245 | `735b8de2664c8d87` | 81 s |
| 2 | long (245) | compileOFF | 4.3817 | 19.64 | 12.48 | 245 | `735b8de2664c8d87` | 77 s |
| 5 | long (245) | compileON A/A | 4.4949 | 18.90 | 12.97 | 245 | `735b8de2664c8d87` | 75 s |
| 3 | ctx1024 (1036) | compileON | 4.2985 | 76.82 | 13.49 | 1036 | `0e0c0824d8ae2bce` | 194 s |
| 4 | ctx1024 (1036) | compileOFF | 4.1803 | 77.92 | 13.30 | 1036 | `0e0c0824d8ae2bce` | 196 s |

- **ON==OFF bit-exact** on both prompts (`735b8de2664c8d87` ×3, `0e0c0824d8ae2bce` ×2); the bf16
  compiled-tape refusal stays absent on 5b18306. Both digests are identical to the Phase B (a1251aaa)
  digests — the 128-token ID sequences are stable across wheels a1251aaa → 5b18306.
- Compiled path: ~+2.4% decode (long), ~+2.8% (ctx1024); prefill parity. Single-run first-indication only —
  no parity/divisor claim, no cross-host comparison.
- Summary-event semantics: `summary_events=1` on every leg, correctly excluded (engine `bench_decode_vlm_v2`).

## Coordination

- `M2BootImplementation` (sole boot/recovery owner, jw14m2) approved the window in-band ("no collision:
  proceed"); constraints honored: no touch of `/var/tmp/ane-t6021-6be485f`, `/var/tmp/ane-w15-fault-capture/`,
  ANE MMIO/pmgr sysfs, no `ane*`/netconsole module loads. GPU yields at their boot boundary.
- `ServePerformanceAudit` (jw16 window) and `GPUparityroot-causeaudit` (jwm1/jw16 lanes) confirmed zero
  jw14m2 overlap.

## Artifacts

- Host (volatile `/tmp/jw14-bench/`): `logs/leg{1,2,3,4,5}-*.log` (full rtmod traces), `results/all-legs.jsonl`,
  `evidence/env-provenance.txt`, `leg-logs.tgz`, `logs/wheel.sha`, `logs/libmlx.sha`, `logs/pip-deps.log`
  (0 `Downloading` lines).
- Repo (persistent, this dir): `evidence/all-legs.jsonl` (5 result lines, sha256 `a61d604b…`),
  `evidence/env-provenance.txt`, `evidence/leg-logs.tgz` (all five full leg logs), `evidence/wheel.sha`,
  `evidence/libmlx.sha`, `receipt.md`.

## Not claimed / open

- ~~Mesa `095cb7e1` sin-FTZ behavior untested~~ → **superseded by the ADDENDUM below** (candidate staged via
  loader override, probe + model A/B executed same session).
- Single-run rates; no thermal/long-run soak.
- The original "no cross-driver comparison" limitation was closed by the addendum; the
  "-8% decode under the candidate lineage" number is single-run and needs its own battery if it becomes
  decision-grade.

---

# ADDENDUM (same session, 2026-09-20 ~23:00Z): Mesa 095cb7e1 sin-FTZ probe + driver-override model A/B

Main extended the lane: stage the fleet-built 095cb7e1 candidate and run a targeted sin-FTZ test, then a
fixed-model A/B. Done in the same window pattern (≤10-min legs, `/tmp/jw14-gpu.lock` — the canonical shared
lock agreed with M2BootImplementation after Main asked both owners to converge on one path).

## Provenance (no build, no system install) — ANCESTRY MANIFEST (Main-directed, verified)

**Exact ancestry / diff proof** (gh api, `joshuaswarren/mesa-1`, confirmed independently by NativeQ4ExactReproduction
and Main's local-git check):
- Chain: `d8d4e1c50` → `3a37b4fb0` (coopmat restore) → `27376cb16` (nir FP_MATH_CTRL revert) → `e16775642`
  (precise div/log/sin FTZ revert) → `095cb7e1b` (**the sin fix**) → `807d9d868` (probe receipt commit).
- `git compare 095cb7e1b...807d9d868`: **1 commit, files touched = `receipts/2026-09-20-sin-ftz-probe/*` only
  (build.sh, 2 spvasm, 2 spv, probe.py) — ZERO driver source changes.** Driver code in the `807d9d868` build
  is exactly `095cb7e1` code.
- Build record: `08b82ea36` "native aarch64 build record for 807d9d86828 on **jw14m2-linux** + loader-proven ICD".
- **Build-hash caveat**: the artifact is pinned by hash (`aade2693…`) to the binary actually run; a fresh
  build from the same source is NOT byte-proven to reproduce it (host/toolchain non-determinism), and no
  independent manifest ties source-file hashes to the binary. Treat as trusted-lineage artifact, not a
  reproducible-build claim.
- Per Main: lineage base is `e16775642` (omarchy devel), which itself differs from stock `mesa 26.2.3-arch1.1`
  by the whole devel delta (SIMDMAT restore, coopmat restore, FTZ-pair reverts, vintage drift). Therefore:

**LABEL CORRECTION (Main-directed): the run below is DIAGNOSTIC of the candidate LINEAGE
(`e167756` + `095cb7e1`), not a qualification of the landed sin fix alone. Specifically: the
`sin(0.5)` correctness delta and the −8% decode delta measure the VINTAGE difference
(stock-26.2.3 vs devel-lineage) plus at most the tiny fix — they CANNOT be attributed to
`095cb7e1` alone. Attribution requires the same-base `e167756` control (planned next gap;
no redundant rebuild — source identity is proven).**

- Candidate driver: fleet-built `libvulkan_asahi-fckey.so` sha256 `aade269367b42001adb20156990570bf6ee1afd1576b43f778ee5c6a507f50b3`
  (63,229,728 B), built **natively on jw14m2-linux** from `joshuaswarren/mesa-1` `hk/fdiv-fckey` at commit
  `807d9d868` (lineage `e16775642` FTZ-revert baseline + `095cb7e1b` sin fix + probe commit; build record
  `08b82ea36`). Source copy was in volatile `/tmp` on jw16 (GPUparity's lane); re-staged to persistent
  `/var/tmp/mesa-095cb/` on jw14m2 (sha verified across all three hops).
- Loader override: `/var/tmp/mesa-095cb/icd-asahi-095cb.json` (sha `bb3c439e…`) with mandatory
  `file_format_version 1.0.1` + ABSOLUTE `library_path`, activated via `VK_DRIVER_FILES` (recipe: GPUparity).
  Fingerprint proof: `vulkaninfo` driverInfo `Mesa 26.3.0-devel`, api 1.4.359 vs stock `26.2.3-arch1.1`/1.4.354.
- Probe: hand-assembled SPIR-V (`sin_ftz.spvasm` → `sin_ftz.spv` sha `7471c2f4…`, spirv-val clean; glslang
  16.4 rejects float-control layout qualifiers, so `OpExecutionMode DenormFlushToZero 32` + `OpCapability
  DenormFlushToZero` written directly) + 100-line C runner (`sin_ftz_runner.c`, clang, sha `be9c157d…`).
  Computes `outs[0]=sin(x)`, `outs[1]=x` with fp32 DenormFlushToZero execution mode.

**Sin-FTZ results (G14C hardware, both drivers) — DIAGNOSTIC (lineage-level, see label correction above)**

| input x | stock 26.2.3 sin | candidate (e167+095cb7) sin | reading |
| --- | --- | --- | --- |
| `0x00000001` (+min subnormal) | `00000000` (+0) | `00000000` (+0) | +0 flushed, both |
| `0x80000001` (−min subnormal) | `00000000` (+0, sign lost) | `80000000` (−0, **sign preserved**) | consistent with the fix's stated intent; strict attribution to `095cb7e1` alone awaits the same-base e167 control |
| `0x3f000000` (0.5, normal) | `3ef57742` (2 ulp off CR) | `3ef57744` (**correctly rounded**) | **vintage-level delta** (devel trig lineage vs stock release), NOT fix-attributable — the fix targets only the flushed-zero path |
| `0x00000000` | `00000000` | `00000000` | both |

The signed-zero flush behavior matches the `095cb7e1` commit's exact contract (flushed, sign-preserving
zero from unflushed sources under DFTZ). The bonus correctly-rounded `sin(0.5)` is a lineage property;
decomposed attribution requires the e167 control.

## Driver-override model A/B (Qwen3.8-27B-4bit, wheel 5b18306, fixed harness, compileON) — DIAGNOSTIC

| leg | prompt | driver | decode tok/s | prefill s | ids sha256_16 |
| --- | --- | --- | ---: | ---: | --- |
| 6 | long (245) | candidate lineage | 4.115 | 18.71 | `1e10ee1431e14597` |
| 7 | long (245) | candidate lineage A/A | 4.114 | 19.65 | `1e10ee1431e14597` ✓ deterministic |
| 8 | ctx1024 (1036) | candidate lineage | 3.9323 | 76.97 | `1731d8318e451a09` |

- **Driver swap changes model digests on both prompts** (long `735b8de2…`→`1e10ee14…`, ctx `0e0c0824…`→
  `1731d831…`). **RoPE HYPOTHESIS (uncontrolled)**: the measured sin precision difference (≤2 ulp on normal
  inputs, vintage-level) feeds RoPE's sin/cos and can flip near-tie greedy tokens. The hypothesis predicts
  the same-base `e167756` control will flip digests IDENTICALLY (since the fix itself only alters
  subnormal-input behavior); if e167 instead holds stock digests, the flip becomes fix-attributable.
  **Control legs are the designated next-gap item.** Per-driver determinism holds (stock A/A 3×, candidate
  A/A 2×).
- Decode rate under candidate lineage: −8.2% (long), −8.5% (ctx) vs STOCK — single-run first-indication;
  **stock is a different vintage, so this is NOT fix-cost attribution**; the meaningful same-base
  candidate-vs-e167 comparison is pending the control driver.
- Contrast: NativeQ4ExactReproduction reports fix-vs-e167-baseline **bit-neutral** on jwm1 Q4 legs (20/20
  digests) — different model/die; jw14m2 Qwen3.8 legs are not bit-neutral across the vintage swap.

## CONTROL CLOSED (same window, e167 same-base on G14C): attribution resolved

Same-base `e16775642` baseline driver (`libvulkan_asahi-e167.so` sha `7087acce…`, jw16 copy of the jwm1
build, staged `/var/tmp/mesa-095cb/` + dedicated ICD) under identical protocol:

| leg | prompt | driver | decode tok/s | prefill s | ids sha256_16 |
| --- | --- | --- | ---: | ---: | --- |
| 9 | long (245) | e167 (no fix) | 4.0785 | 18.78 | `1e10ee1431e14597` == candidate |
| 10 | ctx1024 (1036) | e167 (no fix) | 3.9524 | 76.23 | `1731d8318e451a09` == candidate |

1. **RoPE hypothesis CONFIRMED**: e167 (which lacks the fix) produces digests **byte-identical to the
   candidate** on both prompts. The stock-vs-lineage digest flip is entirely vintage-level; the sin fix is
   **bit-neutral on the model** (matching NativeQ4's jwm1 20/20 result).
2. **Same-base perf**: fix delta = +0.9% (long) / −0.5% (ctx) single-run — within wander, no measurable
   decode cost from `095cb7e1` itself. The −8%-ish stock-vs-lineage decode delta belongs to the devel
   vintage, not the fix.
3. **Signed-zero decomposition completed** (G14C probe): e167 leaks raw subnormals (`sin(−1e−45)=
   0x80000001, no flush), stock 26.2.3 flushes but loses sign (`00000000`), candidate flushes signed zero
   (`80000000` = the fix's contract). Three builds, three behaviors, cleanly attributed.

**Verdict: `095cb7e1` on G14C = subnormal signed-zero flush restored, model-output bit-neutral, no decode
cost vs its own base. Diagnostic-label rescinded for the attribution question; stock-vs-lineage deltas
remain vintage-level.**

---

# ADDENDUM 2 (2026-09-20 ~00:10-00:35Z, post-W16-boot): raw numeric qualification across installed models

Main-directed gap work: greedy generation digest pins (bench_decode.py `f5062d88`, mlx_lm protocol,
64 tokens, prompt long — except q38-2B raw-prompt literal, see below) for installed HF-cache models under
stock vs candidate-lineage driver; wheel 5b18306, HF_HUB_OFFLINE, temp 0 seed 0 warmup 4. Post-reboot
invariance check first: stock Qwen3.8-27B long leg reproduced digest `735b8de2…` at 4.496 tok/s after the
W16 reboot (ane_t6021 pinned+aliased) — GPU environment invariant under the pinned-ANE state.

| model (installed snapshot) | stock digest | e167 digest | candidate (e167+095cb7) digest | reading |
| --- | --- | --- | --- | --- |
| Qwen2.5-0.5B-Instruct-4bit | `fee2baaebf7bae21` | not run | `fee2baaebf7bae21` | vintage bit-neutral |
| SiddhJagani/Qwen3.8-2B-mlx-4Bit (raw prompt; snapshot lacks chat_template) | `f4aa12200cd64eb8` | not run | `f4aa12200cd64eb8` | vintage bit-neutral |
| Ministral-3-8B-Instruct-2512-4bit | `94efc5f2530311cc` (A/A stable: 9.897/9.821 tok/s) | `99f33e795153f7c5` (9.532) | `99f33e795153f7c5` (9.665) | **vintage FLIPS digest; fix bit-neutral vs its base** |
| Qwen3.8-27B-4bit (128 tok, long+ctx, legs 1-10) | `735b8de2…`/`0e0c0824…` | `1e10ee14…`/`1731d831…` | `1e10ee14…`/`1731d831…` | vintage FLIPS; fix bit-neutral |

- Pattern: the devel-vintage trig/precision lineage changes greedy outputs for SOME models
  (Ministral-3-8B, Qwen3.8-27B) and not others (Qwen2.5-0.5B, Qwen3.8-2B at these prompts) — sensitivity is
  model/prompt-dependent, and it is entirely VINTAGE-level: the `095cb7e1` fix is bit-neutral vs its own
  base on every model tested (4/4).
- Same-base paired perf (long, 64-128 tok): fckey 4.0888/4.105/4.115/4.114 vs e167 4.1057/4.0872/4.0785
  tok/s — overlapping bands; Ministral same-base: fckey 9.665 vs e167 9.532 (+1.4%). All single-run or
  few-run SCOPE statements — bands overlap, but "fix cost ≈ 0" is not an equivalence claim without more
  rounds.
- Catalog notes: SiddhJagani/Qwen3.8-2B snapshot ships no `chat_template` (chat-template harness path
  fails; raw-prompt mode used) — packaging fact for the model-catalog lane. 2B decode rates 44.9 (stock)
  vs 39.5 tok/s (candidate) on a 2B model are small-model noise; no perf claim.
- Ops: the fckey ICD json is named `icd-asahi-fckey.json` (renamed from `icd-asahi-095cb.json`, same sha
  `bb3c439e…`; symmetric with `icd-asahi-e167.json`). A transient "failed to open JSON" in one leg batch
  was my own wrong-filename bug, not host state — the `.so`s and jsons survived all reboots in /var/tmp.

**Addendum-2 verdict: raw numeric pins established for 4 installed models across 3 driver builds.
`095cb7e1` is output-bit-neutral vs e167 on all tested models; vintage-level digest sensitivity exists and
is model-dependent — catalog-wide numeric pins must record the driver build they were taken under.**

MATRIX COMPLETION (same window): e167 legs added for the two bit-neutral models —
Qwen2.5-0.5B e167 = `fee2baae…`, Qwen3.8-2B (raw prompt) e167 = `f4aa1220…`: both equal stock AND
candidate. Full 3-driver × 4-model matrix: {0.5B, 2B} digest-identical across ALL THREE builds;
{Ministral-8B, 27B} split stock vs {e167==candidate}. The vintage sensitivity boundary is model-level and
sharp; the fix is bit-neutral universally.

ADDENDUM 2b — Bonsai extension (raw prompt "Describe a lighthouse in one sentence.", 64 tok):

| model | stock | candidate (e167+095cb7) | reading |
| --- | --- | --- | --- |
| prism-ml/Ternary-Bonsai-8B-mlx-2bit | `1d73d64e2da97975` (8.32 tok/s) | `1d73d64e2da97975` (7.92 tok/s) | vintage bit-neutral — 5th model |

- prism-ml/Ternary-Bonsai-2-27B-mlx-2bit is NOT loadable by mlx_lm 0.31.3: custom arch
  `prism_hadamard_qwen35` (`ModuleNotFoundError: mlx_lm.models.prism_hadamard_qwen35`). Loading it requires
  the Bonsai runtime lane's registration (Bonsai2RuntimeEnablement owns that) — catalog fact, not attempted
  further.
- Matrix now 5 models × 3 builds COMPLETE (Bonsai-8B e167 = `1d73d64e…` == stock == candidate; 27B Bonsai
  pending their runtime): {0.5B, 2B, Bonsai-8B} bit-neutral across ALL THREE builds; {Ministral-8B,
  Qwen3.8-27B} split stock vs lineage. No arch-level pattern yet (2-bit Bonsai insensitive, fp16-quant
  Ministral sensitive); sensitivity is per-model, empirically pinned.

---

# ADDENDUM 3 (2026-09-21 ~02:17-02:52Z): ctx4096 matched triple — uninterrupted 35-min window (Main-brokered, M2Hybrid explicit handoff)

Qwen3.8-27B-4bit, prompt ctx4096 (4076 tokens), 128 tok, compileON, fixed harness, same pins; sole device
ownership under `/tmp/jw14-gpu.lock`; Hybrid committed zero device actions for the full window (kept).

| leg | driver | decode tok/s | prefill s | prefill tok/s | ids sha256_16 |
| --- | --- | --- | ---: | ---: | --- |
| 12 | stock 26.2.3 | 3.7205 | 318.81 | 12.78 | `8326e96ef17f40d5` |
| 13 | e167 (no fix) | 3.4722 | 320.68 | 12.71 | `8326e96ef17f40d5` |
| 14 | candidate (e167+095cb7) | 3.4663 | 317.04 | 12.86 | `8326e96ef17f40d5` |

- **ALL THREE builds byte-identical at ctx4096** — including stock==lineage, which did NOT hold at
  ctx1024/long. The vintage-level digest flip is therefore **PROMPT-DEPENDENT** (proven: identical
  outputs at ctx4096, divergent at ctx1024/long). The MECHANISM is not proven: a near-tie token-flip
  account would require logit-margin data, which this harness does not record — treat mechanism as
  hypothesis. The fix remains bit-neutral vs its base at the largest tested context.
- Same-base perf at ctx4096: fix delta −0.2% decode, prefill parity — **single-run scope statement
  only, not an equivalence claim** (no confidence interval from one round).
- Two earlier ctx4096 attempts were clipped by external reboots (00:05Z fault cycle; 02:14Z probe-caused
  freeze, M2Hybrid-owned); Main brokered the 35-min uninterrupted reservation for this run. No driver-side
  errors occurred in any attempt.
- ctx4096 pin: `8326e96ef17f40d5` (n=128) is the jw14m2 G14C reference for this prompt under ANY of the
  three builds.
- ctx4096 note: two earlier triple attempts were clipped by external reboots (00:05Z fault cycle, 02:14Z
  probe-caused freeze) before the Main-brokered uninterrupted window below — see ADDENDUM 3.

## Coordination (updated)

- M2BootImplementation authorized each window in-band and received the attempt-4 GPU yield; ownership then
  handed to **M2HybridBringup** (Main-directed): same shared lock `/tmp/jw14-gpu.lock`, same ANE constraints,
  plus their staged dir `/var/tmp/ane-t6021-6f67/` off-limits; GPU legs run freely between their
  source-heavy phases, yield on IRC before insmod/MMIO.
- Lock note (Main-directed): both owners converge on `/tmp/jw14-gpu.lock` (mirrors jw16's
  `/tmp/m1-gpu.lock`); file is recreated only when unheld (reboot wipes /tmp — the *path* is volatile,
  the *convention* is not).
- Operational lesson applied: post-crash reboots wiped `/tmp` twice today (17:35, 17:42) and the second
  crash ate tail-written files in `/var/tmp/mesa-095cb` (runner+spv, restored); the bench area now lives in
  persistent `/var/tmp/jw14-bench` (rebuild script `.local/jw14-bench-rebuild.sh`, 22 s, zero downloads).

## Addendum artifacts

- `evidence/sin-ftz-probe/` (sin_ftz.spvasm, sin_ftz.spv `7471c2f4…`, sin_ftz_runner.c, icd json `bb3c439e…`)
- `evidence/all-legs.jsonl` — all 8 result rows (sha `0a6a9212…` after merge; supersedes `a61d604b…`)
- `evidence/leg-logs.tgz` — full leg logs 1-8 (rtmod traces included)
- Host (persistent): `/var/tmp/mesa-095cb/` (driver aade2693, ICD, probe), `/var/tmp/jw14-bench/`
  (venv c28a485f libmlx, harness pins in `logs/pins.sha`, leg logs)

