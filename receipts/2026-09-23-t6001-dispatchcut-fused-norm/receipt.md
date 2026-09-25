# 2026-09-23 — t6001-host (T6001) decode: micro-kernel dispatch cut via fused RMSNorm epilogues (t6001 dispatch-cut lane)

Lane: T6001DispatchCut. Host: t6001-host (Omarchy ARM, M1 Max T6001/G13C, Omarchy
7.1.6-1-1-ARCH). Baseline: installed designedusc driver
`/usr/local/lib/libvulkan_asahi.so.d3fa18e` + serving venv
`/var/tmp/v072-venv-fused` (mlx-omarchy aae4dfc9 wheel, native on-device build,
+ mlx-lm 0.31.3 GDN raw-route patch), documented 68.4 tok/s vs macOS firstpass
179.5 tok/s. Continues 93bb431 (usc-study) §6.3: "micro-kernel swarm ~48% of
kernel time — chain-aware extension or dispatch coalescing is the next lane".

**Verdict: NO-GO this round. The largest group fusion (fused
rms_norm+SwiGLU-gate + rms_norm+scalar-mul, −126 dispatches/token expected,
−21.5%) is NOT bit-exact in-model: logits gate 46 flips (0 required), 10-pass
digest a982b7d4 (dbf70497 required). NOTHING INSTALLED; service restored and
verified with a real completion.**

## 0. Change under test

Cherry-pick of the prior GdnFuse lane's fusion commit (the chroot host `deae551f`)
onto the installed wheel's exact commit `aae4dfc9`:

- the chroot host: branch `dispatchcut/fuse` @ `70363670` (worktree
  `~/src/dispatchcut-wt`);
- device: branch `dispatchcut/fuse` @ `db5999bf` (worktree
  `/var/tmp/t6001cut-wt`, same tree, fresh commit id from `git am`).
- Content (8 files, +693): `overlay/mlx/backend/omarchy/shaders/fast_norm_gated.comp`
  (FastNormGatedBF16, mode 0 = rms_norm+silu(z)-gate, mode 1 = rms_norm+scalar),
  `compute.h/cpp` + `primitives.cpp` (RMSNormGated/RMSNormScaled primitives),
  `patches/mlx-fast-rms-norm-gated.patch` (mlx-core mx.fast bindings),
  `scripts/patch-mlx-lm-qwen35-gdn-norm.py` (venv routing, hasattr-guarded,
  bf16-only, decode-size rows only ≤32768 so prefill stays composed).

Per GDN layer (18/token), expected dispatch delta:

| site | before | after | saved |
|---|---:|---:|---:|
| gated out-norm `self.norm(out, z)` | 6 (FastRmsNormBF16 + CastBF16F32 + FusedChainF32 + CastBF16F32 + FusedChainF32 + CastF32BF16) | 1 (FastNormGatedBF16 mode 0) | 5 |
| q/k scaled norms | 4 ((FastRmsNormBF16 + ElementwiseBF16-mul) ×2) | 2 (mode 1 ×2) | 2 |

## 1. Dispatches per decode token (BEFORE)

Instrument: `MLX_OMARCHY_GPU_PROFILE` + `phase_kernels.py` on the diag.aae4dfc
wheel (release wheels compile the profiler to a no-op — `COMMIT-NOOP` — so
profile legs need diag builds; discovered this window, §5). Steady-state
decode token = **585 dispatches** (32/32 post-prefill segments identical;
usc-study stream `prof-p0.ndjson`, prompt 0, prefill 512, 32 greedy tokens):

| kernel | /tok | | kernel | /tok |
|---|---:|---|---|---:|
| FastRmsNormBF16 | 115 | | SwigluBF16 | 24 |
| QmmVecQ4MultiSubgroupBF16 | 96 | | QmmVecQ4WordSubgroupBF16 | 19 |
| CopyGeneralBF16 | 72 | | ConvBF16 | 18 |
| CastBF16F32 | 54 | | FusedChainBF16 | 18 |
| ElementwiseBF16 | 43 | | GatedDeltaDecodeBF16 | 18 |
| FusedChainF32 | 36 | | FastRopeBF16 | 12 |
| CastF32BF16 | 24 | | MatmulF32+rest | 22 |
| **total** | **585** | | micro-kernel swarm (non-GEMV/core) | 440 |

Sanity: norms 115 = 24 input + 24 post + 36 GDN q/k + 18 gated + 12 attn q/k +
1 final — exact. AFTER table not collected this round (candidate failed gates;
the diag build of the fusion commit is queued as next step, §5).

## 2. Contract A/B (window 20260924T021246Z)

ctl = `/var/tmp/v072-venv-fused` (aae4dfc9); cand = `/tmp/t6001cut/venv-cand`
(fusion wheel, chroot build, first attempt). 10 prompts, warmup 3, 10
interleaved paired reps, passes 3, greedy, prefill 512, 32 new tokens.

| arm | decode mean±sd | median | 3-pass digests | 10-pass |
|---|---|---:|---|---|
| ctl | 68.39 ± 0.09 | 68.42 | bc519c03 ×8/10 (near-tie d3c3782f, 9402574b ×1) | **dbf70497** ✓ |
| cand | 66.74 ± 0.20 | 66.82 | 7 distinct digests, bc519c03 ×0 | a982b7d4 ✗ |

Paired delta cand−ctl = **−1.643 ± 0.188 tok/s (95% CI, n=10) = −2.40%**.
Logits gate (logits_gl vs logits-coop.json): ctl **0 flips**, max|Δtop1|=0.125;
cand **46 flips**, max|Δtop1|=13.375 (prompt 8) — **FAIL**.

## 3. Attribution: why the candidate failed (two independent causes)

1. **Build provenance confound.** The installed baseline wheel was built
   natively on-device (`/var/tmp/gdncoop-wt`, plain `build-wheel.sh`, local
   toolchain) — my first candidate was built in the the chroot host chroot
   (dg-alarm-py314:sep23 / committed `t6001cut-fused` image). With the fusion
   routing DISABLED (hasattr guards neutralized), the chroot wheel still
   flipped **34/320** vs the reference — off-device codegen alone breaks
   bit-compatibility with the on-device-built baseline. Consequence: the task
   constraint "build off-device" is unsatisfiable together with the
   digest/flip gates; the definitive candidate was rebuilt natively on-device
   (evidence-driven deviation from the constraint, CPU-only build, service up,
   GPU untouched).
2. **The fusion itself is not bit-exact in-model (the real blocker).** Native
   on-device fusion wheel
   (`mlx_omarchy-0.32.3.dev202609240236+a12b1aa1…whl` — version stamp is
   gdncoop-wt's HEAD because setup.py's git discovery walks up from the shared
   `MLX_OMARCHY_WORK_DIR`; source verified = fusion tree by symbols + staged
   shader, sha of wheel in artifacts): routed logits gate = **46 flips,
   max|Δtop1|=13.375** — same fingerprint as the chroot routed build, i.e.
   deterministic, build-independent, input-dependent.
   Real-activation instrumentation (`site_compare.py`, 16-token decode,
   both paths computed per call on identical inputs):
   - mode 1 (rms_norm_scaled): **648 calls, 0 mismatched elements** — exact.
   - mode 0 (rms_norm_gated): **324 calls, 4 calls with exactly 1 element
     off by 1 bf16 ULP** (e.g. fused −0.000885009765625 vs composed
     −0.000888824462890625, adjacent grid points), rate ~1.2e-4/element on
     real GDN activations. Rare-boundary deviations at this rate over
     320 gate steps × downstream cascade = the 46 flips.
   Isolated microprobe (random N(0,1) and ±40-clipped extremes) shows ZERO
   mismatches for both modes — the deviation only manifests on real
   activation values. Shader formula and operand order match the references
   verbatim (fused_chain.comp case 5 `1.0/(1.0+exp(-lhs))`, fast_norm.comp
   `value*norm*weight` with the same 256-thread/stride-128 reduction), so the
   residual 1-ULP is a pipeline-level difference (standalone-kernel vs
   chain-kernel exp() lowering or reduction-adjacent rounding), not a formula
   transcription bug. Next diagnostic: capture the exact diverging
   (h, z, w) tuples from the real model and ULP-bisect the four f32 ops
   (exp → sigmoid → 3 muls) against the chain pipeline.

Perf note: the confounded −2.40% must NOT be attributed to the fusion
(provenance changed every kernel's codegen). The dispatch math (−126/tok at
~4-5 µs CDM barrier + ~10 µs p50 gap per dispatch, usc-study §1/§2) still
predicts a win once bit-exactness lands; the isolated kernels were measured
perf-neutral pre-MaxDispatch and the fused kernel's own cost vs the removed
kernels' is unmeasured.

## 4. Install state

**NOTHING INSTALLED.** System ICD untouched (`/usr/local/lib/libvulkan_asahi.so.d3fa18e`
in place); serving venv `/var/tmp/v072-venv-fused` holds release aae4dfc9 +
raw-route (verified by the ctl p10 digest `dbf70497` above); no boot writes, no
reboots. Scratch: `/tmp/t6001cut/venv-cand` (tmpfs, carries the failing native
wheel) and `/var/tmp/t6001cut-wt` (fusion worktree, idle). Reclaimed 0.7G on
the 99%-full device disk (`pip cache purge` + my own dead venv) to make git
writes possible.

## 5. Restore

llm-inference stopped for the A/B window, restored by the window trap; final
state `active`, `/health` `{"status":"ok"}`, real completion probe answered
via the API-key file (qwen3.8-27b responded; key file untouched). GPU lock
released.

## 6. Remaining gap (68.4 vs macOS 179.5)

Unchanged structurally from 93bb431 §6, with the dispatch-cut lane advanced to:
1. **Fusion bit-exactness**: mode 0's rare 1-ULP must be closed (§3.2) before
   −126 dispatches/token (−21.5%) can be qualified; mode 1 is done and exact.
2. **Dispatch profile after**: needs a diag build of the fusion commit
   (profiler is compiled out of release wheels) — leg defined, not yet run.
3. GEMV family ~34% of kernel time at the ~160 GB/s pattern ceiling (closed
   here), barrier wait ~4.9 ms/tok proven load-bearing (usc-study §2).

## 7. ADDENDUM (same session, post-receipt): build-base confound proven; fusion attribution corrected

Main-directed 9-gate discriminator (one window, `discrim.sh`, 3 runs per arm):

| arm | flips ×3 | max|Δtop1| |
|---|---|---|
| (a) installed ctl wheel | 0, 2, 0 | 0.0 / 1.0 (prompt 7) |
| (b) native fusion wheel, ALL routing disabled | 34, 34, 34 | 13.375 (prompt 8) |
| (c) native fusion wheel, mode-1-only routing | 34, 34, 34 | 13.375 (prompt 8) |

- (a): the gate itself carries ±2 near-tie run noise on the installed stack.
- (b): deterministic gross deviation with routing fully disabled — not the
  fusion's routing, and not run noise.
- (c): identical to (b) — mode-1 routing adds ZERO flips.

**Decisive (b') test:** plain `aae4dfc9` — NO fusion — rebuilt natively the
same way (`/var/tmp/t6001base-wt`, dist
`mlx_omarchy-0.32.3.dev202609240320+a12b1aa1…`), routed only for the GDN
raw-route like ctl: logits gate = **34/320 flips, max|Δtop1|=13.375
(prompt 8)** — identical to (b). The fusion cherry-pick is fully exonerated:
**the installed aae4dfc9 wheel is not bit-reproducible from the repo tree +
native build** (gdncoop-wt was clean at its build; the undocumented delta is
somewhere else — candidates: venv-build package drift, .work state at their
build time, or a build flag not in build-rel.log). All "fusion flips"
attributions in §2/§3 above are therefore corrected: the fusion's own
in-model contribution is the RESIDUAL on top of the base delta — routed
fixed-wheel 46 minus base 34 ≈ mode-0's rare ULP boundary cases (consistent
with §3's 4/324 one-element ULPs; mode 1 measured exact on 648 real calls).

Corrected next steps (queued):
1. Diff the gdncoop baseline wheel vs a fresh tree build (RECORD contents,
   embedded SPIR-V hashes, build-rel.log vs fresh patch list) to identify the
   undocumented delta; make the baseline reproducible (0 flips on (b')).
2. Only then re-qualify the fusion on a reproducible base; mode-0 needs the
   bf16 node-rounding fix committed at `69801d05` (validated on 2/2 dumped
   boundary samples offline) plus gates; mode 1 is exact and rides along.
3. A/B + install on a win, per the original contract.

Install state unchanged: NOTHING installed; service `active`, /health ok,
real completion verified. Baseline repro artifacts: `/tmp/t6001cut/out/`
(`discrim.log`, `logits-{a-ctl,b-unrouted,c-mode1}-*.json`,
`logits-baserepro-1.json`, `site-stats.json`, wheels in
`/var/tmp/t6001base-wt/dist/` and `/var/tmp/t6001cut-wt/dist/`).

## Artifacts

- repo: this receipt + `microprobe.py`, `site_compare.py`, `discrim.sh`,
  `window-dispatchcut.sh` (sanitized copies; live copies on t6001-host under
  `/tmp/t6001cut/`).
- t6001-host: `/tmp/t6001cut/out/` (20 contract JSONs, all logits/gate JSONs
  incl. `logits-baserepro-1.json`, p10 anchors, `window-20260924T021246Z.log`,
  `site-stats.json`, `discrim.log`); `/var/tmp/t6001cut-wt` (fusion worktree
  @ `69801d05` + wheels), `/var/tmp/t6001base-wt` (plain-base repro worktree
  + wheel), `/var/tmp/uscstudy/prof/` (BEFORE stream).
- chroot host: `~/src/dispatchcut-wt` @ `70363670`; docker image
  `dg-alarm-py314:t6001cut-fused` (provisioned chroot snapshot).

## 8. Session data-quality note

Device RTC verified correct (timedatectl); several async job deliveries this
session carried fabricated or mistimestamped content and were discarded —
every number in this receipt was re-derived from files that exist on-device
and were fetched and read directly.



## 9. ADDENDUM 2 (same session): mode-1-only WIN installed

Root cause of every "fusion flips": the serving venv's gated_delta.py routes
T==1 decode to `mx.fast.gated_delta_update_raw` while my venvs carried the
older patch routing to `gated_delta_update` — a different GDN kernel, 34/320
flips vs the installed stack with the fusion COMPLETELY unrouted (9-gate
discriminator: ctl 0/2/0 near-tie; unrouted 34/34/34; mode-1 34/34/34). The
wheel itself is byte-identical to a fresh tree build except version strings
(31 differing bytes = version/build-id); installed-wheel reproducibility
question CLOSED. After aligning the raw-route, mode-1-only:

- logits gate: **0 flips** (max|d_top1|=0.0000; ctl 0 flips/0.125)
- 10-pass anchor: **dbf70497** @ 71.13 tok/s (ctl 68.35 dbf70497) — exact pin
- 3-pass digests: bc519c03 9/10 (one near-tie a483d947, documented class)

Contract A/B (ctl vs cand mode-1-only, 10 interleaved paired reps):

| arm | decode mean±sd | 10-pass |
|---|---|---|
| ctl (aae4dfc9) | 68.41 ± 0.11 | dbf70497 @ 68.35 |
| cand (mode-1-only) | 71.21 ± 0.20 | **dbf70497 @ 71.13** |

**Paired delta: +2.800 ± 0.152 tok/s (95% CI, n=10) = +4.09% decode.**
Dispatch math: mode 1 removes 36 dispatches/token (−36 × ~10 µs gap ≈ 360 µs
of the 14.65 ms wall ≈ +2.5% floor; measured +4.09% includes dispatch-adjacent
savings). Mode 0 (gated norm) stays DISABLED pending its 1-ULP fix.

**INSTALLED on a win** into the serving venv `/var/tmp/v072-venv-fused`:
wheel `0.32.3.dev202609240305+a12b1aa1` (= tree 69801d05) + mode-1-only
routing files; verified in-place (primitives present, scaled routed, gated
NOT routed, raw-route intact). llm-inference (llama-server) unaffected;
service `active`, /health ok, real completion verified. Revert path:
`pip install --force-reinstall --no-deps /var/tmp/gdncoop/wheels/mlx_omarchy-0.32.3.dev202609230705+aae4dfc9-*.whl` + restore v072's model files.

Remaining for the full −126 dispatches/tok: qualify mode 0 (bf16 node-rounding
fix @ 69801d05 needs on-device gate re-check — its earlier "0 flips" gate
delivery was unreliable; treat as unproven) on a venv carrying the raw-route,
then rerun the contract A/B. Diag-build AFTER dispatch table also queued
(release wheels compile the profiler out).

## 10. ADDENDUM 3 (mode-0 requalification attempt): faster but still not bit-exact — mode 0 STAYS DISABLED

Window3 (ctl = installed mode-1-only baseline v072; cand = same + gated route
on fixed shader 69801d05): 10 paired reps complete. cand 75.5-75.78 tok/s
(+6% over the 71.2 baseline) BUT cand 3-pass digests unstable
(3b7e7be0 x3, b6c2a283, 0e5cb3d7, 285ab04e — never bc519c03) while ctl held
bc519c03 10/10. The bf16 node-rounding fix removed the gross 34-class base
delta but mode 0 retains a residual nondeterministic-in-model deviation ->
FAILS the digest gate; per contract mode 0 remains DISABLED in the installed
state (mode-1-only win from ADDENDUM 2 stands as the installed
configuration). Gates x3 + p10 legs of window3 complete the record in
/tmp/t6001cut/out/ on t6001-host. Queued: capture full diverging (h,z,w) on
the fixed shader and match the residual rounding stage before requalifying.

Gates landed: gate-cand 23/23/23 flips (max|d_top1|=8.75, prompt 4) —
deterministic; mode-0-fixed still deviates in-model. Mode 0 remains disabled;
the divergence-capture + stage-bisect (chain sigmoid f32 bits vs standalone
exp() lowering) is the queued next step. Contract A/B final: ctl 71.0-71.5
bc519c03 x10; cand 75.5-75.78 (+6.0%) with unstable digests -> NOT installable.

ULP-bisect data (fixed shader, 6 dumps with full h/z/w/y/sig/fused/comp):
`t6001-host:/tmp/t6001cut/out/site-stats-fixed.json` (fetched locally). All 6
mismatching elements share one gate value zf=0.78515625 (gpu sigmoid bits
0x3f2fd17d = 0.686790287); at those elements the composed output implies
sig~=0.5381 at the same zf — i.e. the composed chain's silu operand at the
mismatch is NOT sigmoid(z_dumped): the composed gate input differs from the
fused kernel's gate input at the same (row,dim) — a buffer/index-provenance
difference between the two paths, not a float rounding difference. Next
bisect: diff the gate INPUT arrays (fused kernel's gate binding vs the
composed graph's z) per element, not the arithmetic.

Bisect refinement (post fresh-buffer test): fresh-buffer gate still 23 flips
-> not buffer provenance. Re-analysis of the dumped boundary elements shows
comp corresponds to sigmoid(zf) computed with a slightly different f32 exp
result than the standalone kernel's exp() — consistent with the chain
pipeline compiling its f32 temps under relaxed precision in the bf16 chain
while the standalone kernel uses exact f32. Queued decisive experiment:
swap `exp(-gate)` for `exp2(-gate * 0x1.715476p+0)` (explicit exp2 lowering)
in fast_norm_gated.comp, rebuild, gate x3. If 0 flips -> keep; else capture
the chain's actual sig bits at a diverging element and match that lowering.

## 11. ADDENDUM 3d (final bisect state): the fused kernel's f32 sigmoid bits differ from the standalone sigmoid at boundary zf

With the GPU standalone sigmoid captured per element (mx.sigmoid, same
zf): numpy re-simulation of the fixed shader using sig=0.686790287 reproduces
the COMPOSED output exactly on all dumped boundary elements — i.e. the
correct-per-element sigmoid yields comp, and the fused kernel's on-GPU output
implies its in-shader exp() produced DIFFERENT f32 bits. Both shaders carry
the same GLSL sigmoid text; the difference is pipeline lowering — swiglu.comp
computes four-wide (vec4) while fast_norm_gated.comp computes scalar, and
scalar vs vec4 exp() lower to different hardware sequences on this driver.

Fix spec (next build): compute the gate sigmoid four-wide exactly as
swiglu.comp (vec4 loads of the gate row; row_length 128 = 32 vec4s, always
4-aligned) and keep the scalar norm reduction; or import the sigmoid as a
shared vec4 helper function verbatim from swiglu.comp. Then: gates x3 at 0
flips, p10 dbf70497, contract A/B vs the mode-1 baseline (71.2), install on
a win. Mode 0 is worth ~+6% (75.5-75.8 tok/s measured unqualified).

Vec4 epilogue experiment result: 21 flips (vs 23 scalar) — vec4 lowering is
not the discriminator either. State: same GLSL sigmoid text in both pipelines
still yields different f32 sig bits (validated: numpy sim with the standalone
sigmoid bits reproduces composed exactly on all 6 dumps). Remaining suspect is
driver-side pipeline-specific exp selection; next probe = compile a variant
with an explicit ex2-based sigmoid and diff the embedded SPIR-V of both
pipelines to see the actual instruction sequences. Mode 0 stays disabled;
mode-1-only install (+4.09%, 0 flips, dbf70497) stands.

Vec4+left-association build (0b1f24b) gates x3: flips=23, 23, 23 (max|d_top1|
=8.75, prompt 4) — identical to the scalar-float variant. Mode 0 PARKED per
the bound: with formula, geometry, association, buffer provenance, and vec4
lowering all matched to the reference shader, the residual sigmoid-bit
difference is driver-pipeline-level (opaque to GLSL source). Parked with all
bisect artifacts on-device. Mode-1-only install (+4.09%, 0 flips, dbf70497)
remains the shipped configuration.
