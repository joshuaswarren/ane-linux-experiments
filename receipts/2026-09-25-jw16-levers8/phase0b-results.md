# Phase 0b EXECUTED — bootargs region read (2026-09-26, Main-authorized increment)

Scope executed exactly as authorized: PS gate re-checked same boot,
ptr/size re-read, both offsets bound-checked against the driver's
0x80000 map, then ONLY the 564-byte region read. No writes, no
CPU_RUN, no bulk SRAM beyond the bounded region, no reboot, no service
changes. Module /var/tmp/pmp-phase0b on jw16, loaded once, unloaded.

## Raw sequence (dmesg, abridged to the state values; full hex dump in dmesg + this file's addendum)

```
pmp0b: PS raw=0x1f0000ff actual=0xf desired=0xf          # gate re-passed
pmp0b: bootargs ptr=0x00078800 size=0x00000234 (re-read)  # identical to phase0
pmp0b: bounds OK: [0x00078800, 0x00078a34) inside map 0x80000
```

## TLV walk (pmp.rs patch_bootargs structure: u32 key, u32 size, value)

Clean walk end-to-end (lands exactly at 0x234, no overruns). Keys and
values (raw):

| key | size | value |
|---|---:|---|
| STKG | 0x8 | 70 ab 76 6b 54 00 44 6c |
| DVID | 0x4 | 00 00 00 00 |
| DCAP | 0x4 | 00 00 00 00 |
| DSTS/BSTS/USTS/TEST | 0x4 | 00 00 00 00 each |
| BDID | 0x4 | 00 00 00 00 |
| TRCE / RTEV | 0x4 | 01 00 00 00 each |
| SLID, CSSS | 0x8 | zeros |
| DSRL | 0x1 | 00 |
| DSVS, DSCL | 0x8 | zeros |
| RTSZ | 0x4 | 00 40 0f 00 (LE 0x000f4000 = 999424) |
| PTPB, PTVB, T1Ps, GptB, PplB, PTPS, GxPB, GxPS, DSZS, DSZL | 0x8 | zeros |
| GptS | 0x8 | 00 40 00 00 00 00 00 00 (LE 0x4000) |
| TUNS | 0x8 | 34 8a 07 01 00 00 00 00 (LE 0x01078a34) |

Full hex dump (564 B) is in the dmesg capture of the window and in
/var/tmp/pmp-phase0b (module source retained on jw16).

## Validity checks (per Main's framing)

- Structure VALID as a bootargs TLV chain: keys parse cleanly, sizes
  sum exactly to the registered size, ends precisely at the bound.
- BDID = 0, DVID = 0, DCAP = 0: the three entries pmp.rs patches exist
  as PLACEHOLDERS — consistent with iBoot preparing the structure and
  the host OS expected to fill board/dram identity before CPU start.
- RTSZ 0x000f4000 (999,424 B) is consistent with an RTKit image size
  and fits inside the 1 MiB SRAM extent.
- Per Main's caveat: this is a prepared STRUCTURE, not executable-
  firmware validation. No firmware bytes have been read or verified.

## Consequence for the route decision

Phase-0 discrimination now reads: SRAM is PREPARED (bootargs present
and well-formed), not empty. If the firmware image itself is resident
(candidate: the sub-0x78800 region, 0x78800 bytes = 493,568 B, and/or
RTSZ-sized), the in-tree driver's fw=None boot path is viable after
its DT prerequisites — pending firmware-byte validation. Next
increment proposal (awaiting authorization): bounded, hash-only scan
of PMP+0x0000..0x78800 in 4 KiB chunks (read into kernel buffer,
SHA-256 each chunk, print ONLY hashes — no bulk dump) to establish
whether non-uniform firmware-density bytes exist and where.

## Constraints honored

No writes, no CPU_RUN, no bulk SRAM beyond the authorized region, no
reboot, no service changes (llm-inference remains inactive+disabled).
