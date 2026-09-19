# H14/T6021 W13 — boot-ROM entry independently verified (K13 ≡ K14, byte-identical contract); image-placement candidates narrowed; no device contact (2026-09-19)

Verdict: **CONTRACT VERIFIED, PLACEMENT STILL OPEN.** The K14 boot sequence's
RVBAR write value `0x0081_0000_0000_0001` is independently confirmed by the
H13 kext (9.512.0, macstudio boot KC) executing the identical pattern, and
Asahi's own t602x device trees contain no ane node (no independent IRQ
source anywhere — the single-IRQ evidence stands). The one datum still
missing for a boot attempt remains iBoot's image placement. **Zero device
writes; no module load; no reboot** (jw14m2 untouched except reads;
`/sys/firmware/fdt` pulled read-only — memreserve list is empty, so the
live-ADT route on this box needs the jw16-style phram method and was NOT
attempted).

## 1. Boot-ROM entry encoding — independently verified

K14 (`AppleH11ANEInterface` 10.19.2, boot function `…95e9850–95e9988`) and
K13 (9.512.0, same boot function at `…93203b0–93204e0`) execute the same
instruction sequence:

```
movk  xM, #0xff7e, lsl #48 ; mov xN, #-0x800      ; mask = 0xff7e_ffff_ffff_f800
mov   xK, #1 ; movk xK, #0x81, lsl #48            ; entry base = 0x0081_0000_0000_0001
ldr   x8, [dev, #PROP]; ldr x8, [x8, #0x18]       ; "FirmwareLoaded" OSObject value
and   x8, x8, mask ; orr xENTRY, x8, xK           ; reduces to the constant for a bool
ldr   x0, [map]; mov w1, #0x1050000               ; RVBAR (eng + 0x1050000)
bl    readReg ; tbnz w0, #0 -> skip               ; bit0 = released latch (W8 live: 0x1)
bl    writeReg(map, 0x1050000, xENTRY)            ; the boot write
```

Generation-stable H13→H14: same offset, same gate, same entry constant,
same mask. This satisfies the "verify independently before any MMIO" gate
for the entry encoding itself. K13 additionally polls after the write:
`readReg(cfg+0x118) == 0x08042006` (config-driven register, likely
CPU_STATUS; W10's live `CPU_STATUS.STOPPED` read aligns) — a ready-state
handshake datum for the future boot lane.

## 2. Loader layering — who places the image

- **RTBuddy 1.0.0** (`RTBuddy.flat.bin`, symbols extracted to
  `rtbuddy.syms`): `RTBuddy::_loadFirmwareGated`, `_performFirmwareLoad`,
  `_handlePreloadFirmware`, `RTBuddyFirmware::preloadedFirmware`,
  `::iBootLoaded`, boot-args `rtb_disable_fw_load`, strings `pre-loaded`,
  `cold-boot-after-hibernate`, `reboot-firmware`. This is the generic
  segment loader for IOPs whose ADT nodes carry `segment-ranges`
  (sio/dcpext/isp — m1n1's `dt_reserve_asc_firmware` reads the same
  property). **ane0 has no segment-ranges and no iop-nub on any gen**, so
  the ANE image does not ride RTBuddy's generic path.
- **AppleH11ANEInterface** owns the ANE boot end-to-end (Chinook sequence
  above + `SetupFWInitBootArgs(ANESharedMemorySurfaceParams*)` +
  `ANE_CleanupForColdReboot_gated` + custom-FW vnode path). The kext's
  RVBAR write boots a ROM entry, so the image must already be resident
  where that ROM looks — placed by iBoot on macOS boots (BuildManifest
  `IsLoadedByiBoot=true`).
- **iBoot** (`iBoot.j414c.bin`, mBoot-20457.1.29): the coprocessor fw
  descriptor pool is at file 0x225519–0x2256db (`MtpFirmware.img4 ·
  ANE0/ANE/ane0/ANE.img4 · ANE1/ANE/ane1/Ap,ANE1.img4 · AVE… · AOP · GFX ·
  ISP · PMP · SCodec · SIO · DCP`). The descriptor table that references
  this pool is load-relocated (no static pointer runs match any base
  hypothesis; ADRP/ADD xrefs only hit `dart-ane0`), so the placement
  constant needs either the reloc table decoded or the load-path function
  traced — **not cracked this lane**; tooling notes: pointer/table scans
  must account for iBoot self-relocation.

## 3. Live-ADT route on jw14m2 — scoped, not executed

The jw16 precedent (`receipts/2026-09-13-t6001-static-adt/jw16mbp1-linux-adt-exposure.json`)
exposed the boot-time ADT via phram at a known physical address; the live
ADT on a boot where iBoot populated `segment-ranges` would directly state
the ANE placement (if iBoot loads it on this boot chain at all — W10's
stopped-CPU finding says it does not *start* it). On jw14m2 today:
`/sys/firmware/fdt` memreserve list is **empty** (FDT pulled read-only,
`jw14m2-fdt.dtb`), m1n1 uses reserved-memory nodes instead, and the phram
route needs an external module build+load — a device-state change this
lane did not make. If pursued, it is the same class as the jw16 lane and
needs its own approval + netconsole window.

## 4. Doorbell provenance correction (Main steering, reconciled)

W12 said "doorbells eng+0x1844000 … all W10-live-proven offsets". Correct
split, now also fixed in the W12 receipt text:

- **eng+0x1408000 mailbox register file**: W10 *read*-proven live
  (`a2i/i2a controls 0x00020001`, FIFOCNT=0, WPTR/RPTR=0, zero aborts —
  receive path positively mapped, read-only).
- **eng+0x1844000 doorbell**: kext-pinned (W5 provider-kext decode). Host
  writes there were attempted (W5-live, W9) and **SError'd** (0xbe000000,
  5–11 µs after the seam) — W9 showed the class still SErrors even behind
  the W8 aperture grant. The address is real and mapped (permission/write-
  grant fault, not translation fault) but is **not safe** until the fw-CPU
  is running. No claim of a safe write is made.

## 5. Next implementable step

Two candidates, both read-only, either can be the next lane:

1. **iBoot relocation-aware descriptor trace** (pure offline): decode
   iBoot's self-reloc table, find the fw-descriptor array entries for
   `ANE0`/`ANE1`, follow the loader's placement (source img4 → destination
   region → size/`_rtk_boot_l1` patching) and pin the ASC-physical load
   address. Deliverable: the placement constant that makes a boot attempt
   non-blind.
2. **Live-ADT exposure on jw14m2** (jw16 phram method; needs approval +
   module build/load + netconsole window): answers definitively whether
   iBoot populated ane0 `segment-ranges` this boot, plus the m1n1 stage-2
   log region for boot-chain context.

Until (1) or (2) yields the placement, the staged firmware in
`/opt/ane/fw/` stays a staged artifact and no RVBAR/SCRATCH7 write is
made. MMIO write table: none this lane.
