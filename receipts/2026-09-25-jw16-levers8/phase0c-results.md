# Phase 0c EXECUTED — first 4 KiB at PMP+0: resident ARM64 firmware (2026-09-26)

Scope exactly per Main's authorization: PS gate re-passed
(0x1f0000ff f/f), bootargs ptr/size precheck identical
(0x78800/0x234), then ONLY the first 4096 bytes at PMP+0 read and
STORED. No other offsets, no writes, no CPU_RUN. Module
/var/tmp/pmp-phase0c on jw16, loaded once, unloaded.

## Stored bytes

`artifacts/pmp-sram-head-4k.bin` — 4096 bytes,
sha256 `c3208d232d23a8b038c434de69e88c5c7d9c340893688a42677191d01106fbe9`
(reconstructed byte-exact from the module's hex dump; dmesg retained).

## Content class: executable ARM64 firmware, not data, not zeros

- Offset 0x0: `14 00 00 95` LE = 0x14000095 — `b +0x254`: a reset-entry
  branch over a parameter/reserved block. Classic firmware entry.
- Offsets 0x80 / 0x100 / 0x180: 0x80-strided stubs, each beginning with
  `MSR` system-register writes (0xd538521c family) followed by
  `b +0x254`-class branches — the ARM exception-vector layout
  (VBAR-style, 16 × 0x80 slots), i.e. a real vector table.
- From 0x200: dense code (37-60 nonzero bytes per 64 B through the
  head).
- The module's nonzero map: [0x0:2] [0x80:13] [0x100:13] [0x180:13]
  [0x200:37] [0x240:47] [0x280:60] [0x2c0:49] … continuing dense
  through the 4 KiB.

## Identity comparison status

NO identity-matched offline PMP firmware extract exists in our
artifacts (the KC kexts were 7 KB stubs with no blob; SystemKC carries
no PMP content — phase0-plan.md §3d). Therefore this head cannot yet be
matched against a known-good reference; identity verification needs
either a macOS-side firmware source or a decode of the full image
(requires additional bounded reads beyond this authorization). What
the head DOES establish: non-uniform executable ARM64 content with a
coherent vector-table layout resident at PMP+0 in a powered, quiesced
coprocessor — the physical backing for pmp.rs's fw=None assumption.

## What remains before stock-driver RTKit HELLO (pmp.rs probe() order)

1. DT: /soc/pmp@28e700000 `status=okay` (staged DTB, byte-verified
   fallback boot) — currently disabled.
2. DT: add `apple,board-id` + `apple,dram-vendor-id` (optional
   `apple,dram-capacity`) — REQUIRED props; probe fails safely BEFORE
   CPU start without them. Values must be sourced from the boot chain
   and verified.
3. Firmware resident: CONFIRMED present at PMP+0 (this receipt) — the
   driver's fw=None assumption now has physical backing, modulo item
   "identity" above.
4. Mailbox: mbox@28ec08000 platform device present and apple-mailbox
   driver BOUND (verified in sysfs).
5. DART: iommus → /soc/iommu@28e300000, compatible apple,t6000-dart,
   platform device present (binds via the standard apple_dart driver).
6. THEN: probe() → CPU_CONTROL |= CPU_RUN (first write, out of scope of
   this authorization) → RTKit HELLO on endpoint 0x20 → the firmware's
   GET_IOVA_TABLE / MALLOC / SET_BUF / REGISTER_IOREG / SET_IOREG
   requests; missing apple,tunable-* DT tables are logged and
   registered size-0 (boot proceeds unconfigured — the safety boundary
   Main drew; no DVFS/SET_IOREG semantics accepted without verified
   tables).

## Constraints honored

No writes, no CPU_RUN, no bulk beyond the authorized 4 KiB, no
additional offsets, no reboot, no service changes.
