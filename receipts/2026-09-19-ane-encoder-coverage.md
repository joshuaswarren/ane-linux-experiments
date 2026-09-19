# ANE encoder coverage on current main: per-op inventory, B/O marginals, submit-overhead split (jw16, 2026-09-19)

Lane: AneEncoderCoverage. Host: jw16mbp1-linux (T6001, G13C C0). No repo writes in
this lane (measurement + analysis only): runner, worker, compiler, bundles all
pre-staged bytes; no new ANE coverage implemented (see verdict).

## Verdict

**MEASURE + NO-LAND (new coverage).** On current main bytes the encoder wall is
**AC serve 2469.2 ms** (median of 6 interleaved, relay-bypass transport, resident-batch)
— down from the v0.7.1 receipted 3359.9/3391.5 ms on the same host. The full per-op
inventory below shows the remaining wall is dominated by work that further ANE
coverage provably does NOT remove: adding the B island (ABC) nets **+655 ms** and
adding the O island (ACO) nets **+509 ms** on medians, both 104/104-clean. The only
coverage-shaped win left (B's ~1.5 ms GPU select is trivially small; O's GPU linear
is real compute but the island round-trip costs more than it saves). Of the remaining
AC wall, host orchestration (marshal + pipe round-trip), not device compute and not
coverage, is the dominant share. **Submit overhead dominates what remains; coverage
does not.** The sound next lever is fewer/smaller host round-trips (batch shape,
staging), not more islands.

No new island was implemented or enabled in this lane: with both candidate islands
measuring as net losses at 104/104-clean, there was no safe win to land, and the
assignment's "revert on any pin regression" gate never fired because nothing was
changed (18/18 ANE arms 104/104, pins EXACT, cpu_ev 0, timeouts 0 — see §5).

## Stack pins (every number below is on these bytes)

- Runner: `/var/tmp/encwall-relay/cand-run/vulkan_encoder.py` sha256
  `789aaec31029fe625713b82ca24ae95eab47604e6a6992e7378f6a57f7e4af74`
  (= v0.7.1 tag bytes `50eeb290`; stock serve path, unchanged).
- Client: `/var/tmp/encwall-relay/cand-run/ane_resident.py` `ad331981…` (= main
  `e14752ff` relay-bypass client).
- Worker: `/var/tmp/encwall-relay/cand/bin/mlx-omarchy-ane-worker` `44a99528…`
  (= main `e14752ff` splice-pump worker); `MLX_OMARCHY_ANE_RELAY_BYPASS=1` on all arms.
- libane: `/var/tmp/jw16-oproj-place/libane-strict-fill.so` `04a17653…`.
- Bundles: `/var/tmp/jw16-conv-place/bundles-conv` (104 dirs; ABC + O + conv sets staged).
- Venv: `/var/tmp/V071REL-venv` — `venv-identity-guard.py --expect df3d4e74c597956c` PASS
  pre-window (wheel `0.32.3.dev202609190758+50eeb29`, libmlx16 `df3d4e74c597956c`).
- Harness: `/var/tmp/ParakeetE2EJw16/fused_e2e.py`, fixture FLAC, golden
  `/var/tmp/EncoderParityAne/capture`, model pin `b650695c…`, `ANE_OP_WALL=1`.
- Lock: per-arm `flock -w 900 /tmp/m1-gpu.lock` (held only during each ~5 s run, free
  between arms — this is why peer polls saw FREE mid-window; not a stall), inode 12,
  never stolen/unlinked. llm-inference stopped before window, restarted after (see §8).

## 1. Per-op inventory (CURRENT ground truth, re-measured — not inherited)

### 1a. MIL statement census (CPU-only parse of the staged encoder source, `/var/tmp/EncoderParityAne/encoder-source/model.mil`, 668363 bytes)

| op | stmts | placement on the AC arm (this window) |
| --- | ---: | --- |
| const | 1977 | GPU load (byte-reinterpret, not arithmetic) |
| linear | 194 | GPU, all 194 (of which: q/k/v-proj 72, o-proj 24, FFN 96, subsampling 1, epilogue projector 1) |
| add | 183 | GPU |
| transpose | 146 | GPU |
| reshape | 145 | GPU |
| mul | 128 | GPU |
| layer_norm | 120 | GPU |
| conv | 77 | GPU |
| matmul | 72 | **ANE** (all 72: island A 48 = rel-pos + content scores; island C 24 = PV) |
| silu | 72 | GPU (folded into the linear chain kernel where fusable; else standalone dispatch) |
| select | 48 | GPU on AC (24 mask-selects `mx.where`; 24 all-masked-rows selects) — B island NOT placed on AC |
| slice_by_index | 48 | GPU |
| split | 24 | GPU |
| softmax | 24 | GPU |
| sigmoid | 24 | GPU (conv-GLU fusion where applicable) |
| pad | 24 | GPU |
| expand_dims | 13 | GPU |
| cast | 11 | GPU |
| sub / floor / floor_div / relu / less / reduce_min / reduce_sum | ≤4 each | GPU |
| logical_and / logical_not / tile | 1 each | GPU |

Executed-statements cross-check (report `execution`): AC 3399 executed = 1230 gpu_ops +
72 ane_ops + const/materialization remainder; ABC/ACO 1206 gpu_ops + 96 ane_ops; pure-GPU
control 1302 gpu_ops + 0 ane_ops (diverged prefix 97 by design, wall reference only).

Placement letters (runner `vulkan_encoder.py`): A = rel-pos + content scores (2/layer),
B = −inf mask select (1/layer), C = PV matmul (1/layer), O = o-proj linear (1/layer).
**AC = A+C islands** (B's select stays `mx.where` on GPU); ABC adds B; ACO adds O.

### 1b. Measured time shares (AC serve, median of 6 interleaved; encoder wall 2469.2 ms)

`op_wall_ms` buckets synchronous statement time per op (includes island round-trips for
placed ops; GPU ops are mostly enqueue — real GPU compute surfaces in drains; see caveat).
Ranked:

| op | med ms (6 reps) | share of encoder wall | what it is |
| --- | ---: | ---: | --- |
| matmul | 1682.0 | 68.1% | **island A+C statement time** (ANE exec + marshal + feeder drains). No GPU matmul remains on AC. |
| const | 500.4 | 20.3% | per-pass const materialization (knob off; cache exists, default off, +236 ms single-pass penalty — see gap-attribution receipt) |
| conv | 154.5 | 6.3% | 77 GPU convs (subsampling + conv module). V-family ANE placement cuts this but breaks the transcript gate (101/104, F1 forensics) |
| layer_norm | 18.9 | 0.8% | 120 GPU norms |
| linear | 18.0 | 0.7% | 194 GPU linears' enqueue (q/k/v, o-proj, FFN — the compute hides in drains) |
| add | 6.2 | 0.3% | GPU |
| mul | 5.3 | 0.2% | GPU |
| transpose | 4.2 | 0.2% | GPU |
| slice_by_index | 2.2 | 0.1% | GPU |
| reshape | 2.2 | 0.1% | GPU |
| pad | 1.8 | 0.1% | GPU |
| select | 1.4 | 0.1% | 24 GPU `mx.where` mask-selects (= the entire B island's GPU cost) |
| softmax | 1.3 | 0.1% | GPU |
| split / silu | 0.9 / 0.8 | ~0% | GPU |
| rest (sigmoid/cast/expand/sub/floor_div/less/reduces/relu/floor/tile/logicals) | ≤0.1 each | ~0% | GPU |

Full rows per rep are in `rows.jsonl` on jw16 (`/var/tmp/ane-cov/`); arm logs carry the
per-rep `op_wall_ms` lines.

Caveat (verified, not assumed): GPU `op_wall_ms` is enqueue-heavy. Proof: the pure-GPU
control runs all 72 matmuls + 194 linears on GPU yet books matmul 0.8 ms / linear 6.2 ms —
`apply()` issues async work and the real compute drains inside island-marshal `mx.eval`s,
const evals, and the final `mx.eval(keep)`. So `linear 18.0 ms` is NOT the price of the
194 GPU linears, and `const 500.4 ms` is the materialization drain. Time-share ranking
above is valid for *where the wall is booked*; the compute-behind-drains split is priced
by the ABC/ACO marginals in §2 and the host/pipe split in §6 instead.

### 1c. ANE-resident vs fallback, per op

- ANE-resident on AC: **matmul only** (72/72 matmul statements via islands A + C).
- Fallen back to GPU on AC: **everything else** (all linears incl. o-proj/FFN/qkv, all
  convs, norms, softmax, selects, elementwise, shape ops, consts).
- No CPU tensor fallback anywhere: `cpu_tensor_events` 0 in all 18 ANE arms.

## 2. Island marginals (cost saved / implementation risk — measured, interleaved)

Medians of 6 per cell (resident-batch, relay-bypass transport):

| cell | enc wall med | ane_exec | marshal | back | write | read | residual* |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AC (A+C, 48 rounds) | 2469.2 | 718.7 | 880.2 | 50.2 | 189.7 | 504.5 | 833.3 |
| ABC (+B select, 72 rounds) | 3124.7 | 1175.0 | 993.4 | 72.2 | 361.7 | 743.1 | 881.5 |
| ACO (+O oproj, 72 rounds) | 2977.7 | 923.4 | 980.0 | 62.8 | 218.7 | 671.5 | 1012.1 |

\* residual = wall − exec − marshal − back − batch_open (GPU-side drains between islands).

Marginals vs AC (same transport, interleaved, so comparable):

- **B island (ABC − AC): wall +655.5 ms (median).** Select `op_wall` 1.4 → 559.1 ms
  (+557.7); island-select per-bundle total med 419.5 ms / 24 rounds (~17.5 ms/round);
  exec +456.3, marshal +113.2, read +238.6, write +172.0. Saves 24 GPU `mx.where`
  dispatches (~1.4 ms total — the entire GPU cost of B). Ratio: pays ~655 ms to save
  ~1.4 ms. **Risk: none (already minted, gate-passed, 104/104 here) — but the price is
  positive, so there is no win to land.**
- **O island (ACO − AC): wall +508.5 ms (median).** Linear `op_wall` 18.0 → 138.2 ms
  (+120.2 = the 24 oproj island statements booked under linear); oproj per-bundle total
  med 88.2 ms / 24 rounds (~3.7 ms/round device-side); exec +204.7, marshal +99.8,
  read +167.0, residual +178.8 (extra 24 rounds serialize against GPU work). Saves the
  24 GPU o-proj linears' compute (hidden inside drains, not separately priced — bounded
  above by the FFN-placement receipt's ~13 ms/island class, i.e. ≤ ~300 ms even
  generously). Ratio: pays ~509 ms to save at most ~hundreds of ms, measured net loss.
  **Risk: none (minted from mil-hwxc@f122644, device gate worst rel_l2 0.000208,
  104/104 with hidden `ef6afd13…` here) — but the price is positive.**

Ranked by (cost saved)/(implementation risk): both candidates have zero implementation
risk (already built, gated, and 104/104-clean in this window) and negative savings —
**no coverage win exists to land**. The conv V-family (the only family that ever cut the
wall: −11% launch / −24% resident) is excluded on correctness: transcript 101/104 in
every arm, closed as a decoder-tail coin flip at the certified fp16 class (F1 forensics;
any same-class realization breaks with p≈0.5). FFN F/G families are measured net losses
on both hosts in both modes (+1.2 s to +7.9 s). O/B re-measured here as net losses.
**Coverage is exhausted as a wall lever on this orchestration.**

## 3. Highest-value op(s): nothing to implement

Per the ranking above, the highest-value *safe* coverage op does not exist: every
placeable family with a positive saving is already placed (A, C), and every unplaced
family costs more in round-trips than it saves in GPU work. This lane therefore
implements nothing and changes no default — deliberately, per the "one or two real wins
over a broad risky sweep" instruction: zero real wins were available, so zero were
manufactured. The runner/worker/compiler are untouched (pins in the header).

## 4. Correctness: 18/18 ANE arms 104/104 (no change, no revert needed)

All 18 ANE arms (6× AC, 6× ABC, 6× ACO): status `match`, prefix 104/104, transcript
`db501a8c…`, mel `5b54f4a9…`, bounds PASS, `cpu_tensor_events` 0, timeouts 0.
Hidden: `38c73261…` (AC/ABC) / `ef6afd13…` (ACO, the oproj-substitution digest —
expected, transcript-exact). 6 GPU controls diverged prefix 97 by design (wall
reference only). Nothing was implemented, so the revert gate never fired.

## 5. Restated encoder wall + macOS divisor (SAME methodology as the 16.3× figure)

Methodology check first: the 16.3× figure (`2026-09-19-parakeet-e2e-v071-jw16.md`) is
warm + 10 measured whole-pipeline runs, median of runs 2–10, `.ane` total vs the M1-Ultra
`transcribe()` divisor (292.2 ms), with a like-for-like (−audio_load, 16.1×) column
because macOS `transcribe()` excludes audio_load. That methodology is sound for what it
claims (cross-chip, cross-OS, indicative ratios — the receipt states the caveat); the
refinement below is that the divisor's stage split (encoder 135.8 / decode 138.8 /
mel+detok ~17.6) allows an encoder-level divisor too.

This window (same fixture/model/pins, relay-bypass transport = current main default):

| metric (median of 6, interleaved) | this window | divisor | ratio |
| --- | ---: | ---: | ---: |
| whole-pipeline `.ane` total (AC) | 3792.6 | 292.2 (M1-Ultra `transcribe()`) | **13.0×** |
| like-for-like (−audio_load 76.0) | 3716.6 | 292.2 | **12.7×** |
| **encoder stage only (AC)** | **2469.2** | 135.8 (macOS encoder split) | **18.2×** |
| encoder stage (GPU control, ref only) | 847.9 | 135.8 | 6.2× (definitions differ; control diverges prefix 97) |

Stage medians (AC): audio_load 76.0, mel 161.3, encoder 2469.2, decoder_load 69.9,
tdt_decode 968.2, detokenize 52.8. The encoder is 65% of the AC total (was 71% at
3391.5 ms). tdt_decode (~968 ms) vs macOS decode (138.8 ms, ~7.0×) is the second stage
and becomes the next ceiling — out of scope for this lane.

Reading vs the assignment's "3440 → 2530" numbers: those are the relay-bypass
receipt's AC-serve medians (base 3440.5 → candidate 2530.6, `2026-09-19-encwall-relay-bypass.md`).
This window's AC median (2469.2, same transport as the candidate) reproduces the
candidate side within noise (spread 2371–2670). The pre-bypass v0.7.1 baseline
(3359.9/3391.5) is superseded on current main by the bypass default — the wall moved
by transport, not by coverage.

## 6. Island submit overhead (measured — the key open question)

AC serve (48 rounds: 24× attn-a-kt + 24× pv), medians of 6:

- Per-round medians (rep 3, representative; all 6 reps agree): attn-a-kt exec 23.6 ms
  (write 4.8 + read 18.4), marshal 27.0 ms, 3.8 MB in / 6.7 MB out; pv exec 8.4 ms
  (write 3.7 + read 4.1), marshal 5.5 ms, 3.0 MB in / 0.8 MB out.
- Overhead decomposition of the 2469.2 ms wall: marshal 880.2 (35.7%) + back 50.2
  (2.0%) + pipe round-trip inside exec (write 189.7 + read 504.5 = 694.2, 28.1%) +
  residual GPU drains 833.3 (33.8%). Device compute (a0-class ~1.2 ms/round → tens of
  ms total) is ~1–2% of the wall.
- Fixed-vs-compute: the oproj marginal prices it — oproj rounds move 0.75 MB in/out
  for ~3.7 ms device-side round-trip, while attn-a rounds move 10.5 MB for ~23 ms;
  the per-round cost scales weakly with bytes and strongly with round count (adding 24
  B rounds adds +655 ms wall for ~1.4 ms of saved GPU work; adding 24 O rounds adds
  +509 ms). The fixed per-round host cost (marshal eval+drain + pipe write/read +
  protocol parse + sync wakeup) is the wall, not the bytes and not the silicon.
- What would reduce it: (a) fewer rounds — fuse islands per layer into one program
  (the FFN-chain G lane is the template; it lost only because its 48 extra rounds
  rode the same per-round tax — the tax itself is the target); (b) smaller per-round
  host work — the relay-bypass already removed ~910 ms (−26.4%) by cutting the C++
  relay parse; the remainder is runner-side `mx.eval` + numpy staging per round
  (marshal) plus the pipe handoff (write/read); (c) NOT more coverage — §2 proves
  each added round costs more than it saves.

**Which dominates: submit overhead, by far.** Coverage (B+O together) can at best remove
~1.4 ms (B's GPU cost) + low-hundreds ms (O's GPU compute) while adding ~1.1 s of
round-trips — net negative. The remaining wall after AC is ~880 ms marshal + ~694 ms
pipe round-trip + ~833 ms inter-island GPU drains = ~2.4 s of orchestration around
tens of ms of device compute. **Coverage is exhausted; submit overhead is the entire
remaining bottleneck.**

## 7. What was NOT done (explicitly out of scope)

- No new island implemented; no default changed (`AC` stays the default; B/O/V/P/T/F/G
  stay opt-in per `docs/ane-encoder-placement.md` + the V/P/T and F/G disposition rows).
- No GPU driver touched; T6021/M2 untouched (separate lane owns H14).
- No submit-overhead fix implemented (fused-per-layer programs / staging reduction are a
  worker-protocol + compiler lane, named in §6 — this lane measured and priced it).
- Wheel vintage pinned by construction: single venv/wheel (`50eeb29`/`df3d4e74c…`) across
  all 25 runs; interleaved rotation [AC, ABC, ACO, GPU]×6 within one window, medians quoted.

## 8. Window discipline + artifacts

TAKE announced to all lanes before the window (queue: Mesa → Ane → Bf16; Bf16 contested
once, stood down per Main's arbitration, holder PIDs 527020/527021 killed by Bf16 and
verified dead). Sequence: `systemctl stop llm-inference` (active → inactive) → per-arm
`flock -w 900 /tmp/m1-gpu.lock` (inode 12, never stolen/unlinked) → 25 runs (warm + 24
interleaved, ~105 s) → data pull → `RELEASE` + restore (below).

- jw16: `/var/tmp/ane-cov/` — `encov_window.sh` (exact battery script), `rows.jsonl`
  (25 rows with gates + attr), `out-{ac,abc,aco,gpu}-serve*` (e2e-report.json +
  encoder_hidden.npy + transcript.txt + mel.npy per arm), `arm-*.log` (op_wall lines),
  `scratch-*`.
- Local: `.local/encov_window.sh` (shipped copy of the battery script).
- Window script rotation: [AC, ABC, ACO, GPU]×6 interleaved (warm AC first, discarded
  from medians); medians over 6 timed rounds per cell (≥6-round bar met).

## Not claimed

- Same-die macOS divisor for T6001 does not exist; all ratios vs the M1-Ultra (and the
  T8103 same-die 259.9 ms, which would make ratios slightly larger) are indicative.
- macOS `transcribe()` excludes audio_load and model load; like-for-like removes
  audio_load only.
- GPU-control walls carry no correctness claim (diverged prefix 97 by design).
- The ACO hidden `ef6afd13…` is the transcript-exact oproj-substitution digest (same as
  the certified ABCO arms), not a regression.
- Per-op `op_wall_ms` books synchronous statement time (island round-trips for placed
  ops; enqueue for GPU ops) — §1's caveat + §2's marginals are the honest split, not
  the raw ranking alone.
