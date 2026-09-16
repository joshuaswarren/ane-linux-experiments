
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
