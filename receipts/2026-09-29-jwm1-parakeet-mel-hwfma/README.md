# jwm1 Parakeet mel: hardware fast path in the emulated fma32/add32/sub32/mul32 (2026-09-29)

mlx-omarchy origin/main b10235b0c (`overlay/tools/coreml/vulkan_mel.py`, check script `scripts/check-mel-fma-fastpath.py`), deployed on jwm1's live venv (rollback venv /var/tmp/jwm1-venv-440889401).

The DFT and mel-projection kernels were built from `fma32`/`add32`/`sub32`/`mul32`, all backed by `fma32_bits`, an integer emulation of IEEE-754 fma with denormal/NaN/inf/sticky-bit handling (add and mul included). That protects bit-exactness against the macOS reference but costs hundreds of integer ops per arithmetic op. The GPU's fma/add/mul are single-rounding round-to-nearest-even for normal finite operands and results, so the new code returns the hardware result only when every operand and the result have exponent field 1..254 (and returns the addend for a zero product with a normal addend); every other case still takes the unchanged emulation.

Exactness evidence:

- Randomized equivalence: 1,677,721,600 triples per operation across eight input classes (uniform bits, all-normal, moderate exponents, +-3 ulp near-cancellation for fma and for add/sub, small and large exponent boundaries, zeros/denormals/inf/nan specials): 0 mismatches for fma32, add32, sub32 and mul32.
- Full mel outputs (mel, mask, encoder features, encoder mask, all captured stages) SHA-256-identical old vs new on 8 waveforms: the pinned fixture, gaussian noise (0.05, 0.5), silence, 1e-30 and 1e-38 amplitude noise (denormal paths), clipped noise, short sine.
- Pipeline: status match and transcript sha db501a8c0803... in every run (n=18 in the A/B, n=6 on the live venv); Qwen decode/prefill digests unchanged (7fe6badf4d560e25, da5568eeb4b6a1c1, 828b55d6249d9679, ccb601895581d89f).

Timing (medians, ms):

| | frames | dft | power | mel_project | stats | normalize | mel back-to-back |
|---|---:|---:|---:|---:|---:|---:|---:|
| before | 1.06 | 8.77 | 1.03 | 8.11 | 2.03 | 0.43 | 19.86 |
| after | 0.64 | 4.21 | 0.64 | 5.78 | 2.02 | 0.39 | 12.22 |

Pipeline (in-process warm, live venv after deployment, n=6): audio 2.9, decoder_load 43.3, **mel 11.8**, encoder_ane 139.8, tdt 131.5, detokenize 21.3, total 352.9 ms (383.9 before the pre-warm/cache and this change, 360.6 after the pre-warm).

Stage-matched vs the paired macOS stages (mel 14, encoder ~135-138, decode ~120 = 272 ms): Linux mel 11.8 (faster than macOS), encoder 139.8 (+~3), TDT 131.5 (+~11): 283.1 ms = 0.961x of macOS throughput (was 0.886x). Encoder and TDT are still losses; no parity claim for the pipeline.
