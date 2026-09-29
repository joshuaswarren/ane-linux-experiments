# 2026-09-29 — Parakeet e2e beyond the golden fixture (M1 Max, Linux vs macOS, 11-clip corpus)

Corpus: 11 FLAC clips (LibriSpeech validation via hf-internal-testing/librispeech_asr_dummy, 16 kHz mono):
1.64, 2.60, 4.06, 4.65, 5.09, 5.81, 7.10, 8.62, 10.89, 29.4 s plus a 32.4 s concatenation (chunking case).
Builders: `scripts/jw16-macos-parity/make_corpus.py`, `add_long_clip.py`; Linux runner `e2e_free.py`
(same stages/code as `fused_e2e.py` minus the golden capture, models and ANE session opened once);
macOS reference `macos-parakeet-corpus.sh` (pinned CoreML CLI, arms ane and gpu, 3 reps/clip);
comparison `compare_parakeet_corpus.py`. Same physical machine; macOS on AC, automatic power mode.

## Functional parity
Linux (whole-encoder ANE + fused TDT, full 375-frame decode) equals the macOS ane-arm transcript exactly on
9 of 11 clips. The two others (5.09 s, 8.62 s) differ only in the junk tail after speech ends. Mean WER
Linux vs macOS 0.76%. The 32.4 s clip (two 30 s windows) matches exactly. macOS ane and gpu arms disagree
with each other on 8/11 clips in that same tail. The 1.6 s clip yields no words on macOS and Linux alike.

## Finding: pad frames
Both platforms decode all 375 padded encoder frames; the ANE output mask and mel mask are all ones, so pad
frames emit a junk tail. Valid length must come from the sample count (encoder frames = ceil((samples//160+1)/8)).
Decoding only valid frames removes the tail and cuts TDT time (2.6 s clip 447 -> 33 ms, 10.9 s clip 260 -> 115 ms,
total 901 -> 490 ms) but changes the transcript vs the macOS reference; it is not enabled by default.

## Timing (warm medians)
macOS ane inference 0.185-0.407 s (mel ~15 ms, encoder ~147 ms, decode 0.10-0.19 s). Linux full-frame total
641-1430 ms (encoder 441 ms fixed). Linux/macOS 2.7x (10.9 s clip) to 4.5x (1.6 s clip); every clip is a loss.
