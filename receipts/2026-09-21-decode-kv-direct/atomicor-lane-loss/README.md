# atomicOr lane-loss reproducer — Apple Vulkan (Honeykrisp)

Symptom: a disjoint-half `atomicOr` pair into one 32-bit SSBO word
sporadically loses a lane on Apple M1 / M1 Max under Asahi Mesa Vulkan.
Nondeterministic across identical runs; frequency grows with invocation
count.

## Contents

- `atomic_lane.comp` — minimal standalone compute shader: 256-thread
  workgroups, invocation i atomicOrs one 16-bit half into word i/2 of a
  buffer pre-filled 0xBAD0BAD0. Expected final word
  `0x(0400+2w+1)<<16 | 0400+2w`. Any 0xBAD0 half remaining = lost lane.
- `ropediag7.py` — end-to-end repro through the shipped mlx wheel:
  `python ropediag7.py` on a bf16-capable build with the packed-word
  rope store prints NaN / wrong-value rows for the passthrough shapes
  (one element per invocation) while full-rotation shapes (two stores
  per invocation, adjacent words) pass. Same shape passes and fails on
  different runs - the smoking gun for a race, not an addressing bug.

## Suggested driver for atomic_lane.comp

Any existing Vulkan harness works: one descriptor set binding the output
SSBO (storage buffer, std430), push constant `n = 65536`, fill the buffer
with 0xBAD0BAD0, dispatch ceil(n/256) groups of (256,1,1), read back and
check every word. Loop the dispatch a few hundred times without
refilling between iterations only after the first failure mode is
confirmed (a lost OR is sticky once the word is correct: a lost lane
shows only while stale 0xBAD0 halves remain, so refill each iteration).

Context: found while landing the bf16 producer-direct KV cache write
(receipts/2026-09-21-decode-kv-direct/receipt.md) - the packed bf16 rope
output store used disjoint-half atomicOr pairs and produced NaNs /
3.4e38 garbage nondeterministically on the passthrough branch.
