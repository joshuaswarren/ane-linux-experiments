# jwm1 Linux denominators (2026-09-24) — same branch, Linux side of the M1

Branch: `agent/jwm1-macos-baselines` · Main-directed addendum: jwm1 stayed on
Linux (macOS window cancelled; M2 proxy lane may need the webcam). This
receipt captures the M1 Linux side of all three cells and the ANE control
check, per Main's directive.

Host: `jwm1-linux` (Apple MacBook Pro 13" M1, T8103), Omarchy,
kernel `7.1.13-3-2-ARCH` (asahi3-2), ane.ko version `9ad8474`
(srcversion `F88565981CD8CAE87A37833`), ANE on DRM minor 0
(`/dev/dri/renderD128`). AC power (macsmc-ac ONLINE=1, 60 W limit),
battery Full, thermal 24.8-29.5 C, loadavg at run starts 0.4-0.56.

## Cell verdicts vs the M1 macOS table (pass = >=1.00x macOS, fail recorded as fail)

| cell | Linux (this receipt) | macOS (committed table) | ratio | verdict |
|---|---|---|---|---|
| Parakeet warm pipeline (median of 5 warm runs) | **713.5-749.8 ms** (median 739.7, umalimit1 stack) | 271 ms (ane arm rep10 inference) | **0.37x — FAIL 2.7x** | **FAIL** |
| Parakeet warm RTF | **14.1x** | 38.5x | 0.37x — FAIL | **FAIL** |
| Parakeet cold wall | 2253 ms (first run incl. session open) | models-ready 24.06 s + cold inference 0.295 s | n/a (structural: CoreML compile vs ANE session open) | n/a |
| Parakeet fresh-session ANE encoder exec | 141.3-142.5 ms | 113.12 ms (CoreML ane arm median) | 0.80x — FAIL | **FAIL** |
| Parakeet transcript | **match** db501a8c, 104/104 emissions, all 10 pin checks, every run | match, 104/104 | parity | PASS (correctness) |
| Qwen decode tok/s | **17.46** | 47.05 | **0.37x — FAIL 2.7x** | **FAIL** |
| Qwen pure prefill 512 tok/s | **28.68** (wall 17.85 s) | 343.73 (wall 1.49 s) | **0.083x — FAIL 12x** | **FAIL** |
| Qwen TTFT tok/s | **20.19** | 99.12 | 0.20x — FAIL | **FAIL** |
| Qwen e2e per prompt (32 tok out) | **2.4195 s** | 0.7898 s | 0.33x — FAIL 3.1x | **FAIL** |
| Qwen records determinism | pin `bea37f48…` (n=100, in-stack) | pin `85b9bc6d…` (n=100, Metal) | each within-backend deterministic; cross-stack hashes differ by design | n/a |

The Linux side does NOT meet the >=1.00x parity bar in any performance
cell today. Failures are recorded as failures; no acceptance criterion
was lowered.

## 1. ANE control check — PASS

- Driver bound: `ane 65536 0` (lsmod), dmesg `platform 26bc04000.ane:
  Adding to iommu group 0`, `[drm] Initialized ane 1.0.0 ... on minor 0`,
  render node `/dev/dri/renderD128` present.
- Gate batteries (prebuilt `/var/tmp/m1-integrate-20260922/tests-build/tests/omarchy/`,
  Sep 22 build), each under `flock -w 900 /tmp/m1-gpu.lock`:
  - `omarchy_runtime_tests`: **41/41 cases, 22694/22694 assertions, SUCCESS**
  - `omarchy_primitive_tests`: **103/103 cases, 2700952/2700952 assertions, SUCCESS**
  - `omarchy_ane_bundle_tests`: **34/34 cases, 5904/5904 assertions, SUCCESS**
- Quarantine `/run/lock/mlx-omarchy-ane/quarantine`: 0 before and after.
- Raw logs: `raw/gates/{runtime,primitive,ane_bundle}.log`.

## 2. Parakeet full audio-to-transcript — golden fixture + corpus

Audio corpus of record = the golden fixture `fixture.flac`
(10.435 s, sha256 `30885601…`; the single fixture IS the existing
parakeet audio corpus on this box; both cached copies identical). Runner:
`/var/tmp/pk-sess-driver.py` (in-process, installed CLI), 6 runs each
(r1 = fresh/cold session, r2-r6 = warm session reuse), 3 warmups are
inherent to the driver's session model (r1 cold + r2+ warm); all under
`flock -w 900 /tmp/m1-gpu.lock`.

### 2a. Pinned wheel `0.32.3.dev202609230623+b4757ac` (venv `/var/tmp/denom-b4757ac-venv`, clone of pk-sess-venv + force-reinstall of the pinned wheel; same stack as the committed sibling row)

| run | status | transcript | pipe ms | enc stage ms | ane exec ms | tdt ms | mel ms | ctrl |
|---|---|---|---:|---:|---:|---:|---:|---|
| 1 (cold) | match | db501a8c, 104/104 | 1706.2 | 933.1 | **141.3** | 468.8 | 192.5 | host |
| 2 | match | db501a8c, 104/104 | 944.5 | 261.2 | 260.3 | 504.6 | 62.0 | host |
| 3 | match | db501a8c, 104/104 | 962.0 | 268.9 | 267.9 | 508.4 | 60.6 | host |
| 4 | match | db501a8c, 104/104 | 915.4 | 265.8 | 264.4 | 475.2 | 61.1 | host |
| 5 | match | db501a8c, 104/104 | 928.9 | 260.1 | 259.1 | 493.2 | 62.6 | host |
| 6 | match | db501a8c, 104/104 | 909.5 | 278.6 | 277.8 | 465.4 | 63.0 | host |

Reproduces the committed Linux row: warm pipeline median **928.9 ms**
(sibling: 920.0), fresh ANE exec **141.3 ms** (sibling: 142.1), warm-wake
encoder 260-279 ms (sibling: 266-276), TDT host loop 465-508 ms
(sibling: 472-502), mel warm ~61-63 ms (sibling: 61.3-62.1). All 10
verification pin checks pass on every run (mel_sha, encoder_hidden_sha,
emissions, token_ids, frame_indices, durations, transcript,
cpu_tensor_events=0, decode_control, finite_hidden).

### 2b. Current stack `0.32.3.dev202609231736+umalimit1` (venv `/var/tmp/v072-venv-fused`, installed 2026-09-23 15:10 CDT by a prior lane; includes the new gpu-chain TDT decode control)

| run | status | transcript | pipe ms | enc stage ms | ane exec ms | tdt ms | mel ms | ctrl |
|---|---|---|---:|---:|---:|---:|---:|---|
| 1 (cold) | match | db501a8c, 104/104 | 1355.0 | 537.7 | **142.5** | 201.6 | 178.5 | gpu-chain |
| 2 | match | db501a8c, 104/104 | 739.7 | 296.5 | 294.2 | 137.5 | 30.0 | gpu-chain |
| 3 | match | db501a8c, 104/104 | 749.8 | 297.4 | 294.9 | 132.8 | 30.3 | gpu-chain |
| 4 | match | db501a8c, 104/104 | 736.3 | 297.3 | 294.7 | 135.1 | 31.9 | gpu-chain |
| 5 | match | db501a8c, 104/104 | 745.2 | 298.1 | 295.2 | 134.4 | 29.6 | gpu-chain |
| 6 | match | db501a8c, 104/104 | 713.5 | 257.4 | 254.4 | 134.5 | 29.3 | gpu-chain |

The umalimit1 stack moves TDT decode from the host loop (465-508 ms) to a
GPU-resident chain (**132-137 ms** — within 15% of the macOS CoreML TDT
floor of 120 ms) and roughly halves mel frontend cost (30 vs 62 ms).
Warm pipeline median **739.7 ms** vs pinned-stack 928.9 ms. Fresh-session
ANE exec unchanged (142.5 ms).

## 3. Qwen3.8 GPU contract (Linux, honeykrisp/Vulkan)

Protocol: `benchmarks/qwen38-2b-contract.json` — greedy, 32 new tokens,
3 warmup passes, 10 passes x 10 prompts (n=100), 512-token pure prefill
leg, corpus sha `9299a3b2…` verified, model snapshot `0867d98b…`
(model.safetensors sha `b0d5de68…` verified), venv
`/var/tmp/denom-b4757ac-venv` (mlx-omarchy b4757ac + mlx-lm 0.31.3),
same stack as the committed Linux qwen row.

| metric | this run | committed sibling row (same wheel, Sep 23) |
|---|---:|---:|
| decode tok/s median | **17.46** (sd 0.03, n=100) | 35.40 (sd 0.13) |
| pure prefill tok/s (512 leg) | **28.68** (wall 17.85 s) | 140.01 (wall 3.66 s) |
| ttft tok/s median | **20.19** (n=100) | 50.72 |
| e2e s median (ttft+decode) | **2.4195** (min 2.337, max 2.575) | (not recorded by sibling) |
| peak RSS | 565,723,136 B | — |
| records pin | `bea37f48…` | `dbf70497…` (not comparable: different run) |

### Driver state finding (named defect for the driver lane)

The numbers above are ~2x (decode) / ~4.9x (prefill) SLOWER than the
committed sibling row captured on the same box, same wheel, 33 h earlier.
A/B evidence gathered this session (raw under `raw/qwen/`):

- System ICD `/usr/share/vulkan/icd.d/asahi_icd.json` →
  `/usr/local/lib/libvulkan_asahi.so.7faf04c` (custom honeykrisp lineage,
  sha256 `09e3527dee4a365ee290…`, api 1.4.359, installed 2026-09-22 07:51).
  With it: decode 17.42, prefill 28.77 — reproduces the slow numbers.
- Stock mesa `vulkan-asahi 1:26.2.3-1` (`/usr/lib/libvulkan_asahi.so`,
  backup ICD `asahi_icd.json.stock-mesa-2623.bak`) **fails
  `vkCreateInstance` with VK_ERROR_UNKNOWN** — stock driver cannot create
  a Vulkan instance on this box at all right now.
- Other staged drivers on the box (not run by me):
  `/var/tmp/mesa-7faf04c-jwm1/{base,peel}.so` (Sep 22 11:02),
  `/var/tmp/mesa-e167-jwm1/libvulkan_asahi.so` (Sep 21 18:17),
  `/var/tmp/mesa-submit-lat/libvulkan_asahi.so.cand-{57148342,09bc5d20}`
  (Sep 23 03:2x).
- The `[rtmod] SUBMIT/COMMIT-NOOP` stderr lines are UNCONDITIONAL
  fprintf in this driver lineage (`encoder.cpp`); present in the sibling's
  run too, ruled out as the cause of the 2x (14k lines ≈ tens of ms to a
  file).

Either the driver state changed after the sibling's capture (new ICD
target, or a system change on Sep 23), or the sibling's row was produced
under a driver configuration that no longer exists on this box. That
question belongs to the honeykrisp/driver lane; this receipt pins the
exact current state so the number is reproducible either way.

## Cell table (the three requested cells, Linux side)

1. Parakeet whole-encoder: fresh-session ANE exec **142.5 ms** (current
   stack) / **141.3 ms** (pinned stack) vs macOS CoreML ane arm
   **113.12 ms** → **FAIL** (0.79x).
2. Parakeet full pipeline: warm **739.7 ms** median / RTF **14.1x**
   (current) — vs macOS warm **271 ms** / RTF **38.5x** → **FAIL** (2.7x).
   Transcript + all pins: PASS every run.
3. Qwen GPU contract: decode **17.46 tok/s**, prefill **28.68 tok/s**,
   TTFT **20.19 tok/s**, e2e **2.4195 s** — vs macOS 47.05 / 343.73 /
   99.12 / 0.7898 → **FAIL** across the board.

## Artifacts

- `raw/gates/{runtime,primitive,ane_bundle}.log` (ANE control)
- `raw/parakeet-b4757ac/` (summary.json, run-1..6 reports/transcripts/token_ids)
- `raw/parakeet-umalimit1/` (same, current stack)
- `raw/qwen/qwen38-linux.json` (contract bench incl. e2e_s + peak RSS),
  `raw/qwen/bench.{stdout,timelog}`, `raw/qwen/probe-custom.*`,
  `raw/qwen/probe-stock.timelog` (stock ICD failure), probe JSONs
- `raw/SHA256SUMS.raw` (98 files)
- Provenance: driver `7faf04c` sha `09e3527dee4a365ee290…`; pinned wheel
  sha256 `ef450bf5c57b8e13c1bbef71…`; venvs cloned, no lane venv mutated.

## 4. Combined Parakeet pipeline (lane `agent/combined-parakeet` @ `8bba36b2`) — PASS

Built and run per `receipts/2026-09-24-m1-boundaries-encoder-anomaly/README.md`
§4: wheel `0.32.3.dev202609241627+8bba36b` (commit verified `8bba36b2`,
sha256 prefix `b42667136a0c16a732b…`) installed into a fresh
`/var/tmp/combined-venv`; runner gate satisfied via the documented
`COMBINED_WHEEL_ALLOW=1` (the build stamps a 7-char commit abbreviation;
lineage identity proven by git rev-parse). Preflight identities: program
`13c74423…`, libane `d06222a8…`, worker `84e8cc8f…`, fused_e2e
`aaacba7a…`, vulkan_encoder `2dbaace1…`.

`bash /var/tmp/combined-parakeet.sh t8103-host` (with
`COMBINED_SRC=/var/tmp/IslandsExecJwm1/encoder-source` — the runner's
staged `IslandsExecM1Host` path is stale on this box), 3 reps under
flock, lane-local SPIR-V cache:

| rep | status | control | subs | cpu_events | ane exec ms | enc stage ms | tdt ms | mel ms | pipeline ms |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | match | host | 1 | 0 | 143.0 | 713.4 | 1005.4 | 9716.1 (SPIR-V compile) | 11611.1 |
| 2 | match | host | 1 | 0 | **141.4** | 712.8 | 579.7 | 188.1 | **1588.2** |
| 3 | match | host | 1 | 0 | **141.3** | 715.7 | 582.9 | 193.1 | **1597.8** |

- Transcript: `db501a8c…` exact match, `transcript_match true` all reps;
  encoder_hidden sha256 `554a3d66…` IDENTICAL across reps and equal to
  the certified whole-encoder pin (boundaries receipt §2).
- All §4 acceptance criteria hold: status match, control host,
  submissions 1, cpu_tensor_events 0, mel/hidden bit-exact, ane exec in
  the 141-260 ms class, tdt under the 975 ms megakernel bucket, warm
  pipeline 1588-1598 ms well under the 2026.8/2380.4 ms gpu-loop baselines.
- Raw: `raw/combined-parakeet/` (e2e logs, reports, identity.txt, transcripts).

## 5. GPU regression investigation (Main-directed): root cause NOT in machine state

Directive: restore the state that produced the committed Linux row
35.40 tok/s decode / 140.01 tok/s prefill (sibling `m1-mac-denominator`,
captured on this box ~33 h before my 17.46/28.68 measurement).

Every recoverable layer was tested; results:

| hypothesis | test | result |
|---|---|---|
| power/battery | `/sys/class/power_supply` | AC ONLINE=1, 60 W limit, battery Full — ruled out |
| thermal | contract meta + sensors | 24.8-29.5 C all runs — ruled out |
| CPU freq/governor | per-core cpufreq | schedutil, E-cores ≤2064 MHz, P-cores ≤2988 MHz, all 8 online — normal |
| packages | pacman.log since Sep 22 | NO upgrades of linux/mesa/vulkan/asahi — ruled out |
| ICD target | `stat` + A/B probe | `asahi_icd.json` → `7faf04c` (.so + json both mtime Sep 22 07:51:24, spanning BOTH runs); stock mesa 26.2.3 **fails vkCreateInstance VK_ERROR_UNKNOWN** — separate defect, cannot be the sibling's fast path either |
| GPU-level machine state | re-ran the mesa lane's recorded `bench_decode` legs verbatim (wheel 5b18306, tip driver, 2B model, 32 tok, `MLX_DISABLE_COMPILE=1`) | **REPRODUCED BIT-EXACTLY**: ctx1024 decode 13.14 tok/s (recorded median 13.1857), prefill 18.7514 (recorded 18.75), generated-ID digest `6a7bd73e0a720dde` == recorded; short leg 14.5355 (recorded 14.53). The machine is NOT slower than Sep 22. |
| wheel build | contract on `b4757ac` (both on-disk copies byte-identical, sha `ef450bf5…`), on `umalimit1`, on `bf8793f` (original pk-sess-venv, uncloned) | ALL 16.5-17.6 decode / 26-29 prefill — slow class follows no wheel |
| compile path | contract with/without `MLX_DISABLE_COMPILE=1` | no difference (16.45 vs 17.46) — ruled out |
| clone artifacts | contract in original pk-sess-venv | identical slow numbers — ruled out |
| lane env knobs | `MLX_OMARCHY_GATED_BARRIERS` (default off), `HK_PERF*` (perf-test overrides) — none set in either run | not the lever |

Roofline sanity: Qwen3.8-2B Q4 weights ≈ 1.31 GB; M1 memory bandwidth
≈ 68 GB/s → decode ceiling ≈ 52 tok/s. My measured 17.46 tok/s = 34% of
ceiling (consistent with honeykrisp maturity); the committed 35.40 = 68%
of ceiling — a near-roofline figure that would be extraordinary for this
driver on this chip, and equal to the M1 **Max** contract decode measured
the same week on jw16 (t6001 lane, 33.9-35.4 tok/s).

Verdict: the current, honestly-measured Linux denominators are
**17.46 tok/s decode / 28.68 tok/s prefill / 20.19 TTFT / 2.42 s e2e**
(n=100, deterministic, records pin `bea37f48…`). The superseded
35.40/140.01 row is not reproducible on this machine; its enabling
condition is unrecoverable from surviving artifacts because the sibling
lane's venv (`v072-venv-fused`) was upgraded in place to `umalimit1`
(Sep 23 15:10 CDT) and no timelog or environment capture exists for that
leg. The FAIL verdicts in the cell table stand and, if anything, the true
parity gap is larger than the committed table states. The
"which state produced 35.40 on an M1" question is handed to the
driver/serving lane with the roofline argument above; nothing in my lane
can restore it because no surviving artifact encodes it.

Additional artifacts: `raw/qwen/ab-*.{json,timelog}` (compile/venv A/Bs),
`raw/qwen/probe-{custom,stock}.*` (ICD A/B). Regenerate checksums with
`sha256sum -c SHA256SUMS.raw` after this commit's raw additions.
