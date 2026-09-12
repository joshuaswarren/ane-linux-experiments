# Parakeet encoder vs H13 compiler coverage classification

2026-09-12. Classification only — no compiler implementation, no hardware, no
driver work, no parser code. Worker `EncoderCoverage`.

## Pins (exact)

| Artifact | Pin |
|---|---|
| Model repo / rev | `mweinbach1/parakeet-tdt-0.6b-v3-coreml` @ `b650695c2322ee5281dff48d7345b2f3a58ff018` |
| Encoder proto | `encoder.mlpackage/Data/com.apple.CoreML/model.mlmodel`, sha256 `2e4e6b54f32029d7b2a69549c2cedf5cd9c6daa8e5274a2b357fc7911747204b` |
| Encoder weights | `encoder.mlpackage/Data/com.apple.CoreML/weights/weight.bin`, sha256 `23867a834223ee6484d0b7b9b703530e8606546efa8e710535163d51ed9aac04` |
| Compiler source | `/home/joshuawarren/src/mil-hwx-compiler` @ `a0ce354cf800011a84420da4e12013eb8140b2a5` (clean tree, HEAD `a0ce354` "receipt: ane-parity candidate compilation provenance (2026-09-08)") |
| Inspector | `CoremlInspector` @ `bc38ab129d60e79560e5a734029e6fe97b22128b` (not needed for verdicts; raw proto read directly) |
| Analysis base | `ane-linux-experiments` @ `9bf0a72` (branch `composed-main-qual`) |

Extraction used the **official raw MILSpec Model proto** (coremltools 9.0
protos, `specificationVersion: 9`, single `CoreML8` block specialization),
not the summarized inspector JSON. Every parameter (strides, pads, perm,
axes, epsilon, transpose flags, palettization payloads) was read from the
proto's const operands / inline arguments. Reproduce with
`extract_encoder_coverage.py` (needs coremltools protos only).

## Model facts (all 3351 ops)

- Function `main`, I/O contract: `input_features` **fp32[1,3000,128]**,
  `attention_mask` **int32[1,3000]** → `encoder_hidden` **fp32[1,375,640]**,
  `encoder_mask` **int32[1,375]**. Everything interior is fp16 with int32
  index constants and bool masks.
- FastConformer-Hybrid encoder: 2D subsampling convs → 17 Conformer blocks
  (attention + ConvNeXt-style conv module) → pointwise head.
- 31 distinct op types over 3351 operations (1783 of them `const`).
- All 194 `linear` weights are **4-bit palettized** via
  `constexpr_lut_to_dense` (fp16 LUT `[64|256,1,16,1]` ×16 centroids, `uint4`
  indices, blobs in `weight.bin`); the 77 `conv` weights are plain fp16
  `const`s. Zero/`-inf`/`1e-5` (exact fp16 `1.00136e-05`) read from immediate
  bytes.

## Verdict rollup (3351 ops)

| Class | Ops | Meaning |
|---|---:|---|
| `direct` | 294 | the current compiler lowers these as-is |
| `direct-alias` | 158 | reshape/expand_dims shape aliases, no program |
| `direct-const` | 1783 | constant data |
| `normalization-needed` | 427 | reachable via handoff/weight-prep rewrite into an **already-covered** path; no new oracles |
| `missing-envelope` | 250 | H13 implements the semantics, but this geometry/form is outside every decoded oracle table |
| `missing` | 439 | no H13 encoder for the semantics at all |

Per-op table: `coverage.csv`. `direct + alias + const + normalization` =
**2662/3351 (79.5%)** are lowerable without minting a single new oracle. The
remaining **689 (20.5%)** are the plan-gating gap.

## Per-op classification

### direct as-is (294 + 1783 const + 158 alias)

- `add` 168 / `mul` 123: two-runtime same-shape binaries through the
  source-qualified 64-element-slice path, whole-tensor constant folds, inline
  fp16 scalar mul folds, and the three decoded broadcast templates that match
  this model's residual adds (`kBroadcastTasks`).
- `relu` 3: native surfaces miss, but the H13 relu handler rewrites to
  `maximum(x, synthesized zero-splat)` which folds at any static fp16 shape
  (ANEH13Compiler.mm:1486-1510 → 1096-1171).
- `reshape` 145 / `expand_dims` 13: aliases (mm:1456-1482).
- `const` 1783: data, filtered before the program stream (mm:1391-1393).
  Note: proto const immediates are **inline**, so the handoff must re-emit
  matmul/linear weight and bias payloads as `BLOBFILE` consts — the matchers
  require it (mm:1246-1252, 924-931).

### normalization-needed (427) — reachable with no new oracles

- `linear` 194 + `constexpr_lut_to_dense` 194: the linear handler rejects
  non-const weights (`h13.linear-nonconstant-weight`, mm:1550-1553), and no
  H13 path consumes palettized data. Host LUT decompression at weight-prep →
  dense fp16 `const` + `BLOBFILE` unblocks the **existing** linear lowering:
  per-row unroll with bias add (mm:1570-1657), 512-column output slices,
  256/512 reduction chunks, fp16 chunk accumulation (mm:1304-1331,
  H13Program.cpp `encodeMatvec` requires exactly 256/512 reduction).
  *Flag for CompilerPreparation: rows>1 unroll multiplies program count
  (≈375 rows × 194 linears); integration proof needed on a rows>1 receipt.*
- `matmul` 24 (rel-pos score matmuls, const `[1,8,128,749]` weights,
  `transpose_y=false`): outside `kMatmulEnvelopeTasks` → the source-qualified
  chunked matvec path applies; `ty=false` weights are host-transposed to the
  `ty=true` form (mm:1271-1298); weight must be re-emitted `BLOBFILE`.
  Runtime-side proof needed (kMatvecTasks itself only pins small shapes; the
  chunked encoder is generic but unverified at rows=3000).
- `add` 13 / `sub` 2 (lengths math, fp16[1] ± rank-0 scalar consts): the
  scalar fold exists **only for mul** (mm:1108-1114); re-spelling rank-0
  consts as `[1]` tensors at handoff enables the whole-tensor fold.

### missing-envelope (250) — semantics implemented, geometry outside every table

Exact-match selectors: every plan matcher consults a decoded-template table
with exact shape keys (H13Program.cpp:411-470, 909-917). Tables parsed in
full: 87 elementwise, 113 broadcast, 186 norm, 175 conv, 145 matmul-envelope,
36 matvec.

- `conv` 77: 72 are rank-3 1-D spellings (`[1,1024,375]` pointwise k1 ×48,
  depthwise k9 groups=1024 ×24) rejected by `convSurface` (rank-4 NCHW
  batch-1 only, mm:838-840); 5 are the rank-4 subsampling convs whose
  surfaces — up to `(256,1500,64)` — do not exist in `kConvTasks` (max
  spatial 64×64; `(1024,16,16)` is the largest C=1024 surface), and the
  strided ones additionally carry `pad_type=custom` with nonzero `pad`,
  rejected at mm:871-876 (only `same`/`valid`, or explicit all-zero pad).
- `matmul` 48 runtime×runtime (QK^T `3000×128×375` ty=true ×24, PV
  `3000×375×128` ty=false ×24): `kMatmulEnvelopeTasks` pins rows ∈ {1,16}
  only; runtime-weight matmul is parity-path-only with **no chunked
  fallback** (mm:1217-1240, reject `h13.matmul-outside-envelope`).
- `silu` 72 / `sigmoid` 24: unary ops are parity-path-only (no generic
  fallback — final reject mm:1349-1350), and `kElementwiseTasks` unary
  surfaces are channel-vectors `(C,1,1)` with C ≤ 4096 (64/512 for most ops).
  The FF/conv-module tensors are spatial (`(4096,1,375)`, `(1024,1,375)`);
  the flatten alternative `(1536000,1,1)` has no template.
- `softmax` 24 on `[1,8,375,375]` axis −1: norm surface `(8,375,375)` mask
  `0x08` is absent from `kNormTasks` (44 softmax entries, largest spatial
  256×256). `normParityPlan` is softmax's only path.
- `mul` 5 (per-position channel mask, runtime `(1,1,1500,1)`-style operands
  on `(1,256,1500,64)`): no broadcast template for these surfaces.

### missing (439) — no H13 encoder for the semantics

All die at the final reject "H13 has no source-qualified encoder for …"
(mm:1349-1350) or earlier gates:

- `transpose` 146 — no encoder at all; the `[0,2,1,3]`/`[0,2,1]`/`[0,2,-3,-1]`
  perms are the attention head reshuffles and cannot fold into matmul
  transpose flags on these rank-3 spellings (per-head decomposition would
  need slice/split, also missing).
- `slice_by_index` 48, `select` 48, `pad` 24, `less` 4, `logical_and/not` 2,
  `tile` 1, `floor` 3, `floor_div` 3, `split` 24 — none has an encoder.
  The select/pad/slice/less cluster **is** the runtime attention masking
  (`attention_mask` is a function input, so it cannot be constant-folded on
  the host). `split` is additionally unrepresentable in the IR:
  `ANEGraphOperation` has exactly one result (ANEGraphIR.mm:79-103) — GLU
  halves must come from two linears with the palettized weight split at
  decompression time.
- `layer_norm` 120 — the sharpest boundary in the tree:
  `normParityPlan` hard-requires `args==3`, fp32 `epsilon==1e-5` **literal
  attribute**, and **no gamma/beta** ("Apple's compiler in this harness
  rejects every affine form", mm:751-792). All 120 carry gamma+beta, epsilon
  arrives as an fp16 const operand, and even the affine-less core surface
  `(1,375,1024)` is absent from `kNormTasks`. The H16G `ANEDecomposePass`
  layer_norm lowering exists but is not wired into the H13 path, and its own
  decompose is affine-less too.
- `cast` 8 interior (int32/bool domain) — fp16-only stream
  (`fp16Tensor`/`tensorElementCount` gates, mm:26-45).
- `add` 2 / `sub` 1 int32 (lengths), `reduce_min` 1 (no encoding at all —
  `normEncoding` covers sum/max/mean only, mm:89-97), `reduce_sum` 1 (int32
  mask input).

## Textual MIL vs compiler API — minimum faithful handoff

Current H13 entry: `compileMILData:` consumes **textual MIL**
(MILLexer → MILParser → MILGraphImporter → `ANEGraphModule` → plan matchers).
The parser is generic and covers what this model needs *except* what the
proto spells differently: static dims only (fine here — every dim is
constant; `reshape` shape lists even carry `-1`, which the alias path never
parses), named args, typed calls, negative ints, `BLOBFILE`, dicts.

Two handoff shapes were assessed:

1. **proto → coremltools textual MIL → existing `compileMILData:`** — zero
   compiler change, but the printer would inline the 194 palettized weights
   and 266 fp16[1024] consts as enormous literal lists (the proto's
   `blobFileValue` refs have no textual round-trip in coremltools), and the
   matchers' literal-attribute expectations (`fp32(1e-5)` epsilon,
   `bool` transpose flags) do not line up with proto const-operand spellings
   without a rewriting pass anyway.
2. **proto → `ANEGraphModule` importer (recommended minimum)** —
   `ANEGraphOperation{name, result, arguments, attributes}` is structurally
   isomorphic to the MILSpec proto (named const operands ↔ const values,
   inline arguments ↔ literal calls). A dedicated importer in `lib/MIL`
   beside the textual path: (a) re-emits big weights/biases as `const` with
   `BLOBFILE` payloads pointing at the mlpackage's own `weight.bin`,
   (b) spells matcher-required attributes as literals (`fp32(1e-5)`,
   `bool`), (c) re-spells rank-0 consts as `[1]` tensors, (d) drops
   `constexpr_lut_to_dense` in favor of host-decompressed dense consts (or
   leaves them for the unsupported-op reject until weight-prep lands). The
   plan matchers, the relu/clip/linear lowerings, and the alias mechanics are
   reused untouched; the textual path stays for the oracle `.mil` fixtures
   and regressions.

Reuse verdict: the existing representation (`ANEGraphModule` +
`ANEH13Compiler` lowering) is sufficient for the direct + normalization
buckets (79.5%); no new IR is needed for them. The missing 20.5% is not a
representation problem — it is oracle coverage plus two plan-level decisions
below.

## Program-model constraints the handoff must plan around

- Exactly **one function, one returned value equal to the last operation's
  result**; every intermediate consumed by a later op (mm:1400-1427). The
  encoder returns **two** tensors (`encoder_hidden`, `encoder_mask`) —
  program partitioning / second-output policy is a plan decision (drop
  `encoder_mask`? re-derive host-side? partition per region?).
- Manifest bindings are **fp16-only** (`binding()`, mm:424-436), while the
  model I/O contract is fp32-in / fp32+int32-out — boundary type handling
  belongs to the ANE bundle adapter (mlx-omarchy side).
- Linear per-row unroll multiplies program count (~375×194 with bias) —
  dispatch-size implications for the bundle format.

## New blockers requiring a plan stop (with evidence)

1. **Oracle coverage gap is the load-bearing blocker, not code.** The 689
   missing ops include every spatial conv (77), every runtime attention
   matmul (48), attention softmax (24), all FF activations silu/sigmoid (96),
   affine layer_norm (120), and the runtime mask plumbing (~128). Covering
   the pinned encoder on H13 requires a new oracle-minting campaign (hardware
   probes) for at minimum: large-spatial conv surfaces + custom-pad
   spellings, runtime matmul rows ≫ 16, spatial unary surfaces, `(8,375,375)`
   softmax, per-position mask broadcast, affine layer_norm. Evidence: the six
   template tables enumerated above (706 exact-match entries), selectors
   H13Program.cpp:411-470/909-917, gates cited per-op above.
2. **Runtime attention masking has no ANE-side landing place.** select/pad/
   slice/less/logical have no encoder and the mask is a runtime input, so it
   cannot be host-folded. Alternatives are model-side (multiplicative float
   mask instead of −inf select; precomputed masks are impossible for the
   padding path) — a modeling/export decision, not a compiler fix.
3. **Second output + int32 I/O contract** (encoder_mask, fp32/int32
   boundaries) vs the single-return, fp16-binding program model — needs the
   planner/adapter decision before any encoder compile attempt.

None of these block the handoff importer + weight-prep work itself (the 79.5%
reachable set is real and evidenced); they block the *claim* that the pinned
encoder compiles end-to-end on H13 today. It does not, and no existing
semantics should be relabeled as support: every "missing" verdict above cites
the decisive reject or the exact absent table entry.

## Method notes

- Classification replicated the H13 plan matchers line-by-line in Python
  against the parsed tables; per-op verdicts in `coverage.csv` carry the
  decisive note (gate cited or template miss with the queried key).
- `conv` classes: rank-3 spellings are `missing-envelope` (semantics
  implemented, spelling/surface rejected); a rank-4 re-spell cannot rescue
  them because the surfaces are absent from `kConvTasks` either way.
- Runtime×runtime matmul outside the envelope is `missing-envelope` (no
  fallback path exists); const-weight outside the envelope is
  `normalization-needed` (chunked matvec fallback exists).
- Known verdict asymmetries checked against the source: relu's synthesized
  fallback makes all 3 direct; `BinaryScalar` parity needs exact `0x3800`
  bits only in `parityPlan`, not the generic fold; `sub`/`real_div` fold only
  with a constant operand (two-runtime forms are rejected, mm:1067-1071).
- Inspector (`CoremlInspector` @ `bc38ab1`) cross-checked: its summarized JSON
  omits the blob-referenced attribute payloads; the raw proto read here is
  the authoritative source for all parameter values.
