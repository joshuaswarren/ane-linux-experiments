# jwm1 Parakeet current-pipeline measurement capture complete (vs same-laptop macOS rep10) — performance parity REMAINS FAILED; absorption is prospective only

Owner: Jwm1Kernels3, 2026-09-26. Installed stack: mlx-omarchy
`0.32.3.dev202609261526+7d3f69ff2` (GDN prefill 4-lane + translator disk
cache + whole-encoder bundle + GPU mel + gpu-chain TDT; no CPU tensor
fallback — decoder_calls=0, joint_calls=0, decode_path=gpu-chain).

## Determination (Main's question)

The full frozen 3-warmups+10-reps same-laptop macOS comparison EXISTS for
the current combined pipeline; it was NOT rerun for this receipt. What was
missing and is now captured: peak memory + lifecycle boundaries (below).

## Artifact paths (all on jwm1)

- Installed acceptance run (3w+10r, one process, ANE session amortized):
  `/var/tmp/gdnpf-ab7/contract3-memory.log` (10 reps + CONTRACT_SUMMARY),
  stderr `/var/tmp/gdnpf-ab7/contract3-memory.err`; rusage wrapper
  `/var/tmp/memwrap.py`; run under `flock /tmp/m1-gpu.lock`, unit
  gdn-mem2, 2026-09-26 11:06.
- Installed corpus (6 fixtures, tok/frm/dur true x6):
  `/var/tmp/gdnpf-ab7/corpus-installed.log` (also corpus-cand/base.log for
  the A/B arms).
- Pins (installed wheel, passes 1/3/10): unit gdn-mainpin journal —
  `486872c410629f1d` / `bc519c03c4ef5fd1` / `dbf704971617fdfc`, all
  bit-exact; contract JSONs under `/tmp/dft-gates-main-pin/`.
- macOS same-laptop rep10 (reference; do not rerun):
  `receipts/2026-09-24-jwm1-macos-baselines/` — arm `ane`: cold 0.295 s,
  rep10 total 0.271 s, rep10 encoder 0.136 s, rep10 decode 0.120 s,
  transcript match gold 104/104; stdout copies
  `raw/parakeet/stdout_ane-*.txt`.
- Prior stage ledger: `receipts/2026-09-25-jwm1-parity3-parakeet-298/`.

## Acceptance table (current installed pipeline vs macOS rep10)

| stage | cold ms | warm median ms | macOS rep10 | gap |
|---|---:|---:|---:|---|
| audio_load | 2.0 | 6.9 | ~2 | warm-path corpus read, benign |
| mel_frontend | 140.5 | 20.16 | 13-15 | +5-7 (DFT kernel, bit-exact levers landed; residual small) |
| encoder_ane | 139.1 | 143.68 | 136 (engine bench 113.1) | +8 stage; engine clock bucket is NOT software — needs `powermetrics --samplers ane` in a grouped macOS window (Main-gated) |
| tdt_decode | 202.8 | 170.12 | 120 | +50 = 6 serial kernels/slot x ~27 us in-CS dispatch floor (mesa) + chains/window at 79% BW |
| total (rep10/cold) | 484.5 cold | ~341 sum-of-stages (wall incl. inter-stage ~355) | 271 | warm gap ~+70 ms |
| peak RSS | — | **1,095,408 KB (1.07 GB)** | not captured on macOS | captured Linux-side |
| init/lifecycle | island_construct 477.9 ms; cold first 484.5 ms; then warm | | macOS cold 295 ms | init dominated by ANE session/island construct |

## Incomplete criteria (honest list)

1. macOS side of peak-RSS was never captured (macOS capture scripts did
   not record rss; adding it needs a macOS window — Main-gated).
2. `powermetrics --samplers ane` engine-clock attribution (encoder 143.5
   vs macOS 113.1 engine) — explicitly Main-gated on a grouped macOS
   window; recorded as the encoder residual owner.
3. Pass-3 pin `bc519c03c4ef5fd1` verified on the installed wheel in the
   gdn-mainpin battery (journal); not re-run inside the memory pass (same
   wheel, same day — no code change between).

## Corrections (Main review, before any absorption experiment)

1. **The projected pass arithmetic in the earlier chat summary was wrong.**
   Current installed warm wall is ~341-355 ms (sum-of-stages median ~341,
   wall incl. inter-stage ~355). Subtracting the projected ~54 ms gives
   ~287-301 ms — NOT 245-265 ms, and NOT a pass against 271. The 298.6 ms
   baseline in parakeet-298 was the OLDER stack (ce91f5b8e) and cannot
   stand in for the current installed pipeline. The absorption fusion is a
   PROSPECTIVE IMPROVEMENT; performance parity REMAINS FAILED until real
   measurements say otherwise.
2. **macOS rep10 point (271 ms) vs Linux 10-rep median is not a paired
   comparison.** Parity decisions must use the complete existing macOS
   samples in 2026-09-24-jwm1-macos-baselines (cold/warm1/rep1/rep10 arms
   plus the per-rep cpuAndNeuralEngine tables), with distribution context,
   not a single-number point vs a single median.
3. **"Acceptance complete" was the wrong frame.** This receipt is a
   MEASUREMENT CAPTURE (boundaries + correctness corpus + memory +
   lifecycle) for the current installed pipeline; performance parity is
   failed and the encoder engine-clock bucket stays Main-gated.

## Next measured gap (source-backed, NOT falsified)

`receipts/2026-09-25-jwm1-parity3-parakeet-298/` §3 names the only
unfalsified TDT lever: prologue/epilogue ABSORPTION — fold computed in
chains1's prologue, fold_proj in window's prologue, control in window's
epilogue (6 -> 3 kernels/slot, ~-54 ms -> total ~245-265 < 271 PASS).
Distinct from the falsified single-workgroup trio fusion (4.7x slower,
958783d9): absorption keeps the big kernels' parallelism and hides the
tiny chains in their bandwidth slack, at the cost of redundant per-WG
fold chains (O(25.6k MACs) x 100 WGs vs chains1's O(6.5M) — within slack).
Design question to settle first: cross-workgroup visibility of the fold
result (no global barrier in one dispatch) -> every WG recomputes the
prologue redundantly (bit-exact: same fp32 ascending order). Pass
criterion: pins + corpus + contract3 gates + total < 271 ms.

## Absorption experiment: MEASURED FALSIFIED (2026-09-26 late)

Implemented the parakeet-298 §3 absorption (branch
`agent/jwm1-kernels3-tdt-absorb`, commits through "fix: dead-slot
passthrough"): chains1 computes the fold in its sh_a prologue (workgroup 0
publishes h0_out/c0_out), window computes the full fold_proj per
workgroup (sh_h1/sh_c1/sh_pj16 workgroup-local, workgroup 0 publishes
h_state/c_state/pj/pj16). 6 -> 4 dispatches/slot. Control left as its own
dispatch (the risky cross-workgroup piece was deferred).

Measured on jwm1 (chain_bench 64 5, same window discipline, lock held,
installed wheel unchanged — pure tools-tree A/B):

| arm | chain wall median |
|---|---:|
| base (6-dispatch main) | 152.6 ms |
| absorbed (4-dispatch) | **334.7 ms — 2.2x SLOWER** |

Contract digest on the absorbed path was BIT-EXACT (486872c410629f1d on
1-pass) — correctness held; the approach fails on speed. The redundant
per-workgroup fold/fold_proj prologues (strided bsum loads + scattered LUT
reads on the critical path before each WG's barrier, x100/x33 redundancy)
cost ~2x more than the two saved ~94 us dispatches. This lands the same
class as the falsified single-workgroup trio fusion: the grid-1 trio's
cost is dispatch turnaround, and absorbing their work into the bandwidth
kernels damages those kernels' streaming.

Disposition: branch stays pushed as the falsified record; main-pin
installed state (7d3f69ff2) is untouched and remains the verified
baseline. The 958783d9 conclusion is reinforced and EXTENDED: trio fusion
falsified, single-workgroup fusion falsified 4.7x, AND prologue/epilogue
absorption falsified 2.2x — the TDT trio's ~94 us/dispatch is honeykrisp
dispatch-turnaround (mesa-1 lane), and no kernel-structure change tried so
far removes it.

## Dispatch-count reduction probe CLOSED: mlx compile already fuses the GDN gating flood; unfused residual is custom-kernel boundaries; NEW BUG: profiler x compiled = digest break

Paired decode-window profiles on the installed 7d3f69ff2 stack
(/var/tmp/prof/ on jwm1): prof-decode3.jsonl (eager,
MLX_DISABLE_COMPILE=1) vs prof-decode-comp.jsonl (compile enabled). Same
shape: 1 prompt, 1 pass, 32 new tokens, prefill 512.

| family (eager -> compiled) | count | verdict |
|---|---|---|
| AsType/Sigmoid/Multiply gating chains | 2268+1512+756 eager | COLLAPSED into CompiledAsTypeSigmoidBroadcastBroadcastMultiply (3780) + CompiledSigmoid... (1764) + CompiledAsTypeExpNegative... (252) — mlx fusion DOES absorb the GDN gating pointwise adjacency when compilation is enabled |
| total dispatches | 25902 -> 26802 | flat (fusion trades many small for fewer fused; prefill elementwise flood collapsed massively) |

Findings:

1. **The GDN gating/normalization pointwise adjacency is already fused by
   mlx's compiled tape** — the Compiled* families ARE the fused GLSL
   regions. What remains unfused are CUSTOM-KERNEL boundaries: RMSNorm
   (FastNorm, 2268+2058+504+252), the QMM classes (256/768/640 grids),
   GatedDeltaUpdate, Convolution, ScaledDotProductAttention. Fusing across
   those boundaries = new mega-kernel territory adjacent to the falsified
   absorption/fusion family. No measured candidate there.
2. **Measured rate win: none.** Compile-on decode 39.25 vs eager 39.20
   (1-pass, unprofiled, both pin-exact) — fusion is rate-neutral at the
   contract shape, consistent with the elementwise real cost ~0.1-0.2
   ms/token vs the QMM+floor ~25 ms/token.
3. **NEW BUG (diagnostics-only): MLX_OMARCHY_GPU_PROFILE + compiled
   execution together BREAK generation** — profiled compiled run:
   digest `100a61b6247096f5` (wrong), decode 21.82 tok/s (halved), while
   the identical command unprofiled is pin-exact at 39.25. Repro:
   prof-decode-comp.jsonl + contract-profcomp.json vs
   /var/tmp/compiletest/contract-on.json. Suspect: the profiler's
   per-pair timestamp/barrier insertion perturbs the compiled tape's
   execution. Blocks all profiler use on compiled pipelines; owner:
   mesa-1/mlx-omarchy runtime (whoever owns gpu_profiler.h).

Main's directive satisfied: profile taken, adjacency assessed, measured
candidate = none survives the promote bar (fusion already present,
rate-neutral). The no-unfixed status of MLX_DISABLE_COMPILE is updated by
the companion receipt e9effe3b.
