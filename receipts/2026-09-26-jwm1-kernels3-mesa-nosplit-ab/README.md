# jwm1 isolated-ICD Mesa A/B: no-split barrier driver vs its own parent — real win, already installed and banked on jwm1; residual floor mapped

Owner: Jwm1Kernels3, 2026-09-26 (directive: Main — isolated ICD A/B under the
device lock, existing chain-dep-bench only, no global Mesa install, bounded
runs, saved exits, restore after).

## Design

- Arm BASE = mesa `7faf04c065c` (`160b7af8aeb~1`): identical tree WITHOUT the
  no-split barrier change. Built on jwm1 in an isolated worktree
  (`/tmp/mesa-base-wt`, meson config mirroring the prior lane's: defaults,
  `-Dglx=disabled`; needed `python-pycparser` via pacman), installed to
  `/tmp/mesa-base-icd`, selected ONLY via `VK_DRIVER_FILES=/tmp/mesa-base.icd.json`.
- Arm NOSPLIT = the installed system driver (`jwm1-barrier-ab` @
  `160b7af8aeb`), default ICD selection.
- Patch equivalence verified: `git diff 160b7af8aeb 41ccf96cc59 --
  src/asahi/vulkan/hk_cmd_buffer.c` is EMPTY — the installed jwm1 commit and
  the T6001 "no-split barrier driver" (`41ccf96cc59`, receipt a77fd4c8) carry
  the SAME patch.
- Instrument: the existing extended chain-dep-bench (/tmp/cdb, mlx-omarchy
  2d3a77b99). 4 interleaved runs (BASE, NOSPLIT, NOSPLIT, BASE) under
  `flock /tmp/m1-gpu.lock`, each `timeout 300`-bounded, exit-coded (all rc=0,
  raw/), driver selection confirmed in each run's meta line.

## Results (wall_med_us, medians of 31; GPU span where available)

| case | base p1 | base p2 | nosplit p1 | nosplit p2 |
|---|---:|---:|---:|---:|
| cs1_barrier (submit floor) | 202.0 | 191.2 | 190.9 | 192.1 |
| cs1_c_grid20_nots (in-CS dep floor) | 279.5 | 296.2 | **256.1** | **270.8** |
| cs1_c GPU span (3-dispatch chain) | 78.50 | — | **74.54** | — |
| cs1_d_grid20_raw | 259.2 | 275.3 | 258.7 | 257.0 |
| cs3_1submit_sema (CS-boundary) | 452.6 | 540.3 | 446.8 | 472.0 |
| cs3_3submit_sema | 453.8 | 547.5 | 449.5 | 458.6 |
| cs3_fencejoin | 607.5 | 654.2 | 560.0 | 598.3 |

## Reading

1. **The no-split change is a real win on T8103 and it is ALREADY the
   installed, pin-verified driver** (release gates 546dbb896: digest
   bit-exact, decode 39.21 tok/s). Consistent across both interleaved
   passes: in-CS dependent chain ~-24 us wall per 3 dispatches (~-8
   us/dispatch), GPU span only -4 us — so most of the win is HOST-side
   (fewer barrier-forced CS chunk splits per command buffer = cheaper
   record/submit), matching the commit's own rationale ("the split only
   added a stream link and a fresh 64 KiB chunk per barrier"). CS-boundary
   hops mildly better; submit floor equal.
2. **Nothing to land on jwm1 — the win is banked.** The T6001 concern
   (2/290 rare digest flips on 41ccf96cc59, receipt a77fd4c8) applies to the
   same patch: on T8103 the identical code has held all three pins across
   the release gates and this window. Race diagnosis before any T6001
   contract qualification remains the T6001 lane's open gate.
3. **Residual floor after no-split (the remaining mesa target): ~21
   us/dispatch in-CS dependent dispatch at 640 threads (270.8 us wall / 3,
   minus ~191 us submit floor -> ~27 us/dispatch wall, ~25 us GPU) and
   ~128 us CS-boundary hop. Next attribution instruments exist as dormant
   mesa-1 branches: hk/dispatch-trace, hk/dispatch-attrib, hk/maxdispatch.**

## Restore / state

Runner self-restored: `/tmp/mesa-base.icd.json` removed after the runs
(status: `phase:restored:OK`); no service ever used the isolated ICD
(selection was per-process env only); system driver untouched; raw payloads
kept at `/tmp/mesa-base-icd` and `/tmp/ab-mesa/` for forensics. Exit codes:
build SETUP/BUILD/INSTALL all rc=0 (mesa-base.status), all 4 bench runs
rc=0 (session.log), probe pass with CHAIN_DEP_DONE.

## Race-diagnosis pointer (for the T6001 qualification gate)

The T6001 flips were "single-record digest flips" under the no-split
driver — with the patch confirmed identical, the suspects are the removed
per-barrier stream links racing a concurrent graphics batch (the commit
guards on "when no graphics batch is open"). Smallest diagnosis: reproduce
the a77fd4c8 battery shape on T6001 with a compute+graphics interleave
generator while digesting; if it reproduces, the fix candidate is a
graphics-batch-open fallback to the old split path rather than a revert.
