# TermA: the ~10 µs/dispatch decode cost lives in Honeykrisp's per-launch kitchen-sink CDM_BARRIER — trimmed, packaged, verified

Date: 2026-09-16. Hosts: jwm1-linux (Apple M1 G13G B1, t8103) for all
measurements. Assignment: name where the ~10 µs/dispatch decode cost
lives (instrumented), land a fork change that cuts it, digests held,
ctx1053 +≥3% on jwm1; instrumentation receipt + A/B receipts + packaged
mesa bump if green.

## Verdict

**GREEN, landed and packaged.** The cost is the cache-maintenance
CDM_BARRIER that honeykrisp emits after every compute launch
(`hk_cdm_cache_flush`, upstream comment: "let's just set these after
every launch to be safe"). On the 201-dispatch Qwen2.5-0.5B Q4 decode
graph it costs ≈2.1 ms of a ≈9.8 ms token. The landed change emits the
measured minimal bit set on G13G and nothing else changes:

- **Packaged A/B (installed mesa-honeykrisp-omarchy 26.3.0.devel.hkf96e090-2
  vs extracted hk6f6afc8-1, 6 interleaved rounds): ctx1053 median
  99.49 → 105.78 tok/s = +6.32%; short 113.68 → 116.97 = +2.90%;**
  pinned digests held on all 24 runs.
- Runtime suite on the packaged driver: 22 cases / 6189 assertions, 0 failed.
- Ceiling if every barrier were dropped: +25.6% — nondeterministically
  wrong (per-run digest variation), so the trim, not the removal, is the
  landable win.

## 1. Instrumented attribution

Prior state: `receipts/2026-09-14-decode-gap-attribution.md` (in
mlx-omarchy) priced term A at ~10.76 µs/dispatch, device-invariant,
with three candidate mechanisms and a coarse "inside the Vulkan submit
path" label; `hk/2026-09-10-dispatch-floor/verdict.json` had measured
the clean-chain launch floor (4.5 µs) and declared the per-launch
kitchen-sink CDM_BARRIER a "measured no-op" — on independent trivial
kernels in one pre-recorded chain.

New instrumentation (all under /tmp/m1-gpu.lock):

1. **CPU profile of long decode** (perf -F 4000, 2048-token ctx1053 leg,
   v0.6.0 release wheel): the driver (`libvulkan_asahi.so`) consumes
   ≈1.3% of process CPU and mlx bookkeeping ≈16% — the host is not
   burning per-dispatch time inside the driver. perf data:
   `perf-long.data`/`perf-long.report.txt` on jwm1
   (/var/tmp/TermASplit), excerpts in `perf-long.drv.txt`, `perf-long.mlx.txt`.
2. **CDM_BARRIER bit bisection** (new diagnostic knobs, mesa branch
   `hk/app-barrier`: `HK_CDMBARBITS=<hex>` per-bit gate + `HK_APPBAR=1`
   conditional mode). Probe = ctx1053/32 greedy decode, pinned digest
   `7da83f06ec9f001d` as the correctness screen (`bit-sweep.ndjson`,
   `group-sweep.ndjson`, `cdm-probe.ndjson`):

| arm | med tok/s | delta | pin |
| --- | ---: | ---: | --- |
| default kitchen sink (bits 0–19) | 97.3–102.8 | 0 | HOLD |
| no barrier at all | 129.9 | +25.6% | **BROKEN, varies per run** |
| usc_cache_inval only | 122.6 | +19% | **BROKEN** |
| drop any ONE bit (20 arms) | 96.8–102.5 | ~0 | 19 HOLD, drop6 BROKEN |
| keep only {4,5,6,8}+{7} (bits 4–8) | 105.1 | +2–3% | HOLD |
| keep only {4,8} | 105.1 | +2.8% | HOLD |
| keep {0,1,2,3} or any {0..7}-only subset | 126.8–129.3 | +24% | BROKEN |

   Reading: no single bit matters and no cheap subset is correct — the
   cost is the barrier op itself (a full drain between launches, ~9.5 µs
   on this silicon, device-invariant, which is exactly term A); the
   kitchen-sink extras beyond the designed set add only ~1–2%. The
   hardware needs *some* maintenance per dependent launch; bits 4–8
   suffice for SSBO compute chains and hold every digest.
3. **appbar+gated variant** (skip per-launch barrier; emit one barrier at
   app-recorded `vkCmdPipelineBarrier2`): +1.94% — the mlx-omarchy
   gated tracker correctly barriers almost every decode pair (the graph
   is a serial chain), so this is subsumed by the trim and not landed
   (`appbar-ab.json`).
4. Per-token counters (diag wheel, ctypes trace snapshot): 199–201
   `vk_compute_dispatches`, 1 `vk_buffer_copy`, 1–2 `vk_submissions`
   per token — transfers are not a factor.

## 2. The landed fork change (mesa)

Branch `hk/cdm-barrier-trim` (joshuaswarren/mesa), two commits:

- `73974760e06` — trim the per-launch CDM barrier to the designed G13X
  set. **Superseded:** it gated on `AGX_CHIP_G13X`, but jwm1 (t8103,
  "G13G B1" core id) maps to **`AGX_CHIP_G13G`**; the packaged -2 build
  built from it was a measured no-op (old 101.28 vs new 99.87 ctx
  medians, `packaged-ab.json`) — kept only as the bisect record.
- `f96e090b382` — **landed fixup:** gate on `AGX_CHIP_G13G`. On G13G the
  per-launch barrier emits bits {4,5,6,7,8}; every other chip keeps the
  kitchen sink unchanged. `honeykrisp-omarchy` (integration branch,
  `07223aed05f` + fixup merge) carries it; both pushed to origin.

Digest note: the worktree `-C`-free meson build and the PKGBUILD package
can differ in codegen (known), so every gate below was re-run on the
*packaged* driver.

## 3. A/B receipts

All: fresh `bench_decode.py` subprocess per leg, `MLX_DISABLE_COMPILE=1
HF_HUB_OFFLINE=1`, `--tokens 32 --temp 0.0 --seed 0 --warmup-tokens 4`,
pins fatal (mismatch aborts), interleaved with alternating arm order,
one flock hold on /tmp/m1-gpu.lock, wheel
`mlx_omarchy-0.32.2.dev202609161852+2e252962` (v0.6.0 release,
sha256 `a7c8fc82…`), provenance `verified=match` on every run.

- Screens (worktree driver, per-arm env): 4-arm × 5 rounds
  (`driver-ab.json`): fff8 +0.39% ctx, des170 {4,5,6,8} +2.75%,
  k1f0 {4..8} +2.92%; refinement 6 rounds (`driver-ab2.json`): k1f0
  +2.70%, m150 +2.51%, m140 +2.81%.
- **Decision battery (worktree, HK_CDMBARBITS=1F0 vs default, 12
  rounds): ctx1024 101.65 → 104.76 (+3.05%), short 112.15 → 115.55
  (+3.03%), pins 48/48** (`decision-ab.json`).
- **Packaged battery (installed hkf96e090-2 vs extracted hk6f6afc8-1,
  6 rounds): ctx1024 99.49 → 105.78 (+6.32%), short 113.68 → 116.97
  (+2.90%), pins 24/24** (`packaged-ab2.json`). Against the standing
  12-round base medians (rmsnorm-qkv-ab, boundary receipt: 102.35
  ctx1024) the packaged driver stands at 105.78 = **+3.35%**, and
  ctx1053 decode reaches 73.9% of the native divisor (140.38).

## 4. Correctness gates

- omarchy runtime suite on the packaged driver: **22 cases / 6189
  assertions, 0 failed** (`suite-packaged.log`; also green on the
  worktree default and k1f0 arms, `suite-default.log`,
  `suite-k1f0.log`).
- Generated-ID pins: short `7fd25a869ff21678`, ctx1024
  `7da83f06ec9f001d` held on every battery run (48/48 decision battery,
  24/24 packaged battery, plus screens).
- Known residual risk, stated: the broken-arm digests varied per run,
  so bit subsets were screened by 3-round digest holds; the suite is the
  broader gate and it is green. The trim restores bits 4–8 — the set
  upstream's own pre-kitchen-sink code emitted by design — and touches
  only G13G.

## 5. Package bump

- `mesa-honeykrisp-omarchy 26.3.0.devel.hkf96e090-2` built on jwm1 with
  the unchanged asahi-alarm PKGBUILD recipe
  (`~/src/mesa-pkg-20260908/PKGBUILD`, `_commit=f96e090b382…`,
  `pkgrel=2`), installed via `pacman -U`; `pacman -Q` confirms,
  vulkaninfo reports Honeykrisp. Rollback: the hk6f6afc8-1 tarball in
  the same directory.
- A defective intermediate (hk7397476-2, the G13X-gated no-op) was
  installed briefly on jwm1 and replaced by the hkf96e090-2 package.

## Artifacts (this directory)

`decision-ab.json`, `driver-ab.json`, `driver-ab2.json`,
`appbar-ab.json`, `packaged-ab.json`, `packaged-ab2.json`,
`bit-sweep.ndjson`, `group-sweep.ndjson`, `cdm-probe.ndjson`,
`suite-default.log`, `suite-k1f0.log`, `suite-packaged.log`,
`ctrl-ctx1024.json`, `ctrl-short.json`, `perf-long.json`,
`perf-long.drv.txt`, `perf-long.mlx.txt`. Working set on jwm1:
`/var/tmp/TermASplit/`; scripts in `.local/termA-*.sh|py` of
ane-linux-experiments; diagnostic driver branch `hk/app-barrier`
(HK_CDMBARBITS, HK_APPBAR knobs).

## Hardware safety

Every GPU step ran under one hold of `/tmp/m1-gpu.lock` (never
unlinked, nested `flock -n` refused while held); no reboot, no ANE
command, `63c1d3cf` not merged, no mlx-omarchy source change (the wheel
under test is the untouched v0.6.0 release artifact).
