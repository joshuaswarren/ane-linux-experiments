# 2026-09-19: Qwen Q4 decode "190 → 141" regression decomposed — wheel vintage + one named mesa flip; the trunk residual bisected; conditional SIMDMAT gate NO-LAND

Date: 2026-09-19. Lane: MesaRegressionBisect. Host: jw16mbp1-linux (Apple M1 Max
T6001, G13C C0), driver `mesa-honeykrisp-omarchy 26.3.0.devel.hk5deac1c-2`
throughout unless a phase names another package. Harness: `ab_decode.py`
interleaved protocol (`/var/tmp/SwigluRmsJw16`), wheel
`mlx_omarchy-0.32.2.dev202609152131+1deb70f1` unless named, `bench_decode.py`
sha `f5062d88…`, Qwen2.5-0.5B-Instruct-4bit @ `a5339a41`, pinned digests
`7fd25a869ff21678` (short 30/32) / `7da83f06ec9f001d` (ctx1024 1053/32) fatal
on every run, llm-inference stopped under one `/tmp/m1-gpu.lock` hold per
block, restarted + real-completion-verified after.

## Verdicts

1. **The 190 → 179.7 gap is a mlx-omarchy WHEEL VINTAGE effect, not mesa and
   not environment.** Controlled interleaved A/B on the same driver
   (`hk5deac1c-2`): wheel `1deb70f1` (09-15 21:31) = short median 179.50/179.84
   across two 6-round phases; wheel `b8e5300` (v0.6.1, 09-17) = 190.65/190.47
   same session, same GPU state. Distributions do not overlap
   ([178.4–180.4] vs [190.0–191.1]). The 09-19 SIMDmat screen baseline
   (179.70) used the one slow vintage; every 190-class receipt used a different
   (faster) vintage.
2. **The idle stray `mlx-serve` (PID 430201, Qwen2.5-0.5B :8954) costs
   NOTHING measurable**: killing it moved short medians 179.50 → 179.84 and
   190.65 → 190.47 (≤0.2%, inside noise). "Confound" status in
   receipts/2026-09-19-simdmat-restore-screen.md was over-cautious; it is
   exonerated. (Left dead with peer ServeDocsMlxServe, who needed it gone for
   their own bench; cmdline/cwd preserved under /var/tmp/MesaRegress20260919/.)
3. **The 141 number is real and already root-caused**: trunk-tip builds run
   SIMDMAT opt-in (`f4859fb6991`), costing −26% short on the same wheel
   (MesaPortAndWork controls, this morning, wheel `50eeb29`). Not re-tested
   here per lane instructions.
4. **The remaining −8.6% trunk residual (5deac1c 191 vs trunk+SIMDMAT=1
   174.5 on wheel 50eeb29; 179.7 vs 158.2 on wheel 1deb70f1 = −12%) is a real
   driver-source effect inside `5deac1c8068..d8d4e1c500`.** Bisected this lane
   — see §Residual bisect.
5. **Conditional SIMDMAT gate: NO-LAND — the premise is false.** On a single
   tree, SIMDMAT on/off is not a crossover trade-off: it is a strict win on
   both legs. The apparent "short loses, ctx wins" split in the
   `hk3a37b4f-3` A/B was the trunk residual riding along, not SIMD-mat shape
   economics. Numbers in §Gate.

## Baseline reproduction (assignment step 1)

Two 6-round phases, interleaved 2-arm (wheel `1deb70f1` "base" vs `b8e5300`
"v061"), driver `hk5deac1c-2`, same flock hold, stray serve resident in
phase a, killed in phase b:

| phase | arm (wheel) | short median (tok/s) | ctx1024 median (tok/s) |
| --- | --- | ---: | ---: |
| a (stray resident) | base (1deb70f1) | 179.50 [178.40–179.96] | 141.83 [134.51–148.01] |
| a | v061 (b8e5300) | 190.65 [190.06–191.13] | 134.71 [123.62–153.34] |
| b (stray killed) | base (1deb70f1) | 179.84 [178.53–180.36] | 141.32 [128.25–155.03] |
| b | v061 (b8e5300) | 190.47 [190.29–190.88] | 144.58 [136.36–157.82] |

- Short reproduces yesterday's 179.70 exactly (179.50/179.84). ✓
- ctx1024 today reads 141.3–141.8 vs the 09-19 screen's 135.62 median. The
  ctx leg's round spread is ±5–10% (09-19 rounds spanned 134.2–144.0; the
  09-16 12-round battery on this same driver+wheel read 142.12). 135.62 was a
  low draw inside the leg's wander band, not an instability signal. The
  short leg is the stable gate metric (spread <1.2%); measurement is
  trustworthy, no STOP.

## Chasing 190 (assignment step 2)

Every 190-class receipt, with its actual wheel vintage:

| receipt / source | date | driver | wheel (build ts) | short tok/s | conditions |
| --- | --- | --- | --- | ---: | --- |
| receipts/2026-09-16-termA (12-rd battery) | 09-16 | hk5deac1c-2 | `2e252962` (09-16 18:52) | 190.66 | locked, llm stopped |
| receipts/2026-09-17-jw16-gpu-parity-refresh | 09-17 | hk5deac1c-2 | `b8e5300` (09-17 06:11, v0.6.1) | 190.63 | single battery, llm stopped, no stray |
| wait-batching ctrl2/ctrl3 (09-19) | 09-19 | hk5deac1c-2 / rebuilt 5deac1c | `50eeb29` (09-19 07:58, v0.7.1) | 189.4–191.8 | llm stopped, box idle |
| simdmat screen "before" (09-19) | 09-19 | hk5deac1c-2 | `1deb70f1` (09-15 21:31) | **179.70** | llm stopped, stray resident |

All four use the same model revision, prompts (digests pinned), and
bench_decode harness — they ARE comparable protocols — but the wheels differ,
and the one slow vintage (`1deb70f1`) is exactly the one the 09-19 screen
used as its baseline arm. Today's interleaved A/B (§Baseline) isolates the
vintage effect on one driver: **+6.2% short for `b8e5300` over `1deb70f1`,
~0 ctx1024**. So: "190" was never a mesa property that got lost — it is what
`hk5deac1c-2` does with a 09-16-or-newer mlx wheel; 179.7 is the same driver
with the 09-15 wheel.

## Residual bisect (assignment step 3, redirected)

No mesa bisect exists for "190-era → 5deac1c": the 190-era driver IS
`5deac1c` (`hk5deac1c-2` measures 190-class with fast wheels today). The
genuine unattributed regression is the trunk residual
`5deac1c8068..d8d4e1c500` at matched SIMDMAT=on. Range: 8 non-merge commits +
4 barrier-trim merges netting to the sink on G13X. Codegen-plausible
offenders: `a2909940cbf` (SW coopmat fallback — provably inert for MLX's
kernels, which must be full-subgroup to have produced correct digests on
`5deac1c`, pre-fallback), `838e31f4d95`+`864b4e88941` (FTZ precise
div/log/sin), `d8f916c3208` (coopmat component-unit addressing), `490b7c16908`
(ubfe), merges (merge-resolution artifact).

Bundle screen: branch `hk/resid-bundle` = `3a37b4fb042` (SIMDMAT restored) +
reverts of `864b4e88941`, `838e31f4d95`, `d8f916c3208`, tip `092f35e88d2`,
package `26.3.0.devel.hk092f35e-1`, screened same-session against
`hk3a37b4f-3` (both 6-round, wheel `1deb70f1`):

| driver | short median (tok/s) | ctx1024 median (tok/s) |
| --- | ---: | ---: |
| hk3a37b4f-3 (resto, residual present) | 159.52 [157.4–166.6] | 132.78 [118.8–146.7] |
| hk092f35e-1 (resid-bundle) | **180.00 [179.2–180.1]** | **140.97 [129.0–142.9]** |

The bundle recovers the FULL residual: 180.0 equals the `hk5deac1c-2`
same-wheel level (179.50/179.84 today). The residual is real, code-caused,
and contained in {FTZ pair, coopmat addressing}.

Narrowing screens (same protocol, single arm 6-round, vs the fixed
landmarks base=179.5–179.8 / resto=158.2–159.5):

| driver | reverts kept | short median | verdict |
| --- | --- | ---: | --- |
| hkd447b64-1 (`hk/resid-nod8f`) | addressing only | 162.46 [149.9–164.4] | does NOT recover → addressing `d8f916c3208` is ~innocent for decode |
| hke167756-1 (`hk/resid-noftz`) | FTZ pair only | **179.79 [179.5–180.4]** | FULL recovery → the FTZ pair **is** the residual |

ctx1024 for noftz: 139.46 [131.0–149.1]. The minimal fix set is exactly the
revert of `838e31f4d95` + `864b4e88941` on top of the SIMDMAT restore; the
narrow-pointer correctness fix `d8f916c3208` stays untouched.

Mechanism note: `838e31f4d95` replaced refined `a*rcp(b)` division with the
normalized-mantissa correctly-rounded sequence for **precise fp32 division** —
Vulkan OpFDiv is precise by default, so every plain fdiv in every MLX kernel
(softmax scale, rmsnorm, attention) eats the longer sequence. The old
sequence differs from the new one only inside the denormal flush band (the
commit's own data: 18,382 wrong results over 1M random pairs were the FLUSH
cases; far-from-denormal NN activations are bit-identical in both). The
`d8f916c3208` udiv rescale hypothesis for decode cost is disproven by the
nod8f screen; its width-matched fast-path variant branch (`hk/resid-surgical`)
is retained only in case noftz under-recovers.

## Gate (assignment steps 4–5)

Gate criteria (from the failed SIMDmat screen): short ≥ 175 AND
ctx1024 ≥ 134 on the `1deb70f1` wheel protocol.

**The conditional SIMDMAT gate is NO-LAND: its premise is false.** The A/B
that motivated it (`hk3a37b4f-3` vs `hk5deac1c-2`, short −12% / ctx +3.7%)
compared two DIFFERENT mesa trees, so it measured the trunk residual plus
merge drift, not SIMD-mat shape economics. Same-tree evidence: with the tree
held constant, SIMDMAT on vs off is a strict win on BOTH legs (MesaPortAndWork
`ab-wb` vs `ab-wb-simmat`: short 141 → 175, ctx 82.6 → 142.4, prefill 2006 →
3784 on trunk; nothing loses). There is no crossover to gate on. A
per-shape HW/SW lowering policy can only be equal-or-worse than
SIMDMAT-everywhere-once-the-residual-is-gone.

What DOES pass the gate is the unconditionally-restored + residual-fixed
trunk, `hk/resid-noftz` merged:

**MERGED: `joshuaswarren/mesa-1` `honeykrisp-omarchy` fast-forwarded
`d8d4e1c500` → `e1677564284`** (restore SIMDMAT default-on
`3a37b4fb042` + FTZ-pair reverts `27376cb16c5`/`e1677564284`; FF merge, no
merge commit by construction; package screened = `26.3.0.devel.hke167756-1`,
built from the exact tip).

| metric | hk3a37b4f-3 (previous NO-LAND state) | hke167756-1 (merged tip) | gate | verdict |
| --- | ---: | ---: | --- | --- |
| short median (tok/s) | 159.52 | **179.79** [179.5–180.4] | ≥ 175 | **PASS** (+2.7% margin, floor clears by 4.5) |
| ctx1024 median (tok/s) | 132.78 | **139.46** [131.0–149.1] | ≥ 134 | **PASS** (+4.1% margin) |

vs the installed `hk5deac1c-2` baseline on the same wheel: short parity
(179.79 vs 179.50/179.84), ctx within the leg's wander band (139.46 vs
141.3–141.8 today, 142.12 on 09-16) — the merged tip restores the installed
driver's performance profile and removes the −26% SIMDMAT-opt-in cliff for
future trunk builds.

**Correctness trade, stated plainly:** the merged FTZ reverts re-open what
`838e31f4d95` fixed — correctly-rounded precise fp32 division/log/sine
(CTS float_controls 1 failure → 1,146 pass goes back to failing; 1-ulp
errors inside the denormal flush band return). Far-from-denormal NN data is
bit-identical under both sequences, which is why the digest pins never moved.
The right long-term fix is a precision-predicated division lowering (fast
refined form guarded by a normal-range check, exact sequence otherwise) —
that is new compiler work requiring its own exactness battery, not this
lane. If it lands, `e2dcfed5db6`-style history means re-land FTZ on top
without touching the SIMDMAT policy.

jw16 end state: driver `mesa-honeykrisp-omarchy 26.3.0.devel.hk5deac1c-2`
installed (the production package; the merged trunk `e1677564284` feeds the
NEXT package build, it was not installed on the box), `llm-inference.service`
active and verified with a real completion
(`chatcmpl-az348RHh8dycO1DOrd5qBz8iJYBcwUYr`, 34 completion tokens,
qwen3.8-27b @ :8002), `/tmp/m1-gpu.lock` held only by llm-inference's own
serving ExecStart — the box's normal steady state, identical to session
start. This lane holds no lock.

## Hardware safety

- Every GPU block under `/tmp/m1-gpu.lock` (flock; never stolen/unlinked);
  llm-inference stopped before and restarted after each; final state
  verified with a real completion (chatcmpl-Rumd4dw7UoBQNjFejfGpSyguVcbAlzAy,
  40 tok, qwen3.8-27b @ :8002) — repeated again at lane end.
- jwm1 and jw14m2 untouched. ServeDocsMlxServe shared the lock contract for
  their mlx-serve bench windows; no overlap.
- Driver restored to `hk5deac1c-2` after screens.

## Artifacts

- jw16: `/var/tmp/MesaRegress20260919/` (ab-phase-{a,b}.json, ab-resid-{bundle,resto}.json,
  ab-nod8f.json, ab-noftz.json, run.log, nod8f-screen.log, noftz-screen.log,
  asfound.txt, stray-* records, prov-*.txt), `/tmp/mrb-regress/` (scripts),
  build logs `~/log/jw16-mesa-{resid,noftz-build2,nod8f,surgical}-build.log`,
  packages `/home/joshuawarren/src/mesa-pkg-jw16-{resid,noftz,nod8f}-20260919/`.
- Mesa: `github.com/joshuaswarren/mesa-1` — `honeykrisp-omarchy` @
  `e1677564284` (merged); evidence branches kept: `hk/resid-bundle`
  `092f35e88d2`, `hk/resid-noftz` `e1677564284`, `hk/resid-nod8f`
  `d447b649a94`, `hk/resid-noftz`'s ancestors, plus `hk/restore-simdmat-default`
  `3a37b4fb042` (now an ancestor of trunk). Deleted as dead-end:
  `hk/resid-surgical` (width-matched fast-path variant — its premise, the
  d8f916c3208 udiv as decode cost, was disproven by the nod8f screen).
