# jw16 step 2 — macOS window: Parakeet full-pipeline denominator + whole-encoder re-confirm + kernelcaches (2026-09-25)

Owner: Jw16Levers5. Host: jw16 macOS side, 16M1MBP, macOS 26.6.2 (25G83,
Darwin 25.6.0, xnu-12377.161.14~5/RELEASE_ARM64_T6000), Apple M1 Max 64 GB.
Window opened by next-boot-only asahi-bless switch at 17:58:20 CDT (gate PASS:
/boot ext4, ESP vfat); bundle = mac-reference-bundle-full.tar.gz (sha
82c1a70198fd…) reused from Levers3's window; runner = run-levers5.sh +
AneClockM1's name-based ane-perfstate.d (sha e1edfffb…).

## 1. Parakeet full audio->transcript pipeline (the missing jw16 macOS cell)

Shipped bin/parakeet (fallback forced; the pinned ParakeetCLI.swift does not
compile on the newer CLT, jwm1 2026-09-23 deviation 2 — and Levers3's
noswift-shim workaround failed because the shim itself answered `command -v
swift`; this window fixes that by patching the branch to `if false`).
Fixture 1089-134686-0000 (10.435 s), golden transcript gate:
**ane/gpu/all MATCHES golden, cpu DIFFERS (pinned reference contract)** —
`PARAKEET-BUNDLE OK`, out dir parakeet-20260925T175905.

ane arm stage timings (----- timing ----- blocks):

| run | inference s | mel s | encoder s | decode s | tokens | RTFx |
|---|---:|---:|---:|---:|---:|---:|
| cold | 0.299 | 0.016 | 0.160 | 0.122 | 104 | 34.9x |
| warm1 | 0.274 | 0.014 | 0.156 | 0.103 | 104 | 38.2x |
| rep1 | 0.258 | 0.014 | 0.141 | 0.101 | 104 | 40.5x |
| rep10 | **0.264** | 0.015 | 0.147 | 0.102 | 104 | 39.6x |

all arm rep10: inference 0.293 s (encoder 0.175). Models-ready: 39.53 s cold
(ANE compile), 0.31-0.32 s warm.

**Denominator line: jw16 macOS full pipeline = 264 ms (rep10, ane arm) vs
Linux (this laptop, installed stack) 2235 ms = 8.5x gap.** Consistency
anchors: jwm1 macOS ane rep10 = 271 ms (same harness lineage), jw16 whole-encoder
140.27/140.86 ms vs Linux whole-encoder 440 ms = 3.1x gap, Linux pipeline
encoder stage (submit-dense islands) 1438 ms.

## 2. Whole-encoder re-confirm under the window harness (leg B)

bin/encoder_bench, pinned encoder.mlpackage rev b650695c, ane arm 3+10:
median **140.86 ms** (min 137.02, max 142.46), placement ane 1341 / cpu 33,
hidden bit-exact vs Linux gold (0 mismatches, max_delta 0, 240000 words) —
consistent with Levers3's 140.27 ms. The pipeline encoderCoreML (147 ms rep10)
+ overhead sits right on it: the macOS pipeline is encoder-bound at the
whole-encoder speed, single-digit-percent above the raw bench.

## 3. ANE perf-state dtrace capture: BLOCKED by SIP

- `csrutil status`: **System Integrity Protection status: enabled.**
- Probe listing (`sudo dtrace -l -n
  'fbt:com.apple.driver.ApplePMGR:*PerfState*:entry'`): header only —
  `dtrace: failed to match fbt:com.apple.driver.ApplePMGR:*PerfState*:entry:
  System Integrity Protection is on`.
- No capture ran; perfstate.out empty (dtrace started under the mis-firing
  3-line gate and was stopped; harness gate fixed to require probe rows for
  any future window). AneClockM1's script itself is untested until SIP
  allows fbt.
- Main's call: hold SIP (disabling needs hands-on recoveryOS); static route
  first — only if static decode fails would a one-time recoveryOS SIP window
  be requested from Joshua.

## 4. Kernelcaches for the static decode (both on PVE /var/tmp/jw16-kc/)

| artifact | sha256 | note |
|---|---|---|
| kernelcache.release.mac13j (ESP stub) | 5b251a816ed2725d4529660a810b09ba099b71c7b25de1e411dce97138a7b28f | Asahi stub, ProductBuildVersion 22G74 (macOS 13.5), BuildManifest.plist alongside |
| kernel-live.release.bin (from this window) | df5ee19fa7eb6713593549f61b337ab0852b5b9c3c224f63c95feaec11b9f301 | /System/Library/Kernels/kernel.release.adx, 16,728,472 B, Darwin 25.6.0 xnu-12377.161.14~5/RELEASE_ARM64_T6000 |
| BootKernelExtensions.kc | pending next macOS window | the PMGR kext lives here, not in the base KC |

## 5. Return to Omarchy

out5.tgz (sha 41b91301c8e9b0440f556d21cbd80a0027240b01e075033d072c356adb9f6743)
fetched before reboot; plain reboot (BootNext consumed, default Omarchy);
Linux answered ssh at 18:05:11 (up 0 min, 7.1.6-1-1-ARCH); llm-inference
started, `/health` `"status":"ok"` after 1 poll, real completion probe
`finish_reason=length` on qwen3.8-27b (8 max_tokens).

## Artifacts

Shipped Mac outputs are path-scrubbed: `/Users/joshuawarren` → `~`
(privacy-hook policy; hashes and timings unaffected).

`artifacts/step2/`: run5.log, parakeet.log, full ane-arm stderr set
(cold/warm1-3/rep1-10) + stdout_ane-cold + SHA256SUMS.outputs,
bench_ane_dt.json, goldcheck_ane_dt.txt, perfstate-probelist.txt
(all-arm/gpu/cpu stderrs and the kernelcache binaries ride in
`out5.tgz` on PVE, not in git). Raw on the Mac:
~/levers3-mac/out/, on PVE: /var/tmp/levers5/out/.
