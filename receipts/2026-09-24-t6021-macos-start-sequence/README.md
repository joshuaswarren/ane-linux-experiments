# T6021 (M2 Max) ANE start sequence from the macOS 26 kernelcache

Date: 2026-09-24 · AneStaticStart · static path (no device touched)

Source: `/tmp/m2kstart/kc.level9.gz`, macOS 26 kernelcache for T6021/J414c
(raw 0x7744000 bytes). Parsed as an MH_FILESET: the ANE driver is
`com.apple.driver.AppleH11ANEInterface`, with the ASC base classes in
`com.apple.driver.AppleA7IOP`, `com.apple.driver.AppleA7IOP-ASCWrap-v4`,
and the management protocol in `com.apple.driver.RTBuddy`.
All code addresses below are kernelcache VAs in this image. The driver
carries ~11k symbols, so the start path is named-function analysis backed
by direct disassembly, not guesswork.

Notation: [STATIC-CONFIRMED] = disassembled from this kernelcache.
[INFERENCE] = a conclusion drawn from confirmed code. Confidence (HIGH /
MEDIUM) follows each step.

## 0. Chip selection: T6021 takes the RTBuddy path

`ANEHWDeviceConfig::initializeANESoCConfig` reads the ADT `ane-type`
property and switches on it. The T6021 ane0 ADT carries `ane-type = 0xa0`
(device-tree capture in
`receipts/2026-09-23-m2-macos-denominator/m2-macos-window/ane-evidence/ane0-devicetree.txt`),
which lands on the branch at `0xfffffe0009613fc8` that stores version
`0x80` [STATIC-CONFIRMED, HIGH].

That version selects the RTBuddy start path (`dev+0x780 = 1`, set by
`InitializeRTBuddyClient` success in `InitializeProvider`). Once set, the
kext never issues the legacy RVBAR/CPU_CONTROL writes; the legacy code is
still present but dead for this chip [STATIC-CONFIRMED, HIGH].

## 1. Ordered sequence: power-on to first RTKit HELLO

All ANE engine-relative offsets are into the 0x284000000 aperture.

1. **Power domains via the PMGR provider, not direct MMIO**
   [STATIC-CONFIRMED, HIGH].
   `EnableANEClocksAndPower` →
   `enableAneSysClock` → `enableDeviceClock` / `enableDevicePower` with the
   ADT `clock-ids` at code `0xfffffe00095d1d20-0x95d1d90` (provider-call
   form, no kext-side MMIO). Separate per-island `power_on_hardware_gated`
   (`0xfffffe00096076e4`) calls `EnableANEClocksAndPower(true, true)`,
   conditionally `EnableMPMClocksAndPower`, then `ANE_Init`.
   Linux equivalent: the genpd raise. The known gap stands: ADT clock-ids
   318-321 (VENC gates) plus the parent VENC_SYS word have no Linux pmgr
   domain; only the m1n1 `pmgr_adt_power_enable("/arm-io/ane")` walk covers
   them.

2. **RTBuddy power-state change, not a kext MMIO script**
   [STATIC-CONFIRMED, HIGH].
   `EnableCPUClocksAndPower` on the RTBuddy path reduces to
   `ChangePowerState(1)` + `ValidatePowerOnState`
   (`0xfffffe00095d09bc-0x95d09d0`). The actual bringup runs inside
   `RTBuddy::_performPowerStateChangeGated`, which calls the slave's
   `startCPU` (AppleA7IOP vtable slot +0x888) rather than touching ASC
   registers itself.

3. **Firmware mapping / latched-RVBAR handling**
   [STATIC-CONFIRMED, HIGH].
   `AppleA7IOP::startCPUWithOptions` (`0xfffffe0008bc87bc`):
   - `_mapFirmware` checks `_hasiBootFirmware` (`dev+0x128 != 0`). If iBoot
     left a firmware descriptor, it DART-maps those segments
     (`_dartMapiBootFirmware`).
   - With no iBoot descriptor it reads RVBAR (engine+0x1050000) and
     succeeds only if bit 0 (the lock) is already set; otherwise it panics
     (no silent path). It never rewrites a locked RVBAR.
   - The RVBAR compose `0x0081<<48 | (entry & 0xFF7EFFFFFFFFF800)` —
     matching the Linux driver's `ane_t6021_rvbar_compose` and the prior
     H13 cross-check — exists in this image ONLY in `ANE_Init`'s legacy
     branch (`0xfffffe00095e9868-0x95e9988`). That branch is skipped when
     `dev+0x780 = 1`. The constant `0x81<<48` appears in exactly two
     `movz` sites in the entire `__TEXT_EXEC`: `ANE_Init` and the unrelated
     camera `AppleH13CamIn::ISP_StartFirmware`.

   Consequence: on T6021 the kext never programs RVBAR. The latch content
   — including the 0x0081<<48 mode bits — is an iBoot product. macOS boots
   always take the preloaded path (`pre-loaded = 1` in the T6021 ADT);
   a Linux boot that bypasses iBoot-main gets whatever the surviving latch
   holds, and nothing in the macOS driver repairs or rewrites it.

4. **Mailbox init: only the outbox control is touched**
   [STATIC-CONFIRMED, HIGH].
   `_disableAllInterrupts`, `_enableInboxInterrupt`,
   `_enableOutboxInterrupt` are empty stubs (bare `ret`) in ASC wrap v4.
   `_enableOutbox` read-modify-writes engine+0x1408114, setting bit 0.
   ASC register file (from `AppleASCWrapV4`, engine+0x1400000 base):
   CPU_CONTROL +0x44, CPU_STATUS +0x48, inbox/outbox ctrl +0x110/+0x114,
   mailboxes +0x800/+0x808/+0x830/+0x838 — consistent with the live
   offsets the Linux driver already uses.

5. **CPU release: one RMW of CPU_CONTROL**
   [STATIC-CONFIRMED, HIGH].
   `AppleASCWrapV4::_runCPU(true)` (`0xfffffe0008bc5180`) reads
   CPU_CONTROL (engine+0x1400044) via the register accessor and writes
   back with bit 4 set (`ORR w9, w0, #0x10`). `stopCPU` clears bit 4, then
   clears bit 5. `supportReleaseOnEntry` returns 0 for this wrap — there is
   no release-on-entry handshake; RUN is the whole start.

6. **RTKit HELLO follows from the firmware, not the kext**
   [STATIC-CONFIRMED, MEDIUM].
   After RUN the kext waits for management traffic on EP0 (HELLO/EPMAP);
   the ANE_Init tail (`commandWakeup`, shared-memory surface allocation,
   endpoint setup) runs after the firmware announces itself. HELLO never
   precedes a real CPU release.

## 2. Asked-for items: what Linux does NOT do

- **pmgr/PS sequencing order**: the macOS path delegates sequencing to the
  PMGR provider (`enableDevicePower`/`enableDeviceClock` + the RTBuddy
  power-state machine). There is no kext-issued `TARGET=0xf` script for
  T6021 [STATIC-CONFIRMED, HIGH].
- **`ane-power` or SPMI step**: no SPMI string exists in the ANE kext, and
  no power function references one. None in the macOS start
  [STATIC-CONFIRMED, MEDIUM].
- **Coprocessor config register before CPU_CONTROL**: nothing runs between
  the outbox enable and `_runCPU` in `startCPUWithOptions`
  [STATIC-CONFIRMED, MEDIUM].
- **Secure-state / TZ handshake**: `setSecureModeEnabled` is called only
  from the SEP-client power handlers, not the normal start path
  [STATIC-CONFIRMED, MEDIUM].
- **Latched-RVBAR case**: the kext handles it by _not touching it_ — the
  map path requires the lock bit and panics without it, and the compose
  path is legacy-only on this chip [STATIC-CONFIRMED, HIGH]. This matches
  the live box: RVBAR latched at `0x10000000001` with mode bits missing,
  no kext path that would fix it. Clearing the latch needs the ane_cpu
  island power cycle, which stays forbidden from kernel context (s24).

## 3. Diff against the Linux driver's current start path

What already matches: the genpd raise (all eight islands, ACTUAL=0xf gate),
non-posted engine mapping, scratch zeroing, the SCRATCH7 READY poll
constant `0x08042006`, the wake constant, the mailbox offsets, and the
skip-if-locked RVBAR behavior.

What differs:
1. Linux never writes `CPU_CONTROL` RUN (engine+0x1400044 bit 4) — that is
   the single missing start write, and it is also the write the ba1a1e7
   receipt's evidence says parks at STATUS 0x28 when the latch lacks the
   mode bits [INFERENCE, HIGH].
2. Linux has no provider for the VENC clock-ids 318-321 / VENC_SYS parent
   rail — the one macOS power step with no Linux counterpart
   [STATIC-CONFIRMED power step; gap inference HIGH from prior B5/B6
   receipts].
3. Linux should NOT add a coprocessor config write, SPMI step, secure
   handshake, or extra mailbox init — the kernelcache shows none of these
   on this chip's path [STATIC-CONFIRMED, MEDIUM].
4. The legacy-path RVBAR compose in `ANE_Init` confirms (not changes) the
   Linux compose formula; it also confirms there is no kext-side repair
   for a mode-bit-less latch [STATIC-CONFIRMED, HIGH].

## 4. Deliverables and method

- Hub delivery to M2FwStart-2: sent this session (sequence + addresses).
- Method: python + capstone disassembly of the fileset kernelcache
  (MH_FILESET, per-kext LC parsing, symtab load, c++filt names, vtable
  resolution through DYLD_CHAINED_PTR_ARM64E auth-pointer decode, adrp/add
  string-xref scan). Tools available on this host were enough: llvm-objdump
  was not needed and radare2/Ghidra were absent.
- Nothing written outside this receipt and `/tmp/anestatic` scratch.
  No Apple binaries or large artifacts in git. `Never use --no-verify`
  honored: no bypass flags used.

## 5. Open item for the dynamic trace

The static path cannot observe iBoot's own RVBAR write (value and timing).
M2FwStart-2's hv trace covers exactly that: the write to engine+0x1050000
between power-on and kext load, which should carry the 0x0081<<48 bits on
a macOS boot and thereby confirm §1.3's consequence live.

## 6. Parent-ordered follow-up (live M2 result folded in)

Live result (Main, 2026-09-24): engine base 0x284000000, RUN accepted,
CPU_STATUS 0x2a -> 0x28, outbox write read back 0x00020001 (bit 0 armed),
then one I2A word 0x000a0000_00000000 at t+0 and 60 s of silence.

1. **Pre-RUN clock/PS order.** `AppleASCWrapV4::initialize`
   (0xfffffe0008bc4f10) maps the wrapper registers from the ADT reg
   entries first; `RTBuddy::_changePowerState` (0xfffffe000b6afe18)
   raises provider domains before calling the slave's `startCPU`
   (slot +0x888). The ANE kext calls `enableAneSysClock`, then
   `enableDeviceClock`/`enableDevicePower` for the single ADT clock-id in
   dev+0x8f0 (0xfffffe00095d1d20-0x95d1d90); the provider call walks
   parents, so the VENC_SYS rail must grant before the 318-321 leaves can
   latch ACTUAL. Live box confirms the shape: eight ANE islands
   `available` on devlinks while VENC_SYS TARGET never reaches 0xf and
   leaves report without ACTUAL. Linux order: VENC_SYS ps 0x2902803e0
   TARGET 0xf first, poll ACTUAL, then leaves, then islands, then engine
   MMIO. [STATIC-CONFIRMED] call order; [INFERENCE, HIGH] VENC_SYS-first.

2. **Image fetch.** macOS is always the preloaded branch:
   `_hasiBootFirmware` true -> `_dartMapiBootFirmware` maps the ADT
   segments, dev+0x130 done. Live ADT `segment-ranges` decodes to IOVA
   0x10000000000 = TEXT phys 0x1000092c000 len 0xe8000, IOVA
   0x100000e8000 = DATA phys 0x1000150c000 len 0x284000, pre-loaded=1.
   No SART exists in the ANE path (only ANS2/NVMe has one); DART-only on
   dart-ane0 stream 0. No boot-arg or pool surface is written before RUN;
   SCRATCH publish and wake come after READY. [STATIC-CONFIRMED] branch
   structure and segment decode; [INFERENCE, HIGH] park-on-mismatch.

3. **I2A 0x000a0000_00000000.** `RTBuddyManagementEndpoint::_messageHandler`
   (0xfffffe000b6c44f8) extracts bits [55:52] as the message type and
   routes type 1 to `_handleHello` (0xfffffe000b6c5194), type 8 to
   `_handleEPRollCall`. Type 0xa routes nowhere: the firmware posted once
   but did not send HELLO. HELLO itself must carry version min/max 0xc in
   the low halfwords and is answered with a HELLO_REPLY shaped
   0x20000c000c with the endpoint count in the high half. Verdict: the
   core left STOPPED and posted a non-HELLO management word, then went
   quiet — fetch or earliest-boot park, not a mailbox-shape problem.
   [STATIC-CONFIRMED] dispatch and HELLO shape; [INFERENCE] the 0xa word
   is a non-HELLO management message.

All three items were delivered to M2FwStart-2 over hub as produced.
Constraint noted for the retest: no driver bound to 284000000.ane and
STRICT_DEVMEM=y, so the attempt must go through the installed omarchy-ane
driver path, not mmap.

## 7. Post-RUN to HELLO: nothing from the host (M2 offline, committed for the resume)

Live state this answers: RUN via ioremap accepted, STATUS 0x2a -> 0x28,
single I2A word 0x000a0000_00000000, 60 s silence, SCRATCH all zero,
outbox 0x20001.

1. **No host-to-IOP A2I send between `_runCPU` and HELLO**
   [STATIC-CONFIRMED]. `startCPUWithOptions` (0xfffffe0008bc87bc) ends at
   `_runCPU` and returns; `RTBuddy::_performPowerStateChangeGated`
   proceeds to `RTBuddyFirmware::fixup`, `_setIopStatus(4)`, mailbox-IRQ
   enable, `wakeQuiesced`, `_iopValidate` — then waits. ANE
   `SetupFWInitBootArgs` is called only from `SetupEndpoints`
   (0xfffffe00095fe8a0), which runs after the firmware announces itself.
   The only pre-handshake A2I word the host sends is the HELLO_REPLY, and
   only after a valid HELLO.

2. **No SCRATCH or shared-memory write before RUN on this path**
   [STATIC-CONFIRMED]. `InitANEScratchRegisters` (zeroes eight words via
   write32 slot +0x18) runs only in the skipped legacy branch. The first
   thing the firmware reads is what iBoot left: RVBAR entry, mapped
   segments, clocks. The legacy READY poll (SCRATCH7 == 0x08042006,
   1000 x 1 ms, 0xfffffe00095e99e4-0x95e9b8c, with a conditional pre-write
   of dev+0x44c when config+0xec is nonzero) does not run on the RTBuddy
   path; the wait there is the HELLO with iopStatus 4
   (kRtbIopStatusWaitingForVersion).

3. **I2A 0x000a0000_00000000, corrected decode** [STATIC-CONFIRMED].
   Type field is bits [55:52] (`ubfx x21,x20,#0x34,#4` at
   0xfffffe000b6c4520): type = 0, next nibble [51:48] = 0xa. Type 0 is in
   no routed case (1 = `_handleHello` 0xfffffe000b6c5194, 4 = PingAck,
   7 = `_handlePowerAck`, 8 = `_handleEPRollCall`, 0xb, 0xc) and falls to
   the cold path logging `invalid management message %llx received:
   type, status` with NO reply sent. Supersedes the §6 item-3 decode (type
   0xa), which misread the nibble. Valid HELLO needs version min/max 0xc
   in the low halfwords and is answered with HELLO_REPLY shaped
   0x20000c000c with the endpoint count in the high half. Verdict: the
   firmware posted one non-HELLO word and never sent HELLO — fetch or
   earliest-boot park, and RTBuddy waits forever.

4. **No FIFO pop or IRQ ack gates the firmware** [STATIC-CONFIRMED].
   `_outbox` (0xfffffe0008bc5504) reads the I2A pair at wrap+0x8830 and
   `_inbox` (0xfffffe0008bc5520) writes the A2I pair at wrap+0x8800; the
   polled `getMailbox` path works without interrupts, and the IRQ handler
   only logs plus runs the command gate. Outbox 0x20001 with bit 0 set is
   the armed state, not a failure.

Ordered answer delivered to M2FwStart-2 over hub. M2 offline (macOS use);
M2FwStart-2 reads this branch on resume.

## 8. 13.5 payload reset path (Main lane, 2026-09-24)

Source: 13.5 ane0 payload (/tmp/anestatic/fw13-ane0.payload, sha
a9c4b771; geometry TEXT vm0/0xc4000, DATA vm0xc4000/0x438000 — a
different image from the 26 fixture). Entry = first TEXT byte
(`b +0x204`, live head 81 00 00 14).

- Reset: EL3-drop veneer (eret) or direct EL1; VBAR_EL1 = image base;
  own page tables into heap (TTBR0/1, TCR from ID_AA64MMFR0, MAIR,
  SCTLR MMU-on); per-core SP; C main via BSS slot.
- NO pre-main loop waits on anything external: zero MMIO reads in
  0x204-0x900 (no pmgr/DART/ASC/scratch/mailbox immediates, no MMIO
  adrp targets). Inputs are image-local literals, ID regs, MPIDR, ROM
  x0; the map-base chain is runtime BSS from the loaded-segment layout.
- First external wait is post-C-main (HELLO/mailbox or wfi-for-IRQ).
  Verdict: a 0x28 park with zero SCRATCH = pre-C-main park
  (fetch/MMU/EL fault) in the VBAR fault-capture, not a handshake wait.
  [STATIC-CONFIRMED]
- DATA compare (live PA 0x10001400000 4 KB vs payload vm 0xc4000)
  requested from M2FwStart-2; deltas would name the boot-args area.
