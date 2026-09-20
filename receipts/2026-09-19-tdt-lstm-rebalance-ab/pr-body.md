## What

The GPU TDT loop kernel's LSTM chains ran only on threads 0-639 (384 of 1024 idle for the whole section) with all four gate folds inline per lane thread. The 2560 (lane, gate) fold items now map 2-3 per thread across all 1024 threads (512x3 + 512x2), and each gate pre-activation stages through a bit-exact carrier before the unchanged gate-pairing phase reads it back: gate 0 native fp16 in s_relu, gate 1 float carrier in s_bval, gate 2 floatBitsToUint carrier in s_bidx, gate 3 float carrier in s_h1 (read back before the same thread overwrites the slot with the layer's h1). Fold, bias, pairing, cell, argmax, control, barrier count, threadgroup budget (26208 B actual / 28768 requirement / 32768 M1 limit) and the joint head are untouched.

## Exactness

- test_tdt_lstm_rebalance.py 3/3: exact-once item coverage + measured balance; bit-exact round trips of all three carrier forms incl. zero/subnormal/max edges; budget unchanged.
- glslangValidator compiles the rendered kernel clean.
- Device A/B (jw16, interleaved, one corrected-libmlx wheel 0.32.3.dev202609192322+925cfa64 / libmlx16 bbad05a26b32a8ee, two pkg overlays differing by exactly vulkan_tdt_loop.py, warm + 6 measured per arm): 6/6 pins-EXACT EVERY run BOTH arms — 104/104, transcript db501a8c, encoder_hidden 38c73261, mel bit-exact, control gpu-loop, fallback null. Decode pins 7da83f06/7fd25a86 hold.

## Performance (same-host A/B only; no cross-host or divisor claims)

tdt_decode median base 974.0 ms vs candidate 849.2 ms — delta -124.8 ms (-12.8%), per-run ranges fully disjoint (base 962.9-988.9, cand 840.4-866.0).

## Byte provenance (per review requirement)

Measured candidate revision IS the rebased tip 557db2de: vulkan_tdt_loop.py blob 9047bbb7 identical pre-rebase (1b82d4aa) and post; base arm bytes identical under either main tip (git diff 925cfa64 9e18c3a8 -- overlay/tools/coreml/ is EMPTY). Extracted-and-executed pkg files hash-bound to the named revisions; vulkan_decoder_step.py byte-identical across arms. Full table + raw JSON locations: receipts/2026-09-19-tdt-lstm-rebalance-ab.md (ane-linux-experiments @ 0920b4b).

## Gates for merge

Merge pending independent source/receipt review per Main. No GPU recert outside the queue; GPU owns the next slot.
