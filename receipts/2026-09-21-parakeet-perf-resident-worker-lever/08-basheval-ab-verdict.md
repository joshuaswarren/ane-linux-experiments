# 08 — Batch-eval lever: paired interleaved A/B (formally NEUTRAL, strong consistent structure)

**Lane:** `ParakeetPerformance`, branch `agent/parakeet-perf-worker-lever`.
**Run:** `basheval-20260921T074525` on jwm1, lock inode 27 held ~166 s,
released + flock-verified free 12:49:14Z, runid-stamped RELEASE to
EncoderHardwareContinuation (their logical_and dispatches unblocked).
**Order:** R1-base → R2-lever → R3-lever → R4-base (interleaved,
counterbalanced). Warm + 5 measured per pass, **all 20 measured runs
kept**, 20/20 gates green (status=match, prefix=104, mel/hidden/
transcript golden hashes bit-exact every run).

## The lever

One batched `mx.eval(*inputs)` per ANE round instead of one `mx.eval`
per input tensor (4 per island-A round, 2 per island-C round → up to
192 separate graph-walk+sync points per pass reduced to 48). Pure
encoder-runner overlay (`vulkan_encoder_basheval_wrapper.py`); no mlx
common changes, no worker binary change. GPUHardwareContinuation
confirmed their in-flight backend work (kBatchNodeBudget 256→512,
Mesa-only) does not touch the async-eval/sync path, so this A/B is
clean against their lane.

## Result

| pass | runner | encoder_ane median | gates |
|---|---|---:|:-:|
| R1 | base | 5257.890 ms | 5/5 ✅ |
| R2 | **lever** | 5112.205 ms | 5/5 ✅ |
| R3 | **lever** | 5111.258 ms | 5/5 ✅ |
| R4 | base | 5225.007 ms | 5/5 ✅ |

| paired | value |
|---|---:|
| **lever delta (pooled)** | **−137.200 ms (−2.6 %)** |
| base pooled median | 5248.931 ms |
| lever pooled median | 5111.732 ms |
| R1-vs-R4 drift (same binary) | −32.883 ms |
| R2-vs-R3 drift (same binary) | **−0.947 ms** |

## Verdict — NEUTRAL by the pre-registered rule; structure reported

**|−137.2| < 190 ms noise band → formally NEUTRAL** (Main's rule:
"if effect indistinguishable label neutral and retain bench receipt
not performance claim"). No performance claim is made.

However, the structure differs materially from the flush lever (which
flipped sign under counterbalancing):

- The two lever passes agree within **0.95 ms** — near-zero variance.
- Both base passes are slower than both lever passes; the sign is
  consistent in all four pairwise base-vs-lever comparisons.
- Same-binary drift within the run (−33 ms base) is 4× smaller than
  the effect.
- Mechanism is plausible: marshal_eval_ns measured 46.03 ms/round
  (2209 ms/pass) is ~97 % mx.eval readiness wait; batching removes
  up to 144 redundant graph-walk+sync points per pass.

This is below the single-run noise band but directionally stable.
Classified NEUTRAL per rule; the wrapper stays a **bench artifact on
this branch, not landed**, same disposition as the flush lever. The
measurement is forwarded to GPUHardwareContinuation: if their
kBatchNodeBudget work shrinks inter-submission gaps, the mx.eval
readiness share may shrink independently, and any future re-baseline
should re-run this exact harness (`basheval_ab_run.sh`) before
considering the lever for landing.

## Disposition

- `vulkan_encoder_basheval_wrapper.py` + `basheval_ab_run.sh` committed
  as bench artifacts (reusable, env-gated `LEVER_BATCH_EVAL=0` disables).
- Not landed into `encwall-v071/base` or any mlx/omarchy-ane tree.
- No performance claim; no criterion weakened anywhere (104/104 +
  three golden hashes bit-exact on all 40 measured runs today across
  both experiments).

## Next bottleneck (forwarded to GPU owner)

1. GPU-feeder GAP 1,628 ms (30.9 %) — GPU compute, their lane; my
   per-segment decomposition + e2e gpu_counter_delta (224 commits with
   work, 2981 vk_compute_dispatches per pass) is theirs to attribute.
2. mx.eval readiness 2,034 ms (41.9 %) — partially attacked by this
   lever (NEUTRAL-band gain); remainder is genuinely serial GPU
   execution of the per-layer feeder chain.
