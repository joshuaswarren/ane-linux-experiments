
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

## 9. Addendum 4: jw16 per-bit localization — the instrument was invalid; four byte-verified packaged probes; the G13X trade is a coupled mechanism, NO-LAND

Lane: MesaL2Policy (L2/barrier-bit assignment), 2026-09-16. Everything in
this addendum ran on jw16 under `/tmp/m1-gpu.lock` (`flock -w 900`,
service stopped only inside a window, restart+confirm after each; the
service is `active` and `hk5deac1c-2` remains installed).

### 9.1 Instrument correction (supersedes the mask readings in addenda 2–3)

The `knob.so` relayed to jw16 (`/var/tmp/TermAJW16/knob.so`, md5
`ad99693c6e0b7931c58a059106798507`) contains **no** `HK_CDMBARBITS`/
`HK_APPBAR` code (`strings`; the sibling lane confirms it was build3
rebuilt at the trim commits before relay). `agxdecode` shows it emits the
designed set {4,5,6,8} on G13X under **any** `HK_CDMBARBITS` value
including FFFFF. Therefore every jw16 "mask" arm in addenda 2–3 (the
24-mask sweep, the FFFB 140.9 / 168 139.1 / 878 125.9 five-round spot
medians, and the "0xFFF8 = 214.7" short reading) measured the **same
designed emission**: they are noise samples, not mask effects.
Addendum 3's statement that "ctx1053 wants exactly the {0,1,2} bits" is
retracted. The package-pair numbers those addenda rest on for the sink
vs designed comparison (short 190.66 / ctx 142.12 vs short 215.47 /
ctx 137.62, 12-round, pins 48/48) are unaffected. The jwm1 G13G lineage
stands (its sweep ran on a live knob build; drop6 pin-break and
mask-0-broken arms prove mask response; the packaged land gates are
independent of any knob).

New receipt-grade instrument: `ASAHI_MESA_DEBUG=trace` +
`AGXDECODE_DUMP_FILE=<dir>/dump` dumps every CDM_BARRIER with named
fields (`AGX_DEBUG` does **not** enable tracing). Every probe below was
byte-verified against its intended field-set before measurement
(`jw16-decision*.log` fingerprints).

### 9.2 Noise floor (uniform-emission 5×5 screen)

A 5-arm × 5-round × 2-leg screen on the (unknowingly uniform) designed
emission doubles as the host noise floor (`jw16-noisefloor-screen.*`):
short per-arm medians 213.47–214.52 (±0.25% — short is low-noise at
fixed emission); ctx1024 per-run 118–178 across the day, per-arm
5-round medians spread 6.4%. ctx decisions need n≥12 interleaved rounds
with a same-window baseline arm; short resolves 1% effects.

### 9.3 Four packaged, byte-verified probes (branch per mask, same PKGBUILD recipe)

Branches on `github.com/joshuaswarren/mesa`, all off `d8d4e1c500b`
(current `hk/cdm-integration`, untouched), each packaged with the
unchanged asahi-alarm recipe (`_commit` per candidate, makepkg rc=0 on
jwm1) and agxdecode-verified before measurement:

| set | branch / package | short (tok/s) | ctx1024 (tok/s) | pins |
| --- | --- | ---: | ---: | --- |
| sink {0..19} | `hk5deac1c-2` (installed) | 190.66 (12-rd) | 142.12 (12-rd) | hold |
| designed {4,5,6,8} | `hkd71c94e-2` | 215.47 (12-rd) | 137.62 (12-rd) | hold |
| sink−unk_2 {0,1,3,4..19} | `hk/cdm-g13x-fffb` `669557609f6` → `hk6695576-2` | **145.8 (r0)** | **84.3 (r0)** | hold |
| designed, 7 for 6 {4,5,7,8} | `hk/cdm-g13x-578` `49c21f17b18` → `hk49c21f1-2` | — | — | **BROKEN r0** |
| G13G trim on G13X {4,5,6,7,8} | `hk/cdm-g13x-1f0` `5cd0e72f32f` → `hk5cd0e72-2` | **156.5 (r0)** | **87.0 (r0)** | hold |
| designed+USC-inval {3,4,5,6,8} | `hk/cdm-g13x-178` `242e591a853` → `hk242e591-2` | — | — | — (bench failed at instance creation; unmeasured) |

### 9.4 Mechanism, named to the precision the data supports

1. **The CDM_BARRIER bits are a coupled maintenance family, not
   independent switches.** On G13X, two departures from the known-good
   sets are correctness cliffs: dropping unk_6 ({4,5,7,8}) breaks
   generated-ID digests on the first run (matching jwm1's "drop 6 from
   the sink breaks pins"), and jwm1 already showed {0..7}-only subsets
   break. Two further departures are **performance cliffs that dwarf the
   trade**: sink−unk_2 (digests clean) measures −24% short / −40% ctx at
   round 0 (short noise is ±0.5%, so this is decisive at n=1), and
   {4,5,6,7,8} measures −18% short / −38% ctx. The working model: the
   sink bits include flush-trigger/wait-drain pairs; combinations that
   arm a wait without its flush (or drop a flush a wait depends on)
   stall the CDM stream for tens of µs per dispatch. bit 3 is the only
   individually named bit (USC cache invalidate, Asahi Lina); bits 24/26
   are cluster-related (G13X/G14X emission sites).
2. **The measured G13X trade stands, and is not beatable by bounded
   subset selection.** Known-good sets are exactly the full sink
   (ctx-protective: +3.17% ctx1053, short-poison: −13%) and the designed
   set (mirror image). Every sampled subset between them is
   correctness-broken or hits a −18…−40% cliff. jw16 therefore keeps
   `hk5deac1c-2` (full sink); **NO-LAND**.
3. **KV-stream lever mapping (the term-B handoff).** AGX exposes no
   per-descriptor cache-policy or L2 eviction-hint field anywhere in the
   descriptor XML/uAPI; the only per-access control is the load/store
   instruction coherency field (bits 44:46; 4=default, 7=coherent —
   `agx_pack.c`), plus the CDM_BARRIER family measured here. The ~11 GB/s
   effective KV rate is therefore not addressable by a cache-policy
   knob in this driver generation; the next pass for term B is L2
   sector-traffic tracing of the 7× repeat-head dedup (the sibling
   receipt's (a)), not barrier bits or descriptors.

### 9.5 Artifacts

jw16 `receipts/2026-09-16-termA/`: `jw16-decision1.log`,
`jw16-decision2.log` (fingerprints + battery rows + rc),
`jw16-noisefloor-screen.{log,json}`, `emit/` (agxdecode dumps).
jw16 workdir `/var/tmp/MesaL2/` (scripts: `decision2.sh`, `prep-pkg.sh`,
`driver-ab.py`, `land.sh` unused). jwm1 `/var/tmp/MesaL2build/`
(`build.log`, `build2.log`, PKGBUILD restored to `_commit=5deac1c`).
Mesa branches pushed: `hk/cdm-g13x-fffb`, `hk/cdm-g13x-578`,
`hk/cdm-g13x-1f0`, `hk/cdm-g13x-178`. `63c1d3cf` not merged; jwm1
packages and numbers untouched.
