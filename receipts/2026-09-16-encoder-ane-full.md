# Encoder ANE full coverage: pin landed, integration defects fixed, FFN/oproj islands diverge — placement halted (2026-09-16)

Verdict: **STOP at the transcript-pin gate.** The pin bump landed clean and
verified; two compiler bundle-gate defects were found and fixed; the FFN-chain
and output-projection islands mint, load, and submit on jwm1 — but the E2E
**diverges** (0/104 emissions, bounds fail, `encoder_hidden` `302255aa…` vs pin
`38c73261…`), and a unit probe shows the FFN-chain bundle computes the wrong
function. Per the assignment gate, placement is halted and the divergence is
reported before any further work. jw16 was never touched.

## What landed

### mil-hwx-compiler (pushed)

- **`2d11b2a`** on `main` (branch `encoder-leftover-oracles`, WIP `09b96c5` +
  `1744b40` squashed tree-identically). Gates: `make test-h13` exit 0, parity
  **874** cases. Tag `ane-parity-2d11b2a`, release
  `ane-parity-2d11b2a` (archive 84 132 567 B, sha256 `993d8dab83b8…7c3fc`).
- **`db8ffba`** `h13: name the input-first channels the decoded linear and
  chain streams select`: `encodeLinearParity`/`encodeFFNChain` declared
  output-first manifest channels while their decoded task streams bind
  input-first (src=[4], dst=[5]); `encodeANEC` now follows each tensor's
  declared index instead of hardcoding inputs at 5..7. Gates re-run green:
  test-h13 PASS, parity 874 (task/const bytes unchanged), adapter derivation
  matches.
- **`ee2fdec`** `h13: keep the 64-lane split off the whole-tensor linear and
  chain records`: the ffn-chain/linear program output records claimed a
  64-element slice over a 384000-element result; the strict bundle gate
  refused ("output tensor y is not fully written"). Both commits pushed to
  `main` and `ane-integration/input-first-channels`.

### mlx-omarchy (local branch `encoder-ane-full` in `/var/tmp/ANE-full`, NOT pushed)

- `0b53b189` pin bump to `2d11b2a` (+ license/bundle doc pin rows).
  `verify-ane-compiler.sh`: reject PASS, prepare PASS (binary
  `474145617aaa4578…`), h13 qualification PASS (tile program `3d73787c`
  unchanged). GitHub's release CDN flapped 404s right after upload; the
  archive was seeded from identical local bytes, hash gate enforced.
- `a45e69ed` planner: `mint_encoder_islands.py` (emits per-layer island MILs
  from oracle templates with real weights, structure-gates each manifest
  against the compiled qualified oracle record — uniform vs `_idx` payload
  class for the linear — and adapts v2→schema-4) + runner F/O families with
  deterministic refuse-and-fallback (geometry or missing bundle dir → GPU)
  and island-only const skip. **72 bundles minted PASS** (48 FFN chains +
  24 o-proj, 447 MB, `/var/tmp/ANE-full-islands4`, provenance inside).
- `c804ee5c` WIP: harness-path defaults (the E2E harness constructs the
  runner without `placed`), bundle auto-discovery, quote-token strip, and the
  divergence report below.

## The divergence (why this stopped)

jwm1, smoke pass at the staged `/var/tmp/ANE-full-battery` (same site,
worker `f171a61e…`, libane `56b46234…`, bundles dir + new runner): all 168
submits (72 island rounds + 96 attention ops) pass with 0 timeouts, but:

| gate | value |
| --- | --- |
| emissions | **0/104** (native 104) |
| transcript | empty; pin `db501a8c…` broken |
| encoder bounds | **fail** |
| `encoder_hidden` | `302255aa4714549fd323c8f61f0e5d4ea928a1f2bdf277fe86caa0771193ce94` (changed from `38c73261…`, as expected — but wrong) |

Unit probe (worker CLI, launch mode, `island-ffn-L00-f1` with real layer-0
weights and two deterministic inputs): output is finite and plausible-scale,
but vs an fp32 numpy evaluation of the identical chain
(`silu(x@W1ᵀ+b1)@W2ᵀ+b2`) it is **rel_l2 0.94, max_abs 4594** — the bundle
computes the wrong function even though parity-qualified lowerings produced
it. Runner-handoff bugs are largely excluded (the probe bypasses the runner).
Open suspects, in order: (1) input-first channel semantics at the
worker/driver boundary — input [1,375,1024] and output [1,375,1024] have
identical geometry, so a channel swap passes every strict validation while
computing garbage; (2) const-section packing with the real uniform-bias
payloads interacting with the scalar-register fold.

Divergent run report captured at
`receipts/2026-09-16-encoder-ane-full-divergent-e2e-report.json`;
divergent `encoder_hidden` sha `302255aa…`, probe output sha
`c48d6a29…` (jwm1 `/var/tmp/ANE-full-battery/out/r-225946-1/`, `/tmp/probe-y2.bin`).

## Not done (blocked by the gate, not deferred)

- jwm1/jw16 6-run batteries, before/after wall quote, transcript-pin
  restoration, jw16 staging: require the divergence root-caused first.
- qkv head-projection bmm: separately blocked — the packed b8 bmm task
  stream never marks its input surface for the strict derive walk
  (adapter/worker refuse), a compiler-side follow-up on its own.
- The `ane-compiler.lock` still pins `2d11b2a` (gates as stated); the two
  integration fixes (`db8ffba`, `ee2fdec`) are landed on the compiler main
  after it, so a release `ane-parity-ee2fdec` + lock move is the mechanical
  next step once numerics are explained — NOT before.

## Receipts

- Compiler: github releases `ane-parity-2d11b2a`; gates quoted above ran on
  this host (transcript-verified tool output).
- mlx-omarchy: local `encoder-ane-full` `0b53b189`/`a45e69ed`/`c804ee5c` in
  `/var/tmp/ANE-full`; bundles + `provenance.json` at
  `/var/tmp/ANE-full-islands4` (local) and
  `jwm1:/var/tmp/ANE-full-battery/bundles` (staged).
- Divergence: `2026-09-16-encoder-ane-full-divergent-e2e-report.json` (this
  directory), `302255aa…` / `c48d6a29…` shas quoted above.
- `63c1d3cf` untouched. jw16 untouched. No wheel rebuilt; no flags in the
  battery other than the staged environment quoted in the battery script.
