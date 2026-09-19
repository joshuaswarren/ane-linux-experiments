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
for the entry encoding itself. K13 additionally polls after the write
until `readReg(cfg+0x118)` equals `0x08042006` — a config-driven register
at cfg-field `+0x118`; its identity (and what the constant encodes) is
unresolved. Only the read-compare handshake itself is pinned; it is a
boot-lane datum, not a register-name claim.

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
  grant fault, not translation fault). This proves the writes are unsafe
  **in the tested state**; it does not establish what state would make
  them safe, and no such claim is made.

## 5. Placement mechanics mined — the image lives in the DART-mapped shared surface (addendum)

Source-xref trace of the ANE kext's own fw load path (`ANE_LoadFirmware_gated`
log tag; function `0xfffffe00095efe0c–0x95f0700`), all addresses in K14
10.19.2:

1. **Image mapping** — `0x95f0310–0x95f0338`: the fw data object is mapped
   via vtable+`0x228` → +`0x1000` (page) and kept in `x22`.
2. **Placement write** — `0x95f0404–0x95f0464`:
   `cfg = [dev+0x178]; w1 = [cfg+0x138]` (image byte-count from the SoC
   config), `x0 = [[dev+0x978]+0x38]` (the `FirmwareLoaded` OSObject's
   `+0x38` field = the ANE **shared-memory surface** pointer), then
   `bl 0x964c2d8(x0, w1)`; the mapped image bytes are written into that
   surface via `bl 0x964c528([surface], bytes, x23)`.
3. **Cache clean** — `0x95f0688–0x95f06a4`:
   `x8 = [[dev+0x978]+0x38]; x9 = [[dev+0x178]+0x138]; x1 = x8 + x9 -
   0x4000; bl 0x95d92bc(x0=surface_obj, x1)` — cache maintenance over
   `[surface, surface + size − 0x4000)`.
4. **Handoff flag** — `0x95f0640–0x95f0668`: `setProperty("FirmwareLoaded",
   true)` (vtable+`0x298`, cstring at `0x74c3f3d`). The boot sequence
   (`…95e9850`) then reads this property (`+0x18` = OSBoolean value) to
   compose the RVBAR write — image-in-surface strictly precedes CPU boot.
5. `str w24, [dev+0x974]` stores the fw command id (`0x95f0468`).

**Contract for a Linux loader (from kext evidence):** the ANE image is not
placed at a fixed host-MMIO SRAM constant — it is copied into the ANE
shared-memory surface (a runtime buffer made ASC-visible through
dart-ane0/mapper-ane0), cache-cleaned, then RVBAR (`eng+0x1050000` ←
`0x0081_0000_0000_0001`) + SCRATCH7 cold boot run. Still open before
implementation: how the surface address reaches the ROM — the boot-args
path is `SetupFWInitBootArgs(ANESharedMemorySurfaceParams*)`
(`0x95ac8cc–0x95ac9d0` walks per-client blocks of stride `0x158`/`0x11c`
plus variable sizes `8+0x24`/`0x158`, `0x58×n+8+0x24` — the struct layout
is mineable next) and the register/field that publishes it.

## 6. Next implementable step

With placement resolved to "the DART-mapped shared surface" (§5), the
remaining implementation datum is narrower: the `ANESharedMemorySurfaceParams`
layout and the mechanism that publishes the surface address to the ROM
(`SetupFWInitBootArgs` walk `0x95ac8cc–0x95ac9d0` is the first mine
target, followed by whoever calls it with the surface base). Fallback
route, unchanged: live-ADT exposure on jw14m2 (jw16 phram method; needs
approval + module build/load + netconsole window) to check whether iBoot
populated ane0 `segment-ranges` this boot. Until the surface-to-ROM
contract is pinned, the staged firmware in `/opt/ane/fw/` stays a staged
artifact and no RVBAR/SCRATCH7 write is made. MMIO write table: none this
lane.
