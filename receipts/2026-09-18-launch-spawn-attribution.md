# Launch spawn attribution: island B is digest-neutral dead weight; default PLACED=AC ships

2026-09-18, jw16. Controlled launch-mode arms from the d1d9893 accidental
contrast (arms2 `placed=J`, no-A launch 5525 ms vs ABC 10879 ms).

## Setup

- Runner: own worktree copy of the conv-bisect runner family
  (`/tmp/conv-lane/vk_conv.py`, sha256 `dbbd96fb…`) at
  `/var/tmp/jw16-spawn-attrib/vk_conv.py`, plus env-gated per-phase timers
  (`MLX_OMARCHY_LAUNCH_PROFILE=1` → sidecar JSON; single bool check per
  submit when off, no effect on measured arms — ABC re-pinned EXACT with
  profiling on).
- Arms: PLACED ∈ {ABC, BC, AC, AB, ""(pure-GPU)} × {launch, resident-batch}
  × 3 repeats, interleaved order, same window (`flock /tmp/m1-gpu.lock`),
  same bundles-conv/worker/libane/source as the bisect.
- llm-inference stopped before windows, restarted after; /health 200,
  lock inode 12.

## Attribution table (median of 3, ms)

| arm | mode | wall | ane_exec | subs | status | hidden | transcript |
|---|---|---|---|---|---|---|---|
| ABC | launch | 10873 | 2586 | 72 | match | `38c73261` | `db501a8c` |
| ABC | resident | 9049 | 1669 | 1 | match | `38c73261` | `db501a8c` |
| AC | launch | **8835** | 1557 | 48 | **match** | **`38c73261`** | **`db501a8c`** |
| AC | resident | **8033** | 1033 | 1 | **match** | **`38c73261`** | **`db501a8c`** |
| BC | launch | 8986 | 1543 | 48 | match (hidden `47705cad` ≠) | | `db501a8c` |
| AB | launch | 9545 | 2049 | 48 | diverged (`24146f6d`/`075876ef`) | | |
| GPU | launch | 3591 | 0 | 0 | diverged (`e832110d`) | | |

All match rows: emissions 104/104, bounds PASS, 0 timeouts,
0 cpu_tensor_events, mel `5b54f4a9` bit-exact.

ABC per-phase (launch, profile sums over 72 submits):
**eval 6855 ms (63%)** — mx.eval serialization of GPU feeder tensors per
submit; spawn 2587 ms (24%, ~36 ms/submit worker process); write 237;
read 146; convert 51; remainder ~1.0 s GPU-side post-island work.
AC−ABC deltas: eval −594, spawn −1032 (24 × ~43 ms `island-select-8head`
submits), write −145, read −35, convert −19 → wall −2038.
So the accidental 5.3 s "no-A" delta decomposes into: B-family spawn+
marshal ~1.8 s, B-family feeder eval ~0.6 s, and A's own feeder/spawn cost
(the rest); the pure-GPU control bounds total island overhead at ~7.3 s of
the 10.9 s launch wall, dominated by per-submit eval serialization, not
process spawn.

## Finding + shipped cut

Island **B** (`island-select-8head`, 24 submits) is **digest-neutral**:
AC reproduces the certified hidden `38c73261` and transcript `db501a8c`
EXACTLY in 3/3 launch and 3/3 resident runs — the select runs identically
on GPU. Net win: launch −2038 ms (−18.7%), resident −1010 ms (−11.1%).
A is load-bearing (BC hidden diverges `47705cad`); AB diverges both.

Shipped: runner default flipped `ABC` → `AC` (env gate
`MLX_OMARCHY_PLACED` unchanged, `--islands` default aligned) in the
jw16-spawn-attrib worktree runner. Confirmation with NO env set:
launch match 48 subs wall 8777, resident match wall 7982, both
`38c73261`/`db501a8c` EXACT, 104/104, cpu_ev 0. `/tmp/conv-lane/vk_conv.py`
(the shared certified copy) left untouched — flip there is Main's call.
Full E2E default remains ABC elsewhere; the certified ABC numbers above are
the like-for-like baseline.

63c1d3cf ancestry: NOT-ANCESTOR on jw16 mlx-omarchy HEAD `3db3cb9a`
(asserted); no mlx-omarchy push in this work.

Artifacts: `.local/spawn-attrib/{vk_conv.py,attrib_jw16.sh}`,
jw16 `/var/tmp/jw16-spawn-attrib/{arms.jsonl,profile-*.json,arm-*.log}`.

## Landing (Main-directed, same day)

1. mlx-omarchy branch `agent/placed-ac-default` cut from `2da5e052`
   (HEAD of the certified e93500d2 runner bytes worktree), both defaults
   flipped ABC→AC (`MLX_OMARCHY_PLACED` fallback + `--islands`),
   commit `af5394e0`, pushed to origin
   (joshuaswarren/mlx-omarchy). `63c1d3cf` NOT-ANCESTOR asserted on
   `2da5e052` before the push.
2. Certified copy `/tmp/conv-lane/vk_conv.py` flipped the same way;
   backup kept at `/tmp/conv-lane/vk_conv.py.pre-AC-20260918`
   (sha `dbbd96fb…`); verified only the two default strings differ from
   the backup. First flip attempt broke a quote (SyntaxError, zero runs
   executed, no state touched); repaired and diff-verified before any run.
3. Re-baseline on the flipped certified copy, one window, x3 interleaved,
   all 12 arms: status match, 104/104, bounds PASS, 0 timeouts,
   0 cpu_tensor_events, mel `5b54f4a9` bit-exact.

| arm | mode | wall median (ms) | hidden |
|---|---|---|---|
| AC | launch | 8840 | `38c73261` EXACT |
| AC | resident | 7992 | `38c73261` EXACT |
| ACO | launch | 9457 | `ef6afd13` EXACT |
| ACO | resident | 8087 | `ef6afd13` EXACT |

New jw16 conv-lane baselines with B dropped: launch −2033 ms vs the
certified ABC baseline (10873, prior section), resident −1057 ms
(9049); ACO launch −1416 ms vs that ABC baseline. ACO resident per-arch
note: single submit, oproj included, 8087 ms.

llm-inference restarted after the window: ACTIVE, `/health` 200,
lock inode 12.

## Follow-on lane: the 63% eval phase — batch-eval screened, NO-SHIP

Hypothesis: per-input `mx.eval` in the submit loop (island A has 4 inputs,
PV 2 → 6 syncs/layer, 144 total) carries fence overhead; batching to one
`mx.eval(*inputs)` per submit collapses it. Implemented env-gated
(`MLX_OMARCHY_BATCH_EVAL=1`) in the jw16-spawn-attrib worktree runner.

Measurement (AC/ACO × launch/resident × 3, one window, digests and gates
ALL EXACT — `db501a8c`, `38c73261`/`ef6afd13`, `5b54f4a9`, 104/104,
bounds PASS, 0 cpu_tensor_events):

| arm | mode | batch-eval wall median | baseline | delta |
|---|---|---|---|---|
| AC | launch | 8491 | 8840 | **−349** |
| AC | resident | 8538 | 7992 | **+546 WORSE** |
| ACO | launch | 8881 | 9457 | **−576** |
| ACO | resident | 8698 | 8087 | **+611 WORSE** |

Profiled AC launch with batching: eval phase 6048 ms vs 6262 unbatched —
batching removed only 214 ms. Verdict: the per-input evals are already
near-free (most island inputs are shared/precomputed tensors; the cost is
one dominant feeder chunk per submit), so the ~6 s eval phase is genuine
chunked GPU feeder COMPUTE (48 chunks vs the pure-GPU encoder's single
pipelined stream at 3591 ms). Cutting it requires run-ahead/pipelining the
statement interpreter across island submits (overlap next-layer feeder
build+eval with current ANE round) — an architectural change, not a
staging tweak.

DECISION per gate: not green+win in both modes → default stays OFF, no
mlx-omarchy landing, certified copy untouched. Gate code preserved in
`.local/spawn-attrib/vk_conv.py` (`MLX_OMARCHY_BATCH_EVAL`), measured data
in jw16 `/var/tmp/jw16-spawn-attrib/{batcheval.jsonl,profile-be-ac-launch.json}`.
llm-inference ACTIVE, `/health` 200, inode 12 after the window.


