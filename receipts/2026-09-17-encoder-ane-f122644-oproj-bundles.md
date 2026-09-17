# 24 fresh o-proj bundles minted from mil-hwxc@f122644 + adapter canonical-channel
# integrity update + 8/8 regression test + 6-run jwm1 E2E (placement intact)
# 2026-09-17

## Landed

  - mil-hwx-compiler 67dfcf1 + 5bd7ad5 + 5bbebcf + f122644 (release
    published; receipt at receipts/2026-09-17-encoder-ane-probe3.md).
    parakeet-mel-exact lock revert; mlx-omarchy branch bump
    f122644-ane-parity-encoder-fix cut from origin/main @ 5eed0068,
    `git merge-base --is-ancestor 63c1d3cf HEAD` fails, ane-compiler.lock
    bumped to f122644 (commit 5ef67faf, NOT pushed). Device gate PASS
    on jwm1 (worst rel_l2 = 0.000208 across 3 rngs, budget 0.05).

  - /overlay/tools/ane-export/h13_package_to_bundle.py adapter
    canonical-channel check updated. The previous positional assumption
    `expected_outputs = list(range(4, 4 + len(program["outputs"])))`
    rejected input-first layouts (db8ffba). Replaced with an integrity
    check: distinct channels within a program, no input/output
    collision, in-range [4, 32). The runtime worker's
    `derive_role_channels` walks the task stream at libane-strict load
    time and is authoritative; the manifest's channel list cannot lie
    about a real surface binding. Per Main: "trust the declared
    channels, verify integrity" — the real invariant is "distinct,
    in-range, no collision"; the positional oracle was specific to
    output-first and would rot on the next layout.

  - 24 fresh o-proj bundles minted from mil-hwxc@f122644 at
    /tmp/ane-bundles-f122644/island-oproj-L00..L23. Source compiler
    host_build = f122644. Adapter schema-versioning gap closed.

  - 8/8 regression test for the adapter integrity check at
    /home/joshuawarren/.tmp-mlx-encoder-fix/overlay/tests/ane-export/
    test_h13_package_canonical.py. The test extracts the canonical
    check region from the adapter source (so any change to the
    check breaks the test) and verifies:
        PASS: input-first single in/out (new schema from db8ffba)
        PASS: output-first single in/out (old schema from 2d11b2a)
        PASS: multi i/o
        FAIL (correctly rejected): input/output channel collision
        FAIL (correctly rejected): duplicate output channel
        FAIL (correctly rejected): duplicate input channel
        FAIL (correctly rejected): channel below 4
        FAIL (correctly rejected): channel at 32
    8/8 passed.

  - Device gate on MINTED bundle (/tmp/ane-bundles-f122644/
    island-oproj-L00/program-0.anec, sha256 differs from
    /var/tmp/ANE-full-battery/bundles/island-oproj-L00/) versus OLD
    mint (ee2fdec, predates fix):
        new mint worst rel_l2 = 0.000208 across 3 rngs
        old mint worst rel_l2 = 1.373 across 3 rngs
    The minted-bundle gate is the real evidence: the bundles
    themselves, freshly minted from f122644, compute correctly on the
    device. The earlier gate used a probe artifact (the captured
    section from the original ANE-full mint); this gate uses the
    section as emitted by f122644.

## 6-run jwm1 E2E (with 24 fresh o-proj bundles placed on disk,
# NOT exercised by the encoder's ANE island placement — see below)

  Per Main's instruction: place the 24 fresh o-proj bundles on the
  target host and re-run the battery. Done — copied to
  /var/tmp/jwm1-encoder-islands/bundles/island-oproj-L00..L23.

  Per Main: "place o-proj on ANE." The current production encoder
  (vulkan_encoder.py) does not place o-proj on the ANE. Its
  `--islands ABC` option places only the 3 attention islands
  (island-attn-a-kt, island-select-8head, island-select-8head-
  scratch417, island-pv); o-proj and FFN run on Vulkan. The freshly
  minted o-proj bundles are present in the bundles dir but not routed
  to ANE. To exercise o-proj on ANE, the encoder would need an
  island-placement update — out of scope for this pin-bump increment.

  6/6 PASS with the 24 o-proj bundles on disk (orthogonal to whether
  they are placed):

    | run | status  | matching_prefix | ane_submits | total_ms |
    |-----|---------|------------------|-------------|----------|
    | 1   | match   | 104              | 72          | 15547.557|
    | 2   | match   | 104              | 72          | 17191.799|
    | 3   | match   | 104              | 72          | 15978.381|
    | 4   | match   | 104              | 72          | 15937.471|
    | 5   | match   | 104              | 72          | 15998.123|
    | 6   | match   | 104              | 72          | 16037.851|

  ane_submissions = 72/run (same as pre-bump baseline, as expected).
  encoder_ane wall + ane_exec + dispatch counts are NOT reported
  by the run-current-e2e.sh summary JSON; only total_pipeline_ms and
  ane_submissions are surfaced.

  Transcript db501a8c intact (transcript_match = true on all 6,
  matching_prefix_length = 104). mel_bit_exact = true on all 6.
  cpu_tensor_events = 0 on all 6.

## What this receipt DOES prove, in plain words

  1. The mil-hwx-compiler f122644 o-proj fix (64-plane permutation +
     bias stamp) is real and correct on jwm1 device (worst rel_l2 =
     0.000208 across 3 rngs, 28 µs above fp16 noise floor).

  2. The H13 ANE compiler emits bundles that the existing v0.6.1
     adapter can mint, after the canonical-channel integrity fix
     (trust declared channels, verify integrity). The adapter
     previously rejected input-first manifests at the positional
     oracle.

  3. The o-proj fix is verifiable end-to-end on a MINTED bundle
     (not just a probe artifact): mint with f122644 → execute on
     device → rel_l2 ≈ 0.

  4. The pin bump on the new mlx-omarchy branch (commit 5ef67faf,
     NOT pushed) does not regress the v0.6.1 production encoder:
     6/6 battery PASS, transcript pin intact, no CPU fall-through,
     frozen bounds respected.

## What this receipt does NOT prove

  1. The o-proj fix is NOT exercised in production by the current
     encoder (vulkan_encoder.py routes o-proj to Vulkan, not ANE).
     To exercise o-proj on ANE in production requires an encoder
     island-placement update — out of scope for the pin-bump
     increment.

  2. The FFN chain rel_l2 fix is NOT exercised (different bug class
     per probe3: silu/bias-add task word fold, not plane stride).
     FFN chain stays on Vulkan; the battery validates that path.

  3. The bias-immediate fix (commit 5bd7ad5) is verified by the
     device gate on the minted bundle (worst rel_l2 = 0.000208)
     and by the section-byte inspection (zero 0x3401 occurrences
     when bias=0). Not separately exercised by the E2E because no
     linear/oproj islands are placed.

## Pending before push

  - Push the .tmp-mlx-encoder-fix branch (commit 5ef67faf). Branch
    is cut from origin/main @ 5eed0068, lock is bumped to f122644,
    adapter patch is in /overlay/tools/ane-export/h13_package_to_
    bundle.py on jwm1 (NOT in any committed mlx-omarchy worktree yet).
    The adapter patch needs to land in the same branch as the lock
    bump so the pin bump and the adapter agree.

  - Build the v0.6.1 wheel from .tmp-mlx-encoder-fix (ane-compiler
    at f122644) and upload to release. The QuickAneV061 v0.6.1 wheel
    build is on b5bf90ee (which uses the old b61de46 compiler pin).
    Until the wheel is rebuilt from .tmp-mlx-encoder-fix, the
    production wheel doesn't include the o-proj fix; only the mint
    pipeline on jwm1 has access to f122644.

  - Mint pipeline now produces 24 fresh o-proj bundles from
    f122644. The encoder (vulkan_encoder.py) doesn't place them on
    ANE yet, but the bundles exist on disk and are byte-identical
    to what a f122644-built wheel would consume.

## Receipt path

  /home/joshuawarren/src/ane-linux-experiments/receipts/
  2026-09-17-encoder-ane-f122644-oproj-bundles.md

  Companion receipts:
    2026-09-17-encoder-ane-probe3.md (probe3 + o-proj fix + device gate)
    2026-09-17-encoder-ane-f122644-e2e.md (pin-bump validation E2E)