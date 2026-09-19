# H14/W8 — write-grant live test: m1n1 static tunables complete on t6021 with NO abort (2026-09-19)

Verdict: **APERTURE UNLOCKED (first host MMIO write into the ANE control
aperture on jw14m2 that did not SError/reset).** All of m1n1's
`apply_static_tunables()` writes, led by `base+0x0 <- 0x10`, plus a SCRATCH
(GPIO0 `+0x1840048`) write, completed from `/dev/mem` userland under
netconsole pinning. No SError, no reset; same boot before and after
(uptime-s `2026-09-19 12:48:23`, run at t=1294 s in dmesg).

## Execution

- Script: `h14_write_grant_test.py` (repo root, deployed to
  `jw14m2:/tmp/h14_write_grant_test.py`), run `sudo`, `timeout -k 10 150`.
- Every address logged to `/dev/kmsg` (netconsole) BEFORE the access;
  47 lines captured by the fleet receiver (`w8-netconsole.log`), identical
  to the on-box tee (`w8-run.out`, sha256
  `bd6d9d2833b6b16733cc09402e3e37b2747ba10dae56aad2a6541db0ef3649f0`).
- Precondition state: RVBAR `0x285050000` = `0x1` (bit0 set, selene
  released); all eight ps words already `0x3ff` (raised earlier this boot) —
  ps-raise step verified as already-raised, not re-written.

## Results (12 m1n1 tunable writes, exact order)

| i | offset | written | readback | match |
| -- | -- | -- | -- | -- |
| 0 | +0x0 | 0x10 | 0x10 | yes |
| 1 | +0x38 | 0x50020 | 0x20 | no (bits 17+ read 0) |
| 2 | +0x3c | 0xa0030 | 0xa0030 | yes |
| 3 | +0x400 | 0x40010001 | 0x40010001 | yes |
| 4 | +0x600 | 0x1ffffff | 0x0 | no |
| 5 | +0x738 (PMGR1) | 0x200020 | 0x0 | no |
| 6 | +0x798 (PMGR2) | 0x100030 | 0x0 | no |
| 7 | +0x7f8 (PMGR3) | 0x100000a | 0x0 | no |
| 8 | +0x900 | 0x101 | 0x0 | no |
| 9 | +0x410 | 0x1100 | 0x1100 | yes |
| 10 | +0x420 | 0x1100 | 0x1100 | yes |
| 11 | +0x430 | 0x1100 | 0x1100 | yes |

SCRATCH probe `0x285840048` (GPIO0): read `0x0`, wrote the readback value,
read back `0x0` — write transaction accepted, no abort.

## Interpretation (bounds of the claim)

1. **G2 proven at the transaction level.** The fabric accepted every host
   write, including the hypothesized `+0x0 <- 0x10` grant write, where the
   W4-fix/W5/W6 kernel-driver writes SError'd with `0xbe000000`. The write
   wall is gone in this boot's state.
2. **Confounds recorded, not resolved:** (a) the ps chain was already fully
   raised this boot, so the delta vs the W5/W6 abort boots includes boot
   state beyond the tunables; (b) SCRATCH was written with `0x0`, which
   cannot be distinguished from "accepted but not latched" by readback —
   the abort-fires-on-write-transaction argument still makes the pass valid,
   but a nonzero-write probe is the cheap follow-up; (c) tunables
   +0x600/+0x7xx/+0x900 read back zero — on t6021 those t8103 words are
   write-only or absent (consistent with the 09-18 finding that the
   t8103-derived sub-map does not transfer wholesale).
3. Next (per W7 §4): re-run the W6 EP0 HELLO behind this granted aperture,
   and add a nonzero SCRATCH/GPIO write probe.
