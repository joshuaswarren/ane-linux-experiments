# H14 mapping and bootargs evidence

Static evidence only. Firmware boot and MMIO writes remain unqualified.
KC SHA-256: `8304156fe05849a45f1c15807432e82cb0e8ac8cb9c883541889bf51287340fa`.
Addresses below are low32 unslid virtual addresses; file offset = address − `0x7004000`.

## Pointer and symbol decoding

- `nlist_64` is `<IBBHQ>`, 16 bytes, value at +8. The previous `<IBBQQ>` parser was wrong.
- KC chained-fixup header at file `0x7740000` is `(0,28,2336,2336,0,1,0)`; no magic prefix.
- Format8 target is bits0..29; cacheLevel bits30..31. Base is outer `__TEXT`, `0xfffffe0007004000`, not PRELINK `0x700c000`.
- Authenticated entries retain target offsets plus signing metadata. Recovering these targets requires no PAC keys.
- Validated walk: 674 chains, 1,031,644 entries, all cacheLevel0, all targets inside known KC segments.
- Constructor establishes ANEHWDevice address point `0x8141de0` (vtable +16). Slots +0x8a8 and +0x8b0 resolve to `0x95daa38` and `0x95db620`.

## Params and address producer

`ANESharedMemorySurfaceParams` is a 0x78-byte value, not a record extending to +0xe8.

- Params+0x18 is the mapped device address; Params+0x38 is the CPU surface pointer.
- In the Params** allocator at `0x95f679c`, x24=sp+0x70; the mapping call receives x3=x24+0x18 as its address output. The Params value is copied by `setValue` at `0x95f7314`, then returned through the caller's output pointer.
- `ANEHWDevice::dartMapMemoryDescriptor` is `0x95daa38`. Its ordinary path prepares an IODMACommand, generates segments, selects the returned address, and stores it through x19 at `0x95db13c`.
- If visible_out is non-null and dev+0x780 bit0 is set, it calls `makeMemoryVisible` at `0x95db284`. RTBuddyService creates a visible-memory object; that object's vslot+0x138 supplies the address stored through the output pointer at `0x95db3c4`.
- The separate shared_ptr overload's stack+0x18 completion field is unrelated. The earlier claim that the actual Params+0x18 might be completion status is withdrawn.
- RTBuddy's downstream `0xc46e7c4` is a segment-output callback writing address/length pairs, not a vtable.

## Distinct allocations

- dev+0x978: firmware Params*. `ANE_LoadFirmware_gated` (`0x95effa8`) copies the image to Params+0x38; `ANE_Init` folds Params+0x18 into the RVBAR entry.
- dev+0x980: inference-memory Params*. `initializeInferenceRequestMemoryPool` (`0x95e3ce8`) initializes the pool. Cursor publication uses mapped base + CPU cursor − CPU base.
- dev+0x618: RTBuddy FW_INIT endpoint Params*. This is a separately allocated 64KiB surface, not either allocation above.

The observed RVBAR composition is `(Params18 & 0xFF7EFFFFFFFFF800) | 0x0081000000000001`. Register width/access and Linux DMA-domain equivalence still require proof before implementation.

## RTBuddy FW_INIT bootargs

Detailed anchors and runnable check: `2026-09-20-h14-fwinit-surface.json` and `2026-09-18-t6021-engine-layout-mined/tools/check_fwinit_surface.py`.

`InitializeRTBuddyEndpoints` calls `SetupEndpoints` (`0x95fe660`) for indices1..6 in order:

| Index | Name | Allocation | Bootargs flag |
|---|---|---:|---:|
| 1 | FW_INIT | 0x10000 | 1 |
| 2 | T2F_CMD | 0x40000 | 0 |
| 3 | T2F_HIPRI | 0x40000 | 0 |
| 4 | T2H_SHMEM | 0x10000 | 0 |
| 5 | T2H_CMD | 0x20000 | 0 |
| 6 | T2H_TERM | 0x10000 | 0 |

Table base `0x814e520`, stride40. The newly allocated Params* is saved at dev+0x5c0+index*0x40+0x18. Only FW_INIT calls `SetupFWInitBootArgs` (`0x95fe440`).

That function writes surface+0x84=0x40 and copies 0x100 bytes from dev+0x998 to **surface+[0x88,0x188)**. The `str q0,[x24,#0x88]!` writeback changes x24. The old +0x108..0x208 interpretation was wrong. The tail loop logs template words; it does not construct per-client blocks. There is no Params+0xe8 bootargs pointer.

The 0x100-byte template is allocated during `ANEHWDeviceConfig::initializeANEProperties`, stored at dev+0x998 at `0x9612b84`. Observed initial writes: word0 from config+0x1d8, word+0xc0 OR4, bytes[4,12) zero. Complete field meanings and later mutations are still open.

## Branch and qualification limits

The plist supports both RTBuddyService roles ANE/ANE1 and AppleARMIODevice `ane,t8020`. A successful RTBuddy initialization (IOReturn0) sets dev+0x780 bit0. Saved ADT compatibility and plist support do not establish which provider actually bound on macOS.

The endpoint mapping word is sent through an endpoint-object virtual method; a matching Linux transport has not been established. Do not transplant RTBuddy bootargs into the firmware image or infer that this branch is the legacy ANE boot path.

Source-only checks:

```
python3 receipts/2026-09-18-t6021-engine-layout-mined/tools/macho_syms_regression.py
python3 receipts/2026-09-18-t6021-engine-layout-mined/tools/kc_chains_decode.py --regress
python3 receipts/2026-09-18-t6021-engine-layout-mined/tools/check_fwinit_surface.py
```
