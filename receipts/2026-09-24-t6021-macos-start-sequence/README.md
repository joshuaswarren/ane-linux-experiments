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

## 9. Fault-triple: register-only, no PA to read (Main lane, 2026-09-24)

13.5 payload vector table (vm 0x0): capture slots at 0x80/0x100/0x180 do
mrs x28,ESR_EL1 / mrs x29,FAR_EL1 / mrs x30,ELR_EL1 then b self. No store
to memory, no flag, no counter; sync slots re-enter at 0x204. No str
x7/x11/x28/x29/x30 exists in 0x204-0x900. The ESR/FAR/ELR triple is
recoverable only via core-register access (m1n1 debug/JTAG), never via a
reserved-DATA read — do not task a DATA read for it. ROM x0 audit:
x0→x7→x11→C-main x5, feeding only table-size/mask arithmetic pre-MMU,
never stored; ROM-provided, not host-writable pre-RUN. [STATIC-CONFIRMED]

## 10. Live DATA == payload DATA (Main lane, 2026-09-24)

4 KB at PA 0x10001400000 (gated observer read, M2FwStart-2) is
byte-identical to 13.5 payload DATA vm 0xc4000 (4096/4096, sha
2b35a8ad). iBoot does not patch DATA: no boot-args area in the first
4 KB, no host-provided DATA content. Remaining fetch-side variables are
the segment mapping and clocks, not DATA. [MEASURED + STATIC-CONFIRMED]

## 11. First out-of-map access: payload overruns macOS-boot DATA mapping (Main lane, 2026-09-24)

13.5 payload DATA: vm 0xc4000 vmsize 0x438000 (file 0x3e8000, zerofill
0x50000 from vm 0x4ac000, end 0x4fc000). CORRECTION: the 0xe8000/0x284000 ranges are the 26-geometry sources
(26 selene fixture + macOS-boot segment-ranges then), NOT the live
13.5 mapping. The live 13.5 ADT entry1 (PA 0x10001400000 -> IOVA
0x100000c4000, size 0x438000) already covers the full 13.5 DATA span
vm 0xc4000-0x4fc000 including zerofill, and the remap-exact test
mapped exactly that — mapping requirement WITHDRAWN. OPEN: the
zerofill (vm 0x4ac000-0x4fc000 must read zero; garbage reads as
pointers). Stacks (~vm 0xc1aca18) stand as mapped and file-backed. Pre-C-main touches no fixed MMIO (verified clean
0x204-0x900) and no host DATA. [STATIC-CONFIRMED]

## 12. 13.5 kext: writes before CPU_CONTROL (Main lane, 2026-09-24)

Source: 13.5 kernelcache, com.apple.driver.AppleH11ANEInterface
(H11ANEIn). The 13.5 ANE kext starts the ASC itself in
H11ANEIn::ANE_Init (0xfffffe00094e0cfc); it does not go through the
A7IOP/RTBuddy startCPU path. [STATIC-CONFIRMED]

Ordered writes in ANE_Init, engine base 0x284000000, before and
including the CPU release. Offsets are the T6021 (ane-type 0xa0)
column of the per-version tables at 0xfffffe00073a0148+ (index
(version-0x40)>>4 = 6). [STATIC-CONFIRMED]

1. Clear eight scratch registers to 0: engine+0x1840050, +0x1840054,
   +0x1840058, +0x1840060, +0x1840064, +0x1840068, +0x184006c, and the
   eighth from the same table column. Code 0xfffffe00094e0e34-0x94e0e58.
2. RVBAR (engine+0x1050000): read, and write
   (entry & 0xFF7EFFFFFFFFF800) | (0x81<<48) ONLY if bit 0 is clear.
   Code 0xfffffe00094e0e68-0x94e0f18. On the live box the latch has bit 0
   set, so this write is skipped. The kext never rewrites a locked RVBAR.
3. CPU_CONTROL (engine+0x1400044): write 0, then write 0x10 (bit 4).
   Code 0xfffffe00094e0f24-0x94e0f34. This is the release.
4. Entry-address register (engine+0x1840068): written only if dev+0x94
   is nonzero. dev+0x94 is a boot-arg (start() 0xfffffe00094cbb1c), zero
   on a normal boot, so this write does not happen. Code 0xfffffe00094e0f38.
5. Poll engine+0x184006c for 0x08042006 (READY), up to 1000 iterations.
   Code 0xfffffe00094e0f54-0x94e1018.

Conclusion: on the preloaded, RVBAR-latched path the kext writes NO fetch
base before the CPU release. The fetch address is entirely iBoot's RVBAR
latch (0x10000000001 = lock bit | IOVA 0x10000000000, the ADT
segment-ranges TEXT IOVA). The kext's only translation setup is
H11ANEIn::mapFwCTRRRegion (0xfffffe00094cd210), which DART-maps the ADT
segment-ranges through the ane mapper (dev+0x248) before ANE_Init runs;
the IOVA base comes from the mapper's own reservation, not from a kext
register write. [STATIC-CONFIRMED] the no-fetch-base conclusion;
[INFERENCE] that the fetch succeeds only if the DART already translates
the RVBAR IOVA, which iBoot must have programmed since the kext's
reservation base is not pinned to 0x10000000000 by any kext-side constant.

## 13. mapFwCTRRRegion: DART translation the kext builds (Main lane, 2026-09-24)

iBoot leaves all three ANE DARTs empty (ENABLE=0, TTBRs 0). The kext
builds the translation in H11ANEIn::mapFwCTRRRegion (0xfffffe00094cd210),
called from H11ANEIn::start (0xfffffe00094ca4a0) BEFORE ANE_Init's
CPU_CONTROL write. [STATIC-CONFIRMED]

### What it maps, and where

- Reads ADT "segment-ranges" (dev+0x180 provider, getProperty "segment-ranges"
  at 0xfffffe00094cd28c). Two 32-byte entries: TEXT and DATA, each
  phys/size/IOVA. Builds an IOMultiMemoryDescriptor and calls the ane
  mapper (dev+0x248) iovmMapMemory (vtable slot 0x890) then iovmInsert
  (slot 0x8a0) per segment with prot=3. Code 0xfffffe00094cd464-0x94cd684.
- The mapper is dart-ane0 (ADT node, compatible "dart,t8110", page-size
  0x4000, vm-base 0x10000000000, vm-size 0x30000000000). SID property
  "sid" = <0, 15>: SID 0 is the translated stream, SID 15 is the bypass
  stream ("bypass-15" present). The kext maps into SID 0. [STATIC-CONFIRMED]
  from the ADT dump /tmp/m2kstart/dart-ane0-dt.txt.

### PTE format (T8110 DART2, from the PPL builder)

The actual PTE write is in XNU's PPL IOMMU driver (__PPLTEXT
0xfffffe0008bf9820): PTE = (phys >> 12) & 0x3ffffffc, then one protection
bit inserted at bit 31 (bfi w24, w23, #31, #1). No other protection or
attribute bits are set. So a mapped firmware page is:
  valid (bit 0 set by the builder's caller path), bit 31 = the single
  prot flag, and bits 1/2/3 (NO_CACHE/NO_WRITE/NO_READ) all CLEAR.
[STATIC-CONFIRMED] the builder writes only bit 31 besides the address.

### The difference from Linux

Linux io-pgtable-dart (APPLE_DART2) sets bit 1 (NO_CACHE) on a mapping
unless IOMMU_CACHE is passed. The ANE fw alias (ane_t6021_fwload.c:133,
:161) passes IOMMU_CACHE only when dev_is_dma_coherent(ane->dev). macOS's
PPL builder never sets bit 1 at all. So IF the ANE device is not
DMA-coherent, Linux maps the firmware uncached and macOS maps it cached —
a candidate for the silent fetch fault. If it is coherent, both map cached
and this difference vanishes. [INFERENCE] conditional on the coherent flag;
confirm with a live PTE read (bit 1 clear = cached).

### SID and instance programming

registerMapper (AppleT8110DART::registerMapper, 0xfffffe0009bfef98) calls
the PPL SID-config writer (0xfffffe0008bfe380), which writes per-SID:
  TTBR at hw_base + 0x1400 + sid*4 (the shifted table address),
  TCR/config at hw_base + 0x1000 + sid*4 (value from the SID context,
  bit 31 cleared).
enableTranslation (0xfffffe0009bff354) writes the enable/disable command
through the PPL (cmd 0x8114/0x8115). TLB invalidate is a write of 0 to
hw_base+0x80 (0xfffffe0008bfe590). [STATIC-CONFIRMED]

### Order relative to CPU_CONTROL

1. H11ANEIn::start: mapFwCTRRRegion (DART map, SID 0, cached PTEs).
2. Later, on power-on: ANE_Init clears scratch, skips the locked RVBAR,
   writes CPU_CONTROL 0 then 0x10, polls SCRATCH7.
The DART translation is fully in place before the CPU release. There is
no separate "mark as firmware/code" register write; the only distinction
is the PTE attribute bits above. [STATIC-CONFIRMED]

## 14. power_on_hardware before ANE_Init (Main lane, 2026-09-24)

H11ANEIn::power_on_hardware (0xfffffe00094e062c) reaches ANE_Init via bl
at 0xfffffe00094e08ac. Ordered HW-relevant writes before that call,
T6021 (version 0xa0, switch index 7):

1. PS TARGET: EnableANEClocksAndPower (0xfffffe00094ddd64) writes 0xf to
   dev+0x200 + {0xc000,0xc008,0xc010,0xc018,0xc020,0xc028} (tail beyond
   0xc028 not yet fully read), each followed by validatePSReg
   (0xfffffe00094df614) polling ACTUAL==0xff. [STATIC-CONFIRMED] Linux
   genpd raise already covers this. NOT missing.
2. Wake write: *(dev+0x3880)+0x80 <- 1 (kext 0xfffffe00094e0738).
   Fires if version==0x60/0x80, else requires dev+0xec==0xe0; for 0xa0
   the condition is UNCONFIRMED. Target mapping unidentified.
   [STATIC-CONFIRMED write; effect INFERENCE; condition OPEN].
3. Mapper setActive (kIODARTFunctionSetActive) on dev+0x248 (kext
   0xfffffe00094e07b8); dev+0x250 copy skipped for 0xa0 (version>=0xb0
   gate). [STATIC-CONFIRMED] Linux domain-attach equivalence unverified.
4. Slot-0x170 call on dev+0x190 (kext 0xfffffe00094e086c), target
   unidentified, likely command-queue not HW. [OPEN].
5. Kernel debug-trace calls — not HW. Ignored.

Ranking by likelihood of gating fetch/clock: (1) SID-0 stream enable
[INFERENCE]; (2) wake write [condition open]; (3) mapper-setActive
equivalence [write confirmed, Linux side unverified].
SID-enable quote status: NOT YET — enableTranslation
(0xfffffe0009bff354) issues PPL cmd 0x8114/0x8115 via trampoline
0xfffffe000857d900; the stream-enable register write itself is not yet
decoded. bit0=SID0 is inferred from Linux ENABLE=0xfffe + ADT
sid=<0,15>, not from kext code.

## 15. dev+0x3880 = ANE AFE range; the write is AFE+0x80 <- 1 (Main lane)

dev+0x3880 is built in H11ANEIn::start (0xfffffe00094cae08-0x94cae3c):
IOMemoryDescriptor (dev+0x3870) -> IOMemoryMap (dev+0x3868) ->
getVirtualAddress stored at dev+0x3880. The cstring neighborhood names
this range family "AFE". The power_on_hardware write at kext
0xfffffe00094e0738 is AFE+0x80 <- 1, gated (start() 0xfffffe00094cab94:
version==0xa0 requires dev+0xec==0xe0; version 0x60/0x80 unconditionally).
dev+0xec is the kext-internal "ane-subtype" id (boot-arg 'aneType',
else derived; default 0 per start() 0xfffffe00094c8868-0x94c8870) — so on
a default boot the AFE+0x80 write does NOT fire. [STATIC-CONFIRMED
addresses and gates; AFE functional meaning INFERENCE from the name.]
Linux writes nothing to AFE+0x80. Test sent to M2FwStart-2: read the AFE
phys base from the live tree, write 1 to AFE+0x80, 60 s SCRATCH7 poll.

## 16. RETRACTED: the AFE+0x80 test (Main lane, 2026-09-24)

The section-15 claim ("write 1 to AFE+0x80") is withdrawn. Re-derivation:
dev+0x3880's IOMemoryMap is built in start() (0xfffffe00094cae08) only if
the IORegistry lookup for the dev+0x1a8 provider object succeeds
(0xfffffe00094caf9c-0x94caff4). M2FwStart-2 confirms the live ane nub
exposes only three ranges (engine 0x284000000/0x2000000, pmgr
0x28e080000/0x4034, set 0x28e08c000/0x4000) — no AFE range — so the
lookup has nothing to attach and dev+0x3880 stays empty. AFE+0x80 has no
verified physical address; do not re-derive "AFE phys ~0x284xxx000" (AFE
is a separate nub range, not an engine offset). M2FwStart-2 was told not
to run the write. dev+0xec (ane-subtype) is a version selector inside the
kext's own switch tables, default 0, and cannot gate fetch. No remaining
static register candidate in power_on_hardware: PS matches, ENABLE full,
mapper active, PTE exact. [STATIC-CONFIRMED retraction]

## 17. CPU_STATUS 0x2a vs 0x28: what the bits actually say (Main lane)

Bit authority: m1n1 proxyclient/m1n1/hw/asc.py R_CPU_STATUS (the only
bit-level source; Asahi rtkit and the 13.5 kext never decode the bits):
  IDLE=5, FIQ_NOT_PEND=3 (guess), IRQ_NOT_PEND=2 (guess), STOPPED=1,
  RUNNING=0. m1n1's is_running() = NOT STOPPED.

- 0x2a (pre-RUN, matches ane_t6021.h:87 comment): RUNNING=0, STOPPED=1,
  FIQ_NOT_PEND=1, IDLE=1. Stopped and idle. [FACT under m1n1 map]
- 0x28 (post-RUN): RUNNING=0, STOPPED=0, FIQ_NOT_PEND=0, IDLE=1.
  STOPPED cleared; RUNNING bit still 0; IDLE still set.
  [FACT bits; semantics below are INFERENCE]

The 13.5 kext never branches on CPU_STATUS for boot: the only
CPU_STATUS read in H11ANEIn text is the mov w1,#0x48 site in
DumpANERegisters (0xfffffe00094e2f7c), a log dump. The kext's boot
decision is the SCRATCH7 poll for 0x08042006, not CPU_STATUS.
[STATIC-CONFIRMED]

Verdict on premise 1: "0x28 means the CPU runs" is UNPROVEN and, under
the bit map, likely wrong in the strong sense. 0x28 = not-stopped +
idle + RUNNING-bit-clear: exactly what a core looks like sitting in a
wfi-for-IRQ loop, clock-gated, or halted before fetch — the RUN bit
cleared STOPPED (the write was accepted) without any instruction
necessarily executing. The fetch-fault theory survives (nothing in 0x28
contradicts "never fetched"), but the premise must be restated:
STOPPED cleared proves the CPU_CONTROL write landed, not that the CPU
executes. Caveat: FIQ/IRQ_NOT_PEND are m1n1 guesses; IDLE=5's exact
semantics (WFI vs clock gate) are undocumented.

## 18. DRAM vs SRAM: execution is from DRAM through the DART (Main lane)

- ADT ane0: no sram/iram/local-mem property; IODeviceMemory is engine
  (32 MB) + pmgr + set only. segment-ranges points TEXT/DATA at DRAM
  phys (0x10000a5c000-class). [FACT, ane0-dt.txt]
- 13.5 ANE kext cstrings: no "sram" string anywhere in the kext.
  [FACT]
- ANE_Init (0xfffffe00094e0cfc) contains no SRAM copy step: clear
  scratch, RVBAR-if-unlocked, CPU_CONTROL, boot-arg entry reg,
  SCRATCH7 poll. Nothing copies TEXT anywhere. [STATIC-CONFIRMED]
- 13.5 payload reset (0x204-0x900): zero MMIO reads pre-main; it builds
  its own MMU tables over the loaded segments and executes in place
  (reset head vm0 = b +0x204). [STATIC-CONFIRMED]
- Live DATA == payload DATA byte-identical across the RUN attempt
  proves the DRAM contents survive island power-gating: DRAM is not
  gated with the ANE domain, so "iBoot's copy was lost at power-gate"
  is FALSIFIED. [MEASURED]

Verdict on premise 2: execute-from-DRAM-through-DART [INFERENCE, HIGH].
No SRAM copy exists in the kext path, no SRAM region exists in the ADT,
and the kext builds the full TEXT DART map with RVBAR pointing at the
DART IOVA — pointless if the core executed from SRAM. An ASC-local
tightly-coupled SRAM may exist as hardware, but nothing loads it.

## 19. Non-pmgr/DART/CPU/mbox registers on the 13.5 path: the T6021 list (Main lane)

Boundary statement first. Enumerated every 32/64-bit store whose target
is a machine register on the executed path power_on_hardware ->
EnableANEClocksAndPower (T6021 index 7) -> ANE_Init, by scanning each
function body and classifying each store base. NOT covered (named so
nobody re-runs this blind): vtable-called helpers behind braa/blraa
(DART iovmInsert, perf-controller calls), cold-fail blocks, power_off /
stop / deInit, ANE_Show/Debug paths, user-client and external-method
dispatch, the perf-counter writer StartPerformanceCounters (per-domain
0x1c09078/0x1c05058 writes, not on the boot path), and Tunables/data
fields (all dev+0x3xxx structs).

The complete T6021 non-excluded register list, power_on_hardware through
the bl to ANE_Init (0xfffffe00094e08ac):

1. PS TARGET/ACTUAL via dev+0x200 (pmgr-mapped ps window):
   PS+0x8008/0x8010/0x8018 <- 0xf + validatePSReg ACTUAL==0xff
   (kext 0xfffffe00094de598-0x94de60c, validate 0xfffffe00094df614).
   Which index-7 path: version 0xa0 -> tab[7] -> 0x94de53c. pmgr by
   window: EXCLUDED from this list (already match Linux genpd).
2. PWGATE via dev+0x220 (set-window-mapped register block):
   conditional on dev+0x3814 bit1 (default 3, bit1=SET on T6021 boot path
   since the boot-arg read at start() 0xfffffe00094c9428 fails and
   0xfffffe00094c91cc stores w8=3):
   PWGATE+0x12cc <- 3 + validatePWGATEReg(3,3),
   PWGATE+0x13cc <- 0 + validatePWGATEReg(0,1)
   (kext 0xfffffe00094de554-0x94de58c, validate 0xfffffe00094df6bc).
   dev+0x220 is built in start() 0xfffffe00094c94f0 from the PARENT
   provider (start() x22 = the IOService provider arg; slot +0x710 call
   with w1=2 on the provider at kext 0xfffffe00094c9494), then
   map+getVirtualAddress. CORRECTION: the "set" base is the provider's
   index-2 published memory, NOT the ane nub's own 0x28e08c000 range —
   the section-19 "live phys 0x28e092cc/0x28e093cc" assumed base
   0x28e08c000 without proof and is WITHDRAWN. The writes stand as
   provider-set +0x12cc <- 3 / +0x13cc <- 0 with the base unbound;
   naming the provider node and its index-2 memory (likely the
   pmgr-adjacent fabric/ANE-parent nub) needs that node's reg list.
   [STATIC-CONFIRMED code+value+method; BASE CORRECTED, phys OPEN]
3. Pre-CPU ENGINE table via dev+0x1e8 (engine base 0x284000000):
   ENGINE+0x938/0xa18/0xaf8(+0xaf8) <- 0x01ff01ff
   (kext 0xfffffe00094df544-0x94df554; the version>=0x80 gate at
   0xfffffe00094df570 fires for 0xa0, version-gated 0x738/0x798/0x7f8
   skipped). [STATIC-CONFIRMED; the B4 lane already proved 0xB38/0xB98/
   0xBF8 clean from kernel context — this is the same table family at
   the T6021 offsets]
4. ANE_Init scratch clear + CPU_CONTROL + SCRATCH7 poll (section 12;
   mailbox untouched: inbox/outbox enables are stubs). Not repeated.
5. AFE+0x80: RETRACTED (section 16). No other ASCWRAP/coprocessor-config
   write exists: the outbox-enable/class-0x980 RMW (engine+0x1408114 bit
   0) is the mailbox item already listed, and no AIC/IRQ, firewall,
   watchdog, ED/DP-debug, GPIO clock-enable, or tunables store appears
   in ANY scanned body on this path. clk-enable GPIOs (0x1840050+ family)
   are the ANE_Init scratch clears, not clocks.

Ranked test (the single remaining unknown with a physical address):
PWGATE set+0x12cc <- 3 and set+0x13cc <- 0, i.e. phys 0x28e092cc <- 3,
phys 0x28e093cc <- 0 on the set window 0x28e08c000. Rationale: it is the
only non-pmgr, non-DART, non-CPU, non-mailbox machine write the kext
makes before ANE_Init that Linux is not confirmed to make. If the live
box already shows 3/0 there, report and close.

## 20. Write path for the PWGATE word: plain store, RB-polled, cacheability unproven (Main lane)

(1) validatePWGATEReg (0xfffffe00094df6bc): polls the SAME register it
was asked about. `ldr w8,[x8,x23]` (x8=dev+0x220 base, x23=offset arg);
`and w8,w21` (mask); `cmp w20` (expected); loop up to 0x1388 iterations
with a 10 us delay per iteration (mov w0,#0xa; bl delay). For the
T6021 index-7 path: +0x12cc <- 3 then poll (+0x12cc & 3)==3;
+0x13cc <- 0 then poll (+0x13cc & 1)==0. On timeout it logs and
continues (no panic). [STATIC-CONFIRMED]

(2) Write helper: NONE. The write is a plain `str w9,[x8,#0x12cc]`
(kext 0xfffffe00094de558) with x8 = dev+0x220 read via
`ldr x8,[x19,#0x220]`, guarded only by `cbz x8` (map present). There is
no IOMemoryDescriptor write method, no device-power-state check, no
lock, no barrier (no dsb/dmb/isb) between the store and the poll. The
kext relies on the memory type of the mapping for ordering.
[STATIC-CONFIRMED]

(3) Memory type: the kext maps index 2 via provider->slot+0x710
(mapDeviceMemoryWithIndex(2, options=0)) then IOMemoryMap
getVirtualAddress. With options=0 the IOKit ARM64 default for device
memory is kIOMapInhibitCache -> Device-nGnRnE (strongly ordered, no
buffering). No explicit cache-mode flag is passed at the call site.
[STATIC-CONFIRMED options=0; INFERENCE that IOKit maps it as Device].
Linux observer: ioremap_np -> Device-nGnRnE as well. The Linux and
macOS memory types MATCH; ordering is not the discriminator.

Note the observer's `pwg` window is 0x28e092000 (an assumed base, not
the provider index-2 base; section 19's correction applies). If the
write-3/readback-0 was through that window it was to an unbound
address. The kext's own write latches only after EnableANEClocksAndPower's
PS TARGET sequence on the SAME path (the +0x12cc write comes AFTER the
0x8008/0x8010/0x8018 PS raise + ACTUAL poll). A vendor register that
reads 0 after a write of 3, under Device memory with no error, is a
clock-gated register: the fabric domain that owns it isn't up when
Linux writes. The correct test order is PS raise -> poll ACTUAL -> then
the PWGATE write, exactly as the kext sequences it.

## 21. PS window correction: the 0x8008/0x8010/0x8018 writes are VENC, not ANE (Main lane)

M2FwStart-2's index-7 retest wrote 0xf to 0x28e088008/10/18 and read
0x2f forever (TARGET latched, ACTUAL not granted). Root cause is the
window, not the write. dev+0x200 is provider index-1 (start()
0xfffffe00094c9038, slot+0x710 w1=1, options=0, no explicit length).
The receipt that decoded the T6021 pmgr devices table
(receipts/2026-09-22-t6021-start-research §7.3, §7.7) already placed
the kext's +0x8008/+0x8010/+0x8018 in ps-regs[15] = window2 + 0x8000 =
0x290288000: VENC_PIPE4 @0x290288008, VENC_PIPE5 @0x290288010, VENC_ME0
@0x290288018 (+VENC_ME1 @0x290288020). 0x28e088008 is not a ps word.
[STATIC-CONFIRMED kext offsets + prior receipt decode; the live window
identity is M2FwStart-2's to confirm from the provider's reg entry [1].]

validatePSReg (0xfffffe00094df614): ldr w8,[ps+off]; and mask; cmp
expected; 0x1388 x 10us; log+continue. All three index-7 writes use
mask=expected=0xff: it waits for the low byte to read 0xff (TARGET 0xf
and ACTUAL 0xf). 0x2f = TARGET latched / ACTUAL 0 is the leaf-only
signature §7.7 already recorded live: power-up grants parents-first.
Parent chain: VENC_DMA(317) -> VENC_SYS(299, real ps, map 11/28 =
0x2902803e0) -> AVEMSR-V(519, virtual, no write). Correct order:
0x2902803e0 <- 0xf, poll low byte 0xff; then 0x290288008/10/18 <- 0xf,
poll each; THEN the PWGATE pair on provider index-2 (base bound from
the provider's reg entry [2], not assumed 0x28e08c000).
