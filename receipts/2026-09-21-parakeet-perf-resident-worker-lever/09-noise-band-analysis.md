# 09 — CPU-side analysis: empirical noise band from today's paired passes

**Lane:** `ParakeetPerformance`. CPU-only analysis of existing receipts;
no device use (EncoderHardwareContinuation holds m1-test-host until their RELEASE).

## Same-binary paired-pass drift observed today (all gates-green runs)

| experiment | pair | same binary? | delta (ms) |
|---|---|---|---:|
| BCBC-073623 | B1 vs B2 | yes (`f039e5fc`) | −81.053 |
| BCBC-073623 | C1 vs C2 | yes (`afd612c4`) | +56.047 |
| basheval-074525 | R1 vs R4 | yes (base runner) | −32.883 |
| basheval-074525 | R2 vs R3 | yes (lever runner) | −0.947 |

Empirical |drift|: {81.1, 56.0, 32.9, 0.9} → median **44.5 ms**,
max **81.1 ms**.

## Finding: the inherited 3.7 % / 190 ms band is too loose for paired-interleaved designs

The 190 ms band was inherited from the parent's 3.7 %-of-stage figure for
unpaired run-to-run spread. Today's counterbalanced designs measure a much
tighter quantity — same-binary drift between adjacent passes — whose
observed maximum is 81 ms. Under a conservative paired band of
**~120 ms** (max observed drift × 1.5 safety):

- flush lever (BCBC): +68.9 ms → still NEUTRAL (correctly so; sign flipped
  vs single-shot, effect smaller than same-binary drift of −81/+56 ms).
- **batch-eval lever: −137.2 ms → would cross the paired band as a real
  win.** Consistent sign in all 4 base-vs-lever comparisons, lever-pass
  variance 0.95 ms, mechanism plausible (removes up to 144 redundant
  graph-walk+sync points per pass of a segment measured at 2,209 ms/pass).

## Recommendation (methodological, for future experiments in this lane)

1. Pre-register the decision band from **same-binary paired drift**
   observed in the same session (or max(2× median drift, 100 ms)),
   not from stage-relative percentage spread.
2. Minimum 2+2 counterbalanced passes; report per-pass medians AND
   same-binary drift alongside the lever delta.
3. A lever that lands between the paired band and the legacy band gets a
   confirmation replication before any land/no-land decision — chasing it
   by re-running until significance is forbidden (that is cherry-picking).

## Disposition of the batch-eval lever under the corrected band

Main's ruling on the experiment was made under the pre-registered 190 ms
band → NEUTRAL, wrapper retained as bench artifact, not landed. This
analysis does NOT retroactively change that disposition: the honest
statement is "NEUTRAL under the registered rule; would be a win under a
paired-drift rule; one confirmation replication (2 passes, ~90 s device)
would decide it definitively." The decision is Main's; the harness
(`basheval_ab_run.sh`) is ready and the marginal device cost is ~90 s
inside Encoder's next idle window.
