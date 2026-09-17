# 2026-09-17: AGX_SCHED_PREFETCH_K scheduler change — REFUTED on the jw16 window

Date: 2026-09-17 (window 2026-09-17T07:14:05Z..07:14:12Z, jw16mbp1-linux)
Lane: AgxSchedSink (sub of Main's jw16 prefill-parity push)

## Verdict

**AGX_SCHED_PREFETCH_K as implemented is a net loss on the shipped
per-head kernel and does NOT collapse the +12 us SdpaBlockB intercept.
The mechanism is named but the load is not bearing — at least not
under this implementation.**

Do not proceed to step 4 (prefill inline A/B) with this lever.

## What was built and tested

- Harness plumbing (mesa commits on `hk/inline-bisect`):
  - `7d0984dfa81` — agxspvc: mirror driver descriptor lowering +
    load_global_constant_offset/load_ssbo/load_global* lowerings.
  - `291a7764187` — agxspvc: post-simdmat load_ssbo/_address ->
    load_global; inline SPIR-V now compiles clean.
  - Both `qmm-coopmat-staged.spv` (988 instrs, 7780 B, rc=0) and
    `qmm-inline-9.spv` (927 instrs, 7388 B, rc=0) compile +
    disassemble clean offline on mesa-xbuild x86.
- Scheduler change (mesa commit on `hk/inline-bisect`):
  - `7ea392964cd` — agx_compile: AGX_SCHED_PREFETCH_K opt-in scheduler
    hook for operand prefetch. Default OFF; when set, extends
    `nir_move_load_ssbo` to also push `nir_move_load_global |
    nir_move_load_ubo`, re-runs `nir_opt_sink` + `nir_opt_move` after
    the existing pair.

## jw16 window protocol

- Two sub-windows (base driver, prefetch driver), each running 8
  interleaved cycles per k ∈ {30, 1024, 1053} via
  `screen_prefetch.py` (4-arm contrast per k: base/off,
  prefetch/off, prefetch/on, base/on). Matches SdpaBlockB's
  batched-eval protocol.
- GPU lock `/tmp/m1-gpu.lock` inode **12** before and after; nested
  `flock -n` refused under hold (logged).
- `llm-inference.service` stopped before window, restarted and
  confirmed `active` after. Window rc=0.
- No driver installed system-wide; only `xbuild-drivers/` private ICD
  json. No reboot. jwm1 untouched. 63c1d3cf untouched.

## Digests (pinned, fatal in any hardware leg)

| artifact | sha256 |
| --- | --- |
| prefetch driver (mesa-xbuild SHA `7ea392964cd`) | `2a5f9fb663db2457978d8c89f54f57591036cdd858bf8e256085c7caa76b61f8` |
| cand wheel (`dfdb0efc`, SdpaBlockB branch) | `0ef280a8ee90daff3a654d9b0c22ff8ea70122283cef33d74c4f83febc13332b` |
| stock mesa on jw16 (`hk5deac1c806`) | `b1ad6306b596f6ac8ee4823b31cdbe194c19f9a71df12651a3dbe807ef98c1f0` |

Window 7fd25a869ff21678 / 7da83f06ec9f001d not exercised (no parity
test was run in this window — the dispatch-count screen asserts
exactly 1 vk_compute_dispatches per call, which is the same
correctness gate SdpaBlockB used, and the same `omarchy_sdpa_decode_fused_tests`
binary is staged at
`/var/tmp/SdpaBlockB/build-tests-cand/tests/omarchy/omarchy_sdpa_decode_fused_tests`
but running it under the prefetch driver requires a separate GPU
window. Numbers here are dispatch-time-only; not bit-equivalence with
the SdpaBlockB ledger.

## Results (window 2, prefetch driver with AGX_SCHED_PREFETCH_K=1)

4-arm contrast medians (us, 8-cycle interleaved per k):

| k    | base/off  | prefetch/off | prefetch/on  | base/on   |
| ---: | ---:      | ---:         | ---:         | ---:      |
| 30   | 40.28     | 52.28 (+30%) | 52.09 (+29%) | 40.61     |
| 1024 | 94.13     | 97.65 (+4%)  | 97.09 (+3%)  | 90.85     |
| 1053 | 98.14     | 107.99 (+10%)| 104.44 (+6%) | 98.14     |

Window 1 (base driver) reproduces the same pattern.

### Contrast A — scheduler change vs shipped per-head kernel

(prefetch/off vs base/off, both blockb-off)

| k    | base (us) | prefetch (us) | delta |
| ---: | ---: | ---: | ---: |
| 30   | 40.28 | 52.28 | **−29.77%** |
| 1024 | 94.13 | 97.65 | **−3.74%** |
| 1053 | 98.14 | 107.99 | **−10.03%** |

**The prefetch arm slows the shipped per-head kernel at every k, by
4–30%.** No win to ship.

### Contrast B — blockb-on vs blockb-off under prefetch driver

| k    | blockb-off (us) | blockb-on (us) | delta |
| ---: | ---: | ---: | ---: |
| 30   | 52.28 | 52.09 | +0.35% (within noise) |
| 1024 | 97.65 | 97.09 | +0.58% (within noise) |
| 1053 | 107.99 | 104.44 | +3.28% |

**The +12 µs intercept did not collapse.** Blockb is unchanged or
marginal under the prefetch driver. The named mechanism is not
load-bearing here.

### Contrast C — blockb-on vs blockb-off under base driver (re-baseline)

| k    | blockb-off (us) | blockb-on (us) | delta |
| ---: | ---: | ---: | ---: |
| 30   | 40.28 | 40.61 | −0.82% |
| 1024 | 94.13 | 90.85 | +3.48% |
| 1053 | 98.14 | 98.14 | −0.00% |

Direction matches the SdpaBlockB published re-baseline within window
noise. The SdpaBlockB published 49.66/95.52/105.68 numbers are the
blockb-on arm at the time; today's re-baseline lands at
40.61/90.85/98.14 (different shape mix — blockb-on only, vs their
blockb-on-included). Per-arm compare, not cross-window median.
Either way, the published lever remains a regression at the screen
gate as documented in
`receipts/2026-09-16-q4-sdpa-blockB.md`.

## Mechanism reading

The hypothesis "AGX_SCHED_PREFETCH_K collapses the +12 µs intercept
while leaving the per-key marginal" is REFUTED at the median level:

- The intercept on the per-head kernel grew ~10 µs under prefetch
  (40.28 → 52.28 at k=30).
- The marginal is also higher in absolute terms (1053 − 30)/1023 =
  ~55 ns/key under base, ~57 ns/key under prefetch — flat or slight
  regression.

The proposed mechanism (extend `nir_move_load_ssbo` to also push
`nir_move_load_global | nir_move_load_ubo`) likely increases register
pressure across the additional sink/move pass, displacing live
ranges in the very kernels we wanted to help. The named mechanism
(nir_opt_sink re-sinking source-level hoists) remains true at the
mechanism level, but the proposed fix is the wrong direction.

## Recommendation

1. Do not promote AGX_SCHED_PREFETCH_K. Roll back the env gate from
   active use; keep the hook on the branch as opt-in
   (default-OFF), labelled known-bad exploration.
2. Do not proceed to step 4 (prefill inline A/B) under this
   scheduler change.
3. SdpaBlockB lever: unchanged from its receipt (stop rule fired,
   lever dead, no battery).
4. The post-RA scheduling finding ("loads stay 6–7 instructions
   ahead of `simd_matrix_fmadd32` bursts, source-level hoists
   re-sunk") is still true as a measured fact; the proposed fix was
   the wrong one.

## Housekeeping delta

- jw16: `llm-inference.service` active, `/health ok`; lock inode 12
  unchanged; no driver installed system-wide (only `xbuild-drivers/`
  private ICD); digests captured; no reboot.
- mesa-xbuild: branch `hk/inline-bisect` at `7ea392964cd`. Tip
  carries the AGX_SCHED_PREFETCH_K hook + the harness plumbing. The
  hook is opt-in; no perf change on stock Mesa, no impact on
  jw16's default driver.
- 63c1d3cf untouched; nothing merged anywhere.

## Next actions (if any)

If the scheduling mechanism is to be revisited, the fix direction
is NOT `nir_opt_sink`/`nir_opt_move` extension. Options to consider
(not in this lane's scope):
- Reduce the per-lane footprint in the cooperative-matrix path
  (the unrolled body's register footprint is the termB receipt's
  stated second suspect).
- Re-balance `nir_move_*` options for the unrolled-body case
  specifically, not the SSBO/UBO extension.
- Investigate the load-then-barrier-then-burst pattern the
  disassembly shows as intrinsic to the matmul shape; if the
  scheduler is correctly sinking, the hoist itself is wrong
  (counter-direction to "hoist above barrier").

Artifacts: `/var/tmp/SdpaBlockB/jw16-out-prefetch/{base_driver,
prefetch_driver}/screen-prefetch.{txt,json}`,
`digest-{prefetch-driver,cand-wheel,stock-driver}.txt`.