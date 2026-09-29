# jwm1 (M1, T8103) Parakeet per-clip paired stage timings, 2026-09-29 (00:03-00:09Z window)

Goal item: Parakeet beyond the 104-token fixture. Six clips (sha256 prefixes identical to receipts/2026-09-26-jwm1-kernels3-gdn-prefill):
fixture 30885601173f96b0 (10.435 s), fixture_v03 8a94d738993a841c (0.3 s), fixture_v1 b9541731e778128e (1 s),
fixture_v5 ddc49b6596aa8d87 (5 s), fixture_v10 872e0e6a989f6789 (10 s), 1089-134686-0000.wav a7a1b5c9815084cc (10.435 s, same utterance as the fixture).

- macOS (same M1, macOS 27.0 26A428): shipped arm64 `bin/parakeet transcribe --show-timing --compute-units ane`, per clip 1 cold + 3 warm + 10 timed reps.
  Medians of the 10 reps below (the CLI prints milliseconds to 3 decimals of a second, so 0.5 ms granularity after the median). loadavg 2.1-2.9 during the run (post-boot; not idle).
- Linux: `corpus_gate.py` (jwm1-parity3 harness, combined-venv interpreter), 3 passes per clip, TDT chain stage on the GPU, all host-vs-chain checks PASS. This harness times the TDT
  stage only. The installed runtime and `fused_e2e.py` both refuse non-pinned audio ("executes the pinned reference only"), so there is NO whole-pipeline Linux number for the non-fixture clips.

| clip | audio s | tokens macOS / Linux | macOS mel ms | macOS encoder ms | macOS decode ms | Linux TDT chain ms | Linux/macOS decode latency |
|---|---:|---|---:|---:|---:|---:|---:|
| fixture_v03 | 0.30 | 0 / 0 | 14.0 | 134.5 | 55.0 | 44.5 | 0.81 |
| fixture_v1 | 1.00 | 0 / 0 | 14.0 | 135.5 | 22.0 | 42.7 | 1.94 |
| fixture_v5 | 5.00 | 28 / 28 | 14.0 | 135.5 | 90.0 | 98.8 | 1.10 |
| fixture_v10 | 10.00 | 101 / 101 | 14.0 | 137.5 | 112.5 | 138.1 | 1.23 |
| fixture | 10.44 | 104 / 104 | 14.0 | 135.5 | 118.5 | 144.1 | 1.22 |
| 1089-134686-0000.wav | 10.44 | 104 / 104 | 14.0 | 134.5 | 119.0 | 143.6 | 1.21 |

Observations:
- Emission counts agree on all six clips (functional agreement at the count level; token-by-token agreement with macOS goldens is the 6/6 corpus gate in the 2026-09-26 receipt, not re-run here).
- macOS mel (14 ms) and encoder (134-138 ms) are flat across clip length: the encoder is fixed-shape (375 frames for every clip on both OSes).
- macOS decode is 22-119 ms; Linux TDT chain is 43-144 ms (about 42 ms floor + ~1 ms/emission). Linux is slower on 5 of 6 clips (1.10-1.94x latency, i.e. 0.52-0.91x rate) and faster only on the 0.3 s clip.
  The 0.3 s clip's macOS decode is stable at 54-56 ms over all 14 runs, higher than the 1 s clip's 21-22 ms; cause not investigated.
- Not a whole-pipeline pair: Linux mel and encoder per clip were not timed for the non-fixture clips. Whole-pipeline numbers stay fixture-only (see receipts/2026-09-28-jwm1-macos-parity-legs).
- Nothing here reaches 1.00x on decode latency except the 0.3 s clip; the goal's Parakeet cell remains FAIL.

Raw: `raw/macos/*.err|out` (per-run CLI stderr/stdout), `raw/linux/corpus_gate.jsonl`, `raw/mac-parakeet-corpus.sh`, `raw/macos-env.txt`.
