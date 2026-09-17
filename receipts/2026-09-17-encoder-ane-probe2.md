# Encoder-ANE probe 2: channel/stride mapping exonerated; parity gate was
# byte-only; weight-fetch layout measured by device readout (2026-09-17)

Verdict: **the input-first channel mapping, strides, and header geometry are
CORRECT.** Probe 2 exonerates libane, the omarchy-ane driver submit path, and
the worker staging for the FFN/oproj divergence. The wrong function is a
weight-fetch addressing property of the folded-constant (kernel-DMA) path,
which no runtime before today ever executed at scale. The "parity 874" gate
never ran a device. A device-readout experiment now localizes the defect to
the section-fetch base/interleave and gives the tool to finish it.

## What was proven (all on jwm1, `/tmp/m1-gpu.lock`, libane-strict 6fa243a)

1. **Worker == libane-direct, byte-identical** (`probe_libane_direct.py`):
   island-ffn-L00-f1 through the worker CLI and through ctypes
   `__ane_send/ane_exec/__ane_read` with role-index binding produce
   identical outputs. Runtime binding exonerated.
2. **Channel order is irrelevant**: swapping the oproj island to
   output-first (word8 selectors 4<->5 + header tiles/nchw swap,
   `swapfirst.py`) gives a bit-identical (wrong) output. The
   assignment's "emitter-side swap to output-first" is moot.
3. **Task words == Apple capture**: island-oproj-L00 (3 tasks) diffed
   word-by-word against
   `receipts/2026-09-16-compiler-leftover/oracles-round1/encoder_linear_m375_k1024_n1024_bias1.json`
   — zero register-record diffs. Only word0 bit22 differs (the bindTasks
   0x40 stamp; Apple input-first captures carry 0) — tested inert
   (`bit22.py`: FFN rel 0.9353 and oproj rel 1.3706 unchanged).
4. **Section bytes == model**: the minted FFN constant section depacks to the
   true normalized.bin weights exactly (red-outer tile model, 100% match,
   bias strips = true zeros). Header nchw/tiles == Apple's captured tensor
   descriptors ([1,1,375,1024] strides [768000,768000,2048,2]).
5. **"parity 874" is byte-parity, not device numerics**: `make test-h13`
   and `tests/test_h13_parity.py` only compile and compare words/sections
   against the captured oracles (`assert_tasks`/`assert_constants`). No
   input-first or packed-constant program had ever executed on this runtime.
   The working A/B/C islands are output-first AND kernel-fetch-free
   (krn 2-16 KB); every broken island fetches real packed weights
   (ffn krn=16.8 MB, oproj krn=2 MB).
6. **The fetch+compute path is fundamentally faithful** (`fetchfid.py`,
   `finalprobe.py`, `dbg_pat.py`): with the section filled with fp16 1.0,
   y = rowsum(x) exactly per row (row mapping 375/375 correct, fp16-noisy);
   with fp16 patterns {1,2,3} the output reads back the section values
   plus a constant bias immediate of 0x3401 = 0.2502441 (the uniform-oracle
   bias pattern — the compiled island folds the CAPTURE's bias immediate,
   never the real bias; real bias is zero so this only offsets).
   NOTE: earlier "one-hot gives constant 0.25" anomalies were invalid u16
   patterns (subnormal fp16), not runtime misbehavior.
7. **Real weights still compute the wrong function**: rel_l2 0.935 (FFN),
   1.371 (oproj) vs fp32 normalized.bin references; invariant to within-tile
   red_outer/col_outer permutation, bit22, and channel swap.
8. **Device readout of the effective fetch map** (`crt3.py`, `crt4.py`,
   `lanefn.py`): section filled with fp16 (i mod m)+1 for m in
   {3,5,7,11,13,17,19}; one input lane L set on all rows; output row 0
   read back across output lanes j. Calibrated readouts (bias measured
   per-run from a zeros-weights control; expect col = pattern + 0.25):
   for oproj-L00 (m375 k1024 n1024 uniform linear), the engine fetches
   w[j, L] at **P(j, L) = 32768·(plane of group j//16) + (j mod 16)
   + 16·L** — measured exactly: groups 0,1,2 at 0, 32768, 65536
   (32 KB-half = 64 KB planes per 16-output-feature group), lanes at
   stride 16 (L=1023 → +16368, no wrap), features contiguous within 16.
   The compiler instead packs groups CONTIGUOUSLY at 16384-half stride
   (16 KB) — **the fetch reads group 2g where group g was written** —
   a factor-2 plane-stride mismatch. The section size already knows:
   oproj krn = 2,097,152 halves; the packer fills exactly half.
   Caveat: CRT positions for far groups (g >= 16) came out inconsistent
   (single-residue ±1 flips shift by >= 233k) — re-run with redundant
   mods/error correction before trusting the far-plane formula; the
   near-group (g<=2) and lane-stride structure is multi-verified.

## Next session (minutes, not hours)

- Re-run the CRT with error correction: for each (j, L) read residues under
  7 mods PLUS 2 verification mods (23, 29); discard/re-read points whose
  CRT disagrees. Then fit the far-group plane formula exactly (expect a
  32768-half plane per 16-feature group with a to-be-determined far-group
  interleave — near groups are plain 32768·g).
- Repack the linear section with the fitted formula (python patcher as in
  `/tmp/fixstride.py`), re-run `probe_oproj.py` — expect rel_l2 ~1e-3.
- Apply the same plane-stride to the chain: mm1 groups are the same shape
  (16 features, reduction 1024) → 32768-half planes; mm2 groups (6 and 4
  features, reduction 4096) need one CRT probe of their own (same tool,
  chain island, readout through the silu stage) or a size-fit: the chain
  section 16,837,632 halves = 2 × (256×32768) − 16384; derive, then verify.
- Fix the real defect in the emitter: `encodeLinearParity` uniform mode and
  `encodeFFNChain` must lay groups at the measured plane stride (the
  decoded section SIZE already reflected it; the pack loop did not), and
  stamp the REAL bias halves into the scalar-register immediate (today the
  capture's 0x3401 pattern rides along — measured as a +0.2502441 offset
  on every output).
- Then: compiler gates (byte-parity vs oracles re-derived with the fixed
  packer — note the ORACLE sidecars themselves were uniform-payload
  captures, so parity must be re-checked against device, per this
  receipt's finding 5), unit probes rel~0, both-host 6-run E2E per the
  standing plan (transcript pin db501a8c, bounds, walls).

## Tools left on jwm1

`/tmp/probe_libane_direct.py`, `/tmp/probe_reference.py`,
`/tmp/make_candidates.py`, `/tmp/sweep_candidates.py`, `/tmp/probe_oproj.py`,
`/tmp/extract_layout.py`, `/tmp/extract2.py`, `/tmp/extract3.py`,
`/tmp/laneprobe.py`, `/tmp/rowloc.py`, `/tmp/sens.py`, `/tmp/orient.py`,
`/tmp/bit22.py`, `/tmp/swapfirst.py`, `/tmp/task_diff.py`, `/tmp/crt3.py`,
`/tmp/crt4.py` (calibrated CRT, correct output-lane axis),
`/tmp/lanefn.py` (lane-offset measurement), `/tmp/P-clean-lane0.npy`,
`/tmp/ffn-cands/{A-red-outer,B-col-outer}`, `/tmp/fetchfid.py`,
`/tmp/finalprobe.py`, `/tmp/dbg_pat.py`. Bundle: `/var/tmp/ANE-full-battery`.
Weights: `/var/tmp/EncoderParityAne/encoder-source` via
`/var/tmp/ANE-full-battery/mint.py` (Blobs/parse_consts).

## Numbers

- FFN island vs fp32 ref: rel_l2 0.9353 (corr 0.4124) — worker AND libane
  identical; A-red-outer rebuild byte-equal to base.
- oproj-L00 vs fp32 ref: rel_l2 1.3706/1.3709 (corr 0.06).
- ones-weights: y = rowsum(x), rows exact, +0.25 bias immediate.
- p12/p123 pattern weights: readback exact (1.25/2.25/3.25).
- jw16 was never touched; 63c1d3cf untouched; no repos changed (all probes
  ran against staged bundles and patched copies in /tmp).
