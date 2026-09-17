# FFN palette decode: the chain const section was never palettized — XOR-only gate PASSES at rel_l2 0.00024

# 2026-09-17 (offline decode on workstation + one device window on jw16 T6001)

## Verdict

1. The H13 palettized weight format is **decoded** (MIL blob storage: uint4
   LSB-first nibbles + fp16 grouped LUT). Round-trip through palette +
   indices reconstructs the const bytes **bit-exactly** for both L00-f1
   tensors.
2. The decoded dense weights are **bit-identical** to (a) the 2026-09-13
   coreml-text-adapter emission payloads (`emission.json` `payload_sha256`)
   and (b) the `W1_eff`/`W2_eff` extraction from the minted chain bundle's
   const section. **The chain const section already held the true
   dequantized fp16 weights.** The 2026-09-17 addendum's "PALETTIZED const
   section" root cause is retracted; the "dequantized re-mint" closure path
   is moot.
3. With the real reference, the as-minted device output matches the
   **XOR-0xF00-only** model at rel_l2 **2.8e-4**: the device reduction is
   exact apart from the fetch XOR. The staged v2/v3 gate failure
   (0.505-0.508) was the FFT deconv shrinking the payload ~0.44x (predicted
   0.5030 device-free vs 0.508085 measured).
4. Corrected gate v4 (XOR-only pre-scramble, no deconv, no bias/imm
   writes): **rngs 11/33/57 -> rel_l2 0.000242 / 0.000239 / 0.000243 vs
   budget 0.05 — PASS** (worst 0.000243, ~200x margin; decomposed-island
   class is 0.000208). As-minted control reproduces 0.947431 exactly.

## The decode (offline, device-free)

Source: pinned package `mweinbach1/parakeet-tdt-0.6b-v3-coreml` @
`b650695c2322ee5281dff48d7345b2f3a58ff018`, `encoder.mlpackage` weight.bin
(444,016,768 B). Format per the semantics proven in the 2026-09-13
depalettize receipt (`ane-ffn-wt overlay/tools/coreml/depalettize.py`):
blob metadata at `Value.blobFileValue.offset` (sentinel 0xDEADBEEF, dtype
u32, sizeInBytes, data offset, padding bits); UInt4 = blob dtype 11,
nibbles LSB-first (element 2k = low nibble); fp16 LUT `[G,1,16,1]`,
palette = `row // 16` (contiguous per-axis blocks, coremltools
`np.repeat` tile semantics).

L00-f1 blobs (resolved from the package protobuf, not hand-copied offsets):

| tensor | shape | indices @ | indices size | LUT shape | LUT @ | LUT size |
| --- | --- | --- | --- | --- | --- | --- |
| W1 (`feed_forward1_linear1`) | [4096,1024] | 2392000 | 2,097,152 B | [256,1,16,1] | 4489216 | 8,192 B |
| W2 (`feed_forward1_linear2`) | [1024,4096] | 4505728 | 2,097,152 B | [64,1,16,1] | 6602944 | 2,048 B |

Proofs:

1. **Const bytes reconstruct**: re-packing the decoded indices (2 elements
   per byte, low nibble first) + the LUT reproduces both blob payloads
   bit-exactly (`indices EXACT, lut EXACT` for W1 and W2).
2. **Independent cross-check**: dense fp16 sha256 — W1
   `c9b4539c2b1d13eee4d251de248aba02bae66578ed70dc76944eb6c9548fb54c`,
   W2 `2f220ee1670ba4057bcb5109088dc3ce45071b6171767fb0064480271d95745c`
   — byte-identical to the `payload_sha256` recorded for the same tensors
   in `receipts/2026-09-13-coreml-text-adapter/emission.json`
   (payload_size 8,388,608 = dense fp16). Two independent implementations
   of the gather agree byte-for-byte.
3. **Bundle identity**: `gate2-out/W1_eff.npy` / `W2_eff.npy` (extracted
   from the minted chain const section by the v2 gate) satisfy
   `np.array_equal(W_eff, W_real)` for both tensors. Three independent
   paths, one tensor.
4. **Biases**: `linear_1_bias_0` / `linear_2_bias_0` blobs are all-zero
   fp16 (n=4096/1024). The minted bundle's zero biases were correct; v2's
   `ACT_OFF=301` and v3's `off=-0.14` "calibrations" fit nothing
   (corr(res_j, rowsum_j) = -0.005) because there was nothing to fit.

## Root cause of the 0.506 (quantified, device-free)

- Model A: `y[j] = sum_r payload[j, r^3840] * silu(x @ W1.T)[r]`.
  As-minted (payload = W2_eff): rel 0.000283 vs `y0_asmin` (rng 11). The
  v1/v2/v3 kernel story (tap + flat signed sea, FFT deconv, 511.75) —
  collapses to "exact reduction + XOR fetch".
- The "flat sea" (-3.4e-4 per lattice step) is the m5 background fill's
  leak, 3-4 orders under the tap; the sweep's tap value 2.389 is the m5
  fill value at the anchor, not a unit kernel. `sum(K) = 0.99974` — the
  device kernel in ones-normalized units is ~identity.
- The v3 repack `P = IFFT(FFT(W2perm)/FFT(K))` yields `P/W2perm =
  0.444 +- 0.115`: FFT(K)[f != 0] ~= K[0] = 2.389, so every non-DC
  frequency is divided by 2.389. Feeding that payload through Model A
  predicts rel **0.5030** (all j) vs the measured **0.508085**. Case
  closed: the deconv was inverting a phantom kernel.

## Gate v4 (device, jw16, one window)

Repack: `payload[j, q] <- fp16(W2[j, q ^ 3840])` into the existing mm2
interleaved slots; every other byte of the minted bundle untouched (mm1
immediate and mm2 bias slots left as minted — B1 = B2 = 0).

| arm | rng 11 | rng 33 | rng 57 |
| --- | --- | --- | --- |
| XOR-only repacked | 0.000242 | 0.000239 | 0.000243 |
| as-minted control | 0.947431 | — | — |
| budget | 0.05 | 0.05 | 0.05 |

**GATE PASS.** Reference: `silu(x @ W1_real.T) @ W2_real.T` fp32 from the
palette-decoded weights (`.npy` sha256 `5456724f…` / `a8f7b19a…`; dense
payload shas above).

Window discipline: llm-inference stopped -> `flock /tmp/m1-gpu.lock` ->
run (wall 0 s) -> service started, `is-active=active` confirmed, lock
returned to the service flock. TAKE/RELEASE announced to all peers. jwm1
untouched (held by ShmShmoutFix). GPU stand-down after the window: nothing
held.

## The O(±5) reconciliation (premise correction — so nobody re-chases this)

- "Real FFN outputs are O(±5), the ±17.6k reference must be garbage" was
  an **input-scale artifact**: ±17.6k is |ref|max under the gate's std-1
  synthetic fills. The real weights legitimately produce it, and the
  device agrees with the real-weight model at 2.4e-4. Large outputs under
  std-1 input are correct behavior for std-0.47 weights.
- At the model's own operating point the L0-f1 input is LN-pinned:
  per-channel std = `norm_feed_forward1` gamma (median 0.378, mean 0.382).
  Forward with that scale: p1 std 6.6, chain output y std 172,
  |y|max 4.1e3, branch contribution x0.5 (inline fp16 scale). The golden
  `encoder_hidden` fixture is [1,375,640] fp32, std 0.235, |max| 1.87 —
  post final-LN; downstream LNs re-pin scale, so there is no contradiction.
  The "O(5)" expectation does not hold at linear_2-output granularity and
  is not evidence about weight correctness. The decisive evidence is the
  sha triple-match + bit-exact round-trip + device agreement.

## Disposition

- The fused mm1->silu->mm2 chain program **is deployable as minted**
  (mil-hwx-compiler `ffn-mm2-plane` @ `a8392e6`) with the XOR-0xF00 fetch
  correction applied emit-side: pre-scramble the mm2 payload by `q ^
  3840`; **no deconv in the emit path**, no bias compensation, no re-mint.
- Scale to 48 bundles + engine wiring is a later lane (Main's call; not
  started here).
- FFN-on-ANE default: unchanged by this receipt. The gate evidence now
  exists; the default flip is Main/Joshua's decision.

## Evidence

- This repo, `.local/ffn-chain-fusion/` (untracked evidence dir):
  `decode_palette.py` + `decode_palette.json` (decoder + proof record),
  `W1_real_fp16.npy`, `W2_real_fp16.npy`, `b1_real_fp16.npy`,
  `b2_real_fp16.npy`, `ffn_gate4.py`, `gate4.log`, `gate4.json`,
  `y0_asmin.npy`, `ref0.npy`, `W1_eff.npy`/`W2_eff.npy` (bundle
  extraction), `lineG_A_j0line.npy` ([1024,4096] response matrix; only
  row j=0 measured), `encoder_hidden_golden.npy`, and the fetched staged
  scripts `ffn_gate2.py`, `ffn_gate3.py`, `ffn_decodeB2.py`,
  `ffn_rowmap2.py`.
- jw16 `/tmp/ffnprobe/`: `palette-real/` (same weight shas),
  `gate4-out/gate4.json`, `gate4-out/repacked-xor.anec` (sha256
  `dc85fd1245c495a98031855dac7190a1e7c308efe4e4936bf123d8c7aceb309b`),
  `gate4.log`; minted bundle `chain/island-ffn-L00-f1/program-0.anec`
  sha256 `e10db91639ab705509a0e586c017e7687ffb60f391289ace5605574d6382580b`
  (matches its manifest graph_hash — untouched).
- Superseded: the v2/v3 staged gate scripts' XOR+deconv+bias repack — the
  XOR half was right, the deconv and bias terms were compensating a
  self-inflicted 0.44x payload scale.
