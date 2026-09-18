# F1/pw1 drift forensics — the 101/104 transcript break is a decoder-tail coin flip at the certified fp16 noise class (jw16, 2026-09-18)

## Verdict

**Architecture-bounded closure. No device bug, no packing/layout bug, no
accumulation anomaly at H = F1 in-proj/pw1 (1024→2048 k1×1).** The conv
bisect (`d1d9893`, branch `da116c04`) isolated the transcript drift to H;
this lane root-causes the mechanism. The transcript's trailing tokens are
decided by logit margins comparable to the fp16 noise floor of ANY cross-
engine re-implementation of ANY island family: independent drift
realizations at the certified error class break the transcript with
probability **16/32 = 0.500 (95% CI [0.319, 0.681])**, and a pure-GPU
no-islands control — a different family entirely — drifts the same
magnitude (rel_l2 3.93e-3 vs the certified hidden pin) and breaks WORSE
(prefix 97). J's transcript-EXACT 104/104 in the bisect was a favorable
draw, not a family property. **V stays NO-SHIP**; the fatal gate
(transcript `db501a8c…` EXACT + 104/104) cannot be met deterministically by
any fp16-granularity island placement, including H alone.

All three assignment hypotheses are closed with numbers:

1. **Accumulation width (hyp 1): DEAD.** On 24 real pw1 activations captured
   in the certified GPU pipeline, ANE-vs-GPU rel_l2 max **1.58e-4** — below
   the 2.08e-4 synthetic gate class and identical in kind to pw2 (max
   9.2e-5) and dw (max 8.1e-5). ANE-vs-fp32-ref max 2.15e-4 across all
   kinds — one fp16 output rounding, no depth dependence at K=1024.
   Adversarial null-vector inputs at matched reduction depth (smallest
   right singular vector of the real weight matrix, tiled across T, so the
   exact output is ~0 while partial sums are large) keep |ane−ref| at
   4.6–5.4e-4 ABSOLUTE — the output-rounding floor — against |ref| up to
   3.5e-1. A sequential fp16 accumulator would show errors orders of
   magnitude larger. The ANE conv datapath accumulates at fp32 quality at
   H's reduction depth.

2. **Downstream amplification at H (hyp 2): DEAD as an H-specific
   mechanism.** Final encoder hidden drift vs the certified pin is the SAME
   magnitude for J-only (3.88e-3) and JKH (4.03e-3): H's marginal drift
   (out3-jkhi minus out3-j) is 3.86e-3 — 0.99× J's own — and ANTI-correlated
   with it (cos −0.358). H does not amplify more than J; every conv family
   at this floor contributes an equivalent-magnitude, essentially
   independent output drift. Frame 373, where the tail diverges, has
   BELOW-median drift in every arm (0.31–0.33× median) — the break is not a
   drift hot spot but a decision boundary.

3. **Real-weights per-layer comparison (hyp 3): DONE, nothing to name.**
   All 72 conv sites (pw1/dw/pw2 × L00–L23) were captured on real
   activations and executed on their real bundles; the first site where the
   island diverges beyond the fp16 floor does not exist (worst 1.58e-4,
   section 2). The first place the TRANSCRIPT diverges is decoder emission
   101 at frame 373 (pin token 7892 "Ю" → 8029 "Н", duration 0), fully
   determined by the encoder hidden: decode-only probes of the saved
   placed-arm hiddens reproduce the real arms' transcripts bit-for-bit
   (probe-jkh/probe-jkhi → `baad4383…`, prefix 101, identical to the
   bisect arms).

## Refs (both sides of the handoff)

- This repo: `agent/f1-drift-forensics` — receipt, forensic tools, and
  evidence artifacts (`receipts/2026-09-18-f1-drift-forensics/`).
  Lineage: conv bisect receipt `d1d9893` (branch `da116c04`); V/P/T screen
  receipt `f7981c6`/`8e8db6d` on `main`; device-gate receipts `f631ca8`,
  `096164b` (F3 writeout-inverse, mil-hwx-compiler `e7967f9`).
- jw16 artifacts (unchanged certified stack): runner
  `/tmp/conv-lane/vk_conv.py` = mlx-omarchy `agent/ane-conv-placement`
  `486514b4` (bytes sha256 `500256e2…`), worker `6b63261a…`, libane-strict-fill
  `04a17653…`, bundles `/var/tmp/jw16-conv-place/bundles-conv` (77/77 gate
  PASS at mint, `conv-gate.json`), bisect arms `/var/tmp/jw16-conv-place/
  arms3.jsonl`, probe evidence `/var/tmp/f1-drift/` (probes.jsonl,
  in-situ.json, out-probe-*/e2e-report.json, probe-logs/, cap/ = 144 real
  boundary tensors).

## 1. The bisect data this lane starts from (arms3.jsonl, launch mode; resident mode identical)

| arm | placed | hidden sha256 | transcript | prefix |
|---|---|---|---|---|
| abc | ABC | `38c73261f2923027…` (PIN) | `db501a8c…` | 104 |
| j | ABCJ | `aa8854d16a3d3fa3…` | `db501a8c…` | 104 |
| k | ABCK | `38c73261…` (bit-exact) | `db501a8c…` | 104 |
| jk | ABCJK | `aa8854d1…` | `db501a8c…` | 104 |
| jkh | ABCJKH | `047424161da2f253…` | `baad4383…` | **101** |
| jkhi | ABCJKHI | `4c831bf577f5ee74…` | `baad4383…` | **101** |

Key observation: **J's placement already moves the hidden digest
(aa8854d1 ≠ pin) while the transcript stays EXACT.** The per-op gate class
is therefore not what separates 104 from 101 — the transcript response to
same-class drift is.

## 2. In-situ island check on REAL activations (hyp 1/3, f1_capture.py + f1_inprobe.py)

The certified all-GPU pipeline was run on the fixture (fused_e2e `--no-ane`,
wrapper runner dumping every conv boundary tensor — 144 tensors, 24 layers ×
3 conv kinds × {input, output}), then each real input was executed through
its own minted bundle via libane-strict-fill and compared against the GPU
output and an exact fp32 reference built from the real (deparalettized)
weights:

| kind | sites | rel(ane,gpu) max | rel(ane,fp32) max | rel(gpu,fp32) max | ulpflip median |
|---|---|---|---|---|---|
| pw1 (H) | 24 | **1.584e-4** | 2.152e-4 | 2.086e-4 | 0.17 |
| dw (I) | 24 | 8.135e-5 | 2.186e-4 | 2.185e-4 | 0.15 |
| pw2 (J) | 24 | 9.224e-5 | 2.125e-4 | 2.122e-4 | 0.08 |

H's in-situ source error is BELOW the synthetic gate class (2.08e-4) and
the same class as J's. Full table: `in-situ.json`.

Adversarial matched-K cases (L00/L11/L23, null-vector inputs): pw1
|ane−ref|_max 5.1–5.4e-4 vs |ref|_max 1.6e-1–3.5e-1; pw2 (same K=1024)
4.6–5.0e-4 vs |ref|_max 6.9e-4–1.2e-3. The absolute error is pinned at the
fp16 output-rounding floor everywhere; there is no accumulation-width
signature in either geometry.

## 3. Where the drift goes (saved-hidden analysis)

Final hidden (out3-*/encoder_hidden.npy, [1,375,640] fp32) vs the
certified pin:

| arm | rel_l2 | elements ≠ pin | maxabs | transcript |
|---|---|---|---|---|
| j | 3.882e-3 | 92.3% | 0.013 | 104/104 |
| jkh | 4.026e-3 | 92.2% | 0.032 | 101/104 |
| jkhi | 4.385e-3 | 92.5% | 0.049 | 101/104 |
| capgpu (all-GPU control, this lane) | 3.927e-3 | — | — | **97** |

The all-GPU control (islands A/C also moved off the ANE — a different
family, same fp16 granularity) drifts the same magnitude and breaks the
transcript EARLIER (first divergence at token 97). cos(d_j, d_jkh) = 0.556;
cos(H-marginal, d_j) = −0.358 — the arms sample a ~4e-3-magnitude drift
cloud with weakly-correlated directions; H's marginal contribution is
indistinguishable from any other draw. The certified ABC arm's own hidden
sits in the same cloud (its transcript holds because the certified
configuration reproduces the Apple capture — the realization, not the
magnitude, is what varies).

## 4. Decode-transfer probes: P(transcript breaks) at certified-class magnitude (hyp 2's direct test, f1_hprobe.py)

A wrapper runner bypasses the encoder and feeds a prepared hidden straight
to the real decoder, so every probe isolates the transcript's response to
the hidden drift alone. Controls first — the transfer is exact:

| probe | hidden | prefix | transcript |
|---|---|---|---|
| probe-abc | pin, as-is | 104 | `db501a8c…` |
| probe-j | d_j at t=1 | 104 | `db501a8c…` |
| probe-jkh | d_jkh at t=1 | 101 | `baad4383…` (== real arm) |
| probe-jkhi | d_jkhi at t=1 | 101 | `baad4383…` (== real arm) |

Then 32 independent realizations: the real arm drift with elementwise
random sign flips (spectrum preserved, direction decorrelated), at J
magnitude (rel 3.88e-3) and JKHI magnitude (4.38e-3), plus a magnitude
sweep on J:

| draw set | n | breaks | P(break) | 95% CI | break shape |
|---|---|---|---|---|---|
| signflip(d_j), t=1 | 16 | 8 | **0.500** | [0.247, 0.753] | 8× 97 |
| signflip(d_jkhi), t=1 | 16 | 8 | **0.500** | [0.247, 0.753] | 7× 97, 1× 99 |
| pooled t=1 | 32 | 16 | **0.500** | [0.319, 0.681] | — |
| signflip(d_j), t=0.5 | 4 | 1 | 0.25 | [0.006, 0.806] | 97 |
| signflip(d_j), t=2 | 4 | 3 | 0.75 | [0.194, 0.994] | 2× 97, 1× 101 |

(Breaks: prefix 97 → transcript `075876ef…`, prefix 99 → `a4c7d6ba…`,
prefix 101 → `baad4383…`. The decoder's trailing region has a small set of
near-tie outcomes; independent same-class realizations distribute across
them. Even HALF the certified magnitude breaks 1 draw in 4.)

Reading: at the drift magnitude that the certified fp16 class necessarily
produces, the transcript-EXACT gate is a coin flip. The bisect's "J exact /
H diverges" was one favorable draw (J) versus an unfavorable draw (H) of
the SAME mechanism; per-op gate class, geometry, reduction depth, packing
and position were never the discriminator. Full 44-row log:
`probes.jsonl`.

## 5. Mechanism (named)

Placing a conv island changes its output by at most one fp16 output
rounding (per-element 1-ULP flips on 8–19% of elements — in-situ ulpflip
0.08–0.17 median). Through the 24-layer encoder this perturbation class
propagates to a ~4e-3-relative, direction-uncorrelated drift of the final
hidden — the same cloud for every family and for moving islands in either
direction. The TDT decoder's trailing emissions (the long "……" tail at
frame 373, duration-0 blank loops) are decided by margins comparable to
that drift, so the decoded tail is realization-dependent: the certified pin
transcript is one attractor (104), the bisect break another (101,
`baad4383`), and deeper breaks exist (97 `075876ef`, 99 `a4c7d6ba`). The
fatal E2E gate demands attractor 104 exactly and deterministically, which
no fp16-granularity cross-engine placement can deliver.

## Disposition

- **V (and any superset containing H) stays NO-SHIP** — unchanged from
  `f7981c6`. The closure is now mechanism-backed: not "we observed 101/104"
  but "any same-class realization breaks the transcript with p≈0.5".
- **No record-set change, no compiler change, no runner change, no gate
  weakened.** The 77/77 mint gate, the 104/104 pins (`db501a8c` /
  `38c73261` / `ef6afd13` / `5b54f4a9`), and both decode pins stand
  untouched. The certified arms were re-run in-window only as the capture
  vehicle (digest-first regression not needed: no code changed; the
  capture run is diagnostic, `--no-ane`).
- The wall result of `f7981c6` stands as recorded (V cuts encoder wall 11%
  launch / 24% resident) and is now formally unreachable for default
  placement: digest parity forbids it, and the blocker is the transcript
  gate, not any fixable device defect.

## Discipline

One jw16 window (three flock acquisitions of `/tmp/m1-gpu.lock`, inode 12,
never stolen, lock free at release): capture run, 44 decode-only probes,
72-site in-situ ANE check, adversarial matched-K cases. llm-inference
stopped before the window (`active` → `inactive`), restarted and confirmed
`active` (MainPID 120436) before RELEASE; TAKE/RELEASE announced to Main.
Stdout to files under `/var/tmp/f1-drift/`. No SET-block writes, no release
publishing, no formatters, no mlx-omarchy changes, no hand-patched
generated files (all probe runners are diagnostic wrapper modules loaded via
`--encoder-runner`).
