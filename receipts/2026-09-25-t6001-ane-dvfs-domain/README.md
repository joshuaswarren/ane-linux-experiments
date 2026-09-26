# T6001 ANE DVFS domain: decoded from macOS, driven from Linux, no effect (2026-09-25)

Owner: AneClockM1 (Main). Host: jw16 (M1 Max, T6001, j316c, 7.1.6-1-1-ARCH),
slot from Jw16Levers7. Source capture: Jw16Levers7's macOS 25G83 dtrace of
`ApplePMGR::_setPerfState` / `ApplePMGR::writeReg32`
(`/tmp/levers7-raw/ane-perfstate.out` on PVE, sha256 `732fc457ba3b88fd…`,
receipt a3641215 for the raw capture).

## 1. RegMap -> PA

`writeReg32(RegMap, reg, value)`: RegMap N is pmgr ADT `reg[N]`, which equals
ioreg `IODeviceMemory[N]` (241 entries each, same order; IODeviceMemory minus
raw is 0 or 0x200000000). Anchors: map0 0x268 and 0x2c8 are exactly
`ps_ane_sys` and `ps_ane_sys_cpu` of `pmgr@28e080000` in the Linux DT, with
values in the pwrstate layout (bit 28 AUTO_ENABLE, 27:24 PS_AUTO, 19:16
PS_MIN, 7:4 ACTUAL, 3:0 TARGET).

| RegMap | base PA | written regs (DT label) |
|---|---|---|
| 0 | 0x28e080000 | 0x1e8 ps_afr, 0x268 ps_ane_sys, 0x2c8 ps_ane_sys_cpu, 0x1800c, 0x18014 |
| 2 | 0x28e580000 (pmgr_east) | 0x3c0 ps_gfx, 0x1f8 ps_spi1 (GPU/SPI, unfiltered capture), 0x64000 |
| 113 | 0x400004000 (IODeviceMemory[113] = 17179885568, len 0x4000) | 0xa00 DVFS command, 0x2000 DVFS on/off |

## 2. The macOS ANE sequence

Power-up: 0x18014 0xf->0x2f, east+0x64000 = 1, ps_afr on, 0x1800c
0xf->0x2f, ps_ane_sys on, **+0x2000 = 1**, ps_ane_sys auto,
`_setPerfState(8, 0)` -> **+0xa00 = 0x80000000**, ps_ane_sys_cpu on.
Every `_setPerfState(8, s)` is followed within about 10 us by one write to
+0xa00 = `BIT(31) | prev << 4 | new` (all 16 distinct samples fit, e.g.
0x80000035 = 3->5, 0x80000054 = 5->4). A run ramps 0->5 and idle returns
to 0. Power-down mirrors it: state 0, +0x2000 = 0, ps_ane_sys off. The
T6001 ANE ladder (`voltage-states8`) is 300@550, 540@615, 780@650,
1020@734, 1260@800, 1500@909 MHz@mV.

## 3. Linux reads (step 1, SET-gated one-word reader, SET+0 = 0x3ff each)

| PA | Linux value |
|---|---|
| 0x400004A00 (DVFS cmd) | 0x0 |
| 0x400006000 (DVFS on) | 0x0 |
| 0x28e09800c | 0x2f (macOS's powered value) |
| 0x28e098014 | 0x2f (macOS's powered value) |
| 0x28e5e4000 | 0x0 |

All reads clean, no reset.

## 4. dvfs_ane (step 2) and the A/B (step 3)

omarchy-ane `agent/t6001-dvfs-ane` e2a5c5e (not merged): default-off
`dvfs_ane`, T6001 descriptor only, page mapped non-posted; online (+0x2000 = 1,
+0xa00 = 0x80000000) at probe resume and after a recovery cycle, top state on
the boost hold, state 0 on its idle expiry, offline before power-down.

Whole encoder, Jw16Levers7's method (worker at 1 and 8 iterations,
per-iter = (e8 - e1) / 7; pin = output sha16 fca96f1355485ec3; the
`ane-reference/encoder_hidden.npy` float32 file is not the pin):

| arm | per-iter ms | pin |
|---|---|---|
| e2a5c5e, dvfs_ane=0 | 438.78, 436.62 | match |
| e2a5c5e, dvfs_ane=1 | 433.54, 431.46, 431.66 | match |
| installed 5ecff86 after restore | 441.08 | match |

The Jw16Levers7 boot-variance band on this box is 427.6-441.3 ms/iter; a
300 -> 1500 MHz step would be several times faster. After the module wrote
+0x2000 = 1 and +0xa00 = 0x80000000 both read back 0x0
(`raw/jw16-kernel-log.txt`: "ANE-DVFS online: on 0x0 cmd 0x0"), and both
read 0x0 again in the middle of a 16-iteration run with the top state written.
The writes are either write-only commands or dropped; either way the direct
writes do not reproduce what macOS gets. Not merged, not installed; jw16 is
back on 5ecff86.

## 5. The ANE clock/counter pairs are a 24 MHz timebase

`ane_ctr_probe.ko` (omarchy-ane clock worktree, read-only, SET-gated) with
base 0x284000000, snapshots 1 s apart (`raw/ctr-dvfs-on.txt`):

| window | CLK0-3 | CTR0-3 |
|---|---|---|
| idle | 24.000 MHz | constant 0x3 |
| busy (whole-encoder run) | 24.000 MHz | constant 0x3 |

m1n1 hw/ane.py's CLK/CTR registers do not measure the engine clock; the jwm1
reads Main held for the T8103 1.22x gap were withdrawn (same layout there).

## 6. Open

- What the macOS accessor does for RegMap 113 beyond the traced arguments:
  AppleT6000PMGR::writeReg32 has a read-modify-write path that ORs BIT(29)
  before the bus write (22G74 disassembly, AneClockM1 earlier today), and a
  PMP- or firmware-backed map would also explain read-as-zero. Needs kext
  disassembly of the 25G83 ApplePMGR accessor for map 113.
- east+0x64000 is 1 in every macOS ANE power-up and 0 on Linux.

## 7. Note on receipt a535ac93

Commit a535ac93 (section 10 of receipts/2026-09-25-m1-ane-clock-macos) carries
the author email `816217+joshuawarren@users.noreply.github.com` (missing the
"s"); history was left alone because another agent's commit already sat on
top of it.
