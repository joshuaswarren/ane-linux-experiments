# 2026-10-01 jwm1 Parakeet stage-matched inference, Linux vs macOS, five corpus clips

Host: jwm1 (Apple M1, T8103), Linux live venv = mlx-omarchy wheel 2cc1175b5 (GPU driver: Honeykrisp fork with paired fragment loads, shared-address fold, compute-shader scheduler skip). macOS reference: the same laptop, `~/mac-reference-bundle/bin/parakeet transcribe --show-timing --compute-units ane`, 10 repetitions per clip (receipts/2026-09-28-jwm1-parity-macos-legs and the H9 corpus run; recomputed here from the archived per-rep outputs with `raw/an_mac_pk.py`).

Measure: "stage-matched inference" = mel + ANE encoder + TDT decode, the sum macOS's CLI prints as `inference`. Linux numbers come from the product CLI path (`mlx-omarchy-parakeet`, in-process, `raw/run_pk_clips.sh`), 11 runs per clip with run 1 (cold) excluded, so n=10 warm. The fixture is pinned (transcript sha `db501a8c0803`, status `match`); the other four clips run the general-audio contract (status `match`, no failed checks, token emissions 0 / 0 / 28 / 101, equal to macOS).

| clip | Linux mel / encoder / TDT = sum (ms) | macOS mel / encoder / decode = sum (ms) | Linux vs macOS |
|---|---|---|---|
| fixture_v03 (0.3 s, 0 tokens) | 11.1 / 140.2 / 34.6 = 185.9 | 14.0 / 134.5 / 55.0 = 205.0 | 1.103x (pass) |
| fixture_v1 (1 s, 0 tokens) | 11.0 / 139.9 / 33.5 = 184.4 | 14.0 / 135.5 / 22.0 = 171.5 | **0.930x (LOSS)** |
| fixture_v5 (5 s, 28 tokens) | 11.4 / 140.6 / 80.5 = 232.5 | 14.0 / 135.5 / 90.0 = 239.5 | 1.030x (pass) |
| fixture_v10 (10 s, 101 tokens) | 11.8 / 140.7 / 104.5 = 257.0 | 14.0 / 137.5 / 112.5 = 264.0 | 1.027x (pass) |
| fixture (10.44 s, 104 tokens) | 11.8 / 140.4 / 110.5 = 262.5 | 14.0 / 135.5 / 118.5 = 268.5 | 1.023x (pass) |

Reading. Against the >= 1.00x rule the stage-matched sum passes on 4 of 5 paired clips and loses on the 1 s clip (TDT floor 33.5 ms vs macOS 22.0, encoder +4.4 ms). The ANE encoder stage alone is 3-4% slower than macOS's CLI encoder on every clip (about 140 vs 135 ms) and 24% slower than macOS's isolated ANE harness (113.27 ms); the ANE-inference cell (0.81x) remains a loss. Mel (11-12 vs 14 ms) and TDT on clips with tokens are faster than macOS.

Not claimed: any total-process or cold-start comparison. Linux `total_pipeline` (326.8 ms on the fixture) also includes decoder_load 40.3, audio_load 2.8 and detokenize 21.5 ms that macOS's `inference` figure excludes, while macOS separately spends 0.12 s loading models once; those are not paired here. The 1 s cell is a loss and the Parakeet surface is not closed until it passes or is explicitly scoped out. macOS's own v03 decode (55 ms for 0 tokens, against 22 ms on the 1 s clip with 0 tokens) is taken as measured.

Raw: `raw/pk117.log` (fixture, 11 runs), `raw/pk118-fixture_v*.log` (per-clip, 11 runs each; one JSON row per run with stage table, status, emissions, failed checks), analysis scripts alongside. Notebook: entries/jwm1-parity/20261001T140000Z-jwm1-parakeet-stage-matched-h117.md.

## Follow-up (same day): TDT-stage levers tried on the 1 s clip, all exact, none shipped
- First-chunk sizing (H119): no effect, because every clip passes valid_frames = 375 (fixed 30 s encoder shape), so short clips walk their padding; a 64-slot chunk is always needed.
- Wider joint window, `_WINDOW_ROWS` 10/13 (H124): output identical, TDT stage slower (v1 33.5 -> 44.5/42.6 ms; fixture 110.5 -> 140.4/141.8).
- Narrower window, 3/4/5 rows (H125): output identical; v1 43.2/47.2/29.4, fixture 105.0/105.2/108.1; no setting brings the 1 s cell to parity (best stage-matched sum 181.4 vs macOS 171.5) and each helps one clip class while hurting another.
The 1 s cell (0.930x) stays a loss. Notebook entries: 20261001T150000Z-jwm1-tdt-first-chunk-h119.md, 20261001T190000Z-jwm1-tdt-window-rows-h124.md.

## Update after the window-kernel change (mlx-omarchy b791539ed, deployed)
The TDT window kernel now issues 8 independent weight loads per k block and accumulates with fma (bit-identical: f16 x f16 products are exact in fp32; corpus gate PASS on four clips, five-clip transcript sha/emission counts unchanged, pinned fixture sha db501a8c0803). Stage-matched sums, live venv, n=10 warm: v03 182.3 vs macOS 205.0 (1.125x), **v1 180.1 vs 171.5 (0.952x, LOSS)**, v5 234.6 vs 239.5 (1.021x), v10 258.8 vs 264.0 (1.020x), fixture 263.0 vs 268.5 (1.021x). The machine was warm (Qwen decode 43.75 vs the usual 44.35 tok/s), so token-clip gains from this change are within noise (0-4%); the blank-dominated clips improved ~13%. 4/5 cells pass; the 1 s cell is still a loss. Notebook: entries/jwm1-parity/20261001T210000Z-jwm1-tdt-window-fma-h126.md.
