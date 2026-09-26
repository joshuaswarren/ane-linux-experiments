# T6001 ANE perf-state capture decoded — ApplePMGR domain 8 apply path captured live (2026-09-25)

Owner: Jw16Levers5 (analysis). Capture: Jw16Levers7's jw16 macOS window
(SIP disable took on retry; AneClockM1's name-based ane-perfstate.d,
25G83 adaptation 3). Raw: PVE `/tmp/levers7-raw/ane-perfstate.out`
(84,643 B, 950 lines, sha256 prefix 732fc457ba3b88fd). This closes the
original step-3 blocker: the exact write set macOS performs for the ANE
perf state on T6001 is captured.

## What the capture proves (live T6001, macOS 26.6.2/25G83)

1. **`ApplePMGR::_setPerfState` IS the live ANE path, and the ANE domain is
   8** — 36 probe hits `SET f=_ZN9ApplePMGR13_setPerfStateEjhj a2=8` (the
   (u32, u8, u32) signature; a2 = domain). This supersedes the 22G74 static
   read ("domains 1-5/13 accepted, 8 not seen") — the live 25G83 kext
   accepts domain 8, same as T8103. States requested: 0 only, in this
   window (idle-state requests; the ANE work was running during the WRITE
   bursts that precede/follow them).
2. **913 `writeReg32` writes captured inside the domain-8 gate** (i.e. the
   ANE perf-state apply), across 10 distinct (RegMap, reg) targets, in 16
   time bursts (gap > 0.5 s) that align with the window's encoder runs.
3. **Targets** (RegMap index = ApplePMGR's internal map; the map→base-PA
   table lives inside the kext, not in the capture — decode assigned to
   AneClockM1 from the 22G74 ApplePMGR disassembly):

| RegMap | reg | writes | distinct set values | read |
|---|---|---:|---|---|
| 0 | 0x1e8 | 430 | 9: 0x0404004f, 0x04040340, 0x00f040000, 0x00f04000f, 0x00f0403ff, 0x00f0f02ff, 0x0140f024f, 0x01f04000f | hottest target; reads as the ANE PS/PLL ladder steps |
| 0 | 0x268 | 12 | 0x00f00000f, 0x00f0000ff, 0x00f0003f0, 0x01f00000f | ladder |
| 0 | 0x2c8 | 7 | 0xf, 0x3f0, 0x1000000f | ladder |
| 0 | 0x1800c | 9 | 0x0, 0xf, 0x2f | gate open/close around bursts |
| 0 | 0x18014 | 138 | 0x0, 0xf, 0x2f | gate open/close around bursts |
| 2 | 0x1f8 | 3 | 0xf, 0x3f0, 0x1000000f | ladder |
| 2 | 0x3c0 | 180 | 0x00f00000f, 0x00f0000ff, 0x00f0003f0, 0x01f00000f | ladder |
| 2 | 0x64000 | 92 | 0x0, 0x1 | power-gate toggle |
| 113 | 0xa00 | 36 | 0x80000000\|N, N ∈ {0,1,2,5,0x10,0x12,0x23,0x30,…} | ascending perf-controller work tokens (submitWorkToPerfController shape) |
| 113 | 0x2000 | 6 | 0x0, 0x1 | toggle |

## Consequences

- The step-3 blocker is **gone**: the exact behavioral write set exists as
  captured data. What remains before a Linux driver can replicate it is
  only the RegMap→base-PA table (AneClockM1, from the 22G74 ApplePMGR
  disassembly / T6001 ADT pmgr reg entries; note the T6001 ANE-adjacent
  PMGR is at 0x28e080000 per the j316c overlay dts, and perf-regs[8]
  (ANE PLL block) is 0x28e070000 size 0x64).
- The `ane_tunable` scaffold (Jw16Levers6, /var/tmp/levers5-tunable-scaffold/)
  was deliberately engine-window-only; the captured targets are PMGR-mapped,
  so applying them needs the scaffold extended with a scoped PMGR-map base
  (or a second param) once AneClockM1's RegMap→PA decode lands. Jw16Levers6
  owns install/measure.
- Kernel-collection note for the record: /System/Library/KernelCollections/
  on 26.6.2 holds x86_64 stub executables (cputype 7, ncmds=3, sizeofcmds=12),
  not ARM64 collections; the boot payload used at runtime appears transient
  (Preboot/<UUID>/boot/kernelcache, 31.5 MB, seen once then cleaned). The
  T6001 ANE tunable-table lead therefore closes as "not statically present
  in any obtainable container" per the 0865be7/0af98f6 receipts.

## Artifacts

- `results/perfstate-capture-analysis.json` — structured targets + summary.
- Raw capture on PVE `/tmp/levers7-raw/ane-perfstate.out` (sha 732fc457…,
  3-day /tmp retention on PVE unknown — copied into this receipt as
  `results/ane-perfstate.out`).
