# 2026-10-02 jwm1 Parakeet TDT stage: two exact dense-phase changes shipped, blank-phase floor characterized

Host jwm1 (T8103), Linux 7.1.13-3-2-ARCH, mlx-omarchy main 2c08e72dd (H142 e73f4613e + H143 2c08e72dd), live venv deployed; rollback venvs pre-h142 and pre-h143 kept on the host. Method for every row: product path (in-process driver, 11 runs, run 1 excluded), control and candidate venvs interleaved twice (ctl, cand, ctl2, cand2), GPU lock held, transcript sha / emission count / status compared across all arms (EXACT on every clip in every arm).

## Shipped
| Change | Where it acts | TDT stage effect (ms, n=10 median, ctl -> cand) |
|---|---|---|
| H142: control kernel reduces only the rows the window computed (7 before the first emission, 1 after) | every slot after the first emission | v5 80.8/82.6 -> 77.1/78.8; v10 105.4/105.7 -> 100.1/101.0; fixture 111.3/110.2 -> 106.6/106.3 |
| H143: one-row window path issues 4 independent weight loads per k block (fma of two f16 operands = old mul+add exactly) and stages only the row it uses | every slot after the first emission | v5 78.6/79.1 -> 73.4/74.6; v10 103.2/101.3 -> 95.1/95.5; fixture 108.3/107.7 -> 99.9/99.5 |

Stage-matched sums with both changes (mel + encoder + TDT, sum of stage medians, same method as the H117 table) against macOS's paired "inference": v03 ~182.1 vs 205.0 (1.126x), v5 ~226.1 vs 239.5 (1.059x), v10 ~247.6 vs 264.0 (1.066x), fixture ~252.2 vs 268.5 (1.065x): all pass. fixture_v1 (1 s, 0 tokens) ~180.6 vs 171.5 (0.950x): still a LOSS. Post-deploy smoke on the live venv: fixture status match, sha db501a8c0803, 104 emissions, total pipeline 317-321 ms (was 340).

## Measured negatives that bound the 1 s cell (all exact, none shipped)
- H140 joint-only schedule (2 dispatches per blank slot instead of 6): v1 29.5 -> 29.7/26.3 (noise), dense clips +3.5 to +9 ms. The pass-through LSTM dispatches are not the floor.
- H141a/b window rows: stock window per call 383 us at 7 rows, 1845 us at 16 (threadgroup footprint halves occupancy: 32 KB core memory, R*640 halves per workgroup). A k-sliced 16-row window is bit-identical and 712-749 us per call (44.5 us/row vs 54.6), but in the chain the control's per-row reduction and the argmax tail (~16 us/row each) scale with rows, and v1 got slower (32.1 vs 28.4 ms). Candidate patch kept in the notebook artifacts.
- Ceiling estimate for a wide-window prefix with a rewritten tail and control: v1 TDT ~17 ms, sum ~168.5 vs 171.5: three kernel rewrites for a thin margin, and the ANE encoder is +5 ms behind macOS on this clip regardless.

Notebook entries H140, H141a, H141b, H142, H143 (lab notebook, uncommitted by design); artifacts under artifacts/jwm1-parity/tdt-*.
