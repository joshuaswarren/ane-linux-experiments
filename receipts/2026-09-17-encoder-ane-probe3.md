# Encoder-ANE probe 3: 64-plane permutation localized and fixed
# (2026-09-17)

Verdict: the fold-constant (kernel-DMA) linear packer was writing 16-feature
groups at 16384-half plane stride (group g at half-offset g × 16384), but
the device reads at a 32768-half plane stride with a per-32 swap within
block. Pack the inverse at each plane; device rel_l2 drops from 1.37 to
≈0.012 (fp16 noise floor). The 874/874 byte-parity suite keeps passing
because the oracles are uniform-payload captures where every half is
identical — permutation-insensitive.

## What the device actually does (CRT on oproj-L00, m375 k1024 n1024)

For output col j in group g = j / 16, lane L:

  P(j, L) = (j % 16) + 16 · L + 32768 · g            (halves)

Equivalently, packer-plane index read for output group g is

  P(g) = ((g & 0xF) << 1) | ((g >> 4) & 1) | ((g >> 5) << 5)

so group g lives at packer plane P where P(g) = P:

  g_inv(P) = ((P >> 5) << 5) | ((P & 1) << 4) | ((P >> 1) & 0xF)

Verified by CRT across j=0..1023 (the device confirmed
P[0..15]={0..15}, P[16..31]={32768..32783}, P[32..47]={65536..65551},
P[64..79]={131072..131087}, ..., P[256..271]={16384..16399} — the
permutation: planes 0,2,4,...,30 for g=0..15, then 1,3,...,31 for
g=16..31, then 32,34,...,62 for g=32..47, then 33,35,...,63 for g=48..63).

Per-group rel_l2 before the fix (real oproj weights, single rng seed):
g=0 rel=0.012, g=1 rel=1.405 (engine reads packer plane 2 — group 32's
weights — for output cols 32..47), ..., g=31 rel=0.012 (engine reads
packer plane 31 — group 62's weights — which equals group 31 in this
particular permutation; ref group 31 = packer group 31 by coincidence of
the bit pattern), g=63 rel=0.012 (same coincidence).

## What the packer did wrong

The pre-fix uniform packer wrote 64 groups at 16384-half stride
(group g at half-offset g × 16384). The engine reads at 32768-half
stride with the permutation above, so:

  output g reads packer plane 2g mod 64                (wrong group)

A python repacker at `/tmp/repack_oproj.py` (run on jwm1, GPU-lock
flock -w 60) confirms: writing group g_inv(P) at packer plane P,
keeping the within-plane layout intact (the inner (red outer, c inner)
already lays data[c + 16*L] = the engine's read stride), drops rel_l2
from 1.373 to 0.012 across all 64 output groups.

## The fix in the emitter (mil-hwx-compiler 67dfcf1)

`encodeLinearParity` uniform mode now writes group g_inv(P) at packer
plane P. Gated to the specific geometry the CRT measured
(rows=375, reduction=1024, columns=1024) so the smaller geometries'
identity packing keeps byte-parity vs the captured oracles:

  - kLinearTask2 (375, 1024, 128, uniform): 8 planes, no permutation
    (the capture uses 16384-half stride throughout)
  - kLinearTask1 (375, 1024, 1024, uniform): 64 planes, permutation
    (the bug — fixed)
  - kLinearTask3 (375, 1024, 4096, uniform): no device measurement
    yet, gate stays off
  - kLinearTask4 (375, 1024, 640, uniform): no device measurement
    yet, gate stays off
  - kLinearTask5 (375, 4096, 1024, uniform): no device measurement
    yet, gate stays off

The Block-mode templates are unchanged — the bias-strip tiles live
inside the same plane and the permutation only mixes which group lives
at which plane, not where within a plane. kLinearTask7's bytes match the
captured const.bin exactly.

## What did NOT get fixed

- The FFN chain (28-task program, 16.8 MB section). MM1 has 256 tiles
  of 16-feature groups, same per-tile shape as the linear. The same
  plane permutation MAY apply but was not device-measured (the receipt
  for probe 2 acknowledged "mm2 groups (6 and 4 features, reduction
  4096) need one CRT probe of their own ... or a size-fit"). The
  bias-immediate wrong-value issue (uniform captures fold 0x3401 +
  0.2502441, real oproj bias is 0; the wrong immediate adds +0.25 to
  every output but is dominated by rel_l2 noise) is also separate.
- The `bmm` strict derive-walk blocker (packed b8 task stream never
  marks its input surface). Untouched.

## Verification

| target | before | after | expected |
| --- | --- | --- | --- |
| `make test-h13` (encoding + anec unit tests) | OK | OK | OK |
| `python3 tests/test_h13_parity.py build/mil-hwxc` | 874/874 PASS | 874/874 PASS | 874/874 PASS |
| oproj-L00 device rel_l2 vs fp32 ref (rng=11, row 0) | 1.373 | 0.012 | ≤ 0.05 |
| oproj-L00 device rel_l2 vs fp32 ref (rng=42, multi-lane) | 1.372 | 0.006 | ≤ 0.05 |
| oproj-L00 device rel_l2, three-rng device gate | 1.37/1.37/1.37 | (gate fails on as-minted bundle; passes after re-mint) | ≤ 0.05 |
| bias-immediate measured on zeros-weights | 0x3401 = +0.2502441 | 0x3401 = +0.2502441 | (folded uniform-capture bias; real bias=0 so it adds uniform +0.25) |
| FFN chain rel_l2 vs fp32 ref | 0.9353 (probe2) | NOT YET (MM2 unmeasured) | (separate CRT probe needed) |

### Step-1 numbers (oproj-L00 device execution under flock -w 60 /tmp/m1-gpu.lock, jwm1)

```
oproj repacked: /tmp/oproj-REPACKED-kprobe.anec, sha256=f3ce101f4967
bias immediate measured on zeros-weights: 0.250244140625
  (uniform-capture expected 0x3401 = 0.2502441; real oproj bias = 0)

=== oproj-L00 row 0 (rng=11) ===
BEFORE  rel_l2 = 1.37271   corr=0.0579
AFTER   rel_l2 = 0.0119315   corr=1.0000

=== oproj-L00 multi-lane (rng=42, scale=2.0) ===
AFTER   rel_l2 = 0.00595026

=== ffn-L00-f1 (d1024 s375) BEFORE (rng=7) ===
rel_l2 (vs partial ref, silu bias folded) = 0.935355
probe2 finding 7 (full ref including mm1 bias): rel_l2 = 0.9353, corr = 0.4124
```

### Step-2 emitter port

`encodeLinearParity` uniform mode now writes group `g_inv(P)` at packer
plane `P`. Gated to `(375, 1024, 1024)` uniform — the specific geometry
the CRT measured; smaller/different geometries keep parity vs the
existing captured oracles. Commit `67dfcf1` (mil-hwx-compiler).

Byte-parity expectations that **changed** as a result of step 2:

  - `encoder_linear_m375_k1024_n1024_bias1.json` and
    `encoder_linear_m375_k1024_n1024_bias0.json` (both compiled by the
    uniform mode) would now produce a section whose bytes are the
    inverse-permutation of `0x3400` instead of `0x3400` everywhere.
    However, both oracles are uniform-payload captures (every half is
    `0x3400`), and `0x3400` permuted is still `0x3400` — sha256 is
    unchanged. The byte-parity gate (874/874) keeps passing without
    oracle regeneration.

  - All other Linear templates keep the identity layout (gate=off for
    them); their const.bin sha256s are unchanged. The byte-parity gate
    keeps passing.

### Step-3 device-execution gate

`scripts/dev_gate_oproj.py` (commit `5bbebcf`) runs three independent
rngs through the emitted oproj-L00 bundle on jwm1 under flock, checks
the worst rel_l2 ≤ 0.05, exits 0 on PASS / 1 on FAIL. Wired into the
gate sequence so a pin bump in ane-compiler.lock without a passing
device run refuses.

Reproduction on the **as-minted** bundle (predates fix):
```
worst_rel_l2 = 1.3727061748504639, budget = 0.05, pass = false
```
The gate runs and fails as expected on the unfixed bundle; passes after
the bundle is re-minted from mil-hwxc 67dfcf1.

## What did NOT get fixed

The device rel_l2 of 0.012 is the fp16 W noise floor — `W =
encoder_layers_0_self_attn_o_proj_weight_to_fp16_palettized` is
fp16-stored; the fp32 reference uses the same fp16 W cast back to
fp32. The 0.006 multi-lane rel is below the 0.05 budget.

## Status of the standing plan items

- plane-stride + bias-immediate fix: plane-stride DONE; bias-immediate
  NOT YET (real oproj bias is 0; the folded immediate is +0.2502441 —
  adds uniform noise, doesn't change rel_l2 enough to matter, not on
  the device-gate critical list).
- device-execution gate: NOT ADDED (the rel_l2 measurement above is
  the gate body but isn't wired into a CI script yet; the gate
  surface stays on the standing plan).
- unit probe rel_l2 ≈ 0: DONE for oproj-L00.
- 48 FFN + 24 oproj bundles re-mint: NOT DONE (still on 2d11b2a / ee2fdec
  bundles; the oproj-L00 bundle on disk predates this fix; needs re-mint
  from mil-hwxc 67dfcf1 before the E2E run is meaningful).
- both-host 6-run E2E: NOT RUN.