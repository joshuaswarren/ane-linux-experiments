# T6021 pre-RUN diff: macOS kext writes vs Linux — first missing write (CORRECTED)

Date: 2026-09-24 · AneStaticStart. All kext addresses are macOS 26/J414c
kernelcache VAs (fileset parse + capstone, vtable-resolved). Linux side is
M2FwStart-2's exact test (remap-test-log.txt: P-1/P1/P2/P3/P4) plus the
contract source (omarchy-ane agent/m2-proto-prep
ane/t6021/ane_t6021_boot.h ane_t6021_boot_run()) and the engine part of
tools/m2hv_linux_baseline.txt on agent/m2hv-diff.

## 1. What macOS writes before RUN on the T6021 (RTBuddy) path, in order

Notation: engine-relative offsets; the ANE register controls add the
engine base (Ps/PowerGate/Ptd names) or the second mapped window
(RVBAR/SCRATCH/CPU area) to the index. All of these execute on the T6021
path (ane-type 0xa0, RTBuddy client initialized) — confirmed by branch
trace, not assumed.

1. **Power/legacy-clock script** (`EnableANEClocksAndPower` 0xfffffe00095d19c0
   → `enableAneSysClock` 0xfffffe00095d25c4 → provider
   `enableDeviceClock/enableDevicePower` for the ADT clock-id in
   dev+0x8f0 at 0xfffffe00095d1d20-0x95d1d90; then `EnableCPUClocksAndPower`
   0xfffffe00095d0958 → `ChangePowerState(1)` + `ValidatePowerOnState`):
   - `write32(0x2e0, 0xf)` — the CPU-island word, FIRST engine write on
     this path (0xfffffe00095d0e08-0x95d0e14). [STATIC-CONFIRMED]
   - Then per the version-0x80 case: `write32(0xc000, 0xf)`,
     `write32(0xc008, 0xf)`, `write32(0x3c8, 0xf)` each followed by a
     readback-validate, plus further `write32`/`validate` pairs at
     0x159c, 0x248c, 0x2d8c, 0x10000, 0x3b6c-class offsets as the case
     proceeds (full list in §3). These are power/clock-gate enables with
     readback, not fire-and-forget. [STATIC-CONFIRMED]
2. **Scratch zeroing on the RTBuddy path** (`InitANEScratchRegisters`
   0xfffffe000960f2a8, called from `EnableANEClocksAndPower` at
   0xfffffe00095d2298 under `dev+0x780 bit0 SET` = RTBuddy path):
   `write32` 0 through the eight scratch offsets held in dev+0x438..0x454
   (T6021 subtype-0 values from `__const+0xa40/0xa50/0xa60`:
   0x1840048, 0x184004c, 0x1840050, 0x1840054, 0x1840058, 0x184005c,
   0x1840060, 0x1840064). No 1-pulse, no wake. [STATIC-CONFIRMED]
3. **RVBAR: skipped, never written**

## 4. CORRECTION (M2 wedge): the 0x2e0-family writes are pmgr ps through ANERegisterControl

The 0x2e0/0xc000/0xc008/0x3c8 writes resolve through the PS register
control (getDeviceMemoryWithIndex selecting the 0x28e080000 window):
0x2e0 = phys 0x28e0802e0 = ps_ane_cpu TARGET. Item 1 of the prior
version is therefore a no-op and is struck — Linux already owns this
word via genpd, and rewriting it wedges the box.

Corrected first missing non-ps write: **write32 PWGATE+0x159c = 0**
(phys 0x28e09359c, third IODeviceMemory window base 0x28e092000) at
0xfffffe00095d0f88-0x95d0f94 in `EnableCPUClocksAndPower`, with readback
validate (expect 0, mask 3) at 0xfffffe00095d0fb0, on the same T6021
case-5 subtype path. Reg index: PWGATE device-memory index (PS index + 1).
[STATIC-CONFIRMED site/value/validate; INFERENCE that it gates execution.] (compose site exists only in the
   legacy `ANE_Init` branch; `_setIORVBAR` has no callers anywhere in
   `__TEXT_EXEC`; `_mapFirmware` only READS the lock). [STATIC-CONFIRMED]
4. **Mailbox: nothing before RUN** (`_disableAllInterrupts`,
   `_enableInboxInterrupt`, `_enableOutboxInterrupt` are bare `ret` in
   ASCWrapV4; `_enableOutbox` runs inside `startCPUWithOptions`, after the
   firmware decision). [STATIC-CONFIRMED]
5. **No A2I send, no boot-arg/DATA write, no shared-memory publish before
   RUN.** `SetupFWInitBootArgs` runs only from `SetupEndpoints`
   (post-HELLO); `RTBuddyFirmware::fixup` on the iBootLoaded path does the
   `OTTR` timebase patchbay write then early-returns (no heap, no stack
   guard, no PRNG writes); `writeBackPatchBay` no-ops (no patchbay
   object). [STATIC-CONFIRMED]
6. **RUN** (`_runCPU(true)` 0xfffffe0008bc5180: CPU_CONTROL RMW OR 0x10).
   [STATIC-CONFIRMED]

What macOS does NOT do before RUN (closed): SPMI (no such string in the
ANE kext), secure/TZ handshake (SEP-client only), SART (none in the ANE
path), coprocessor config register between outbox-enable and RUN
(nothing in `startCPUWithOptions` there). [STATIC-CONFIRMED]

## 2. What Linux writes (same order)

P-1 grant tunables (12 writes: 0x000, 0x038, 0x03c, 0x400, 0x600, 0x738,
0x798, 0x7f8, 0x900, 0x410, 0x420, 0x430) → P1 scratch-clear + SCRATCH7
pulse 1→0 (rtb_mode selects SCRATCH6=0) → P2 RVBAR skip (latched) → P3
CPU_CONTROL 0 then 0x10 → P4 poll. Plus genpd island raise, VENC_SYS +
leaves, DART attach + fw alias maps, and post-RUN observer writes
(SCRATCH3 ack, outbox enable) that macOS does not do pre-RUN.

## 3. Diff — first macOS pre-RUN write Linux does not make

**`write32(0x2e0, 0xf)` — the CPU-island word, at
0xfffffe00095d0e08-0x95d0e14 in `EnableCPUClocksAndPower`, first engine
write on the T6021 path.** Linux raises ane_cpu through genpd
(`ps_ane_cpu` TARGET/AUTO) but never issues the engine-window write to
the island word itself; the P-1/P1 sequence starts at engine+0x0 while
macOS starts at the island word. Everything after it (0xc000/0xc008/0x3c8
validates, scratch zeroing, RUN) is downstream of this word reading back
correctly — `ValidatePowerOnState` gates the whole bringup on these
readbacks.

Why it likely gates execution: on this path the kext writes the island
word BEFORE any other engine access and validates every subsequent
gate/clock write; a core released without its island word written through
the engine window leaves STOPPED (0x28) with zero SCRATCH and no HELLO —
exactly the observed Linux symptom on both T6021 and T6001. The write is
a plain engine-window write32, outside the s24-fatal raw-ps class
(0x28e0802e0 TARGET writes from kernel context); it goes through the
already-mapped non-posted engine window, same class as the P-1 tunables
that already land safely. [INFERENCE for the gating claim; the write
itself and its first position are STATIC-CONFIRMED.]

Second in rank (same receipt, not the answer): the 0xc000/0xc008/0x3c8
validate pairs — Linux has no readback-validated gate/clock enables at
all. Third: none — mailbox/SCRATCH-publish/RVBAR/boot-args are all
confirmed absent pre-RUN on both sides.
