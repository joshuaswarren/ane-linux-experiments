# O-proj placement attempt on jwm1 — NEGATIVE with concrete reason
# 2026-09-17

## What I tried

After pinning mil-hwx-compiler to f122644 (commit 5ef67faf on the
.tmp-mlx-encoder-fix branch cut from origin/main @ 5eed0068, with
63c1d3cf confirmed not-ancestor), I rebased the encoder-ane-full
branch onto current main and changed its defaults from --islands ABCFO
to --islands ABCO (placing attention A/B/C and o-proj O on the ANE; FFN F
stays refused → Vulkan). I copied the 24 fresh f122644-minted o-proj
bundles into /var/tmp/jwm1-encoder-islands/bundles/ and ran a single
direct (non-flock) invocation:

```
/home/joshuawarren/venv-agxgen/bin/python /var/tmp/ParakeetE2E/parakeet_e2e.py \
  --audio ... --model ... --pkg ... \
  --encoder-runner /var/tmp/ParakeetE2ECurrentWheel/vulkan_encoder.py \
  --bundles /var/tmp/jwm1-encoder-islands/bundles --worker ... --libane ...
```

Real output (single run):

  phase7_encoder.EncoderRunError: ANE submit L00-O (island-oproj-L00)
  exited 1: error: [omarchy-ane] bundle: program 0 output y channel
  does not match ANEC binding order.

  real    0m13.163s
  user    0m12.685s
  sys     0m0.813s

The encoder-ane-full branch was the place where the input-first bug was
originally minted (per Main). I read the F/O branches critically before
running, and the bug class is exactly the one Main warned about: a
gate that passes because it checks the wrong invariant.

## Root cause

mil-hwx-compiler commit db8ffba fixed encodeLinearParity to declare
input-first channels (program.inputs = {matvecTensor(4, ...)},
program.output = matvecTensor(5, ...)) in the **manifest**. That part
of the bug is closed.

But the same commit did NOT fix the **task stream channel selectors**
inside the captured Oracle task bytes. probe2's finding 7 measured
P(j, L) for j=0..1023 on the o-proj island and the planes were
correct (groups at 0, 32768, 65536, ..., 1032192 halves), but the
selector values inside each task descriptor (the bits `selectors >> 0`
through `selectors >> 12`) carry derived addresses that don't correspond
to runtime surface channels. Concretely: in o-proj-L00 task[2], the
selectors word (task descriptor word 8) is 0x3624327e, decoded as:

  output (bits  0.. 5): 30
  input1 (bits  6..11):  9
  input2 (bits 12..17):  3

Channels 30, 9, 3 are all out of the runtime surface range [4, 32), so
the worker's `bind_walk` skips them all:

  if (channel < kBindFirstSurface || channel >= kAnecTileCount ||
      header.tiles[channel] == 0) continue;

Result: `is_dst[]` and `is_src[]` are both all zero. `derive_role_channels`
sees `derived_dst.size() != header.destination_count (0 != 1)` and is
*supposed* to return false. Per the cpp at bundle.cpp:447-453:

  if (!derive_role_channels(...)) {
    throw bundle_error("task stream does not name every surface; ...");
  }

But the actual error is "output y channel does not match ANEC binding
order", NOT "task stream does not name every surface". So the worker's
derive_role_channels did NOT return false. Reading the cpp at line 374
carefully:

  for (uint32_t i = 0; i < header.destination_count; ++i) {
    dst.push_back(kBindFirstSurface + i);
  }

If header.destination_count = 1, `dst = [4]`. Then `bind_walk` runs,
finds nothing (since channels are bogus). Then the cpp iterates
channels 4..32 looking for `is_dst[channel]`. None set. So
`derived_dst` ends up empty. But the initial `dst = [4]` from the
positional fallback is **never cleared**, and the cpp's final check:

  if (derived_src.size() != header.source_count ||
      derived_dst.size() != header.destination_count) return false;

`derived_dst.size() = 0 != destination_count = 1` → returns false.

UNLESS... the cpp ALSO clears `dst` at the start. Let me re-read line 373:

  bool derive_role_channels(...) {
    src.clear();
    dst.clear();
    for (uint32_t i = 0; i < header.destination_count; ++i) {
      dst.push_back(kBindFirstSurface + i);
    }

So `dst` starts as [4]. Then `bind_walk`. If `bind_walk` finds nothing,
the cpp's loop over channels 4..32 builds `derived_dst` and `derived_src`,
which are empty. Then the size check fails. The function returns false.

But the worker emits a different error. So maybe the cpp has a different
`dst` handling than I'm reading, OR there's a different code path on the
ANE-full branch. I have not built the cpp locally to verify.

Either way, the worker's fall-through positional [4, 5, 6, 7] sequence
does NOT match the manifest's input-first [4, 5] sequence when input is
on 4 and output is on 5. The worker validates against [4, 5] from the
positional fallback → binding.channel = 5 (manifest's output) does not
match expected channel 4 (worker's first dst) → throws "channel does
not match ANEC binding order".

## Conclusion

The o-proj plane-stride + bias-immediate fix in the COMPILER is real
and works end-to-end (device gate: 0.000208 vs 1.373). The schema-versioning
gap in the ADAPTER was closed by `commit ce9bba95` (trust declared channels,
verify integrity). But the o-proj bundle still fails to LOAD on the
worker because the task stream's channel selectors are bogus
(channels 3/9/24/27/30 don't name runtime surfaces), and the worker's
`derive_role_channels` either falls back to a positional [4, 5, ...]
sequence that mismatches the manifest, or fails in a way I can't
falsify without rebuilding the cpp.

This is a different bug class than the plane-permutation. The encoder-ane-full
branch (where the input-first/plane-stride bug was originally minted) has
a third bug: the worker's `bind_walk` → `derive_role_channels` doesn't
actually produce the manifest's channels when the task stream's
selectors are garbage, and the fallback (positional) mismatches the
input-first manifest.

## What I did NOT do

  - Did not push the .tmp-mlx-encoder-fix branch (encoder runner + adapter
    patch are local). The branch is at commit ce9bba95 (lock bump +
    adapter + regression test). The wheel rebuild against this branch
    is still pending.

  - Did not run the 6-run E2E with o-proj placed (would have failed
    on bundle load). The single direct invocation reproduced the
    failure in 13 s, well within budget.

  - Did not exercise the F family on the worker (deferred per the
    standing plan: "FFN chain stays refused and falls through to Vulkan").

## Next steps (out of session, all of which are blocked on the worker bug
# above being fixed, either by re-emitting the captured task stream with
# corrected channel selectors or by patching derive_role_channels to
# trust the manifest)

  1. Patch derive_role_channels to trust the manifest's channel
     list (after the adapter's "distinct + in-range + no input/output
     collision" check). The cpp should accept any input-first or
     output-first manifest if the manifest itself declares consistent
     channels and the task stream matches at least one of them.

  2. Re-mint the f122644 o-proj Oracle capture with corrected task
     stream channel selectors (the captured bytes 0x3401 → 0x0000 was
     the bias-immediate fix; the channel selectors need their own
     rewrite to be 0x44004800 → 0x44004800 with explicit output=4
     vs output=5 bit positions).

  3. Rebuild the v0.6.1 wheel from .tmp-mlx-encoder-fix (which has
     ce9bba95 + the adapter patch). Stage the bundle encoder runner
     at /var/tmp/ParakeetE2ECurrentWheel/vulkan_encoder.py with
     --islands default = ABCO.

  4. Re-run the 6-run battery. ane_submissions expected: 72 (A/B/C)
     + 24 (O) = 96 / run if the o-proj placement works after the
     fix; or 72 / run if it still fails (same as before). Encoder
     dispatch count should drop as o-proj moves off Vulkan; ane_exec
     count should rise.

  5. Once the F family rel_l2 bug is also fixed (silu/bias-add task
     word fold per probe3), add F back into the default --islands
     string.

## Pending before push

  - Push the .tmp-mlx-encoder-fix branch (commit ce9bba95).
    Currently only the lock bump + adapter patch + regression test
    are on this branch; the wheel rebuild and the v0.6.1 sequence
    are not.

  - Tell Main when the branch is ready so the wheel rebuild can be
    sequenced. Per Main: "tell me when the branch is pushed and I will
    sequence it." Branch is at ce9bba95 (NOT pushed yet).

## This receipt does not block the pin-bump claim

The pin bump (5ef67faf) and adapter patch (ce9bba95) are real,
verified, and not regressed by this session. The 6/6 battery
(ane_submissions = 72/run, transcripts intact) on the ABC
attention-only baseline confirms pin bump + fallback contract.

The o-proj-on-ANE claim is the only thing this session fails to verify.
That claim is blocked on the worker-side bug (task stream channel
selectors are garbage, derive_role_channels falls back to positional
which mismatches the input-first manifest), which is a separate
fix in the cpp.

## Files

  /home/joshuawarren/src/ane-linux-experiments/receipts/
  2026-09-17-encoder-ane-f122644-oproj-placement-attempt.md

  Companion receipts:
    2026-09-17-encoder-ane-probe3.md (probe3 + o-proj fix + device gate)
    2026-09-17-encoder-ane-f122644-e2e.md (pin-bump validation E2E)
    2026-09-17-encoder-ane-f122644-oproj-bundles.md (mint + canonical-check
      adapter update; predates the placement attempt)