# DART / segment-map / CTRR decode — ANE CSNE on T6001 (companion to FINDINGS.md, FINDINGS-2.md)

Kext: `receipts/2026-09-18-t6021-engine-layout-mined/kext-h13/AppleH11ANEInterface-9.512.0-macstudio-25G83`
(H13 slice; VMAs are slice addresses, `__TEXT_EXEC` file 0x48000 ↔ vma 0xfffffe0009284260).
T6001 device tree: `receipts/2026-09-22-ane-dvfs/t6001-ane0-adt.txt` (+ the lane's own DT
read of the three ANE DARTs at 0x285800000 / 0x285810000 / 0x285820000).
RTKit reference: `/tmp/rtkit-asahi.c`, `/tmp/asahi-dt/include/linux/soc/apple/rtkit.h`.
m1n1 DART model: `~/src/m2-m1n1/m1n1/hw/dart8020.py`, `m1n1/fw/ane.py`.

## 1. DART configuration: what the kext does and requires

**The kext never touches DART TTBRs or PTEs.** All mapping goes through
IOMemoryDescriptor::prepare + IODMACommand / IODARTVMAllocator; the page tables are
filled by the DART framework (AppleDART). In-kext evidence:

- IODARTVMAllocator is linked into the kext (symbols `__ZN17IODARTVMAllocator11findVMSpaceEj`
  etc., code block file 0x8a61b+).
- `ANEHWDevice::setupDartRemap` (body ~0xfffffe000931338c, guarded by flag
  [dev+0x3564+0x34]):
  - creates a lock-ordered allocation source (`bl 0xbe98568`, cmp fn 0x9313524,
    w0=0x400) → [dev+0x3570];
  - creates a DeviceMemoryManager with VM size **0x1F400000** (`mov w1,#0x1f400000`,
    DMM ctor 0x92cc264) → **[dev+0x35A0]** — the shared-malloc DART VM pool;
  - creates `fDartInfoListLock` → [dev+0x3568], resets [dev+0x3584].
  - every DART-backed allocation is tracked by
    `setDartAllocationInfo(phys, size, usageType, ANEResource)` /
    `removeDartAllocationInfo(id)` (os_log_fmt syms @0x376ea/0x37727).
- ANECPU command buffer: `bl 0x932d97c(this, 0x40000, &out /*->[dev+0x498]*/, 1,
  0x444D4D20, 1, 0, 0)` @0xfffffe0009338578; then DeviceMemoryManager ctor
  [dev+0x478] with (0x40000, 0) @0x93385d8. The captured device VA of this buffer is
  **0x1fb08000** — inside the dart-ane VA space; the PTEs are filled by the map call
  inside 0x932d97c's path, not by ANE code.
- Per-CSNE-send slot: `DeviceMemoryManager::Allocate(size)` 0x92cc34c on [dev+0x478]
  returns a byte offset; host VA = [[dev+0x498]+0x38] + offset; the offset is what the
  doorbell entry carries (FINDINGS.md §4) and what the FW reads through dart-ane.

**Three DARTs, one table set.** The ane0 ADT node has `iommu-parent = <4e010000>`
(t6001-ane0-adt.txt) and the DT shows ANE DARTs at 0x285800000 / 0x285810000 /
0x285820000. m1n1's ANE driver independently requires ALL THREE darts programmed:
it builds `dart_regs[0..2]` and copies TTBR0 into `dart_regs[1]` and `dart_regs[2]`
("DMA fails w/o", m1n1/fw/ane.py __init__), plus the two config registers
`ANEDARTRegs.UNK_CONFIG_68 = 0x68` / `UNK_CONFIG_6c = 0x6c` per DART. For T6001 this
is the same topology — if the M2 lane programs only one DART, firmware-side
translation of the cmd buffer fails silently. Field-for-field DART programming
reference (m1n1 dart8020, t6000-class):

```
TCR      @0x100 + 4*sid    TRANSLATE_ENABLE=7, BYPASS_DART=8, BYPASS_DAPF=12
TTBR     @0x200 + 16*sid + 4*bank   VALID=31, ADDR=[30:0]   (4 KiB table, 11-bit)
ENABLED_STREAMS 0xfc
REMAP    @0x80..0x8c (4 regs)  {MAP0[7:0], MAP1[15:8], MAP2[23:16], MAP3[31:24]}
PTE_T6000: SP_START[63:52], SP_END[51:40], OFFSET[39:10], SP_PROT_DIS=1, VALID=0
```
(m1n1 ane init uses iova_range (0x4000, 0xe0000000) and a dummy first mapping at
IOVA 0 to initialize the base TTBR before copying it to the other DARTs.)

## 2. CTRR remap 0x1f0000f4000 — `ANEHWDevice::mapFwCTRRRegion` (0xfffffe0009326180)

Source of truth is the device tree, not a register sequence:

1. `getProperty("segment-ranges")` from the device entry (vtable +0x2d8 on
   [dev+0x2B0] @0x93261ec-f4; string 0xfffffe000748903a8-adjacent "segment-ranges").
   Missing → `"mapFwCTRRRegion segment-ranges is not in the device tree"` (oslog
   0xfffffe00074743f9) and abort.
2. Property = N × 0x20-byte entries: `{u64 phys; u64 virt; u64 remap; u32 size;
   u32 pad}`. The kext logs per entry:
   `"FW __TEXT segment phy: 0x%llx, virt: 0x%llx, remap: 0x%llx, size: 0x%x"` and
   the same for `__DATA` (@0xfffffe0007474011 / 0x7474061 refs).
3. Entries are stored on the device: TEXT → [dev+0x220..0x240), DATA →
   [dev+0x240..0x260) (stp q0/q1/q2/q3 @0x93262f4-0x9326300).
   The t6001 ane0 `segment-ranges` blob decodes as:
   - TEXT: phys=0x10000a5c000, virt=0x0, remap=0x10000a5c000 (identity), size=0x03000f40
   - DATA: phys=0x10001684040, virt=0xf4040, **remap=0x1f0000f4040**, size=0x5f80
   The captured "fw text CTRR-remapped to 0x1f0000f4000" is the DATA-segment remap
   window base (0x1f0000f4040 page-aligned) — it comes straight from this DT property.
4. Sizes are rounded up to the DART granule at [dev+0x3620]
   (`x9 = ((phys_or_base + size + granule - 1) / granule) * granule`
   @0x9326430-0x9326468).
5. Two IOMemoryDescriptors are created via the [dev+0x3D0] factory
   (`bl 0xbf56bd0`, args (rangesPtr, w1=1, w2=0, x3=0, w4=tag), tag **0x21** for
   TEXT → [dev+0x270], tag **0x23** for DATA → [dev+0x278]) and `prepare`d
   (vtable +0x218 with w1=0 @0x93264b4-0x93264dc / 0x93265b0-0x93265d8).
6. The dart mapping happens through the [dev+0x3D0] object vtable +0x890 call
   (@0x93266b0-0x93266fc, args x1=0, x2=0, w4=3, out-VA/out-len by ref) — i.e. the
   descriptors are mapped into dart-ane so the firmware's CTRR-remapped fetch/data
   addresses (the `remap` values) resolve to `phys`. Who creates the remap: the DT
   author (firmware/OS image); the kext only creates the DART translations that make
   `remap → phys` true. On bare metal: either program dart-ane PTEs so VA 0x1f0000f4040
   hits DATA phys 0x10001684040 (and TEXT identity), or use the DART REMAP segment
   registers (0x80..0x8c) if your target's fw expects segment remapping.
7. CTRR state gating (strings + prior lane): fw reload is refused in CTRR environments
   (`"FW reload is not allowed for CTRR enviorment, fEnableFwReload is not set"`,
   oslog 0xfffffe0007474adb); preload path selected by the ADT `pre-loaded` flag
   (ane0 ADT has `"pre-loaded" = <01000000>`) plus `"ctrr-disabled"` /
   `"ctrr-unlocked"` selectors; on T6001AscDebug the fw was already booted
   (CPU_STATUS 0x2a→0x28, CPU_CONTROL 0→0x10), so the TEXT/DATA windows above are
   what the already-running fw expects to be present in dart-ane — if your PTEs do
   not cover `remap` windows, fw fetch/data faults, matching "accepts writes, no
   reaction".

## 3. Boot args / shmem surfaces — the unanswered HELLO

- `ANEHWDevice::parseANEBootArgs` exists (sym file 0x7209f) but the boot-args page
  layout is NOT statically recovered (matches the h14 lane's open gap). The ADT
  `pre-loaded` flag and the CTRR segment table above are the inputs that ARE decoded.
- The practical HELLO gap is RTKit management: an RTKit firmware boots, then sends
  `HELLO` on the management endpoint and waits. No reply → fw never announces
  endpoints, never opens channels → every later CSNE write is ignored (exactly
  T6001AscDebug's symptom: MMIO accepted, no interrupt, no reply). Reference
  constants (`/tmp/rtkit-asahi.c`, `/tmp/asahi-dt/.../rtkit.h`):

```
Endpoints: MGMT=0, CRASHLOG=1, SYSLOG=2, IOREPORT=4, OSLOG=8
MGMT messages:
  HELLO=1        {minver[15:0], maxver[31:16]}
  HELLO_REPLY=2  {minver, maxver = chosen version in both fields}
  STARTEP=5      {ep[39:32], FLAG=bit1}
  SET_IOP_PWR_STATE=6 / ACK=7
  EPMAP=8        {bitmap[31:0], base[34:32], LAST=bit51}
  EPMAP_REPLY=8  {bitmap, base, LAST, MORE=bit0}
Handshake: reply HELLO with min=max=chosen ver; reply each EPMAP bitmap
  (set MORE if more bitmap messages follow, echo LAST on the final one);
  ack STARTEP per endpoint; then SET_IOP_PWR_STATE handling.
```

- Shared-malloc surfaces are firmware-driven after the handshake: the fw asks the
  host to map/allocate surfaces (h14: channel "T2H_SHMEM" index 4,
  `processSharedMallocRequestEndpoint`, struct `ANESharedMemorySurfaceParams` —
  layout still an open gap). The H13 kext's equivalent shared-malloc pool is the
  0x1F400000-byte DART VM allocator from `setupDartRemap` (§1).

## 4. Ordering for the M2 bare-metal bring-up (with the round-2 sequence)

1. Fill dart-ane page tables: TEXT (identity per segment-ranges phys), DATA
   (remap 0x1f0000f4040 → phys), the 0x40000 cmd buffer, the PMU window
   (0x28e08c000 +0x4000), and any shared-malloc windows. Program ALL THREE DARTs
   (TTBR0 copies + UNK_CONFIG_68/6c) and sync.
2. Complete RTKit HELLO/EPMAP/STARTEP/PWR handshake on the mailbox (this is the
   piece between "ASC booted" and "fw consumes commands").
3. Wait for the channel-description-table-ready event (round 2: second interrupt;
   rtkit terms: endpoint announcements), resolve "IO"/"IO_T2H".
4. Allocate the 0x40000 ANECPU buffer (IOVA 0x1fb08000-class), then the CSNE
   sequence of FINDINGS.md (PRINT_ENABLE → … → RESOURCE_INFO_GET).

Open gaps (honest): boot-args page layout; ANESharedMemorySurfaceParams layout;
the exact dart-ane stream/sid the fw uses (m1n1 uses sid 0; macOS stream numbers not
decoded statically).

## Evidence anchors

- setupDartRemap body 0xfffffe000931338c-0x9313524 (0x1F400000 DMM, lock, list)
- mapFwCTRRRegion 0xfffffe0009326180-0x9326804; segment-ranges getProperty
  0x93261ec; entry stores 0x93262f4-0x9326300; log fmts oslog 0xfffffe0007474011 /
  0x7474061; granule round 0x9326430-68; descriptor factory 0x932646c-0x93264a8;
  map call 0x93266b0-0x93266fc
- CTRR gating strings: oslog 0xfffffe0007477d2b ("usb get preloads the fw is true,
  fEnableFwCTRR = true"), 0x7477d6a, 0x7477e12, 0x7474adb, 0x74788e5, 0x747893a
- ANECPU buffer create: 0xfffffe0009338544-0x93385dc
- DMM alloc + doorbell offset: 0x92cc34c / FINDINGS.md §4
- t6001 ane0 ADT: t6001-ane0-adt.txt (`segment-ranges`, `pre-loaded`,
  `iommu-parent=<4e010000>`, reg = 0x284000000/0x2000000 + 0x28e080000/0xC02C)
- rtkit constants: /tmp/rtkit-asahi.c lines 19-52, 110-146, 159-194
- m1n1 three-dart TTBR0 + UNK_CONFIG_68/6c: m1n1/fw/ane.py __init__
