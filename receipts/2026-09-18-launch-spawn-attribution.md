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
