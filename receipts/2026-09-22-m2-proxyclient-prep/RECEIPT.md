# m1n1 proxyclient prep — T6021 ANE ASC (m2-host), 2026-09-22

Lane: M2ProxyclientPrep. Deliverable: the session is wired so the bring-up
runs the moment the USB cable is connected. NO hardware was touched from this
lane (read-only rule respected).

## Artifacts (branch `m2-proxyclient-prep`)

- `scripts/m2-proxyclient/t6021_consts.py` — all addresses + self-validation
- `scripts/m2-proxyclient/ane_bringup.py` — session script, steps (a)–(e)
- `scripts/m2-proxyclient/mock_proxy.py` — stub ASC (happy + negative paths)
- `scripts/m2-proxyclient/RUNBOOK.md` — boot-side setup + 10-minute checklist

## Dry-run receipts (this dir)

- `consts-validation.log` — 18/18 OK against the ADT capture
  (`<capture-dir>/m2-macos-capture-20260921/ane0-dt.txt`) and the hunter
  selftest constants. exit=0.
- `mock-happy-path.log` — full (a)–(e) dry run: ADT dump → power cycle →
  RVBAR write 0x0081010000000001 accepted (readback matches) → DART map at
  DVA 0x10000000000 → RUN → SCRATCH7 READY 0x08042006 on poll 5 → RTKit
  step reached. exit=0.
- `mock-latched-rvbar-negative.log` — with the s23 latched value 0x10000000001
  (write-ignore), the script ABORTS at the RVBAR readback check before
  touching RUN. exit=1. This is exactly the behaviour wanted: no silent park.
- `hunter-selftests.log` — the five ane-hunter selftests still pass on the
  same fixtures.

## Address arithmetic corrections captured during validation

- ASC control block is engine+0x1400000 (CPUCTL 0x285400044, STATUS
  0x285400048) — matches `.work/s22_arm.py` (`CPUCTL, STATUS, RVBAR =
  ANE+0x1400044, ANE+0x1400048, ANE+0x1050000`). The NIGHT-SUMMARY prose
  "0x28540044" dropped a digit.
- RVBAR DVA field = 0x10000000000 (ASC fetch aperture), so
  rvbar_value() = 0x0081_0100_0000_0001 exactly as the night-summary states;
  the latched 0x10000000001 differs only by mode bits 0x0081<<48.
- Sleep note (ANALYSIS, unverified on hardware): mailbox registers under
  m1n1 assumed at ASC_BLOCK+0x8110/0x8830 (m1n1 hw/asc.py layout); step (e)
  is bounded at 10 s and reports the epmap either way.

## Hardware state (read-only hourly arm, 06:27 UTC)

`ssh laptop` → connect timeout (<tailscale-ip>:22); `laptop-ts` does not
resolve; ping unavailable (no cap_net_raw). m2-host unreachable from this
workstation — asleep or lid-closed, expected overnight. No writes attempted,
none pending. Last known state remains the night-close record: up 11 min
post-watchdog, module-absent, STATUS 0x2a, CPUCTL 0x0, RVBAR 0x10000000001,
S7 0x0, ane_cpu 0x1f0003ff.

## Next concrete step (for the lane that picks this up)

Cable in → RUNBOOK 10-minute checklist step by step; tee the run to this
receipt dir. If READY + RTKit completes, the TQ contract on the running
selene is next (`.work/2026-09-21-t6021-host-tm-contract.md`).
