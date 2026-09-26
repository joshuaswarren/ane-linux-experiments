# jwm1 coopmat-prefetch re-introduction stopped pre-promotion — twice-falsified candidate caught by ownership review

Owner: Jwm1Kernels3, 2026-09-26. Main's live-activity review stopped my
re-port of the parity8 qmm coopmat prefetch before any promotion.

## What happened

I ported `c86b36224` (qmm coopmat prefetch/double-buffer:
`qmm_coopmat.comp` rework + 2x shared-memory budget constexpr) onto current
main as `agent/jwm1-kernels3-coopmat-pf` `fbad793fc`, on the strength of the
scout's "implemented but not yet merged" note and the commit's "same
matrix-step sequence" phrasing. Main interrupted: the parity8/10 stage-2
summary had EXCLUDED coopmat — "gdn/qmm rejected on pin" (35a7d60b).

## Stage-2 verdict (wt-ale-parity10, receipts/2026-09-25-jwm1-parity10-stage2)

| candidate | dump vs base | 1-pass digest | verdict |
|---|---|---|---|
| qmm coopmat prefetch (alone) `c86b36224` | 15/15 bitwise equal | `61b73e28f50edb50` != pin | **rejected** |
| (base `bfe2ddc6d`) | — | `486872c410629f1d` x6 | winner |

And slower: qmm 38.7 vs base 39.2 tok/s decode. Lesson recorded there and
re-verified here: **kernel dumps bitwise-equal does NOT cover the live
model's shape; the interleaved full-model digest screen is the only gate
that predicted the break.**

## Disposition

- Branch `agent/jwm1-kernels3-coopmat-pf` `fbad793fc` stays PUSHED as the
  falsified-artifact record (fleet rule), NOT merged, no wheel built for
  distribution (build unit stopped pre-dist; unit coop-wheel inactive).
- My "bit-exact by construction" commit-message claim was exactly the
  by-name-alone trap Main flagged. The stage-2 evidence outranks it.
- Re-falsification cost: zero device-gate runs wasted (stopped at review).

## Next measured bottleneck (not falsified, evidence-backed)

Prefill-route A/B via EXISTING runtime env knobs on the installed
`7d3f69ff2` wheel — coopmat (default) vs NO_COOPMAT vs NO_QMM_FMA vs
QMM_TILE=0, interleaved 1-pass contracts measuring prefill-512/TTFT. The
jw16-levers2 lever note stands: decode dispatch COUNT (459 -> 405/token,
~2%) and the mesa dispatch floor own the decode gap; prefill-512 remains
0.66x of macOS with no proven code lever yet — the route A/B is the
cheapest unmeasured question.
