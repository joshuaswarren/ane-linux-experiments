# m1n1 pmgr cleanup does not gate ANE — 2026-09-24

Source: `.work/m1n1` at 4184923. The live proxy banner printed
`PROXY60 4184923`. Linux chosen stage2 is `v1.6.1-pdtrace`.
Stage1 chosen is `v1.6.1-dirty`. ESP boot.bin sha is
`43ec6090516a2fcf38252ccd90394383e1a23df830463fbfe2815e4e072dea86`,
not stock `a3f533b9`.

## Cleanup

`pmgr_init` (`src/pmgr.c`) prints "Cleaning up device states..." and
then only enables parents of devices whose own TARGET is already
active or AUTO_ENABLE. It does not power-gate. It is called from
`m1n1_main` unless `BRINGUP`, so it runs on the normal Linux path
and on the proxy path.

`tunables_apply_static` does power-gate after applying tunables, but
the ANE path is T8103 only. T6021 falls through `default` and is not
touched. That call is in `kboot_boot`, after the proxy wait.

## Guest log

`/tmp/m2hv/run-atcrt.log` has no kext error string. The only error
lines are m1n1's "Error getting cpu-uttdbg-reg property" and the
SerialException at disconnect. `error-handler[2]` is the HV's ADT
name for the target address `0x28e0802e0`. The PC was
`0xfffffe0014eab908`.

## Decision

Do not build a stage2 that excludes ANE from this cleanup. The
cleanup is not the gate.
