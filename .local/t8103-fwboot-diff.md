# T8103 (M1) firmware-boot reference vs T6001/T6021 — field-by-field diff

Date: 2026-09-24 · AneStaticStart. Sources: omarchy-ane `ane/src`
(`ane_drv.c`/`ane_tm.c`, current checkout), m1n1
`proxyclient/m1n1/fw/ane.py` + `m1n1/hw/ane.py` (Eileen's H13 oracle),
H13 kext 9.512.0 fixture
(`receipts/2026-09-18-t6021-engine-layout-mined/kext-h13/`), prior T6021
kernelcache work (`receipts/2026-09-24-t6021-macos-start-sequence`).

## 1. The headline correction

Main's premise ("omarchy-ane already starts the ANE firmware on the M1")
is TRUE but easily misread. What the M1 path starts is NOT a coprocessor
CPU. The H13 (T8103/T6001) architecture has **no firmware-owned CPU start
at all**:

- Eileen's m1n1 oracle (`fw/ane.py`) `power_up()` = `pmgr_adt_power_enable`
  for `/arm-io/ane` + `/arm-io/dart-ane`, then raw ps words
  `ps_base+0x00..0x38 ← 0xf`, then `tm.reset()`. There is NO RVBAR write,
  NO CPU_CONTROL write, NO firmware image staged anywhere in the file.
  `grep` for rvbar/cpu_control/RUN/boot/start-firmware finds nothing;
  `ANEFirmware` in that file parses the *task* (.anec) container, not a
  coprocessor image.
- omarchy-ane `ane/src/ane_tm.c` `ane_tm_enable()` = `TM_TQ_EN ← |=0x1000`,
  8× `TQ_PRTY ← table`, `TM_IRQ_EN1 ← 0x4000000`, `TM_IRQ_EN2 ← 0x6`,
  then submit via `TM_ADDR/TM_INFO/TM_PUSH` and poll `TM_STATUS & IDLE`.
  Again no RVBAR, no CPU_CONTROL, no firmware load.
- Prior receipt rows already converged on this twice: the t8103 oracle
  "writes ONLY the island ps SET words" (no CPU_CONTROL, no RVBAR in the
  file), and the H13 architecture correction accepted that H13 macOS is
  the same iBoot-preload + kext-RPC family as H14 — the "host-TM" label
  belongs to Eileen's fw-less experiment flow, NOT to macOS.

So the working M1 reference proves the **host-driven task-manager submit
path** (power → tunables → TM enable → push → poll IDLE), which is exactly
the path that does NOT exist on T6021 (firmware owns TM there; the kext
scan shows zero TM/TQ sites on K14).

## 2. T8103 start path, in order (the reference)

From `fw/ane.py` + `ane_tm.c`:

1. `pmgr_adt_power_enable('/arm-io/ane')` + `.../dart-ane` (ADT parent
   walk; equivalent of Linux genpd attach).
2. ps words `ps_base+0x00..0x38 ← 0xf` stride 8 (T8103 `ps_base`
   0x23b70c000; T6001 0x28e08c000; T6021 0x28e08c000 per the SoC table in
   `ane_drv.c:707-744` — T6021 is RECOGNIZED, needs
   `allow_unqualified=1`).
3. Static tunables (`apply_static_tunables`, "cost me a solid week"):
   `(0x0,0x10) (0x38,0x50020) (0x3c,0xa0030) (0x400,0x40010001)
   (0x600,0x1ffffff) (0x738,0x200020) (0x798,0x100030)
   (0x7f8,0x100000a) (0x900,0x101) (0x410,0x1100) (0x420,0x1100)
   (0x430,0x1100)` — engine-relative, posted `write32`.
4. DART: `DART.from_adt(...).initialize()`, TTBR shared to all three
   instances, stream-0 iomap for task/data surfaces.
5. TM reset: `TQ_EN ← 0x3000` (m1n1) / `|=0x1000` (Linux driver keeps bits),
   priorities, IRQ enables. Submit: `STATUS←1, BAR1[], SIZE1/ADDR1/NID1`,
   `TM_ADDR/TM_INFO/TM_PUSH`, poll IDLE.

## 3. H13 kext: what macOS does that Linux skips (same generation!)

The H13 kext 9.512.0 `ANE_Init` (0xfffffe000931ffc4) does MORE than the
Linux driver even on H13:

- `InitializeRTBuddyEndpoints` → `InitANEScratchRegisters` →
  `startCPUWithOptions` → **RVBAR read/compose/write**
  (`read64OneShot(0x1050000)`; skip iff bit0; else
  `write64(0x8100000000000001 | entry & 0xFF7EFFFFFFFFF800)`) →
  `write32(0x1400044/CPU off, 0)` then `write32(0x10)` (0xfffffe00093204e4
  -0x9320500) → poll `read32(SCRATCH7) == 0x08042006` (1000×).
- I.e. even the H13 kext boots an ASC coprocessor CPU (Chinook
  RVBAR/CPU_CONTROL/SCRATCH7 in kext init) — the Linux driver never does
  this on ANY SoC. What Eileen bypassed with direct TM programming, macOS
  does through firmware.

## 4. Field-by-field diff: T8103 vs T6001 vs T6021 (Linux driver state)

| # | Step | T8103 Linux (works) | T6001 Linux | T6021 Linux |
|---|---|---|---|---|
| 1 | genpd/island raise | yes (5 sets, ACTUAL=0xf) | yes (SET0..4 via overlay) | yes (8 islands) — plus VENC_SYS + leaves gap (no provider) |
| 2 | static tunables | n/a (TM path needs none beyond driver) | same | MISSING: T6021 pre-CPU table 0xB38/0xB98/0xBF8 ← 0x01FF01FF is kext-table sourced; Linux table_mode=1 replicates, mode 2 skips |
| 3 | DART stream-0 + TTBR | yes (task surfaces) | yes | yes (staging + entry alias) |
| 4 | firmware image stage | NONE (no fw CPU on H13 path) | NONE (eos preloaded, never RUN) | selene staged + aliased, x22 stamp patched; BSS/VM-span gaps receipted |
| 5 | RVBAR compose/write | NEVER (no ASC start) | NEVER | skipped-if-locked; latch lacks 0x0081<<48; no kext path repairs it on-chip |
| 6 | CPU_CONTROL RUN | NEVER | NEVER | written (0→0x10) → STATUS 0x28 park, no HELLO |
| 7 | READY/wake | n/a (TM_STATUS IDLE poll) | n/a | SCRATCH7 stays 0; single type-0 I2A word, no HELLO |
| 8 | submit | TM push, works | TM push, works (jw16 parity batteries) | RTKit handshake blocked at fw start |

## 5. What this means for the two work items

- **AneBoundaries (T6001/jw16):** apply the T8103 sequence with T6001
  offsets (engine 0x284000000, ps 0x28e08c000, SET genpd overlay
  `ane/t6001-j316c-set-domains.dts`, TM base engine+0x1C24000-class per
  the H13 layout). No firmware work: T6001's eos stays stopped, same as
  the working M1. главной risk is NOT the sequence but the known T6001
  hazards: ASCWRAP-class reads hard-reset (h13-fw-perf §2b) and pmgr
  beyond SET+0x38 is read-hostile (4 platform resets).
- **M2FwStart-2 (T6021):** the M1 path does NOT transfer — there is no
  host-TM on T6021 by hardware design (firmware owns TM; zero kext
  TM/TQ sites). The T6021 work stays: fetch-side (iBoot segments, DART
  mapping, VENC chain) + mailbox binding, not the poll. The hv trace
  stays paused per Main unless a gap only it can answer appears; the one
  candidate gap is iBoot's own RVBAR write value/timing.

## 6. Confidence

- T8103 oracle + Linux driver steps: source-read, HIGH.
- H13 kext ANE_Init RVBAR/RUN/poll: disassembled, STATIC-CONFIRMED.
- T6001 offsets/hazards: receipt-cited, MEDIUM (not re-verified here).
- T6021 column: prior receipts + kernelcache work, STATIC-CONFIRMED
  where addressed.
