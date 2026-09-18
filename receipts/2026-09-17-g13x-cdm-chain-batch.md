# G13X CDM_BARRIER chain-batching across dependent compute chains — NO-SHIP (2026-09-17)

Lane: MesaCdmAmortize (sub of Main's jw16 parity push). Assignment: elide or
batch the kitchen-sink CDM_BARRIER across dependent compute chains in
command-stream emission (`src/asahi/vulkan`), cs-emission only, bit-set
mid-sets forbidden. Screen digests `7fd25a869ff21678` (short-32) /
`7da83f06ec9f001d` (ctx1024) FIRST on jw16; tok/s vs the post-two-pass
baseline (short 191.4 / ctx1024 149.3 on fb649d8d, 165.3 best two-pass
window).

## Verdict

**NO-SHIP.** The full elision (98.7% of CDM_BARRIERs removed) digest-breaks
with silent corruption (`b1f5584685681a5e` ≠ short pin on jw16). The
conservative variant that keeps a barrier at every launch→launch boundary
holds digests 24/24 but measures exactly neutral (−0.03% short, −1.06%
ctx1024 within-window) — no gain, nothing to ship. The kitchen-sink barrier
is load-bearing launch→launch on G13X for these chains.

## The structural finding (changes the problem statement)

Per-cs submit stats (`AGX_MESA_DEBUG=perf`? no — `ASAHI_MESA_DEBUG=perf`,
`MESA_LOG_LEVEL=warning`; one short leg per driver) show what a decode
token's command stream actually looks like on the fork tip
(`d8d4e1c500b`, jw16, M1 Max G13C):

| quantity (32-token short decode) | value |
| --- | ---: |
| physical CDM control streams | 82 |
| emitted CDM launches | 12,594 (~394/token) |
| cs merged away by `merge_control_streams` | 12,464 |
| CDM_BARRIERs emitted (base driver) | 12,676 (~396/token) |

MLX's per-dispatch `vkCmdPipelineBarrier2` hits honeykrisp's "big hammer"
(`hk_CmdPipelineBarrier2` ends the compute batch), so nearly every dispatch
lands in its own control stream; the merge optimizer then rejoins them into
~82 physical streams — and every rejoined seam carries a kitchen-sink
CDB_BARRIER, because in base every launch is followed by one. That is ~2×
the "201 dispatches/token" premise (launches, not API dispatches) and it
means **per-launch barriers live at merge seams, not inside long
within-cs chains**. Batching strictly inside a cs therefore has nothing to
batch (most cs are 1 launch).

## What was built and screened (mesa `hk/cdm-chain-batch`)

All on `github.com/joshuaswarren/mesa` branch `hk/cdm-chain-batch`, base
`d8d4e1c500b` (= `honeykrisp-omarchy`), cross-built on mesa-xbuild, loaded
via private ICDs (`/var/tmp/CdmChain/{base,cand}-icd.json`), same wheel
(`V064REL-venv`, `0.32.2.dev202609172230+fb649d8d`, libmlx pinned
`e9e709f38331ff10` fatal), same pinned harness bytes (`bench_decode.py`
`f5062d88…`, `bench_matrix.json` `df8eb9f3…`). Base driver arm =
`d8d4e1c500b` (`a2a8646ded…`), built in the same cross-build as the
candidates so the contrast isolates the emission change.

1. **v1 `e774f5f12d1` (`9b60b41609…`)** — launch defers its barrier
   (`hk_cs.cdm_barrier_pending`); `hk_cdm_cache_flush` becomes idempotent
   emit-if-pending; trailing flush at compute-stream end; indirect-grid
   launches pre-drain. Barrier content untouched.
   - Digests: **24/24 rows exact pins on BOTH drivers** (6 interleaved
     rounds × 2 arms × 2 legs).
   - Perf: base 140.23 short / 82.38 ctx1024 vs cand 140.19 / 81.50 tok/s
     (all-round medians): **short −0.03%, ctx1024 −1.06%**; paired per-round
     cand/base median ratio short 1.005 (4/6 positive), ctx1024 0.991
     (1/6 positive). Steady-state rounds identical to all-round. **Neutral.**
2. **v2 `80dec13acad`** — extends the elision across merge seams
   (`hk_cs_merge_cdm` drops a's pending barrier, chains join; terminate
   flushes unmerged tails). **Host assert crash** before any cand
   submission: the merge sets `a->current = b->current` without propagating
   `chunk`/`end`, so the terminate-time flush bounds-checked a stale `end`.
   Fix = propagate `chunk`/`end` through the merge and grow via
   `hk_ensure_cs_has_space` instead of asserting.
3. **v3 `ae819e10cb6` (`85ff2b0c0d…`)** — crash-fixed merge-seam elision.
   Digest screen: base probe passed (12,676 flushes, pin exact), cand probe
   **DIGEST FAIL: `b1f5584685681a5e` ≠ `7fd25a869ff21678`** — generated ids
   begin `0,140012,111598` and end in zeros (expected `9707,0,…`): silent
   corruption, not a crash. The A/B battery was auto-skipped by the screen
   gate (window #3's gate keyed on probe exit codes; the battery never ran).

Barrier count accounting: v1 removed only 130 of 12,676 barriers (1%); v3
removed ~98.7% (~164 remain: imm-write tails, indirect pre-drains, per-cs
terminates). The break at v3 identifies the launch→launch kitchen-sink
barrier as the load-bearing element on G13X — consistent with the in-tree
comment (inter-dispatch cache coherency / sync, "hit this with blits") and
with the forbidden bit-set lane's coupling result.

## tok/s vs baseline

The A/B contrasts above are within-window and self-contained. **Absolute
levels in all three of today's windows ran ~27-45% below this morning's
same-host baselines** (base short 136-141 vs gate 190.59/191.4; ctx1024
82 vs 149.3/165.3), consistently across windows, probes, and arms — so no
absolute improvement can be claimed from these windows and none is. The
no-ship verdict rests on the digest break (fatal regardless of speed) plus
the measured neutrality of the digest-clean variant.

## Conclusion for the decode-gap attribution

The ~50% fixed-overhead share of jw16's ctx1024 gap is **not recoverable by
cs-emission barrier elision**: the per-launch kitchen-sink CDM_BARRIER is
required for correctness on G13X at essentially every launch→launch
boundary in these chains. With bit-set mid-set experiments forbidden by
this lane's contract, the remaining Mesa-side levers would be (a) a sourced
minimal G13X bit set that holds both legs (the forbidden bit-set family,
open per the decode-gap receipt) or (b) reducing the barrier COUNT by
removing MLX's per-dispatch `vkCmdPipelineBarrier2` churn (MLX-side hazard
tracking — the fold family, which has its own digest history). Neither is
this lane.

## Hardware safety / coordination

- Three windows, one `flock -w 900` hold each on `/tmp/m1-gpu.lock`
  (inode 12 before and after every window; never stolen, never unlinked).
- `llm-inference.service` stopped before and restarted + CONFIRMED ACTIVE
  after every window (`post: active`, MainPID readback after #3 = 92845).
- jwm1 never touched. No system driver installed or modified on jw16
  (private ICDs only); no reboot; `63c1d3cf` N/A for mesa.
- TAKE/RELEASE announced via hub per window; screen-failure path skipped
  the battery automatically (window #3) instead of claiming a perf number.

## Artifacts

- jw16 `/var/tmp/CdmChain/`: `window{,2,3}.log`, `exit.txt`, `service.txt`,
  `lock.txt`, `cs-{base,cand}.json`, `raw-{base,cand}.log` (per-cs stats),
  `cdm-chain-ab.json` (v1 battery, 24 rows), `{base,cand}-icd.json`,
  `libvulkan_base-d8d4e1c.so` (`a2a8646ded…`),
  `libvulkan_cand-e774f5f.so` (`9b60b41609…`),
  `libvulkan_cand-80dec13.so` (crashed build),
  `libvulkan_cand-ae819e1.so` (`85ff2b0c0d…`).
- mesa-xbuild `~/src/mesa-cdm-chain` (worktree, cross-build `build-cdm`).
- Mesa: `joshuaswarren/mesa` branch `hk/cdm-chain-batch` @ `ae819e10cb6`
  (pushed; single commit on `honeykrisp-omarchy` `d8d4e1c500b`), preserved
  as the screened no-ship record.
- ane-linux-experiments: this receipt (both refs: mesa
  `hk/cdm-chain-batch@ae819e10cb6` + this repo's receipt commit).
