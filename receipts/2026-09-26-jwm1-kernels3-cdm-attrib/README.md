# T8103 CDM barrier-field attribution: the ~25 us in-CS dispatch floor is NOT the barrier fields (cross-chip divergence from jw16)

Owner: Jwm1Kernels3, 2026-09-26. Instrument: extended chain-dep-bench on
jwm1 (T8103/G13G), experiment driver =
mesa-1 `hk/dispatch-attrib` (`77e122b1798`, the designedusccdmbarrier
perftest knob; jwm1-side cherry-pick of ccad76a6160), built as an ISOLATED
ICD (/var/tmp/dispatch-icd.json, env-selected only, system driver
untouched). Camera-pause honored.

## Reconciliation of the dispatch-cost numbers (Main's ask)

- `93.8 us` fold/fold_proj/control per-slot attributions (958783d9) were
  TIMESTAMP-POLLUTED (~54 us/kernel; real ~40 us).
- The true in-CS dependent-dispatch floor on T8103 is **~25 us** (my
  isolation: grid-20 dependent dispatch ~25 us GPU span; matches the jw16
  full-sink 25.11 us/launch attribution — same number, and as now proven,
  NOT the same mechanism).
- CS-boundary ~128 us is a separate cost (batched-submit semaphore
  resolution), untouched by any of this.

## Result (T8103, in-CS dependent floor, cs1_c_grid20_nots wall med)

| arm | cs1_barrier | cs1_c floor | cs3_1submit |
|---|---:|---:|---:|
| installed driver, full sink | 156.4 / 187.5 | 245.4 / 256.8 | 437.4 / 422.9 |
| experiment build, full sink | 190.7 | 260.2 | 449.2 |
| experiment, DESIGNEDUSC {4,5,6,8}+usc | 188.7 / 189.4 | 269.2 / 257.1 | 442.2 / 409.1 |
| experiment, USC-INVAL-ONLY | 175.3 | 254.2 | 379.8 |
| experiment, NO barrier at all | 175.5 | 265.5 | 422.3 |

**Dropping the ENTIRE barrier sink changes nothing on T8103** (265.5 vs
245.4-260.2 — within run drift), while on jw16 the same knobs moved
25.11 -> 9.34 -> 4.72 us/launch. Cross-chip divergence is real:

- jw16/T6001: the 25 us/launch IS the CDM barrier field block
  (unk_0..unk_19 PBE/texture maintenance = 15.8 us + USC inval 4.6 us) —
  trimmable, and the designed-set trim held digests 48/48 there.
- jwm1/T8103: the ~25 us in-CS dependent-dispatch floor is per-launch
  FIRMWARE PACKET COST, insensitive to every barrier-field mask including
  "none". No driver-side field or emission change can remove it.

## Consequence

The T8103 dispatch floor is not addressable by any barrier-field runtime
change (the jw16 trim does NOT transfer). The honest remaining routes for
M1 dispatch cost: (a) dispatch-COUNT reduction at the runtime level
(mlx-omarchy MULTI grouping — the 4-weight QMM grouping already landed;
further merged-dispatch work is runtime, not driver), (b) firmware path
(Main-gated, needs approval, out of driver scope), or (c) accept the floor
as chip behavior. The TDT trio absorption falsification (companion receipt
d54bdba4) is consistent: absorbing work into neighbors beats paying the
floor, but the prologue redundancy overshoots.

## Hygiene

Experiment driver ran as an isolated ICD (env-selected per-process only);
system driver untouched; camera-pause flag honored; /tmp instruments
redeployed under /var/tmp after the M2-window reboot wiped the tmpfs.
