# 2026-09-23 — T6021 decode-gap levers: batchbudget A/B + split status

Lane: M2Gpu, per Main's decode-gap directive (Linux 72.6 vs macOS 179.0 tok/s
decode = 0.41×; M1 Max shows the same ~2.5× class gap). Split agreed via hub:
the fusion lane — norm/swiglu fusion (dispatch-count reduction); the submission/flush lane —
submission/flush batching; M2Gpu — GEMV/occupancy + M2 measurement device.
Install bar: a decode win with digest identical to `dbf70497…`.

## 1. Batchbudget candidate (the submission/flush lane's lever): NO WIN — NOT INSTALLED

Candidate = qualified base `aae4dfc9` + cherry-picks `8fed014e6` (batch node
budget 256→4096), `c23198997` (BATCH_TRACE instrumentation, default-inert),
`fbe4fc0ae` (allocator total_memory = largest HOST_VISIBLE heap; the UMA fix
the submission/flush lane marks mandatory-with-budget). Built as
`mlx_omarchy-0.32.3.dev202609232014+cb10253e2` in the dg-alarm-py314:sep23
chroot on the build host (sha256 `552cb44a…`), installed into a CLONE venv
(`/var/tmp/m2gpu-stage/venv-cand`, mlx-lm patches untouched: raw route count 2).

Gate results (system driver, normal environment):

| gate | candidate | accepted baseline | verdict |
| --- | --- | --- | --- |
| logits vs T6001 ref | 320 steps, 0 flips, max\|d_top1\|=0.0 | same | bit-exact ✓ |
| records digest | `dbf70497…` | `dbf70497…` | identical ✓ |
| decode median | 72.57 tok/s (σ 0.14) | 72.58 [72.55, 72.62] | **no win (−0.01)** |
| ttft median | 85.69 | 85.59 | flat |
| pure prefill-512 | 947.52 | 906.84 | within session variance (sysinstall 1-pass measured 948.04) |
| peak RSS | 587,024 KB | 553,488 KB | +6% (larger retained graph) |

Submit-count proof the lever changed nothing observable: `[rtmod] SUBMIT`
count in the 10-pass contract log is **10501 in BOTH** baseline and candidate
(COMMITs 3434 both). Root cause of the non-engagement: the M2 reports a single
**unified 47.12 GiB DEVICE_LOCAL+HOST_VISIBLE heap** — (a) the fbe4fc0ae UMA
fix is a no-op here (the T8103 ~16 MB device-local defect does not exist on
T6021), and (b) the decode graph's 3-way submit split on T6021 is therefore
not node-budget- nor byte-budget-driven — a different partitioning mechanism
than T6001's, owned by the submission/flush lane's lane to identify (BATCH_TRACE does not
fire in release wheels; a diag build of cb10253e2 would be needed for the
flush-reason trace).

Per the install bar (win + identical digests): the qualified venv is
UNTOUCHED; the candidate lives only in `venv-cand`.

## 2. GEMV/occupancy lever (M2Gpu): blocked on driver surface + bench drift

- The shipped decode GEMV at aae4dfc9 is the xpack kernel
  (QmmVecQ4MultiSubgroupBF16 = 23.8% + WordSubgroup 8.5% of T6021 decode
  time). The T6001 occupancy lane already measured this family AT its
  dispatch-geometry ceiling (160 GB/s in-model vs 310.6 GB/s pattern roof;
  wide-load/quad4/unroll/wg128/split-K all bit-worse or slower) and concluded
  the remaining lever is a honeykrisp occupancy/L2-policy driver feature.
- M2 re-measurement deferred with cause: `tools/q4-bw-bench`'s base shader
  predates the shipped xpack shader — the provenance drift gate fails at
  `aae4dfc9` (base `qmm_vec_base.comp` ≠ production `qmm_vec.comp`), so the
  bench cannot certify shipped-kernel numbers until the tools lane refreshes
  the base copy. Running it anyway would produce an uncertified number.
- Request to the tools/mesa owners: refresh the bench base at the production
  shader rev, then the T6021 ceiling measurement is a 10-minute follow-up.

## 3. Parakeet macOS gate (Main's item 1) — see receipts/2026-09-23-m2-macos-denominator

M1 macOS and M1 Max macOS both PASS bit-identically to golden
(db501a8c, 104 tokens); T6021 macOS FAILS with +3 trailing decoder-junk
tokens ("ЮНЕН" vs "Юн Ю"), encoder core proven bit-exact on pinned features.
Full evidence chain in that receipt; no criterion invented.

## 4. Fusion lever (the fusion lane's scaled-only route): candidate built, gate armed

- Candidate wheel built off-device from `agent/gdn-fuse-m1host` @ `4fd2130ed`
  ("gdn-fuse: unroute rms_norm_gated pending exp tie-rounding root cause"):
  `mlx_omarchy-0.32.3.dev202609232032+4fd2130ed-cp314-cp314-linux_aarch64.whl`
  (sha256 `174c17c2…`, 416 MB — the sha-verified whole-encoder parakeet bundle
  is baked in at this rev because the build had `MLX_OMARCHY_WHOLE_BUNDLE_DIR`
  set; harmless for the qwen gates).
- Route patch verified to be the CURRENT scaled-only variant: the gated
  rms_norm site stays UNROUTED (1-ULP exp-codegen deviation documented by the
  fusion lane); q/k norms route to `rms_norm_scaled` gated to bf16 rows
  ≤ 32768. Note: an older size-gate variant that ROUTES the gated kernel is
  what circulates on some host staging dirs — the git extraction at
  4fd2130ed is authoritative and is what is staged.
- Gate sequence armed to run automatically when the M2 returns from the ANE
  reservation boot (results to be appended): `qual_sweep_s.py` bit-exact
  sweep → logits gate vs T6001 reference → 10-pass contract (digest must
  equal `dbf70497…`, decode vs 72.58 CI). Install bar unchanged: win +
  identical digests.
- Dependency discovered: the qualified wheel `aae4dfc9` ships NO
  `rms_norm_scaled`/`rms_norm_gated` primitives — the fusion lever requires
  this newer wheel, i.e. its candidate changes the base, not just the venv.

## 5. Fusion lever gate result: REJECT — not installed

Gate run on the M2 (fresh venv, fusion wheel
`0.32.3.dev202609232032+4fd2130ed` sha `174c17c2…`, scaled-only route patch):

- `qual_sweep_s.py`: PASSED (tensor-level bit-exact on decode shapes).
- Logits gate vs T6001 reference: **FAILED — 23 flips / 320 steps,
  max |Δtop1| = 8.75** (prompts 2, 4, 7), against 0 flips / 0.0 for the
  qualified stack and 0 flips on the fusion lane's m1-host validation.
- Contract: not completable as a candidate — the fusion wheel's decode is
  dramatically slower on T6021 (pass 2/10 after ~10 min vs ~70 s for all ten
  baseline passes); digest necessarily divergent given the logit flips.
- Verdict: the `57c3963ad`-lineage wheel base plus the scaled route is NOT
  numerically clean on T6021 — a cross-silicon divergence beyond the m1-host
  1-ULP class. Qualified stack unchanged (`aae4dfc9`, digest `dbf70497…`).
  Candidate artifacts: M2 `/var/tmp/m2gpu-run/fuse/` and `venv-fuse`.

Raw: raw/fuse/ (logits-verdict-fuse.txt, qual-sweep.txt, contract-fuse.log).

## 6. Reclassification (fusion lane concurrence)

The fusion lane confirmed the REJECT and reclassified the failure: 23 flips +
max |Δtop1| 8.75 + a ~10× slower contract is NOT the m1-host 1-ULP tie class —
the fused scaled kernel lands on a driver fallback/emulated path on T6021
(structurally wrong math AND slow). The sweep passing while end-to-end
explodes fits: fresh contiguous tensors exercise the healthy path; the
in-model path feeds strided views that trip the bad one.

Actions: (1) the fusion lane fixed the stale staged patch copy (it was the
old gated-routing variant); (2) recommendation adopted — the scaled route
stays UNROUTED on T6021 until the misbehavior is reproduced in isolation
(minimal rms_norm_scaled-vs-composed sweep with in-model-like strided inputs,
queued behind device availability); (3) the fusion lane will add a
capability-gated dispatch (refuse the fused kernel outside the proven
silicon set) — to be verified on the M2 when it lands.

## 7. Occupancy lever (mesa-1): CLOSED — kernels already at maximum occupancy

Shaderdb capture of the shipped model path on T6021 (qualified stack, system
fork driver, AGX_MESA_DEBUG=shaderdb,internal + cache disabled; raw/shaderdb.log):
24 CS kernel variants compiled. Every decode-path kernel — including the
QmmVecQ4 xpack GEMV family — lands in the TOP occupancy bucket (1024
threads/core); the only sub-maximum kernel is the known GDN prefill kernel
(531 instrs / 255 gprs / 384 threads / 95:106 spills — receipted separately
on T6001, prefill-side, not decode).

The compiler occupancy table (agx_performance.c) maps register demand to
threads/core and regalloc rounds demand UP within the highest achievable
bucket (agx_register_allocate.c: "round up demand to the maximum number of
registers without affecting occupancy"). With the GEMV already at 1024
threads/core, the compiler occupancy lever is CLOSED: the pattern ceiling is
hardware-latency-bound (dependent-load ~430 ns on T6001; T6021 curve pending
via the refreshed --occ instrument), not resource-limited.

Remaining driver-side items are outside this lane's implementable surface:
L2/SLC policy (no reverse-engineered surface in the driver), barrier bit
selection + dispatch fixed cost (the submission/flush lane, landing), and
MLX-level dispatch-count reduction (fusion lane; scaled route REJECTED on
T6021, gated variant accepted upstream).

## 8. Correction + decode-set identification (supersedes §7's kernel census)

§7 miscounted: 21 of 24 kernels run at 1024 threads; THREE are sub-maximum
(1041 instrs / 143 gprs / 704 threads; 531 / 255 gprs / 384 threads = the
known GDN prefill; 1068 / 147 gprs / 640 threads). Decode-set identification
(two-run shaderdb diff — prefill-only vs prefill+decode, raw/ holds both
captures): the four decode-only kernels ALL run at 1024 threads — including
the 1216-instr / 39 gprs GDN decode kernel and the decode GEMV family.
The three sub-maximum kernels are PREFILL-side.

Corrected conclusion, now on the right evidence: the decode path is at
maximum compiler occupancy; the occupancy lever for the decode gap is CLOSED.
The prefill-side sub-maximum kernels (704/640 threads) are a potential
prefill-side compiler lever (143 gprs is 1 register from the 768-thread
bucket) — prefill is already at 907–948 tok/s Linux vs 1110 macOS, so the
upside there is bounded; noted for a future lane, not this one.

## 9. Occupancy-priority A/B (driver compiler): bit-exact, small positive, INDICATIVE — not installed yet

Driver built in the shared persistent container (dg-maxdispatch recipe,
meson release, asahi vulkan only) from honeykrisp-omarchy tip 7faf04c065c +
`AGX_OCC_REGALLOC_PRIORITY` (env-gated regalloc cap trading registers for
occupancy buckets; bit-exact by construction). Deployed as
`/var/tmp/mesa-occ-m2` (sha `b51efd72…`) via VK_DRIVER_FILES.

Back-to-back arms (1 pass × 10 prompts each, same session):

| arm | records digest | decode tok/s | prefill-512 tok/s |
| --- | --- | ---: | ---: |
| ctl (priority unset) | `486872c4…` | 63.36 | 675.1 |
| priority=1 | `486872c4…` | 63.71 | 697.06 |
| priority=2 | `486872c4…` | 64.67 | 682.83 |

- **Bit-exact: all three arms produce identical output_ids** (digest
  `486872c4…`, the 10-record-set digest; the logits gate under priority=1 vs
  the T6001 reference: 0 flips, max |Δtop1| = 0.0). The cap does not change
  arithmetic, as designed.
- Direction positive but small: prefill +3.3% (p1), decode +2.1% (p2) —
  within/near session noise at 1 pass per arm.
- **Absolute numbers are depressed vs the production-built system driver**
  (decode 63-65 vs 72.5, prefill 675-697 vs 907-948): my chroot build's
  config differs from the production .so build (the system driver predates
  and was built by another lane's flow). Fair installation comparison
  requires reproducing the production build config, plus multi-pass CIs and
  an idle box (MaxDispatch's M2 A/B may have been concurrent here).
- **Robustness finding**: shaderdb run under priority=1 SEGFAULTED
  (core dumped) — the RA spill path under a tightened cap hits a crash the
  default path does not; needs root-cause before any install consideration
  (core + log on the M2 at /var/tmp/m2gpu-occ/, /var/tmp/m2gpu-run/occ/).

## 10. Fixed-build full A/B (10-pass arms): prefill +3.6% at priority=1, bit-exact

With the spill-path fix (cap applied before spill planning), the full contract
ran per arm on the M2 before the ANE marker-boot reassignment cut the p2 arm:

| arm | n | records digest | decode tok/s | prefill-512 tok/s |
| --- | --- | --- | ---: | ---: |
| ctl (priority unset) | 100 | `dbf70497…` ✓ | 72.6 | 713.18 |
| priority=1 | 100 | `dbf70497…` ✓ **bit-identical** | 72.69 | **738.57** |
| priority=2 | 10 (cut by boot) | `486872c4…` (stale 1-pass file) | 64.67 | 682.83 |

- The ctl arm on my freshly-built driver reproduces the accepted cell exactly
  (dbf70497 at 72.6 decode) — the regalloc commit introduces no regression.
- priority=1 is bit-identical with prefill +3.6% (738.57 vs 713.18) and decode
  flat (+0.12%) — consistent with the lever's mechanism (only prefill-side
  kernels are sub-maximum occupancy). Single 10-pass sample: the +3.6% sits at
  the edge of session prefill variance (~4.5% across today's sessions) and
  needs the confirm pass (t6001-host through MaxDispatch's windows, and/or an M2
  repeat) before an install call.
- priority=2's file is stale 1-pass data (the ANE marker-boot reassignment cut
  the arm); rerun queued on the next M2 gap.
- Install decision for the combined qualified driver (barrier fix + occupancy
  commit) belongs to MaxDispatch per Main's reassignment — their receipt
  addendum §8 records the handoff and the decision rule.

## 11. Full three-arm completion (corrects §10's p2 row)

All three arms completed 10-pass contracts; every arm bit-exact
(`dbf70497…`):

| arm | decode tok/s | prefill-512 tok/s |
| --- | ---: | ---: |
| ctl (priority unset) | 72.6 | 713.18 |
| priority=1 | 72.69 | **738.57** (+3.6%) |
| priority=2 | 72.77 | 731.14 (+2.5%) |

Shaderdb under priority=1 confirms the mechanism — the spiller adapted the
two big qmm prefill kernels to better buckets: the 1041-instr kernel now
compiles at **768 threads** (135 gprs, 3:3 spills; was 704) and the
1068-instr kernel at **704 threads** (143 gprs, 8:4 spills; was 640).
The 531-instr GDN prefill did not move (its raw demand sits at the {256,384}
bucket edge; follow-up item if its prefill share justifies it).

Decode flat (+0.1-0.2%, expected: decode kernels untouched by the cap).
The prefill gain (+2.5-3.6%) is at the edge of session variance — the
confirm pass runs on t6001-host through MaxDispatch's windows, and the combined
qualified driver (barrier fix + this commit) carries the install decision.
