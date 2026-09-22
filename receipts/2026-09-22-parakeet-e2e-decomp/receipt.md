# Parakeet end-to-end decomposition + TDT host-loop/defer-commit landing, both hosts (2026-09-22)

Lane: ParakeetE2EParity. Branch of this repo: `agent/parakeet-perf-worker-lever`;
backend change on mlx-omarchy branch `agent/parakeet-defer-commit`
(worktree ~/src/mlx-defercommit on m1max-host, wheel
0.32.3.dev202609221218+925cfa6). Raw batteries archived at
`~/.local/state/omarchy-private-evidence/receipts-raw-2026-09-22-parakeet-decomp/`
plus per-battery dirs under `/var/tmp/encwall-decomp/decomp-*` on each host.
Hosts are named m1max-host (T6001) and m1-host (T8103).

## Stack under test

In-process ANE island submission, cached-BO ane.ko (writecombine=N), all-ops
async issue on m1max-host (`MLX_OMARCHY_PIPE_OPS=`), soundfile audio decode.
`MLX_OMARCHY_FUSED_AB=1` is currently unrunnable on m1max-host (runner A->B
splice check rejects the committed source; EncoderFusionBC root-caused: the
select's b operand is a MUL in the current source, and last night's "fused"
battery never actually submitted out_ab - that -107 ms delta is void). All
numbers below are unfused (encoder_ane ~1210-1260 ms on m1max-host).
m1-host batteries require `VK_DRIVER_FILES=/var/tmp/mesa-e167-m1host/icd.json`
(stock mesa 26.2.3 segfaults rc=139 at ~8 submits, reconfirmed today).

## KEY CORRECTION vs the morning decomposition

The production TDT path is `parakeet_tdt.tdt_decode` -> `vulkan_tdt_loop.
run_tdt_loop`: the whole greedy loop runs as ONE single-threadgroup megakernel
dispatch. The earlier per-step numbers in this receipt's first draft
(probe_tdt_step.py: 2.25/1.58 ms per step) measured the UNUSED host-fallback
components, not the loop. Steady-state cost of the actual megakernel:
1120-1130 ms per call on m1max-host (probe_tdt_loop.py, 30 iters) - the loop,
not the encoder, was the second-largest bucket, and it is ~100x off roofline
because one threadgroup re-streams ~23 MB of weights through one GPU core per
frame.

## Landed changes (both measured, all pins green)

1. **soundfile audio fast path.** `decode_flac` already preferred soundfile;
   the venvs lacked the package. Installed soundfile 0.14.0 (FLAC lossless ->
   int16 PCM identical; transcript pins confirm).

   | host | audio_load A | B | delta |
   | --- | ---: | ---: | ---: |
   | m1max-host | 76.9 ms | 7.5 ms | -69.4 ms |
   | m1-host | 173.3 ms | 9.5 ms | -163.8 ms |

2. **Host-control TDT loop (`MLX_OMARCHY_TDT_HOST=1`) + defer-commit backend
   knob (`MLX_OMARCHY_DEFER_COMMIT=1`, mlx-omarchy agent/parakeet-defer-commit:
   eval.cpp finalize() keeps the open command buffer across graph-eval
   boundaries so consecutive custom-kernel dispatches share one submit;
   batches still close at node/byte budgets and every host-read sync).**
   Switching the loop from the megakernel to the callback path (multi-
   threadgroup kernels) plus one-submit-per-step batching of the 5-dispatch
   decoder step took the TDT bucket on m1max-host from 975 ms to 398 ms
   (decoder 249.6 + joint 148.3), total pipeline 2448.6 -> 1805.0 ms median.
   Same-window A/B of defer alone on the dispatch components: joint-only step
   1.39 -> 0.83 ms (-40%), full LSTM step 1.69 -> 1.44 ms.
   ALL RUNS GREEN: status match, 104/104 prefix, mel 5b54f4a9 / hidden
   38c73261 / transcript db501a8c bit-exact.

3. **Silent-run joint batching (Main-directed): implemented, measured
   NEGATIVE, default OFF.** `vulkan_decoder_step.run_joint_batch` (one
   dispatch for all frames of a silent run; per-frame arithmetic bitwise
   identical to the unbatched joint; sequence-identity asserted over 30
   repeats in probe_tdt_hostloop.py) plus speculative batch consumption in
   `greedy_tdt_decode`. Measured on m1max-host: tdt 398 -> 554 ms with
   batching (window 16), and a window sweep 0/2/4/8/16/32 showed 974-999 ms
   flat on the isolated loop - the silent runs are short (42 silent frames in
   ~30 runs), so each speculative batch wastes most of its frames and the
   saved dispatch round trip never pays. Kept behind
   `MLX_OMARCHY_TDT_BATCH=<n>` (default 0 = off); not part of the landed
   defaults.

## Per-stage decomposition (medians, current stack, post-landing)

| stage (ms) | m1max-host | vs T6001 enc 158.1 | m1-host | vs T8103 enc 113.0 |
| --- | ---: | ---: | ---: | ---: |
| audio_load | 7.7 | - | 9.5 | - |
| mel_frontend | 139.6 | 0.88x | 185.8 | 1.64x |
| encoder_ane | 1210-1293 | 7.7-8.2x | 3505.6 | 31.02x |
| decoder_load | 48.7 | - | 83.2 | - |
| tdt_decode | 398.4 | 2.78x* | (pending) | * |
| detokenize | 11.5-55 | - | 40.5 | - |
| total pipeline | 1805.0 | | 4660.5 | |

*macOS decoder+joint TDT divisor 143.5 ms; the linux tdt_decode wall includes
one-time per-process kernel transpile.

**m1-host caveat:** the final new-stack m1-host battery died with the host -
m1-host left the network at ~07:45Z ~90 s into overlapping battery runs
(EncoderPipelining's ANE_ASYNC_ISLANDS=1 battery started ~90 s earlier is the
suspect, unconfirmed). The m1-host column above is the pre-TDT-landing stack
(complete green battery decomp-m1host-20260922T070655: audio soundfile delta
-163.8 ms measured). The TDT host-loop + defer-commit re-measure on m1-host is
pending host recovery; the m1-host venv (`/var/tmp/defercommit-venv`) and
patched sources are already deployed, so the successor lane only needs to run
`bash /var/tmp/encwall-decomp/parakeet-e2e-decomp.sh m1-host`.

## Negative results (all bitwise-clean where applicable)

- megakernel-side: none attempted beyond measurement; single-group execution
  is the design's ceiling.
- run_step threadgroup split (640 -> 10x64): 0 change.
- TDT_JOINT_THREADS 128/512/1024: flat.
- non-rtmod libmlx (v068REL): no change (rtmod instrumentation costs nothing).
- proj+joint single-dispatch fusion, two variants (bitwise 0/200): slower
  (4.59/3.55 vs 2.35 ms); variants deleted.
- silent-run batch windows 2-32: no improvement; window 16 regressed the
  battery by ~+140 ms.

## Next levers

1. Re-measure m1-host with the new stack when the host returns.
2. The remaining tdt wall (398 ms) is ~104 run_step calls x ~1.4-2.4 ms;
   the per-dispatch ~0.4 ms round trip is now amortized by defer-commit, so
   the next cut is kernel-exec-side (the chains weights re-stream per step).
3. Encoder feeder remains the dominant bucket (1.21 s / 3.51 s).
