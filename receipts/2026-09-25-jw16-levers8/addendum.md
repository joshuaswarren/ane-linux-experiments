# jw16-levers8 addendum — boundary-corrected contract, mel host cost located, PMP prerequisites (2026-09-26)

Owner: Jw16Levers8. Continues receipt.md in this directory. Supersedes the
mixed-boundary 4.6x framing per Main's parsed denominators.

## 1. Boundary correction (Main parsed all ten step2 logs)

macOS (jw16 macOS slice, 25.83, levers5 step2, n=10): inference median
**264 ms** (mel 15 + encoder 146.5 + decode 102.5), models-ready median
**315 ms**, paired load+inference median **576 ms** (excludes process
startup + audio decode; NOT full CLI time). 264 is a true median of the
ten reps, not just rep10.

Linux (jw16, f26192bbf wheel, warm per-process transcribe reports, n=7):
mel 113.8 ±2, tdt 174.6, encoder stage wall 868 (spawn+boot+exec+transfer,
0 GPU submits from the app process — the ANE worker is a separate
process), audio 6.5, decoder_load 45, detokenize 9.4.

Matched boundaries, no bar change (strict same-boundary <=1.00x stands):

| boundary | macOS | Linux | ratio |
|---|---:|---:|---:|
| inference-only (mel+enc-exec+tdt) | 264 | ~728 (112 + ~440 enc-exec [cross-harness: Jw16Levers6 slope, not timed inside transcribe] + 175) | ~2.76x |
| models-ready (adds decoder_load) | 315 | ~773 | ~2.45x |
| load+inference (macOS definition) | 576 | not directly comparable: Linux loads worker + islands per process | — |
| full per-process transcribe (mixed boundary) | n/a | 1207-1240 | qualified mixed-boundary, NOT an acceptance result |

The Linux encoder-exec number inside the app path is the open
measurement gap for a clean 1.00x verdict; the direct-worker slope 440
ms/iter is the best current attribution.

## 2. Mel host cost — MEASURED, per-process one-time setup

Installed app (f26192bbf wheel), warm caches, fresh process:
mel_frontend = **113.8 ms wall, ONE submission, 6 compute dispatches**;
same call repeated in-process = **7.4-9.4 ms total**. The ~106 ms is
per-process one-time setup before/at the first eval, NOT per-call work.

Cold-cache physics (profiler over the installed module, no code
changes): first eval in a fresh process = **10.15 s** with cold Mesa
shader cache AND cold pipeline cache (matches the app's cold-cold
transcribe 10226 ms exactly); in-process repeats 7.4-9.4 ms. Warm-cache
fresh process = 110.8-146.4 ms first call (two back-to-back processes +
one after a 90 s idle gap; matches the app's 113.8), so cross-process
cache persistence works and the ~100 ms toll survives it.

Per-kernel split of the fresh-process toll (per-stage first eval, two
processes, warm caches — reproducible ±2 ms):
frames 22.5-22.9, dft 29.9-31.2, power 15.8, mel_project 22.8-25.8,
statistics 20.0-20.8, normalize 2.2-2.3 ms — sum ≈ 117-120 ms.
Graph construction is trivial (constants 0.4 ms, all build phases
<1.4 ms). Verdict: the ~100 ms is a **uniform per-pipeline first-use
toll (~16-31 ms × 7 stages) at first dispatch, host/driver-side**
(GPU busy during mel is only 22.9 ms per the levers7 profile, so the
toll is not GPU work). Neither the SPIR-V cache nor the VkPipelineCache
absorbs it (A/B receipt.md: neutral). The lever, if wanted, lives in
Mesa's per-pipeline first-use path (joshuaswarren/mesa-1,
honeykrisp-omarchy) or a backend persistent pre-warm — a Mesa/backend
lane, not an application change. melprof1's one 10.2 s warm-cache
outlier remains unexplained (melprof2's identical setup reproduced
110-146 ms) — flagged, not load-bearing.

## 3. PMP — read-only inspection results (no hardware writes, no boot changes)

Kernel/DT inventory (all read from the live system):
- kernel 7.1.6-1-1-ARCH: **CONFIG_APPLE_PMP=y, CONFIG_APPLE_PMP_REPORT=y**
  (in-tree Rust driver apple_pmp, compatible apple,t6000-pmp-v2).
- live DTB: /soc/pmp@28e700000 EXISTS, **status=disabled**, reg-names
  "pmp"+"asc" (matches driver), iommus + mboxes + power-domains +
  apple,pio-ranges (4 entries) all declared. /soc/pmp_report@28e3c0000
  present and BOUND (report@11, report@1d sub-devices live in sysfs);
  the ANE report entry (report@a pmp-ane-sys) remains disabled per the
  2026-09-23 m1max-ane-clock receipt.
- prior capture (existing, cited): report SRAM reads tgt_read=0x60003000,
  actual=0x0, status=0x0, no ack on bit-set = **PMP firmware not running
  under Linux**; the report-bit write was proven reversible (probe
  cleared it on unload).

Driver source (AsahiLinux/linux asahi branch, drivers/soc/apple/pmp.rs,
449 lines) — ABI facts that size the prerequisites:
- probe() boots the CPU IMMEDIATELY on bind: CPU_CONTROL |= CPU_RUN,
  RTKit with **fw = None** (no firmware file anywhere in the driver) —
  the driver can only boot iBoot-parked firmware already in PMP SRAM.
  Whether jw16's SRAM still holds parked fw under Linux is UNKNOWN —
  no full SRAM dump exists (only the report-SRAM registers above).
- probe() REQUIRES DT props apple,board-id + apple,dram-vendor-id
  (optional apple,dram-capacity) to patch bootargs (BDID/DVID/DCAP).
  jw16's pmp node HAS NONE of these — so a naive status=okay flip fails
  at probe() BEFORE any CPU start (fails safe). The IDs must be sourced
  from the live ADT (iBoot-written) and added to the node.
- tunables: the fw REQUESTS IOREGs by name (REGISTER_IOREG, 0x30-byte
  name); the driver answers from DT apple,tunable-<name>; **missing
  names log "unknown property" and register size 0 — boot proceeds**.
  Consequence (Main's concern, confirmed at source level): a PMP booted
  on this DT would run with ZERO registered IOREG rail configuration.
  No SET_IOREG of substance, no DVFS replay, and no trust in reboot
  reversibility until the exact table set is extracted and verified.
  Upside: the boot-time request list itself enumerates precisely which
  tables macOS supplies — the metadata extraction target list.

### Exact prerequisite chain to bounded PMP bring-up

1. **Phase 0 (smallest discriminating step, read-only):** quiesce-window
   driver that (a) checks the PMP power-domain state via kernel-owned
   interfaces, (b) if powered, maps and READS PMP SRAM 0x28e700000
   +0x100000 (firmware present? bootargs ptr at +0x22c) and ASC
   CPU_CONTROL 0x44 (CPU_RUN bit), 16 KiB-class dumps, no writes.
   Discriminates: parked-fw (RTKit can boot as-is) vs empty-SRAM
   (firmware staging from the macOS ApplePMPFirmware payload required —
   a categorically larger prerequisite: custom fw loading the in-tree
   driver does not support).
2. Extract/verify firmware ABI + rail metadata (off-device, can start
   now): the decompressed 22G74 kernelcache macho on PVE
   (/var/tmp/jw16-kc/kernelcache.release.mac13j.macho, 96.7 MB) contains
   the ApplePMP kexts (558 ApplePMP string hits; kexts are linked, no
   LC_FILESET entries — extraction needs segment-level parsing or the
   clean source: /System/Library/Extensions/ApplePMP{,Firmware}.kext
   from jw16's macOS volume). Deliverables: firmware blob identity +
   the IOREG name->payload tables; cross-check against the boot-time
   request list from (1)'s optional follow-up.
3. DT patch content: status=okay + apple,board-id/DVID(/DCAP) from live
   ADT + (only when metadata lands) apple,tunable-* tables. Staged DTB
   with byte-verified fallback boot; netconsole armed.
4. Review gate: SoC-wide power infrastructure — bring-up executes only
   on a reviewed plan (this addendum + Phase 0 results are the inputs),
   idle quiesce window, no serving load, reboot as the documented
   reversal. Direct PLL_ANE0 writes without voltage sequencing remain
   forbidden (ane-dvfs §5 class). map113 DVFS replay stays gated behind
   verified tunables + healthy report acks.

No PMP hardware writes were performed in this lane; every action above
is either a file read, a sysfs read, or a proposal.

## 3b. Per-pipeline first-use — PROFILED: the omarchy MSL translator (2026-09-26 followup)

perf (4999 Hz, frame pointers, one fresh process running the per-kernel
split; 1203 samples): the toll is **the backend's MSL→SPIR-V kernel
translator**, not Mesa. Flat profile: std::regex machinery in
libmlx.so ≈ 35-40% of samples (`_Executor` 20.8%, `regex_traits`
4.5+4.1+1.7+0.65%, `vector<sub_match>` 2.3%, `__regex_algo` 0.9%,
locale/string support ~2%), against Mesa's `blake3_hash_many_neon`
(cache keying, libvulkan_asahi) at only 0.8%. Call chain:
`eval → eval_impl → gpu eval → mlx::core::fast::CustomKernel::eval_gpu →
translate_msl / translate_types / translate_atomic_parameter /
translate_bfloat_parameter` (symbols confirmed via nm -C; the same
"shared-memory regex" translator family documented in the
tdt-speculative-window receipt). Each of the 7 mel kernels pays its
translation per process; steady state (9.4 ms) skips it.

**Fix that removes the actual cost** (backend change, mlx-omarchy):
persist the translated SPIR-V per dynamic kernel across processes,
keyed by source hash, and skip `translate_msl` on hit — the backend
already has a content-addressed SPIR-V disk cache for its embedded
kernels; the dynamic `mx.fast.metal_kernel` path evidently bypasses it.
Provable with the existing fresh-process mel A/B harness (first-call
110-146 ms → expected ~25-40 if translation is the whole toll). NOT
implemented in this lane; scoped for the next one.

## 3c. Resident combined path — MEASURED (existing consumer, no new abstraction)

The shipped CLI already supports `--repeat N` (resident ANE session,
`ANE_ISLAND_MODE=resident-batch` default). One process, --repeat 4,
all pins green (104/104, transcript match):

| rep | total ms | mel | encoder | tdt | notes |
|---|---:|---:|---:|---:|---|
| r1 (startup) | 1249.2 | 115.3 | 870.0 | 197.2 | worker spawn+boot+island load |
| r2 | 633.1 | **7.8** | **440.8** | 130.8 | resident: exec only |
| r3 | 634.7 | 7.8 | 440.8 | 130.8 | |
| r4 | 636.3 | 7.8 | 440.8 | 130.8 | |

Cold-cache reference (separate, receipts §2/§3): first process with
cold Mesa+pipeline caches = 11387 ms total, mel 10226.

Same-boundary comparison at warm-resident: Linux 634 ms full combined
vs macOS models-ready median 315 (2.0x) and macOS load+inference 576
(1.10x, boundary caveat: Linux r2 still pays decoder_load 42.1/call);
inference-only mel+enc-exec+tdt = 579.4 vs macOS 264 (2.19x). The two
remaining gaps are ANE encoder exec (440.8 vs 146.5 — the ANE clock
story; PMP lane) and TDT (130.8 vs 102.5 — Mesa hop/bandwidth per
Jwm1Kernels3). Mel warm (7.8) is FASTER than macOS (15).

## 3d. PMP firmware/ABI extraction from the committed KC (off-device)

Parsed /var/tmp/jw16-kc/kernelcache.release.mac13j.macho (22G74 boot
KC, 2 sections: __PRELINK_TEXT 0x96c000 + __PRELINK_INFO 0x320000;
no LC_FILESET — prelink layout). Extracted from the prelink info dicts:

- ApplePMPFirmware.kext: LoadAddr 0xfffffe00074771f0, **size 7193 B**,
  dumped (`ApplePMPFirmware.bin`, sha256 434c13873058ab7f…). Sections:
  __text 0x1208 + __const 0x9d8 — a driver stub, **NO firmware blob**.
- ApplePMP.kext: LoadAddr 0xfffffe00074755d0, listed size 7193 B but
  its sections (incl. __text 0xd718, __DATA_CONST __const 0x5140)
  reference addresses OUTSIDE this macho's __PRELINK_TEXT — the
  driver's real content lives in the System KC / on-demand collection,
  not in this boot KC file. Fresh dump written (`ApplePMP.bin`,
  sha256 1524be24e5f0fa10…, known-incomplete).

Consequence for the prerequisite chain (§3): the firmware payload is
NOT in the committed boot KC. Verified sources to check before any PMP
boot: (a) the System KC macho (361 MB, on PVE, complete as of the
levers7 re-pull), (b) the macOS volume kexts, (c) iBoot NOR provisioning
— note the ADT has NO pre-loaded for pmp (vs ane0 pre-loaded=1), so
iBoot parking under Asahi is unproven. This sharpens Main's warning:
do not boot PMP until the firmware blob is extracted AND its identity
verified against the RTKit expectations, and tunables are in hand.



## 4. macOS denominator receipt

All ten step2 logs parsed by Main: medians inference 264, models-ready
315, load+inference 576; component medians mel 15 / encoder 146.5 /
decode 102.5. Raw logs:
.work/jw16-levers5/receipts/2026-09-25-jw16-levers5/artifacts/step2 (relative to the shared checkout, read-only)
(read-only; the shared checkout is untouched).
