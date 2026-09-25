# T6001 ANE Start-Path Capture — jw16 (M1 Max, macOS 26.6.2)

Campaign: capture the T6001 macOS ANE firmware START PATH (every host
write-class event to ANE engine, DART, pmgr, and firmware memory from first
CoreML ANE app use through the firmware's first message), to name the missing
host write that the M2 firmware boot needs (the M2 fw parks on a flag word
only the host sets).

## Capture grade achieved (this run)

SIP was ENABLED on the macOS side and recoveryOS is not remotely reachable
(Apple Silicon 1TR: no sshd, no NVRAM one-shot; verified against Apple
security docs). dtrace fbt on `AppleH11ANEInterface` (the ANE kext, loaded at
boot as index 49) is therefore BLOCKED pending a human/KVM `csrutil disable`
in 1TR. This run therefore captured the reachable grade:

- Live unified `log stream` (debug level) from BEFORE first ANE use, filtered
  to kernel ANE/H11/dart-ane lines + aned + ANE-named processes.
- Full reference workload `~/mac-reference-bundle/run-core.sh`
  (cpu/ane/all arms; the ANE arm is the first ANE use of the boot).
- `ioreg -l` snapshots before/after the workload.
- `powermetrics --samplers ane_power` (run inside run-core.sh, per arm).
- Full log-store sweep of the whole boot as belt-and-braces.

## Known T6001 hardware map (from Linux ADT/DT, same silicon)

- ANE platform node: `ane@284000000` (`apple,t6000-ane`), engine window reg
  `0x285c04000 + 0x24000`; full aperture `0x284000000..`.
- ANE DARTs (3): `0x285800000`, `0x285810000`, `0x285820000` (each +0x4000).
- pmgr: `0x28e080000`; ANE power domains `ps_ane_base` @+0xc008,
  `ps_ane_set0..5` @+0xc000.., `ane_cpu_pd` @+0x2c8 region.
- Engine-internal fw-CPU start registers (M2-lane register map):
  `ASC_IO_RVBAR` = engine+0x1050000, `ASC_EDPRCR` = engine+0x1010310,
  PMGR1/2/3 = engine+0x738/0x798/0x7f8; TaskManager at engine+0x1c24000,
  TaskQueue at engine+0x1c25000.

## M2 bare-metal reference start sequence (jw M2 lane, working on M2)

1. pmgr enable `/arm-io/ane` + `/arm-io/dart-ane` (ADT power enable).
2. Static tunables — 12 engine writes: `0x0←0x10, 0x38←0x50020, 0x3c←0xa0030,
   0x400←0x40010001, 0x600←0x1ffffff, 0x738←0x200020, 0x798←0x100030,
   0x7f8←0x100000a, 0x900←0x101, 0x410/0x420/0x430←0x1100`.
3. Power domains: `ps_base+0x0..0x30 step 8 ← 0x300` (down), then `← 0xf`
   (up); TaskManager reset (`TQ_EN←0x3000`, queue priorities, IRQ enables).
4. DART init: iova range, base TTBR map, **TTBR0 of dart1 and dart2 copied
   from dart0** ("DMA fails w/o" — the 3-DART sync).
5. Task descriptors mapped via DART; task queue enqueue (BARs, REQ_ADDR1,
   REQ_NID1) and execution doorbell (`TM.REQ_ADDR/REQ_INFO/REQ_PUSH`).

The M2 firmware parks on a flag word that only a host write clears; the macOS
kext performs at least one write the Linux/M2-bare-metal sequence lacks.

## macOS capture results (this run)

(TBD — filled from run data.)

## Flag-word write

(TBD.)

## Raw artifacts

(TBD — paths.)
