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

## Provenance (no build, no system install)

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

## Sin-FTZ results (G14C hardware, both drivers)

| input x | stock 26.2.3 sin | 095cb7e1 sin | expectation |
| --- | --- | --- | --- |
| `0x00000001` (+min subnormal) | `00000000` (+0) | `00000000` (+0) | +0 flushed ✓ both |
| `0x80000001` (−min subnormal) | `00000000` (+0, **sign lost**) | `80000000` (−0, **sign preserved**) | fix present only in candidate |
| `0x3f000000` (0.5, normal) | `3ef57742` (**2 ulp off**) | `3ef57744` (**correctly rounded**) | candidate more accurate |
| `0x00000000` | `00000000` | `00000000` | both |

**The fix works on G14C**: flushed signed zero under DFTZ, matching CTS expectations; stock shows the exact
defect the commit describes. Bonus finding: the candidate's sin is correctly rounded on normal inputs where
stock 26.2.3 is 2 ulp off.

## Driver-override model A/B (Qwen3.8-27B-4bit, wheel 5b18306, fixed harness, compileON)

| leg | prompt | driver | decode tok/s | prefill s | ids sha256_16 |
| --- | --- | --- | ---: | ---: | --- |
| 6 | long (245) | 095cb7e1 | 4.115 | 18.71 | `1e10ee1431e14597` |
| 7 | long (245) | 095cb7e1 A/A | 4.114 | 19.65 | `1e10ee1431e14597` ✓ deterministic |
| 8 | ctx1024 (1036) | 095cb7e1 | 3.9323 | 76.97 | `1731d8318e451a09` |

- **Driver swap changes model digests on both prompts** (long `735b8de2…`→`1e10ee14…`, ctx `0e0c0824…`→
  `1731d831…`). Causally consistent with the measured sin difference: RoPE consumes sin/cos of position
  values, a ≤2-ulp sin change flips near-tie greedy tokens. The candidate's sin is the correctly-rounded
  one, so the digest flip is a precision-lineage change, **not** evidence of candidate-side corruption.
  Per-driver determinism holds (stock A/A 3×, override A/A 2×).
- Decode rate under override: −8.2% (long), −8.5% (ctx), single-run first-indication, consistent magnitude
  across both prompts; prefill unchanged (18.7-19.6 s / 76.8-77.0 s). Consistent with the known
  precise-trig decode cost from the jw16 FTZ-lineage history; labeled observation, not a causal claim.
- Contrast: NativeQ4ExactReproduction reports fix-vs-baseline **bit-neutral** on jwm1 Q4 legs (20/20
  digests) — different model/die; jw14m2 Qwen3.8 legs are NOT bit-neutral across the driver swap.

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

