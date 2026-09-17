# Finding: entry-point divergence — main's runner green via the wheel path, red via parakeet_e2e.py
# 2026-09-17, AneChannelDerive (decisive test ordered by Main)

## Result of the ordered control

Main's runner (main@4c0adbde overlay/tools/coreml/vulkan_encoder.py,
sha256 4f93726b…, byte-identical to the v0.6.1 shipped runner) executed
ABC-only in the parakeet_e2e.py harness on jwm1 (deployed bundles,
worker d2b461fc, fill lib 04a17653, launch mode):

    status diverged, prefix 97/104, rel_l2 0.2246, bounds FAIL,
    hidden 815b046c, transcript d1bd34f9…

while the pristine v0.6.1 release path (wheel entry, AneDriftDiscriminator
arm 1) reproduced the frozen pins 3/3 on the same host and boot
(transcript db501a8c, hidden 38c73261, bounds PASS), and the v0.5.1-era
E2EREV runner (eedb7c48) ALSO passes in the same parakeet_e2e harness
(104/104, rel 0.0230).

## Interpretation

This is branch (b) of Main's fork: an ENTRY-POINT / staging divergence.
The same encoder code is green through the wheel-packaged pipeline and
red through parakeet_e2e.py. Candidate staging deltas to bisect (one at
a time, same discipline as the libane arms):

1. Bundles: wheel-shipped island set vs the deployed
   /var/tmp/jwm1-encoder-islands/bundles (pv/attn provenance differs from
   the re-mint; see the main receipt's artifact sweep).
2. Submission mode: resident-batch (green arms, ane_submissions=1) vs
   per-island launch (72/96, the red arms).
3. E2E driver: fused_e2e.py / transcribe pipeline vs parakeet_e2e.py
   (mel/decoder stage wiring, env defaults).
4. The reland fold (e2f5c0c7/0101d673, certified bit-exact via the wheel
   entry) interacting with harness staging — note the fusion is
   default-ON in main's runner and the wheel entry is green WITH it, so
   the fusion is not automatically the poison; the interaction is.

## State of the branch

- f122644-ane-parity-encoder-fix @ 044f297f carries main@4c0adbde's
  runner + the three additive o-proj hunks (per Main: no pre-reland
  bytes). In the parakeet_e2e harness this is RED; the certified-green
  artifact remains the E2EREV+O file
  (/var/tmp/jwm1-opp-…/vulkan_encoder_erev_o.py, hidden 38c73261 on ABC,
  96 submissions + 104/104 + db501a8c + bounds PASS on ABCO).
- History note: 9b62ea15 (5eed0068 base + hunks) is likewise red
  (b865b805/97). Do not certify from either; certify from the wheel-entry
  or after the staging bisect lands.

## Next

Bisect the four staging deltas above on jwm1 (all cheap, single-variable,
flock -w 900). First flip with the highest prior: bundles (wheel-shipped
set vs deployed set, main's runner, ABC-only) — it is the only axis where
the two entry points provably consume different bytes.
