# Phase 0 EXECUTED RESULTS — bounded read-only probe (2026-09-26, post dca3eacd review)

Scope executed exactly per phase0-plan.md as narrowed by Main's review:
PS gate first, then 3 readl (CPU_CONTROL + bootargs ptr/size). NO bulk
SRAM, no writes, no reboot, module loaded once and unloaded
(/var/tmp/pmp-phase0/pmp_phase0.c + .ko on jw16).

## Raw values (dmesg, unmodified)

```
pmp_phase0: PS raw=0x1f0000ff actual=0xf desired=0xf
pmp_phase0: PS gate passed (f/f)
pmp_phase0: CPU_CONTROL raw=0x00000000 cpu_run=0
pmp_phase0: BOOTARGS ptr=0x00078800 size=0x00000234
pmp_phase0: unloaded (read-only probe)
```

## Reading (held to Main's caveats)

- PS f/f: hardware power confirmed beyond the apple,always-on policy
  flag. Gate passed.
- CPU_RUN=0: the PMP CPU is quiesced under Linux, as expected — iBoot
  did not leave it running.
- BOOTARGS ptr=0x78800 size=0x234: NONZERO, and ptr+size (0x78a34) fit
  exactly inside the driver's own 0x80000 map. Leans
  parked-structure-present. Per Main: nonzero does not prove valid
  firmware, and zeros would not have proven absence elsewhere.
- Reg extent reconciled from the live DT before execution: pmp reg[0]
  = 0x28e700000 size 0x100000 (1 MiB, matches the ADT extent — the
  earlier 0x80000-vs-1 MiB discrepancy was the DRIVER's conservative
  map, not a DT conflict); asc reg[1] = 0x28ec00000 size 0x4000.

## Next increment (proposed, not authorized)

One bounded read of the 564-byte bootargs region at PMP+0x78800,
checking for the BDID/DVID/DCAP key tags pmp.rs patches. Still
read-only, same window discipline.
