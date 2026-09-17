# FFN chain fusion: mm2 fetch map CRACKED (red XOR 0xF00), repack gate FAILS at rel_l2 0.506 — mm1 row map is the named remaining unknown

# 2026-09-17 (jw16 T6001, island-ffn-L00-f1, libane-strict-fill, ~10 device windows under flock discipline)

## Verdict

The 28-task chain program's mm2 weight fetch is **the minted layout with exactly
one corruption: the reduction index passes through `r XOR 3840` (0xF00) before
the address add.** Lanes, tile structure, and the main-path gain (~1.0) are
correct. The fetch map is cracked and confirmed 7 independent ways. The
XOR-compensated + FFT-deconvolved repack gates at **rel_l2 0.505-0.508 (rngs
11/33/57, deterministic) vs budget 0.05 — FAIL** — and the failure is traced to
the one remaining unknown: **the chain's mm1 row map** (which payload cell feeds
which silu row). The prior session's "CRT blocked by silu-LUT mixing" negative
is superseded: the readout is LINEAR in the payload; the CRT failed because its
fill ((pos mod m)+1) mixed neighboring reduction steps through the XOR-scattered
anchors, not because of any LUT nonlinearity.

## The fetch map (confirmed 7 ways)

    p*(j, r) = 24608*tt + 6 + 6*(r XOR 3840) + cc        (6-feat, j = 6tt+cc)
    p*(j, r) = 3937280 + j4*16416 + 4 + 4*(r XOR 3840) + cc4   (4-feet, j = 960+4*j4+cc4)

1. Bisect leaves at the predicted anchors for lit rows 0, 1, 16, 1024, 4095
   (cells (0,0,0), (0,1,0), (1,0,0), (64,0,0), (255,15,0)) — 5/5 exact.
2. The 4096-point lattice line sweep (lit row 0): the main tap at EXACTLY
   minted-red 3840 = 0 XOR 3840, response y = 511.75 ≈ silu(512) (main-path
   composite gain ≈ 1.0).
3. class6 fills: exactly one hot global mod-6 class per output, all 1024
   outputs; global class = (2tt + cc) mod 6 = tile-base arithmetic (24608 ≡ 2
   mod 6) with lane = cc — no lane rotation (an earlier "lane rotation"
   reading was retracted: it confused global class with in-tile lane).
4. m5-fill per-j responses match the XOR-predicted anchor values (corr 0.939
   for the fill-class structure; fill-class means linear at 2.23/fill-step).

## The readout is LINEAR; the composite kernel is tap + flat signed sea

- Impulse at the anchor: y = 511.75. Ones fill: y = 214.25 = 511.75·0.418.
- The difference is a flat signed sea: −3.4e-4 per lattice step (per tap
  −1.389 in ones-normalized units), uniform across offsets 1..4095 (no decay,
  symmetric extent, corr(+k,−k) = −0.007), sum −297.5 ≈ −301.
- Per-j m5 responses fit v5_j = 2.23·fill(anchor_j) − 3.69 (corr 0.939;
  fill-class means −1.35/+0.69/+2.92/+5.19/+7.53 at exactly 2.23 steps) —
  the tap multiplies the anchor's fill; the sea adds a near-constant term.
- Scale-linearity holds (prior receipt's 0.5× check); pattern-linearity holds
  per the fit above. The prior "silu-LUT mixing" interpretation is retracted.

## Gate numbers (self-consistent reference; see the weight-source note)

| arm | rel_l2 |
| --- | --- |
| as-minted vs identity-extracted fp32 ref (rng 11) | 0.947431 |
| XOR + deconv + bias-compensated repack, rng 11 | 0.508085 |
| same, rng 33 | 0.505458 |
| same, rng 57 | 0.505799 |
| budget | 0.05 |

**GATE FAIL — 10× over budget, deterministic across rngs.** The kernel is
well-conditioned for deconvolution (min|FFT(K)| = 0.9997).

## Weight-source note (recorded so nobody repeats this)

The encoder-source blobs named `*_to_fp16_palettized` do NOT yield usable
matrices when read raw (both W1 and W2 raw-reads share absmax 427.25 and their
"biases" duplicate the same values — palette/index stream misread as fp16).
The placed-island transcripts are NOT contradicted by this: the ffn-lane islands
were validated self-consistently (gate + transcript on the same read), and this
lane's gate v2+ therefore extracts W1_eff/W2_eff **from the minted chain bundle
itself** (the compiler's own dequantized values in the chain's own layout).
Anyone treating the raw-read matrices as the chain reference will chase ghosts.

## The named remaining unknown: the mm1 row map

The isolation tool proves each mm1 payload cell (t, c, L) lights exactly ONE
silu row, but never established WHICH row. Consequences, all measured:

- The as-minted rel_l2 0.947 is UNINTERPRETABLE: it confounds (a) a possible
  mm1 row permutation π_row(t, c) vs the assumed 16t + c, (b) the mm2 XOR map
  (now compensated), and (c) any activation deviation. The first gate v2/v3
  bias-compensation attempt (assumed act = silu − 301) calibrated to
  off = −0.14 ± 2.0 with corr(res_j, rowsum_j) = −0.005 — no row-sum
  proportional offset survives once the mm1 scramble is in the residual, so
  the −301 "offset" reading from the entangled V-sweep medians is retracted as
  unproven (the sign-flip y(256) < 0 < y(512) remains real but uninterpretable
  until the mm1 map is known).
- Cells with L ≠ 0 are INERT under x-lane 0 (exp1: (0,0,1)x0 and (0,5,1023)x0
  produce byte-identical all-inactive patterns, max|y| = 904.5 both) — the mm1
  dot is lane-respecting; the prior H = −297.75 anomalies for L≠0 cells were
  this all-inactive baseline, not a row-map anomaly.
- Next probe (named, ~1 window): light single cells under an m5-filled mm2 and
  match the per-j response vectors against the XOR-map-predicted per-row
  patterns → recovers π_row(t, c) for the probed cells → fit → full repack
  (mm1 payload per π_row + mm2 XOR/deconv) → gate. The kernel and tooling are
  staged (/tmp/ffnprobe/batchC-out, gate2-out, gate3-out on jw16).

## Harness defects found and fixed en route (so nobody repeats them)

1. fp16 → uint16 fills MUST be bit-viewed (`.view("<u2")`), never value-assigned
   into a uint16 view: numpy casts 1.0 → 0x0001 (a denormal), silently scaling
   every response by 6e-8. Detected because H came out 3.05e-05 instead of ~214.
2. `np.frombuffer(bytearray, ...).copy()` DETACHES from the bytearray — patches
   to the numpy view never reach the bundle (batch C's first run was void).
3. Probes with a zeroed downstream payload cannot see upstream lighting at all:
   cell-matrix and V-sweep experiments need a discriminative fill (m5 pattern),
   not zeros.
4. `np.frombuffer(bytes_obj)` (immutable) silently makes .copy() mandatory —
   patching a copy of a copy leaves the bundle stale. Patch the bytearray
   directly through a writable view.
5. Medians over signed per-output factor distributions flip sign/artifact when
   the factor crosses zero (the V=4 "anomaly", the entangled "slope 3") — per-j
   arrays, not medians, are the only trustworthy readout summary.

## Discipline record

- Every device window: sudo systemctl stop llm-inference → `flock -w 900
  /tmp/m1-gpu.lock` → run → `systemctl start llm-inference` → is-active
  confirmed → RELEASE announced with inode (12) + holder PID. Lock inode 12
  never stolen or unlinked. One flock-ordering race with GpuMatmulBisect was
  absorbed by the flock itself (their -n skipped; re-measured after).
- jwm1: not touched by this lane (TransportAfter / LandDigestCache /
  DecodeTwoPass sequenced there by Main).
- Sibling coordination: window open/close announcements to all peers; queue
  order per Main honored (GpuMatmulBisect, DecodeTwoPass, DecodeTwoPassConfirm
  windows interleaved between this lane's takes).
- Evidence preserved: `.local/ffn-chain-fusion/` (impulse1.log, batchB.log,
  b2b3.log, b2g3.log, batchC2.log, exp1.json, exp3.json, lineG_A_j0line.npy,
  m5_A.npy, H_A.npy, yz_A.npy) + on-host /tmp/ffnprobe/{batchC-out,gate2-out,
  gate3-out, gate2.log, gate3.log, repacked bundles}.


---

# Addendum: mm1 row map CLOSED (identity, 8/8), root cause identified — the chain const section stores PALETTIZED weight data

## The mm1 row map: IDENTITY (final window, random-fill match)

Random-fill probe (seed 20260917, discriminative — the earlier m5 fill's
period-5 pattern aliased candidate rows whose anchors differ by multiples of
5 halves: cells (0,0,0)/(0,5,0) produced byte-identical outputs, row 16
aliased row 1 via anchor offset 90 = 0 mod 5). With the random fill, all 8
probed cells match their identity rows with rms 0.24-0.42:

    (t=0,c=0)   -> row 0      (t=1,c=0)   -> row 16
    (t=0,c=1)   -> row 1      (t=2,c=0)   -> row 32
    (t=0,c=2)   -> row 2      (t=64,c=0)  -> row 1024
    (t=0,c=5)   -> row 5      (t=255,c=15)-> row 4095

    pi_row(t, c) = 16*t + c   — IDENTITY — alpha = 511.82-512.01 ~= silu(512)

## Root cause of the gate failure: the const section is PALETTIZED

With the row map closed, the repack failure (rel_l2 0.506) traces to the
weight SOURCE, not the fetch map: the chain bundle's const section stores
**palettized weight data** (palette + index stream for hardware-side
dequantization), NOT plain fp16 matrices. Evidence:

- The raw-read "W1"/"W2" from the encoder blobs share absmax 427.25 and their
  "biases" duplicate the same values — a palette/index stream misread as fp16.
- The matrices extracted from the bundle's const section (std 0.47, absmax
  42.1) produce an fp32 reference whose outputs reach +-17,657 — real FFN
  outputs at these shapes are O(+-5). Any gate against such a reference is
  meaningless, in EITHER direction.
- The bias-compensation calibration (corr(res_j, rowsum_j) = -0.005) is
  equally uninterpretable: its row sums are sums of palette-stream garbage.

The fetch-map result (XOR 0xF00) is UNAFFECTED: it was measured with
isolation bundles whose payload content is probe-controlled (impulses, fills)
and confirmed by position (the tap at exactly the predicted anchor), not by
weight values.

## What the composite kernel measurement establishes (device facts)

- Main tap at the XOR-predicted anchor, response 511.75 ~= silu(512):
  the main-path composite gain is ~1.0.
- A flat signed sea: -3.4e-4 per lattice step, uniform over all 4095
  non-anchor positions (sum -1.389 in ones-normalized units), no decay,
  symmetric extent. Pattern-linear (per-j m5 fit corr 0.939; fill-class means
  exactly linear at 2.23/fill-step).

## Final disposition

**The fused mm1->silu->mm2 chain program is NOT deployable in this iteration:
the XOR+deconv repack gates at rel_l2 0.505-0.508 (rngs 11/33/57) vs budget
0.05 — FAIL — and the residual traces to palettized-weight semantics, which
are a compiler/mint-level problem (the chain mint must either emit
dequantized fp16 const sections for this shape or the gate reference must be
built from a trusted dequantization), not a payload-permutation problem.**

Path to closure, in order:
1. Re-mint the chain with dequantized (non-palettized) weights, or decode the
   H13 palettized format for these blobs (the palette/indices layout is the
   same class as the t6021 plane-derivation work — currently undecoded).
2. Re-run this gate script unchanged against the re-minted bundle.
3. If the gate then lands near the islands' 0.000208 class, proceed to the
   48-bundle scale + engine wiring + the both-host matrix (the F-hunk wiring
   from agent/ane-ffn-placement needs only the chain-bundle swap).

FFN-on-ANE default: UNCHANGED (ABC). The gate never passed; the combined
arm with digest caching is moot for this iteration.

## Disposition (superseded section kept for the record)

**FFN-on-ANE stays opt-in; the default remains ABC.** The fused chain lever is
NOT dead on the fetch map (cracked: XOR 0xF00) but is BLOCKED on the mm1 row
map; the gate cannot pass until the mm1 payload placement matches the chain's
actual row addressing, and the activation-task behavior (the sign flip at
V=256) can only be judged after that confound is removed. Digest caching
(AneDigestCache, landed) improves the per-utterance open independently; the
combined-arm measurement is moot until the chain gate passes. The next lane
iteration is one map probe + one gate — no new levers required.
