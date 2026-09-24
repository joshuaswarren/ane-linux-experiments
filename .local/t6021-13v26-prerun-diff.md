# 13.5 (22G74) vs 26/27 pre-RUN diff, T6021 (J414c target)

Date: 2026-09-24 · AneStaticStart. 13.5 source: jwm1:~/m2proxy/kernelcache.mac13j
(Mach-O arm64e 93 MB, sha 9615a486511c7a60, fetched read-only to
/tmp/anestatic/kc13macho). 26/27 source: /tmp/m2kstart/kc.level9.gz per the
receipts/2026-09-24-t6021-macos-start-sequence work. All addresses are VAs
in their own image. [STATIC-CONFIRMED] = disassembled; [INFERENCE] = drawn.

## 1. Same skeleton, different driver generation

13.5's ANE driver is class H11ANEIn (ANE_Init 0xfffffe00094e0cfc);
26/27's is ANEHWDevice. The start path shape is the same — clock/power
validate script → scratch zeroing → RVBAR skip-or-compose → CPU release →
SCRATCH7 READY poll — but every offset table, flag byte, and helper is
laid out differently. Nothing below transfers by address; only by role.

## 2. Pre-RUN sequence in 13.5 (ordered)

1. **Clock/power validates, not writes.** 13.5 EnableANEClocksAndPower
   (0xfffffe00094ddd64) calls two helpers (0xfffffe00094df614 on the
   [x0+0x200] window, 0xfffffe00094df6bc on [x0+0x220]) that READ
   [base+index], compare `(val & mask) == expected`, and retry 0x1388
   times before logging. Indices validated include 0xc000-0xc038,
   0x2c8, 0x2e0, 0x170, 0x3f00-0x3f20, 0x4008-0x4030, 0x2dc, 0x272c,
   0x199c, 0x1f8c, 0x5a8-0x5c0. The actual power writes happen in the PMGR
   provider (enableDeviceClock/Power), same delegation as 26/27.
   [STATIC-CONFIRMED]
2. **Scratch zeroing is table-driven and runs pre-RUN.** ANE_Init zeroes
   eight SCRATCH cells through per-variant tables at __const
   0xfffffe00073a0148-0x73a0350 (indexed by dev+0x3c10), then reads RVBAR
   (0x1050000) and skips-or-composes with the same 0x0081<<48 constant
   (0xfffffe00094e0e74-0x94e0f18). [STATIC-CONFIRMED]
3. **CPU release identical:** write32 0 then 0x10 to the CPU word
   (0xfffffe00094e0f24-0x94e0f34), then SCRATCH7 READY poll for
   0x08042006 with the 1000-iteration bounded loop. [STATIC-CONFIRMED]
4. **No DATA write, no boot-arg write, no shared-memory publish before
   RUN.** ANE_SetFirmwareBootArg(_gated) (0xfffffe00094f1cb0) writes a
   u32 into a host-side array ([x0+0x318]+index), never into firmware
   memory; it is a UserClient-settable table, not part of the boot path.
   ANE_LoadFirmware(_gated) (0xfffffe00094f2cd4) takes firmware
   payload args — on the preloaded path the firmware comes from iBoot
   segments, same as 26/27. SetupEndpoints/channelNameToIndex traffic
   (0xfffffe00094f4664 loop at 0x94e1e58+) is post-HELLO channel bringup.
   [STATIC-CONFIRMED]
5. **RTKit init order identical:** _handleHello (0xfffffe000aea725c)
   requires iopStatus 4/0x8000, checks version min/max 0xc, sets status
   5, replies; EPRollCall after. Same contract as 26/27.
   [STATIC-CONFIRMED]

## 3. Deltas 13.5 vs 26/27 that matter for the port

- **No PWGATE-window writes exist in 13.5's path.** The 26/27
  PWGATE+0x159c/0x248c/0x2d8c/0x3b6c validated writes have no 13.5
  counterpart; 13.5 validates its index set and writes nothing outside
  the provider. The TSV rows against the 0x28e092000 window do not apply
  to the 13.5 firmware on the box. [STATIC-CONFIRMED negative: full
  EnableANEClocksAndPower call list is validate-helper calls only]
- **The TSV's PS-window rows DO apply** (0x2e0/0xc000/0xc008/0x3c8-class
  indices appear in both), but they are provider-owned either way —
  already struck. [STATIC-CONFIRMED]
- **RVBAR/RUN/READY constants identical** (0x0081<<48, 0x10,
  0x08042006). The 13.5 firmware expects exactly what the 26/27 analysis
  says. [STATIC-CONFIRMED]
- **Boot-arg/SCRATCH/DATA conclusion unchanged:** nothing host-written
  into firmware memory before RUN in either generation. The firmware's
  pre-RUN inputs remain: RVBAR entry, mapped segments, clocks.
  [STATIC-CONFIRMED]

## 4. Rows that differ from what Linux does — 13.5-corrected

Against the 13.5 preloaded firmware actually on the M2, there are NO
remaining host-side pre-RUN register writes Linux is missing: power is
provider-owned, scratch zeroing Linux already does (P1), RVBAR is
skip-if-locked on both sides, RUN Linux already does (P3), mailbox
enable is post-decision on both sides. The delta that remains is the one
the fetch-side work already owns: iBoot's segment mapping + the 13.5
firmware's own early-boot expectations (stamp, BSS/VM span), not a host
register. The PWGATE-window line of investigation is closed for the
13.5 target — it was a 26/27-only artifact. [INFERENCE from confirmed
negatives]
