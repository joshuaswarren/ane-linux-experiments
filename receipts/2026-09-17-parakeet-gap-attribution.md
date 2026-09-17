# Parakeet gap attribution: Linux E2E vs the macOS divisor, priced cause by cause (2026-09-17)

Verdict: **ANALYSIS.** Host-only attribution built entirely from already-landed
receipts; no new measurement taken, no host touched (jwm1 stays untouched —
AneChannelDerive holds it, and it is soft-wedged per
`receipts/2026-09-16-ane-submit-settle.md`; jw16 needed nothing). The gap is
**~29× on jwm1 and ~22× on jw16** against a 292.2 ms whole-pipeline macOS
reference, and the encoder stage alone carries 51–53× of it. Everything below
quotes measured numbers; the only unpriced quantity is called out as such.

## Reference and comparability frame

- **Divisor (cross-chip, M1 Ultra/T6000, macOS 26.6.2, CoreML 3520.5.1):**
  whole-pipeline `transcribe()` median **292.2 ms** (`.ane`, runs 2–10;
  `.all` 305.8 ms), same pinned model `mweinbach1/parakeet-tdt-0.6b-v3-coreml`
  @ `b650695c`, same licensed LibriSpeech fixture `1089-134686-0000`
  (10.435 s, sha `30885601…`), 104-token guard + transcript `db501a8c…` held
  22/22. Receipt: `receipts/2026-09-16-parakeet-macos-timing-m1ultra.md`.
  Library-reported splits: encoder 135.8 ms / decode 138.8 ms / mel+detok
  remainder ≈ 17.6 ms.
- **Linux baselines (v0.6.1-era, warm medians r2–r6):** jwm1 total 8541.8 ms,
  jw16 6418.5 ms (`receipts/2026-09-16-parakeet-e2e-both-hosts.md`);
  jwm1 100-run warm median 8549.6 ms, flat RSS
  (`receipts/2026-09-16-parakeet-100-run.md`).
- Like-for-like note: macOS `transcribe()` has **no audio_load stage**; the
  Linux `total_pipeline` does. Like-for-like totals are total − audio_load:
  jwm1 8364.0 ms, jw16 6343.8 ms.

## Stage table (warm medians; ratios vs the macOS stage splits)

jwm1/jw16 from `2026-09-16-parakeet-e2e-both-hosts.md` (f43ab71, fold
reverted). "post-fold" encoder values (jwm1 7036, jw16 4872) are the
bias+silu-fold lineage quoted in that receipt's successor notes.

| Stage | jwm1 ms | jw16 ms | macOS ms | jwm1 ×macOS | jw16 ×macOS |
| --- | ---: | ---: | ---: | ---: | ---: |
| audio_load | 177.8 | 74.7 | — (not in `transcribe()`) | n/a | n/a |
| mel_frontend | 247.4 | 164.7 | ≈17.6 (mel+detok bucket) | ≈14× (bucket) | ≈9× (bucket) |
| **encoder_ane** | **7215.3** (post-fold ~7036) | **5083.0** (post-fold ~4872) | **135.8** | **53.1×** (51.8× post-fold) | **37.4×** (35.9× post-fold) |
| decoder_load | 84.5 | 82.4 | — (model load excluded) | n/a | n/a |
| tdt_decode | 830.8 | 961.2 | 138.8 | 6.0× | 6.9× |
| detokenize | 40.1 | 56.2 | (in 17.6 bucket) | — | — |
| **total_pipeline** | **8541.8** | **6418.5** | **292.2** | **29.2×** (28.6× like-for-like) | **22.0×** (21.7× like-for-like) |

Reading: the encoder is 84 % of jwm1's total and carries essentially the whole
gap. Fixing encoder to parity-equivalent would leave jwm1 at roughly
160+247+136+97+830+40 ≈ 1.5 s — the decode loop's own 6–7× gap becomes the
next ceiling after that, but it is a separate lane (see ranking).

## Cause decomposition with prices (jwm1 encoder, ~7.04–7.22 s wall)

Independent accounting: encoder wall 7036 (post-fold) = ane_exec 2626 (worker
side, 100-run median 2625.9) + non-ANE ≈ 4410. The non-ANE 4410 splits as
GPU busy ≈ 2900 (of which the custom coopmat+chain bucket ≈ 1750, attention
MatmulF32 ≈ 353, other Vulkan ops ≈ 800) + host graph residual ≈ 1040
(of which ≈ 700 per-process const materialization) + ≈ 470 unattributed
serialization/gaps. Sources: `2026-09-16-encoder-gpu-busy*`,
`-host-residual*`, `-encoder-fold-reland*` receipt lineage (as summarized in
the standing notes), `2026-09-16-parakeet-100-run.md`.

**(a) ANE work not yet placed on the ANE.**
- *FFN chain (48 layers) — the coopmat+chain bucket, ≈1750 ms GPU busy.*
  Price if placed: up to ≈1.7–2.0 s of wall. Blocked: unmeasured MM2 plane —
  probe3 (`2026-09-17-encoder-ane-probe3.md`) sized the chain section as the
  natural packer size (no 2× mismatch) but the failure is a different class
  (silu/bias-add task-word fold or per-tile header placement); MM1's extended
  o-proj permutation hypothesis measured 0.94 vs 0.935 baseline, rejected.
  FFN currently falls through to Vulkan and computes correctly (the golden
  transcript proves it).
- *o-proj (24 layers) — the attention MatmulF32 bucket, ≈353 ms GPU busy.*
  Price if placed: ≈0.3–0.4 s. Status: compiler fix is real and gate-proven
  (f122644 device gate worst rel_l2 0.000208 vs 1.373 on b61de46), but the
  bundle fails to **load** on the worker — task-stream channel selectors are
  garbage (channels 3/9/30 out of surface range [4,32)) and
  `derive_role_channels`' positional fallback mismatches the input-first
  manifest (`2026-09-17-encoder-ane-f122644-oproj-placement-attempt.md`).
  In flight; needs a worker cpp patch or a task-stream re-emit.

**(b) Island submit overhead.** 72 submits/run (3 attention islands × 24
layers; the 09-17 pin-bump battery confirms 72 with 0 o-proj/FFN placed),
ane_exec 2626 ms ⇒ **≈36.5 ms per island submit**. macOS runs the entire
encoder as one CoreML plan — its 135.8 ms encoder wall includes zero submit
boundaries of this kind. If per-island fixed cost is even ~20 ms, submit
consolidation is worth ≈1–1.5 s; the honest bound is that this is **partially
unpriced** because fixed-vs-compute split per island has not been isolated
(the settle experiment (`2026-09-16-ane-submit-settle.md`) ruled out doorbell
pacing as the mechanism but did not decompose the 36.5 ms). Dependency:
fewer, larger programs — which the FFN-chain placement would naturally
provide (72 → ~120+ submits if placed naively; consolidation must be designed
in, not assumed).

**(c) Per-process const materialization.** ≈700 ms every process. An opt-in
resident-const cache exists but stays default-off because residency cost
single-pass runs +236 ms (`receipts/2026-09-16-encoder-const-resident/`
lineage). Price: 700 ms/process when the runtime is reused across runs;
~0 (slightly negative) for the current one-fresh-process-per-run contract.

**(d) Genuine GPU compute for ops that will never move to the ANE.**
≈800 ms GPU busy (2900 − 1750 − 353) in remaining Vulkan ops plus the ANE
islands' own real compute inside ane_exec. Partially irreducible; shrinkable
only by kernel work, unpriced here (no per-kernel wall attribution exists —
GPU busy ≠ wall).

**(e) Host interpreter/graph residual.** ≈340 ms (1040 − 700 const) plus
≈470 ms of unattributed serialization gaps between GPU-busy time and encoder
wall. Diffuse; lowest priority.

**Illustrative floor, clearly labeled an estimate, not a claim:** if o-proj
lands, FFN lands, submits consolidate, and consts amortize, the encoder could
plausibly reach ~1.5–2.5 s and jwm1 total ~3.3–4.3 s (≈11–15× the current
cross-chip divisor) — enough to make the tdt_decode gap (6–7×) the next
bottleneck. No number in this paragraph is measured.

## Ranked next levers (ms per unit effort)

1. **o-proj placement** — ≈350 ms for a bounded worker-cpp patch / task-stream
   re-emit; the compiler fix is already gate-proven and the bundle is minted.
   Best ratio on the board. Unblocks the linear-island path FFN also needs.
2. **Const-cache policy for reused runtimes** — ≈700 ms/run wherever the
   process contract allows reuse, for a default flip already built. Keep the
   default off for single-pass (the +236 ms penalty is measured).
3. **FFN chain ANE placement** — ≈1.7–2.0 s, the largest single prize, but
   blocked on the MM2-plane / silu-bias fold bug class and needs the linear
   path proven by #1 first. Worst effort ratio; sequence it, don't start it
   first.
4. **Submit consolidation** — potentially ≈1–1.5 s, but its price is only
   half-measured (36.5 ms/island, fixed-cost share unknown) and its mechanism
   is coupled to #3's program shapes. Design it with #3, measure the
   fixed/compute split when the island count changes.
5. **tdt_decode (side lane, not an encoder cause)** — jwm1 830.8 ms and jw16
   961.2 ms vs macOS 138.8 ms (6–7×). Becomes the dominant residual once the
   encoder closes; no cause decomposition exists for it yet.
6. **Host residual + gaps** — ≈0.8 s combined, diffuse, last.

## Not claimed / not apples-to-apples

- **The divisor is cross-chip.** M1 Ultra (T6000, 10 GPU cores, more ANE) vs
  T8103 (jwm1) and T6001 (jw16). The same-die T8103 divisor is queued
  (jwm1-macbook needs booting to macOS — owner action) and will be somewhat
  larger; every × ratio above is therefore an upper bound on the true
  same-die gap.
- **One fused plan vs island+Vulkan split.** CoreML compiles and executes the
  whole encoder as a single ANE plan; we execute 3 attention-island families
  (72 submits) with o-proj, FFN, and consts on Vulkan. The per-stage
  "encoder ×macOS" ratio conflates chip, framework, and architecture; the
  cause decomposition is what separates them, and (b) exists only because of
  the split.
- **Stage-definition mismatch.** macOS numbers are `transcribe()` only (no
  audio_load, model load excluded); Linux totals include audio_load and a
  differently split stage list. Like-for-like totals quoted above; mel and
  detokenize are only available on the macOS side as a combined ≈17.6 ms
  bucket.
- **Submit overhead is half-priced.** ≈36.5 ms/island is measured; the
  fixed-vs-compute split inside it is not. Lever 4's 1–1.5 s is a bound, not
  a measurement.
- **The "illustrative floor" is arithmetic on measured parts, not a run.**
- jwm1 state note: the submit-settle lane left jwm1 soft-wedged ("preserving
  resources until reboot"); nothing in this receipt touched any host.
- `63c1d3cf` never merged, not touched.
