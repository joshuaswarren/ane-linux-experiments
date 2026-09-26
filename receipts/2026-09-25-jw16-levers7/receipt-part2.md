# jw16-levers7 part 2 — SIP window: perf-state CAPTURED and decoded; 5ecff86 installed; levers staged (2026-09-25)

Owner: Jw16Levers7. Continues receipt-part1.md after Joshua's second
recoveryOS pass.

## 1. The capture (the step-3 unblock)

- `csrutil status`: **disabled** (verified over ssh on 26.6.2). fbt
  probes listed live.
- Script provenance: AneClockM1's name-based ane-perfstate.d does NOT
  compile on 25G83 — `_handlePerfStateRequest` does not exist on this
  build (a `-l` pre-verify that counts error lines as matches says
  otherwise; lesson recorded). Adapted script (macOS dtrace matches
  script probes against RAW mangled names; wildcards hit):
  `/private/var/tmp/ane-perfstate-25g83b.d`, compile-checked with
  `dtrace -e` before any bench. Capture + `bin/encoder_bench … ane
  3 10` on the Mac, SIGINT stop.
- Artifact: PVE `/tmp/levers7-raw/ane-perfstate.out`, 950 lines,
  sha256 `732fc457ba3b88fd…`. Decode (Jw16Levers5 receipt
  `2026-09-25-t6001-perfstate-capture`, main @ 4e221b34, +
  AneClockM1's RegMap bridge resolution):
  **ANE = ApplePMGR domain 8** (`_setPerfState(Ejhj)`, 36 hits);
  op-point write = **PA 0x400004A00** (DVFS_CMD, RegMap113 0x400004000
  +0xa00, pre-bridge ADT 0x200004000), 32-bit,
  **value = 0x80000000 | (prev_state << 4) | new_state**
  (0x80000035 = 3→5 …); companion **0x400006000** (DVFS_ON, 0/1).
  6-entry T6001 ANE ladder, state 5 = 1500 MHz; macOS ramps 0→5 per
  run, 0 when idle. The 440/140.6 = 3.1× gap fits Linux sitting at
  state 1 (540 MHz, 2.78×) + the T8103-class 1.13 residual — matching
  the part-1 receipt's inference. Linux never writes 0x400004A00.
  Excluded as NOT ANE perf: map0 0x1e8 = ps_afr, map2 0x3c0 = ps_gfx,
  map2 0x1f8 = ps_spi1 (pwrstate words).
- dvfs_ane apply (default-off param, read-before-write, encoder A/B +
  gold + battery + Parakeet gates) = AneClockM1, Main-approved, jw16
  owner-coordinated; my generic PA=VALUE scaffold was deleted unused
  in favor of their semantic-aware param.

## 2. macOS denominators (this session, 25.83 boot)

encoder_bench ane arm 3+10 medians: **140.58 → 138.17 → 132.07 →
132.50 → 136.68 ms** (compile_ms 302→253; hidden_count 240000,
mask_sum 375 every run; the ane 1341/cpu 33 placement constant). The
macOS number breathes 132–141; the pass bar stays ≤140.86 per
assignment, with 132 as the stretch mark.

## 3. omarchy-ane main 5ecff86 on jw16 (boost hold-while-busy)

Merged by AneClockM1 after jwm1 gates (my premature push was rolled
back pre-build; see part 1). Built on jw16 (isolated tree copy — jw16
has no GitHub creds), srcversion `9109B200A150B27F484F718` (identical
to the jwm1 install), installed at
`/lib/modules/$(uname -r)/updates/ane.ko` (stock backup
`/tmp/ane.ko.stock-32DC3F35.bak`; /tmp wipes each boot). Encoder A/B:
n1/n8 pairs → **441.0 / 441.3 / 429.3 ms/iter** — straddles the
427–441 boot-variance band = **neutral on T6001, as predicted**
(engine-side perf state is the gap, not CPU submit bandwidth). Gold
`fca96f1355485ec3…` bit-exact on every run; llm real-completion probe
green after. Left installed per fleet decision.

## 4. jw16 boot policy incident + fix

The macOS-window reboots revealed jw16's default boot volume had
become macOS (likely reset during Joshua's 1TR pairing). macOS-side
`bless --setBoot --device disk0s4` fails ("no group UUID"); the
working path was `sudo bless --setBoot --mount /Volumes/Omarchy` (the
APFS stub volume, disk0s3 container) — reboot then landed Linux and
verified. Noted for any future dual-OS window on jw16.

## 5. KC verdict (with Jw16Levers5)

/System/Library/KernelCollections/*.kc on 26.6.2 are **x86_64 stubs**
(cputype 7) — byte-faithful copies staged at
`/var/tmp/jw16-kc/{Boot,System}KernelExtensions.kc.levers7` (shas
c80161fa… / fbab2d48…, on-Mac-verified) are the wrong container for
the tunables walk. A transient Preboot boot/kernelcache (31.5 MB)
self-cleaned mid-window. Levers5's closing verdict: "not statically
present in any obtainable container" — the dtrace capture supersedes
the static route. `ane-perfstate-25g83b.d` staged on the Mac for any
future window.

## 6. Parakeet mel lever — root cause + patch staged (not hardware-proven)

mel_frontend = wall 140.2 ms, GPU busy 22.9, ONE submission with 8
compute dispatches (gpu_counter deltas), run→done 22.9, queue→run
0.016: the ~117 ms is host-side pre/post the single job. Found:
`vkCreateComputePipelines(device, VK_NULL_HANDLE, …)` — **no
VkPipelineCache at all** in the omarchy backend, so every fresh
process pays Mesa's full pipeline compile for the 8 mel kernels even
with the SPIR-V disk cache warm (that cache stores binaries, not
compiled pipelines). Patch on mlx-omarchy **agent/pipeline-cache**
(f97afca13): persistent VkPipelineCache seeded from
`~/.cache/mlx-omarchy/pipelines/<uuid>.vkpc` (magic+UUID-validated
header), passed to vkCreateComputePipelines, written back on teardown
(atomic tmp+rename, 64 MB cap), `MLX_OMARCHY_PIPELINE_CACHE=0`
disables. 148 insertions across compute.h/.cpp/device.cpp; one call
site (create_pipeline(kernel) funnels into the span overload). NOT
yet built/deployed/measured — the A/B (mel stage before/after, then
full contract vs macOS 264) is queued behind the DVFS lane on the
same box. TDT fusion lever unchanged from part-2-of-levers6 evidence
(278 jobs × 0.9 ms engine; merge decoder+joint into one eval per
frame = the next bounded step).

## Host state (close of my lane)

jw16: Linux (now blessed default), ane = 5ecff86 installed, gold
bit-exact, llm-inference healthy with real-completion probe, ANE/GPU
idle, DVFS lane handed to AneClockM1 (read-only probe first, then the
Main-approved dvfs_ane param). No uncommitted work on any host.
