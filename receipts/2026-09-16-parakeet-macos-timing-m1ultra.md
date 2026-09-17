# Parakeet macOS CoreML timing, M1 Ultra (cross-chip): ANE median 292.2 ms for the 10.435 s LibriSpeech fixture (2026-09-16)

Verdict: **LAND.** The pinned public Parakeet reference
(`mweinbach1/parakeet-tdt-0.6b-v3-coreml` @ `b650695c…`, reference impl
`mweinbach/parakeet-coreml-swift` @ `75aec2a1…`) transcribes the licensed
LibriSpeech fixture `1089-134686-0000` (10.435 s, sha `30885601…`) on
macstudio's M1 Ultra in a median of **292.2 ms wall** (runs 2–10 of 10
measured; all-10 median 293.3 ms) with `computeUnits: .ane`. Every run of
the battery — warm + 10 measured × 2 compute-unit configurations, plus 3
pre-window smoke runs — held the guard: **104 tokens, exact golden token
ids, transcript sha `db501a8c…`**. **All numbers below are
M1-Ultra-cross-chip** (T6000 die, `Mac13,2`); the same-die T8103 divisor
stays queued for jwm1-macbook.

## Setup (same construction as the golden capture)

- Host: `ssh macstudio` → macOS 26.6.2 (25G83), CoreML framework 3520.5.1,
  Apple M1 Ultra, 128 GB. Fleet-SSH skill followed; no sudo, no firmware or
  driver writes.
- Harness: extended the existing capture package `~/parakeet-mel-stage`
  (not forked) with a `parakeet-timing` executable target; SwiftPM
  dependency pinned to `75aec2a1…` (Package.resolved verified). The timed
  call is exactly the capture's: `try ParakeetTranscriber(modelsRoot:…,
  computeUnits:…, decoderWorkers: 1)` then `transcribe(audioURL:)`.
  Wall time = `ContinuousClock` around the transcribe call only; model
  load is recorded separately and excluded.
- Model fetch/verify via the mandated same download path:
  `fetch_parakeet_reference.py download` on the Mac → 12/12 files verified
  into `~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/
  parakeet-tdt-0.6b-v3-coreml/b650695c…/`; the staged
  `~/parakeet-ref-capture/models/mweinbach1` used for inference matched all
  12 lock hashes (`shasum -a 256 -c`, every file OK). Encoder weights
  `23867a83…`, tokenizer `bd321b09…`. Fixture re-hashed on the host:
  `30885601…` OK.

## Service pause (recorded per the standing discipline)

`llm-inference.service` does not exist on macOS — the router leg is
launchd label **`com.warren.omlx-advisor`** (omlx-server on `:8002`).
Main pre-approved the window. Stopped 19:03:43 (`launchctl bootout
gui/501/com.warren.omlx-advisor`); `com.warren.omlx-watchdog` was **not
loaded** pre-change (bootout: "No such process"), so nothing to restore
there. Confirmed down (no omlx-server process, `:8002` LISTEN count 0),
ran the battery, bootstrapped back at 19:05:17, confirmed serving 19:05:22
(state running, pid 98775, `LISTEN *:8002`, `/v1/models` answers with the
Qwen pool). **≈ 99 s stopped**, far inside the 15-min cap.

## Result — 1 warm + 10 measured runs per configuration

`.ane` (`.cpuAndNeuralEngine`), model load 257 ms (compile cache warm):

| run | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| wall ms | 295.4 | 288.2 | 291.5 | 294.4 | 282.2 | 292.2 | 297.3 | 291.0 | 302.1 | 296.5 |
| encoder ms | 139.6 | 130.8 | 135.8 | 138.3 | 128.1 | 135.8 | 138.3 | 136.7 | 128.3 | 133.7 |
| decode ms | 138.5 | 139.9 | 137.7 | 138.8 | 136.7 | 138.8 | 141.6 | 136.9 | 156.2 | 145.3 |

Warm run 421.5 ms (first transcribe after load). **Median all 10 =
293.3 ms; median runs 2–10 = 292.2 ms** (min 282.2, max 302.1). RTFx ≈
35.7× against the 10.435 s fixture. Library-reported inference splits
≈ 135.8 ms encoder / 138.8 ms decode / remainder mel + detokenize.

`.all` (`MLComputeUnits.all`), recorded as the cheap second config:

| run | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| wall ms | 300.7 | 305.4 | 306.1 | 320.2 | 303.1 | 305.8 | 302.5 | 297.5 | 310.7 | 326.3 |

Warm 499.2 ms; **median all 10 = 305.6 ms; median runs 2–10 = 305.8 ms**.
Core ML's scheduler picked a slightly *slower* schedule than pinned ANE on
this host (+13.6 ms median). Its model load recompiled for the .all
configuration (45.2 s, recorded as load time, not transcribe).

## 104-token guard

The harness asserts, for every run before recording a number: token count
== 104, token ids == golden ids (`token_ids.json` sha `a175a5f9…` from the
golden capture `20260912T154759Z-librispeech/ane`), and
SHA-256(transcript) == `db501a8c…`. Any mismatch exits non-zero and the
run is not counted. 22/22 in-window runs plus 3 smoke runs held both pins;
no drift was observed at any point, so no number above can be quoted from
corrupted output.

## Comparability note (read before forming the divisor)

These walls are `transcribe()` only — mel + encoder + decode loop +
detokenize, no model load, no separate audio-load stage. The Linux E2E
receipts quote `total_pipeline` (which includes `audio_load` and a
differently split stage list). Match stage definitions before dividing:
the like-for-like stage sums are recorded per-run in the raw JSONs
(`inferenceSeconds`, `melMs`, `encoderMs`, `decoderLoopMs`,
`detokenizeMs`).

## Artifacts

`receipts/2026-09-16-parakeet-macos-timing-m1ultra/`: `timing-ane.json`,
`timing-all.json` (raw harness output: environment, per-run wall + phase
breakdown, guard record). Summary: `…-m1ultra.json`. Host-side:
`~/parakeet-mel-stage/Sources/parakeet-timing/main.swift` (harness),
`~/parakeet-ref-capture/fetch-tool/` (downloader + lock),
`~/.cache/mlx-omarchy/parakeet-reference/...` (verified model cache).

## Mutations on macstudio (complete list)

Harness target in `~/parakeet-mel-stage` (mandated extension),
`fetch-tool/` staging dir + pinned model cache (mandated fetch path), two
battery JSONs in `/tmp`, `.build` output. Golden captures, `63c1d3cf`, and
all other host state untouched.

## Not claimed

- No T8103 numbers (queued for jwm1-macbook; no confirmed remote path).
- No Linux ANE comparison or final parity divisor — this receipt supplies
  the macOS leg only.
- No cold-start claim: the `.ane` compile cache was warm (load 257 ms);
  the `.all` load compiled fresh and is excluded from transcribe walls.
- No `gpu`/`cpu` configuration measured.
