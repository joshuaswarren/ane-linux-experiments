
## 7. Addendum 2: jw16 G13X bit-set sweep — no Pareto set; residual named

Bounded sweep on jw16 with the `hk/app-barrier` diagnostic knobs (knob
driver relayed from jwm1 via ICD; llm-inference pause window; lock
`flock -w 900`): 24 supersets/subsets of the designed {4,5,6,8} toward
the 20-bit sink, one screening round per leg, digest-screened
(`sweep.ndjson`, `sweep.log`). Findings:

1. **Short decode is build-bound, not bit-bound, on jw16:** every mask
   (including mask 0 and near-full sinks) screens at ~213–215 tok/s,
   while both package builds (-1 and the interim -2) sat at 190.7 /
   215.5 in the 12-round battery. The battery's "+13% short" split
   between the two PACKAGES is a build-configuration difference, not a
   barrier-bit effect.
2. **ctx1053 varies wildly per single round** (old-arm battery spread
   122–159; sweep masks 118–162), so the sweep's apparent ctx winners
   are noise. A paired 5-round interleaved spot of the best masks
   (`spot.ndjson`, `spot.log`) settles it:

| mask | bits | ctx1053 med | pins |
| --- | --- | ---: | --- |
| FFFFF (sink) | all | 140.5 | 5/5 |
| 168 ({4,5,7,8}) | designed−6+7 | 139.1 | 5/5 |
| FFFB (sink−{2}) | | 140.9 | 5/5 |
| 878 ({3,4,5,6,7,11}) | | 125.9 | 5/5 |

**Verdict: no Pareto-positive set found within the sweep budget; the
G13X trim stays reverted** (`5deac1c8068`), jw16 remains on the
hk6f6afc8-1 sink package (control ctx pin held after rollback). The
named trade: on the Max, ctx1053 (KV-stream bound) does not tolerate
any *reduction* of the per-launch maintenance we measured — the
candidates that help short in build terms do not move ctx, and ctx
moves only downward as bits are removed. The named jw16 mesa levers,
in order: (a) **L2 sector/cache policy for 16-bit SSBO repeat traffic**
(boundary receipt item 3 — the KV stream runs ~11.5 GB/s vs native's
322.9 GB/s), and (b) **reconcile the package build configuration with
the worktree codegen on G13X** — the ad-hoc meson build runs jw16 short
decode ~+12% (214 vs 191 tok/s) with identical digests, a build-flag
investigation, not a barrier one.

## 8. Addendum 3: jw16 sweep corrections and the toolchain-hypothesis test

Two corrections and one refuted hypothesis, from a decisive paired test
(`toolchain-ab.json`, `toolchain.log`):

1. **Correction (addendum 2, finding 1):** the jw16 short-decode split
   (190.7 vs ~214) is **barrier-bit-dependent, not build-bound**. The
   sweep's "sink-baseline DEFAULT" arm was invalid —
   `strtoul("DEFAULT", 16)` parses to 0xD — so the sweep never measured
   the true full-sink emission, and its flat-short reading was an
   artifact. The package pair proves the bit effect: -1 (full sink)
   short 190.66 vs -2 (designed {4,5,6,8}) 215.47, same recipe, same
   toolchain. Masks missing {0,1,2} run fast (0xFFF8 = 214.7); the full
   sink runs slow — the short poison lives in the {0,1,2}×sink
   configuration, while ctx1053 wants exactly those extra bits.
2. **Toolchain-drift hypothesis REFUTED:** package `hk5deac1c-2` (current
   tip 5deac1c8068: G13X = sink, built today) vs installed -1, 5-round
   paired on jw16: short 190.56 vs 190.69 (−0.07%), ctx1024 140.70 vs
   141.89 (−0.84%), pins 10/10. Package builds across Sep 8 → today are
   performance-identical at matched emission. (This also cross-checks
   the battery: -2's designed-set ctx 137.62 is a real bit effect.)
3. **jw16 final state:** `hk5deac1c-2` left installed (byte-equivalent
   emission to -1 on G13X, current source), llm-inference restarted
   active, rollback tarballs staged. The G13X trade stands as named:
   designed set buys +13% short at −3.2% ctx; the sink holds ctx. The
   residual remains the named L2 sector/cache policy lever, now with the
   sharpened statement that the ctx-relevant maintenance is in the
   {0,1,2} bit region whose presence costs the short win.
4. **jwm1:** no rebuild required — the tip differs from the installed
   `hkf96e090-2` only in the G13X gate (dead code on G13G); jwm1's
   packaged numbers (+6.32% ctx1053 / +2.90% short, pins+suite green)
   stand as measured.
