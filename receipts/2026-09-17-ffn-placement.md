# FFN linear-island placement (F family): pin bumped to a8392e6, both-host E2E matrix — NET LOSS, default stays ABC
# 2026-09-17 (jwm1 T8103 + jw16 T6001)

## Verdict

The FFN decomposition (mm1 + mm2 linear islands, receipts/2026-09-17-ffn-mm2-plane.md)
is wired into the certified linear placement path and is **numerically perfect
everywhere it runs** — but it is a **large performance NET LOSS on both hosts and
in both submission modes**. Placement stays **opt-in via `MLX_OMARCHY_PLACED`**
(and `--islands`); the default remains **ABC**.

    resident-batch, total_pipeline_ms (ABC -> ABCF):
      jwm1: 10,187.8 -> 17,670.8   (+7,483.0 ms)
      jw16:  6,138.9 -> 14,046.8   (+7,907.9 ms)
    launch, total_pipeline_ms (ABC -> ABCF):
      jwm1: 12,966.9 -> 24,407.8  (+11,440.9 ms)
      jw16:  8,036.9 -> 18,522.0  (+10,485.1 ms)

Why the predicted ~1 s win did not materialize: the "~1.75 s FFN GPU bucket" is
the *fused* linear+silu coopmat/chain bucket. Removing the FFN matmuls from the
GPU does not remove that bucket proportionally — the chain fusion is undone
(the ANE emits pre-silu, so the silu must execute as its own GPU op again), the
mm1 islands re-stream 8.4 MB of weights per layer per round through host
staging, and the submit marginal measured at ~13–14 ms/island resident. 96
islands × ~13 ms ≈ 1.25 s added ANE time, plus the returned silu GPU work and
per-submit host overhead, against a much smaller realized GPU saving
(`gpu_ops` drops only 1206 → 1158, because placed linears and unfused silus
trade almost one-for-one).

## What landed

- mil-hwx-compiler `ffn-mm2-plane` @ `a8392e6` pushed and released:
  https://github.com/joshuaswarren/mil-hwx-compiler/releases/tag/a8392e6-ffn-mm2-plane
  (archive sha256 21192f23c3f365ceb0a8fe7737b31b404ca9b1feda3ab59ef1f167428b28874d).
- mlx-omarchy branch `agent/ane-ffn-placement` (pushed, f0711039 tip, cut from
  origin/main @ 8edcecfb; `git merge-base --is-ancestor 63c1d3cf HEAD` FAILS):
  - `ane-compiler.lock` bumped to `a8392e6961522455e18c4869e9831bbda0353c12`.
  - overlay/tools/coreml/vulkan_encoder.py: additive F hunks on main's
    certified runner bytes — FFN linear registration in `_index_islands`
    (weight-name regex `encoder_layers_N_feed_forward{m}_linear{h}_weight…`,
    output-shape assert, bundle-dir gated), `execute` dispatch branch for
    `"F"`, `_run_island_ffn`, resident bundle-set extension (O/F placed sets
    extend `AneIsland.resident_bundles`), `--islands` accepts `ABCOF`.
  - Chain-fusion interaction: for a placed FFN linear the runner discards the
    planned linear+bias→silu fold (`silu_done.discard`) because the ANE island
    emits the PRE-silu linear result; the silu statement executes on the GPU.
    First ABCF attempt without this failed `unresolved tensor
    'input_25_cast_fp16'` exactly as the fusion predicts.

## Mint + device gate (both hosts, before any E2E)

Pin gates re-run fresh at the pinned binary on jw16 at lane start:
`test_h13_encoding` OK, `test_h13_anec` exit 0, byte-parity 874/874 PASS.

96 islands = 24 layers × 2 feed-forward modules × {linear1 = mm1
(375,1024,4096), linear2 = mm2 (375,4096,1024)}. NOTE: the ticket predicted 48
bundles (2 per layer); the encoder MIL actually carries TWO feed-forward
modules per layer (feed_forward1 + feed_forward2, distinct weight blobs at
distinct offsets), so the full FFN family — the one that owns the 1.75 s
bucket — is 96 islands. Bundle names: `island-ffn{module}{half}-L{layer:02d}`.

Minted on jw16 from `~/src/mil-hwx-compiler/build/mil-hwxc` (ffn-mm2-plane
build) with real per-layer dequantized weights + per-site bias consts read
from the encoder source; wrapped as schema-4 bundles by the certified
`h13_v2_to_schema4.py` adapter (branch bytes, incl. the f1539d54
declared==derived channel check). Identical bundle bytes shipped to both hosts.

Device gate (`ffn_lane.py gate`, libane-strict-fill, real per-layer weights,
fp32 refs, rngs 11/33/57, budget 0.05):

    jw16: gate PASS, 96/96 bundles, worst rel_l2 0.0002086
    jwm1: gate PASS, 96/96 bundles, worst rel_l2 0.0002086
    (evidence: 2026-09-17-ffn-placement-{jw16,jwm1}-gate.json)

Per-bundle rel_l2 sits at the same fp16-noise floor (0.000207–0.000209) the
o-proj family measured — the mm1 256-plane permutation and mm2 8/8 column
split are correct on real encoder weights on both devices.

## E2E matrix (full JSON: 2026-09-17-ffn-placement-{jw16,jwm1}-matrix.json)

Gates, nothing relaxed: status=match, matching_prefix 104/104, transcript
`db501a8c…` EXACT (sha256 db501a8c080380ea…), bounds vs the macOS golden PASS,
cpu_tensor_events 0, 0 timeouts — in every arm on both hosts. ABC baseline
reproduces pin hidden `38c73261…` byte-exact on both hosts. The F substitution
is deterministic and cross-host identical: ABCF hidden `91b0e28d…` and ABCFO
hidden `7a6d9adf…` are byte-identical on jwm1 and jw16.

    arm            | host  | subs | gpu_ops | enc_wall_ms | ane_exec_ms | total_ms
    ---------------+-------+------+---------+-------------+-------------+----------
    ABC  launch   | jwm1  |  72  |  1206   |     9524.0  |    4403.9   |  12966.9
    ABCF launch   | jwm1  |  168 |  1158   |    21041.3  |   15887.4   |  24407.8
    ABCFO launch  | jwm1  |  192 |  1134   |    22186.4  |   16974.0   |  25554.3
    ABC  resident | jwm1  |   1  |  1206   |     6818.4  |    2431.0   |  10187.8
    ABCF resident | jwm1  |   1  |  1158   |    14271.0  |    3754.0   |  17670.8
    ABCFO resident| jwm1  |   1  |  1134   |    14707.6  |    3745.4   |  18090.3
    ABC  launch   | jw16  |  72  |  1206   |     6688.9  |    3290.7   |   8036.9
    ABCF launch   | jw16  |  168 |  1158   |    17170.1  |   13196.7   |  18522.0
    ABCFO launch  | jw16  |  192 |  1134   |    18133.6  |   14114.8   |  19526.1
    ABC  resident | jw16  |   1  |  1206   |     4769.2  |    2358.4   |   6138.9
    ABCF resident | jw16  |   1  |  1158   |    12734.4  |    3616.1   |  14046.8
    ABCFO resident| jw16  |   1  |  1134   |    13027.3  |    3585.3   |  14400.6

Submission counts land exactly on the family arithmetic (72 = 3 islands × 24
layers; +96 F islands; +24 O islands). `ane_submissions = 1` in resident mode
is one batch submit; the 96 FFN rounds ride inside it.

Marginal per FFN island (resident, ABCF − ABC, ane_exec_ms / 96): jwm1
13.8 ms, jw16 13.1 ms — consistent with the o-proj-derived ~16 ms/island
estimate. O placement on top of F costs a further ~250–420 ms resident.
The o-proj family alone (ABCO vs ABC, from this same matrix) remains a loss
too, matching its earlier certification numbers.

## Disposition

- **ABCF/ABCFO: keep opt-in, do NOT default.** The decomposition question
  ("does FFN compute correctly on the ANE") is now settled YES with
  device evidence on both hosts; the placement question is settled NO with
  numbers on both hosts. The encoder default stays `ABC`.
- What would have to change for F to pay: worker-side FFN chaining (mm1 →
  silu → mm2 fused programs so the 8.4 MB mm1 weights stop re-streaming per
  round and the silu GPU round-trip disappears), or a resident
  constant-input/cached-read path that removes the ~13 ms/island staging
  share (AneRoundtripLevers lever 1). Neither exists today.

## Stack under test (receipted deployed artifacts, unchanged)

- Worker: launch d2b461fc… (derive+fill), resident cc1caa6e (r4-wheelx,
  batch grammar + positional fill); libane strict-fill 04a17653 both.
- Runner: branch overlay vulkan_encoder.py (main@4c0adbde bytes + additive O
  hunks + additive F hunks), sha 43d5f3cf… + silu-unmark fix.
- jw16 llm-inference.service stopped for device work, restarted, confirmed
  active, lock inode 12 held by the service again. jwm1 lock free throughout,
  flock -w 900, never stolen or unlinked.
- Lane scripts: jw16/jwm1 `/tmp/ffn-lane/` (ffn_lane.py, e2e scripts);
  mint+gate tool carried in `ane-linux-experiments/.local/ffn_lane.py`.

## Files

- ane-linux-experiments/receipts/2026-09-17-ffn-placement.md (this file)
- 2026-09-17-ffn-placement-{jw16,jwm1}-matrix.json, -{jw16,jwm1}-gate.json
- mlx-omarchy branch agent/ane-ffn-placement (pushed): lock bump + F hunks +
  docs/ane-encoder-placement.md
