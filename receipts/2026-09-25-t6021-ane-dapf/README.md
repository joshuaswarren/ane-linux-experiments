# T6021 ANE DAPF: dart-ane0 windows that nothing programs on Linux (2026-09-25)

The J414cAP ADT gives dart-ane0 a DAPF at reg[3] (PA 0x285804000, instance
name "DAPFLLT") and a `dapf-instance-0` property with five windows
(`adt-dart-ane0.txt`, from the 2026-09-18 ADT dump):

| # | start | end | r0 (r0h<<4 or r0l) | r20 |
|---|---|---|---|---|
| 0 | 0x28e084000 | 0x28e084033 | 0x31 | 1 |
| 1 | 0x28e080260 | 0x28e080263 | 0x31 | 1 |
| 2 | 0x38545c000 | 0x38545c003 | 0x31 | 1 |
| 3 | 0x406468000 | 0x406468003 | 0x31 | 1 |
| 4 | 0x228545c000 | 0x228545c003 | 0x31 | 1 |

Window 0 is the ANE pmgr ps block (ane_sys_mpm@4000 through set4@4030).
The DAPF filters the ANE's physical (bypass-stream) MMIO accesses.

Who programs it:
- macOS: XNU applies `dapf-instance-0` for T8110 DARTs.
- m1n1: `dapf_init_all` covers only dart-aop, dart-mtp, dart-pmp and
  dart-isp/isp0 (`m1n1-dapf-entries.txt`). The M2 43ec boot log shows
  "dapf: Initialized /arm-io/dart-aop, dart-mtp, dart-isp0" and nothing for
  dart-ane0. m1n1 applies the ANE DAPF (as part of its static ANE tunables)
  only on T8103, where `t8103_ane_dapf_entry` at 0x26b804000 opens the
  analogous windows (ANE ps 0x23b70c000-33, 0x2b45c000-03).
- Static XNU tables: none for T6020/T6021 in the 13.5 or 27.0 kernelcache
  (receipt 2026-09-25-ane-tunables-static, ane-linux-experiments 0865be7).

So under Linux on T6021, the ANE firmware's path to its own power-state
registers stays in the reset DAPF state. [INFERENCE] That fits firmware
that runs after release but never reaches READY.

Test leg: omarchy-ane agent/t6021-leg-baseline e8411ac adds `fw_start_dapf`
(default off). Before CPU release it writes the five entries in m1n1
`dapf_init_t8110a` register order (r4, start, end, r0, r20), and it logs
each entry before and after, plus the first unused slot. Main's leg 1 is
mpm_off + venc_gates=0 + dapf + dart_single_stream (mbox bit 19 excluded).
Not yet run on hardware: the M2 is waiting for a cold reset.
