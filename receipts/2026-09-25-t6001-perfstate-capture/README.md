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
   table lives inside the kext, not in the capture — decoded by AneClockM1,
   see the amended Consequences section: map0 = 0x28e080000, map2 =
   0x28e580000, map113 = 0x400004000; the "reads" below are my FIRST-PASS
   hypotheses, superseded there):

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

## Consequences (amended after decode — AneClockM1, data-derived; Main reassigned
## the RegMap decode to them after this receipt's first pass)

- **RegMap→PA decoded from the T6001 ADT** (pmgr reg[] = 241 IODeviceMemory
  entries; anchored by map0 0x268/0x2c8 = ps_ane_sys/ps_ane_sys_cpu):
  **map0 = 0x28e080000, map2 = 0x28e580000, map113 = 0x400004000**
  (independently cross-checked by me for map0/map2: ADT reg[0] = 0x8e080000,
  reg[2] = 0x8e580000 with the 0x2_00000000 bridge — both confirm; for
  map113 the ADT reads reg[113] = 0x200004000, one digit off the decode's
  0x400004000 — flagged, AneClockM1 owns the final PA call).
- **Correction to my first-pass table read**: map0 0x1e8 (= ps_afr,
  0x28e0801e8) and map2 0x3c0 (= ps_gfx, 0x28e5803c0) are PWRSTATE words
  (AUTO_ENABLE bit 28 / PS_AUTO 27:24 / PS_MIN 19:16 / target 3:0) and
  partly GPU — NOT ANE perf hardware. The "ladder-shaped" 0x1e8 values are
  PS_AUTO/PS_MIN changes.
- **The domain-8 ANE perf write = PA 0x400004A00 (map113 base + 0xa00),
  value = 0x80000000 | (prev_state << 4) | new_state** — the T6001 ANE
  op-point register; state indices run a 6-entry ANE ladder (state 5 =
  1500 MHz). This is the write a Linux default-off param replicates
  (implementation: AneClockM1 + Jw16Levers7 on jw16, in flight at receipt
  time).
- The `ane_tunable` scaffold (Jw16Levers6) stays engine-window-only; the
  ANE op-point write needs its own scoped-base param (base 0x400004000 or
  the corrected PA, offset 0xa00) — Jw16Levers6 owns install/measure.
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
