# H14/T6021 — DART surface mapping + Params+0x18 RVBAR fold: static symbol-anchored receipt (2026-09-20)

Lane: H14DartAudit. Source-only; zero device contact. Image: AppleH11ANEInterface-10.19.2-mac14j-26A428
(whole-file sha256 db30863ed0b24e39…, __TEXT_EXEC blob fd5c43178033533f…). All addresses byte-anchored.

## 1. Corrected chained-pointer base

KC-level LC_DYLD_CHAINED_FIXUPS header is the canonical 7-u32 struct (NO magic):
`(fixups_version 0, starts_offset 28, imports_offset 2336, symbols_offset 2336, imports_count 0, imports_format 1, symbols_format 0)`
at KC file 0x7740000; fixupStarts at payload+28 declares 9 segments, chains on segs 2/3/7:
__DATA_CONST (file 0xde4000, page_size 0x4000, 803 pages), __DATA_SPTM (0x1a70000, 29), __DATA (0x5944000, 264).

Entry format 8 (DYLD_CHAINED_PTR_64_KERNEL_CACHE), LSB-first:
`{target[0:30), cacheLevel[30:32), diversity[32:48), addrDiv[48], key[49:51), next[51:63), isAuth[63]}`;
stride = next*4; **recovered address = KC __TEXT vm 0xfffffe0007004000 + target**.
Auth entries (isAuth=1) carry target30 + signing metadata — target recovery needs NO keys (the boot-time
signer adds slide and re-signs). Earlier 0xfffffe000700c000 base and any "auth targets undecodable" claims are
retracted. Walk: 674 chains, 1,031,644 entries, all cacheLevel 0, targets 100% inside known KC segments.

## 2. Symbol-anchored class model (fixed <IBBHQ> nlist parser)

- dev->0x978 and dev->0x980 hold **ANESharedMemorySurfaceParams\*** values (the T value of
  OSValueObject<ANESharedMemorySurfaceParams> instances), stored at 0x95f7114-18 by
  AllocateSharedMemorySurface_gated[params\*\* overload 0x95f679c] via create (0x95f727c) /
  setValue (0x95f7314) / init (0x95fd29c); gMetaClass 0xcb6e5e8; __ZTV 0x814d7d8.
- The RVBAR entry compose in ANEHWDevice::ANE_Init (0x95e942c, compose at 0x95e9858-0x95e9910):
  `entry = ([dev->0x978]+0x18 & 0xFF7EFFFFFFFFF800) | 0x0081_0000_0000_0001`, written to eng+0x1050000,
  gated by a prior readReg bit0 test. **Params+0x18 is the folded field.**
- Params+0x38 = surface base (store-destination proven in SetupFWInitBootArgs 0x95fe440:
  boot-args blocks written at params->0x38 + offset).
- Params+0xe8 = boot-args buffer pointer (W13 §6).
- SCRATCH0/1 = lo/hi of (params->0x18 + ring cursor − params->0x38) — runtime position publish;
  SCRATCH3 = ack 0x08042006; SCRATCH7 = 0 cold / 1 warm / wake 0xf7fbdff9, host polls for 0x08042006.

## 3. Params+0x18 producer (named)

ANEHWDevice::dartMapMemoryDescriptor
(IOMemoryDescriptor\*, IODMACommand\*\*, u64\* iova_out, IOMapper\*, bool, ANEResourceUsageType, u64, RTBuddyVisibleMemory\*\*)
= 0x95daa38 (vtable slot +0x8a8 of __ZTV11ANEHWDevice 0x8141dd0, address point 0x8141de0 — ctor 0x959b180
stores the vptr via pacda(0x8141de0)). The gated flow calls slot +0x8a8 with iova_out pointing at the Params
field staging; variant slot +0x8b0 → dartMapMemoryDescriptorSharedMallocRegion (0x95db620).
makeMemoryVisible (0x95db284) publishes via RTBuddyService::makeMemoryVisible → RTBuddyVisibleMemory
→ vtable+0x138 getter → IOVA to Params+0x18 byref (peer's raw chain).

## 4. Two personalities, two branches (exact plist facts)

__PRELINK_INFO (file 0x55a4000+0x3a0000), _PrelinkInfoDictionary[75] = com.apple.driver.AppleH11ANEInterface:
1. `RTBuddyBringu`: IOProviderClass **RTBuddyService**, IOPropertyMatch {role: ANE} (+role ANE1 twin).
2. `t8020`: IOProviderClass **AppleARMIODevice**, IONameMatch **"ane,t8020"** — matches the saved T6021 ADT
   ane0 node (compatible ane,t8020) directly.

InitializeProvider (0x96005e8) compares the provider class: "RTBuddyService" → InitializeRTBuddyClient
(0x95ffd60) → kIOReturnSuccess(0) ⇒ dev+0x780 bit0 = 1 (strb at 0x9600288); "ane" → the alternate object
(dev+0x810) path, bit0 untouched. makeMemoryVisible takes the rtbuddy alternative iff visible_out != NULL
and bit0 = 1. The gated map-path selector uses dev+0x3aa0 bit0 and global 0xcb6dc60 bit2 (default 0 →
slot +0x8a8 path). **Open discriminator: which personality/nub the jw14m2 macOS side actually bound —
runtime state, not in the saved captures; no claim made.**

## 5. Regression commands (all source-only)

```
cd receipts/2026-09-18-t6021-engine-layout-mined/tools
python3 macho_syms_regression.py            # 3/3 anchors + <IBBQQ> mutant-kill (commit daf2a25)
python3 kc_chains_decode.py --regress       # header pin (0,28,2336,2336,0,1,0) + cacheLevel-0 assert
                                            # + seg-range validation + slot asserts
                                            # vptr+0x8a8 -> 0x95daa38, vptr+0x8b0 -> 0x95db620 (commit a626afd/ba6186d)
```
Parser fix: macho_syms.py nlist_64 = <IBBHQ> 16 B (was <IBBQQ> 22 B reading n_value at +14 — garbage).
Commits: d6a12f6 (parser fix), daf2a25 (production-parser + mutant-kill regression), a626afd (chain decoder),
ba6186d (hardening: header pin, cacheLevel assert, segok exit).

## 6. Register-level boot contract (def-use summary)

1. AllocateSharedMemorySurface_gated → params record; Params+0x18 = dartMapMemoryDescriptor iova_out
   (commit vcall return / error 0xe00002bd on the failure path); Params+0x38 = surface base;
   Params+0xe8 = boot-args buffer.
2. SetupFWInitBootArgs (0x95fe440) consumes Params (0x38 base, 0xe8 buffer).
3. ANE_Init composes the entry word folding Params+0x18, writes RVBAR (eng+0x1050000) after the
   readReg bit0 gate, then SCRATCH7 = 0 (cold) / 1 (warm); host ack SCRATCH3 = 0x08042006;
   wake poke 0xf7fbdff9; host polls SCRATCH7 == 0x08042006.
4. Zeroing routine 0x957a2d0 covers [+0x0,+0x88)+arrays (whole-record zero before fill).

## 7. AMENDMENT (2026-09-20, same lane): two-surface model; +0xe8 claim withdrawn

Fixed-symbol re-trace supersedes parts of §2/§6:

- SetupFWInitBootArgs true address = 0x95fe440 (single caller 0x95fe8a0 inside
  ANEHWDevice::SetupEndpoints(u32, ANESharedMemorySurfaceParams**)); conditional
  on a flag byte ([x27+0x20] bit0). It initializes the SURFACE HEADER of the
  params->0x38 surface: +0x84 = 0x40, +0x88..+0x108 zeroed, a 0x100-byte template
  from dev->0x998 copied to +0x108..+0x208, then per-client blocks.
- The earlier "[surface+0xe8] = boot-args buffer" reading is surface-relative
  (correct as a surface offset); the receipt's "Params+0xe8 = boot-args buffer
  pointer" line is WITHDRAWN — the params record (T size 0x78, setValue copy)
  only has the fields below.
- dev->0x978 and dev->0x980 are TWO SEPARATE params (ANESharedMemorySurfaceParams)
  slots, both values of OSValueObject<Params> instances (keys "FirmwareLoaded" and
  id 0x40000):
  - 0x978 = FIRMWARE slot: ANE_LoadFirmware_gated (0x95effa8) copies the fw image
    to params->0x38 surface; ANE_Init folds params->0x18 into the RVBAR word.
  - 0x980 = INFERENCE-memory slot: ANEFirmwareManager::
    initializeInferenceRequestMemoryPool (0x95e3ce8) writes the pool base at
    params->0x38; SCRATCH0/1 position math uses params->0x18 + cursor − params->0x38.
- Params+0x18 producer (corrected): the gated-alloc completion (0x95f6570) stores
  the completion-vcall return into record+0x18 via the stack byref — a completion
  status/value on the gated-alloc record; its identity to the params struct is the
  remaining formal step. The RVBAR fold semantics for that field follow from the
  fw lane's producer trace.
- True symbol anchors (fixed <IBBHQ> parser): SetupFWInitBootArgs 0x95fe440,
  ANE_LoadFirmware_gated 0x95effa8, ANE_Init 0x95e942c, ANEFirmwareManager ctor
  0x95e3a04, initializeInferenceRequestMemoryPool 0x95e3ce8,
  createANESurface 0x95a9ac4, dartMapMemoryDescriptor 0x95daa38,
  dartMapMemoryDescriptorSharedMallocRegion 0x95db620, makeMemoryVisible 0x95db284,
  SharedMemorySurfaceTargetPhysicalAddressToHostVirtualAddress 0x95f73cc,
  OSValueObject<Params> create 0x95f727c / setValue 0x95f7314 / init 0x95fd29c.
- The earlier broken-parser addresses (0x9579520/0x957a2f0/0x9579560/0x9579b14 and
  the 0x957a2d0/0x957a1ac zero/ctor attributions) are discarded.
