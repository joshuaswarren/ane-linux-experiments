# jwm1 Linux vs macOS ledger after H49-H67 (2026-09-30)

Live stack on jwm1: mlx-omarchy wheel 0.32.3.dev202609291016+... (source 0fd3aefaa on origin/main: submit early-first batch via mlx-lm patch, Parakeet GPU pre-warm + 1 GB buffer cache, mel hardware-fma fast path, TDT fold_proj prefetch, decode SDPA prefetch and 7168-key range) + qk/conv/gated mlx-lm patches + ttft patch + soundfile. Every pin identical on every cell (decode64 7fe6badf4d560e25, decode128 da5568eeb4b6a1c1, decode256 828b55d6249d9679, prefill ccb601895581d89f; Parakeet status match, transcript sha db501a8c0803...). macOS cells are the paired same-die values from receipts/2026-09-28-jwm1-macos-parity-legs and 2026-09-29-jwm1-parakeet-corpus.

| Cell | Linux now | macOS | Linux/macOS | Was (start of the day) | Result |
|---|---:|---:|---:|---:|---|
| decode 64 tok/s (n=3 x 5 prompts) | 41.70 (41.68-41.71) | 49.36 | 0.845 | 0.824 | LOSS |
| decode 128 tok/s (n=3) | 41.20 (41.19-41.36) | 49.26 | 0.836 | 0.828 | LOSS |
| decode 256 tok/s (n=5) | 41.34 (41.28-41.41) | 49.33 | 0.838 | 0.808 | LOSS |
| prefill 512 tok/s (n=5) | 256.96 (255.84-257.29) | 345.31 | 0.744 | 0.742 | LOSS |
| prefill 1024 tok/s (n=5) | 257.08 (256.68-257.15) | 345.76 | 0.744 | 0.741 | LOSS |
| prefill 2048 tok/s (n=5) | 250.31 (249.00-253.22) | 341.80 | 0.732 | 0.732 | LOSS |
| TTFT s, decode64 prompts (patch on vs off, 3 pairs) | 0.1599 (off 0.1814) | 0.1248 | 1.28x latency (off 1.45x) | 1.57x | LOSS |
| Parakeet stage-matched mel + encoder + TDT (ms) | 11.8 + 140.3 + 111.3 = 263.4 | 14 + ~136 + ~119 = 272 (inference 268-272) | 1.03x throughput (stage sum) | 0.886x | see note |
| Parakeet whole warm pipeline incl. per-run model loads (ms) | 330.8 | not comparable (macOS models load outside "inference", 0.12 s) | - | 384 | - |
| whole-encoder ANE ms (bit-exact both sides) | 138.86 (not re-measured today) | 113.24 | 0.815 | 0.815 | LOSS |
| Qwen ANE (decode tok/s / TTFT / e2e) | not re-run today (2026-09-25 committed receipt) | 5.625 / 1.189 s / 6.718 s | Linux paired PASS earlier | - | unchanged |

Parakeet note: the stage-matched sum on the fixture is at or slightly better than macOS on this die (mel 11.8 vs 14, TDT 111 vs 119; encoder 140.3 vs ~136 is a small loss). It is NOT a parity claim for the Parakeet cell: the cell requires the six-clip corpus, and the chain-only per-clip timings in a fresh process (median of passes 2-4, old -> new package, cache 1 GB) are v03 28.1 (macOS 55.0), v1 26.6 (macOS 22.0), v5 86.6 (90.0), v10 118.6 (112.5), fixture 123.2 (118.5), wav 123.2 (119.0) ms, with 3-4 pass drift in this harness; the corpus gate (chain vs the independent host path, bitwise) PASSES on all six clips with the new kernels. The encoder stage on the corpus is fixed-shape (375 frames) and equal to the fixture.

What moved the numbers today (all exact, all digest-gated): early-first submit for prompt+first token (TTFT -12%); Parakeet GPU pre-warm + 1 GB cache (mel 29 -> 19.5 ms, TDT -4 ms); mel hardware-fma fast path (mel 19.5 -> 11.8); TDT fold_proj weight prefetch (TDT 133 -> 111); decode SDPA prefetch + 7168-key range (decode256 +3.6%, long-context decay -44% -> -20%). Findings without a shipped gain: qmm schedule probes (H35-H40), governor/pre-warm interplay (H26-H30), main-tip and poll-driver A/Bs (H42, H44), thermal/fan hypothesis (H63-H64: rejected; SMC fan control module built and verified as a tool), decode SDPA double-buffering (H67).

Remaining losses and their measured sources: prefill (qmm coopmat at M >= 32 is 1.2-1.4x slower than Metal; the 512-token forward is ~2.0 s vs 1.48 s); decode (~14% under macOS: dependent tiny dispatches cost ~4-11 us vs macOS ~1.7-4.4, plus qmm ~84% of the read roof in-chain, plus the SDPA arm's ~0.38 us/key context slope); TTFT (host record cost exposed in synchronous paths, small-M qmm floor); whole-encoder ANE (clock state; no host observability).
