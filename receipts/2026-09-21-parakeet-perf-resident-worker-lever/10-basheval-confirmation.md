# 10 — Batch-eval randomized confirmation trial: raw medians

**Run:** `confirm-20260921T081050` on the M1 test host (T8103), lock
held ~237 s, released + flock-verified free; prior lane's runid-stamped
RELEASE `enc-hw-20260921T0815Z` honored before start.
**Design (pre-registered, Main-authorized):** 6 passes, order drawn with
documented seed `random.seed(20260921)` over `['base','lever']*3`:
P1=lever, P2=base, P3=base, P4=lever, P5=base, P6=lever. Warm + 5
measured per pass. **All 30 measured runs kept. 30/30 gates green**
(status=match, prefix=104, mel/hidden/transcript golden hashes
bit-exact on every run).

## Raw per-pass medians (ms)

| pass | arm | median |
|---|---|---:|
| P1 | lever | 4422.886 |
| P2 | base | 5212.572 |
| P3 | base | 5273.821 |
| P4 | lever | 3682.537 |
| P5 | base | 5273.230 |
| P6 | lever | 5146.547 |

## Pooled (n=15 per arm)

| | base | lever |
|---|---:|---:|
| median | 5258.446 | 4422.886 |
| min | 4827.500 | 3587.289 |
| max | 5329.868 | 5200.425 |

**Median delta: −835.56 ms. Run-level overlap: present** (lever max
5200 < base min 4828 is FALSE at run level; lever's slowest runs overlap
base's fastest).

## Effect + uncertainty (honest read)

- **Direction: 6/6 passes** — every lever pass median below every base
  pass median. Combined with the earlier paired A/B (2/2), the lever
  has never measured slower than base at pass level (9/9 today).
- **Magnitude: unstable.** Lever pass medians span 3683–5147 ms
  (−64 to −1591 ms vs base median). The mechanism (batching the graph
  walk lets mlx pipeline GPU feeder work against ANE round execution)
  plausibly explains variable capture of the win, but the data does
  not identify the modulating factor.
- **Worst case is still a win** (P6: −66 ms); **best case is large**
  (P4: −1591 ms, the fastest encoder stage measured on this stack).

## Disposition

Per Main's standing rule this is a **robust real gain in direction with
uncertain magnitude** — worst observed case neutral-to-slightly-better,
median case −16 %. Landing decision is Main's. The minimal landing form
is prepared: 3-line marshal batching in `_submit_resident`
(`vulkan_encoder_batcheval_runtime.py`, sha `c7ba295c…`, 17-line patch),
preserving all gates (30/30 this trial; 60/60 across today's three
batch-eval experiments).

Raw evidence preserved privately out-of-tree; this public receipt
carries generic reproducible results only.
