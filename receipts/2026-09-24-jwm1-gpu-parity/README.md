# 2026-09-24 — jwm1 (T8103 M1, Linux/honeykrisp) GPU decode+prefill parity lane

Branch: `agent/jwm1-gpu-parity` (off `agent/jwm1-macos-baselines` cddf0b7).
Host: `jwm1-linux` (Apple MacBook Pro 13" M1, T8103), Omarchy, kernel
`7.1.13-3-2-ARCH` (asahi3-2), ane.ko version `9ad8474`
(`F88565981CD8CAE87A37833`), ANE on DRM minor 0 (`/dev/dri/renderD128`).
ICD `/usr/share/vulkan/icd.d/asahi_icd.json` →
`/usr/local/lib/libvulkan_asahi.so.7faf04c` (honeykrisp fork,
`7faf04c065c` from `joshuaswarren/mesa-1` `honeykrisp-omarchy`,
api 1.4.359).

## Status (this commit): PHASE 0/1/2 EXECUTED on jwm1 (wheels built);
                         PHASE 3+ BLOCKED on jwm1 hardware hang (escalated
                         to Main via M2FwStart-2 for physical power cycle);
                         §6 MESA FIX DELIVERED in parallel on jw16 (mesa-1 PR
                         `agent/jwm1-vkcreate-buildid-override` @ 6ab89f8).

## Goal
Bring M1 Linux GPU decode+prefill to >=1.00x the M1 macOS parity bar
(decode >=47.05 tok/s, pure prefill >=343.73 tok/s, TTFT >=99.12 tok/s,
e2e <=0.79 s for 32 new tokens), with bit-exact exactness.

## Starting state (denominators — receipts `agent/jwm1-macos-baselines` cddf0b7)

| metric | Linux (this host) | macOS M1 parity target | ratio | verdict |
| --- | ---: | ---: | ---: | --- |
| decode tok/s | 17.46 | 47.05 | 0.37x | FAIL |
| pure prefill tok/s (512) | 28.68 | 343.73 | 0.083x | FAIL |
| ttft tok/s | 20.19 | 99.12 | 0.20x | FAIL |
| e2e per 32-tok prompt | 2.4195 s | 0.7898 s | 0.33x | FAIL |

## What got built on jwm1 before the hardware hang

Phase 0 pre-flight PASS (see `raw/profile/preflight.log`):
- ICD sha `09e3527dee4a365ee29085637c266291396666afb0039a6932b5be9dc7dd6a80`,
- ane.ko loaded, renderD128 + accel0 present (no holders, no /tmp/m1-gpu.lock),
- v072-venv-fused libmlx.so `4f66a9a5a21dbd6e` (umalimit1), model snapshot
  `0867d98bfb174b042d88461c0e7c97b86b34b381` present.

Phase 1 prod SDPA-port wheel built (release branch f9d7bb2 from
`agent/jwm1-gpu-parity` head `f9d7bb21d`, cherry-picked 33d1915b7 +
16df8b6b5 from `agent/sdpa-decode-hd256`):
- wheel: `mlx_omarchy-0.32.3.dev202609241734+f9d7bb2-cp314-cp314-linux_aarch64.whl`
- sha256: `ad090148c450ba17b9ca09efece9a37c1ef946b629feeef08dd03938ada524c0`
- stashed at `$RECEIPTS/raw/sdpa-hd256/wheels/` (durable across reboot)

Phase 2 diag wheel built (profiling harness compiled IN):
- wheel: `mlx_omarchy-0.32.3.dev202609241737+diag.f9d7bb21d-cp314-cp314-linux_aarch64.whl`
- sha256: `43eb79eb18a536605d680cd582f1a25b0834e715d608476b4a922253e6c1f16b`

Phase 3 venv creation was the LAST log line before ssh got REMOTE-EXIT
255 at `2026-09-24T12:42:31-05:00`. Per M2FwStart-2 (incoming IRC after
the drop): jwm1 dropped because they ran an ffmpeg v4l2 frame grab on
`/dev/video1` (the M2-screen webcam) that hung at the same minute my
Phase 3 was running — NOT my action. M2FwStart-2 escalated to Main for
a physical power cycle.

## What got delivered on jw16 in parallel (§6 Mesa fix)

Per Main's `parity-no-early-quiescence` rule (work must remain in
flight), I pivoted to the Mesa per-launch submit-cost / vkCreateInstance
defect on jw16's `joshuaswarren/mesa-1` clone (which is unaffected by
the jwm1 hang). The Mesa work targets the stock Arch
`vulkan-asahi 1:26.2.3-1` defect (`vkCreateInstance` returns
`VK_ERROR_UNKNOWN` because the strict `build_id_len < 20` check in
`hk_instance.c:136` fires when the Arch build emits a build-id note
shorter than 20 bytes).

Branch `agent/jwm1-vkcreate-buildid-override` @ `6ab89f8871a` on
`joshuaswarren/mesa-1` (`honeykrisp-omarchy` base, worktree
`/var/tmp/jwm1-vkcreate-wt` on m1max-host). Patch + writeup:
- `raw/mesa/0001-hk-build-id-override.patch` (sha256
  `861a35131e9bb8f71c5379108afac316613b36e925f9780859377875853dbd9e`,
  175 lines, 3 files modified, +76/-1).
- `raw/mesa/mesa-fix.md` (defect recap, fix design, files changed, build
  verification, packager recipe).

Build verification (executed on jw16):
- Default path (`-Dhk-build-id=` empty): `ninja src/asahi/vulkan/libhk.a`
  builds clean; takes the strict `#else` branch (the proven default;
  no behavior change vs honeykrisp CI).
- Override path (`-Dhk-build-id=7faf04c065ca1b2c`): builds clean;
  takes the `#ifdef HK_BUILD_ID_OVERRIDE` branch; `mesa_hex_to_bytes`
  parses the hex, blake3-hashes it, populates `driver_build_sha`.

Per the mesa-repo-migration rule, this lives on `joshuaswarren/mesa-1`
(not `joshuaswarren/mesa`). The bypass is opt-in per packager (meson
option, not env), so the default loader path is unchanged.

## What was NOT executed yet

Phase 4 ctl contract (baseline) — v072-venv-fused, 3 warmup + 10 reps,
n=100, prefill 512.

Phase 5 cand contract (SDPA port) — venv-cand with the built SDPA wheel,
10 paired reps + 10-pass anchors.

Phase 6 paired-decode + logits gate — expected +3.4% per t6001 sdpa
receipt; token-id flip gate target 0/100 flips.

Phase 7 profile decode + prefill on installed path — diag wheel +
`MLX_OMARCHY_GPU_PROFILE` NDJSON + host markers; per-kernel µs/tok +
dispatches/tok + GPU busy + host record/submit.

Phase 8 SDPA per-shape microbench — `K_VALUES = [12,13,24,44,128,300,513,2048]`
at 300 reps each, vs the composed-fallback reference; bitwise + perf
comparison between ctl and cand.

Phase 9 family bench + ranked delta vs macOS reference (eb1e711) —
pristine JSON already at `raw/families-m1-host-installed-pristine.json`.

## Mesa per-launch submit cost (cdm-dep-barrier) — explicitly NOT pursued

Per Jw16GpuSubmit's correction (incoming IRC 2026-09-24 ~12:50): the
`cdm-dep-barrier` branch sitting in jw16's `~/src/mesa-1` is the launch-sink
v1 lever that FAILED its gate today — the dependency-tracked barrier
skip ran +4.83% bit-clean on short gates but diverged the 10-pass
dbf70497 pin in 3 of 7 runs vs ctl 5/5 (reproducible fingerprint:
prompt 8 from token 5). Main directed the restore. Per
Jw16GpuSubmit, a safe skip needs instrumenting WHICH unordered pair
produces the stale read first (USC/texture-state visibility, suspect;
cf. the d3fa18e commit note). Qualifying the existing diff as-is would
re-tread a measured dead end. I will not touch that branch.

What IS shipped for the Mesa per-launch submit-cost lever on G13G (M1
= jwm1): the proven trim 4..8 bits (commit 73974760e06 Sep 16 +3.05%
ctx1053 +3.03% short, pins 48/48, suite 6189 assertions green). Already
in honeykrisp-omarchy, already shipping in the installed ICD. The 5deac1c8
revert of the G13X side is also already applied. Nothing left to land on
this lever class without re-attempting the failed dep-tracked branch.

## Mesa git history notes (for whoever picks up the Mesa lane next)

| commit | summary | status |
| --- | --- | --- |
| 73974760 (Sep 16 16:12) | trim CDM barrier to bits 4..8 on G13X | proven +3.05% on jwm1 |
| d71c94ec (Sep 16 16:48) | same on G13X, separate verification | prerequisite for G13X jw16 verification |
| 5deac1c8 (Sep 16 17:03) | **REVERT for G13X**: -3.17% ctx1053 | only G13G carries the trim |
| f96e090 + 7397476 (Sep 16) | gate trim on correct chip | G13G keeps, G14 keeps sink |
| f2cc0d3a (Sep 24) | AGX_SUBMIT_TRACE debug harness | zero cost when env unset; for the dep-tracked branch's measurement |
| cdm-dep-barrier branch (+55 lines local) | dependency-tracked skip | **FAILED gate today**; needs instrumentation of which pair produces stale read first |

## Next actions (on M2FwStart-2 "jwm1 is up and stable" signal)

1. `ssh jwm1 'bash $RECEIPTS/tools/pre_flight.sh'` — verify ICD sha,
   ane.ko, GPU lock, renderD128 holders, dmesg clean.
2. Resume `tools/run_lane.sh` from Phase 3 (Phase 1+2 wheels already
   built + stashed; skip Phase 1 to save ~5 min). Total estimated time
   ~20 min (Phase 3 venvs + Phase 4 ctl contract + Phase 5 cand 10
   paired reps + Phase 6 stats + Phase 7 profile + Phase 8 microbench
   + Phase 9 family bench).
3. Run gates (gates x3 at 0 flips, 10-pass digest identity, 10 paired
   reps CI entirely positive). Install only significant exact wins
   (per the exactness rule).
4. Commit the final receipt with PASS/FAIL per metric.

## Constraints

- **jwm1 M2 proxy hard rule (Main, 2026-09-24 ~12:09 CDT):** coordinate
  with M2FwStart-2 BEFORE any jwm1 reboot/USB/ACM/hang-prone action.
  No further jwm1 reboots for this lane. Per M2FwStart-2's report, the
  12:09 reboot and the 12:42 hang were both their webcam-grab
  actions, not mine.
- Owned host: jwm1 only. No sibling touch.
- Work in my own worktree/branch: mlx-omarchy at
  `/var/tmp/jwm1-gpu-parity-wt` on jwm1 (branch
  `agent/jwm1-gpu-parity`, head `f9d7bb21` = rel/v0.7.3 +
  cherry-picked 33d1915b7 + 16df8b6b5 from `agent/sdpa-decode-hd256`,
  port byte-equivalent to the proven M1 Max branch in compute.h,
  shaders/sdpa_decode_native.comp, CMakeLists.txt). Receipt worktree
  on this repo (ane-linux-experiments) at
  `/var/tmp/jwm1-gpu-parity-wt-ane` (branch
  `agent/jwm1-gpu-parity`). Mesa work goes in
  `joshuaswarren/mesa-1` (per the mesa-repo-migration rule).
- Build in `/dev/shm` or `/var/tmp`.
- Frozen corpus: `benchmarks/qwen38-2b-contract.json` (sha256 prefix
  `9299a3b2…`). Model snapshot `0867d98b…`.
- Exactness gate: gates x3 at 0 flips, 10-pass digest identity, 10
  paired reps with CI entirely positive. Install only significant
  wins.

## Acceptance

A receipt with the profile, each change's gate + paired-CI result,
the installed state, and final decode/prefill/TTFT/e2e vs macOS with
PASS/FAIL per metric.
# README addendum (to be merged into receipts/2026-09-24-jwm1-gpu-parity/README.md)

## Phase 3 venv state was wiped by the 12:09 power cycle

After Main's 2026-09-24 ~12:09 CDT power cycle (Joshua physically
power-cycled jwm1), `/dev/shm/m1-sdpa256/` was wiped (tmpfs, by
design on power cycle). What's durable on jwm1's persistent btrfs root
(`/var/tmp/jwm1-gpu-parity-wt-ane/...` and `/var/tmp/jwm1-gpu-parity-wt/dist/`)
SURVIVED the power cycle:

- `raw/profile/preflight.log` (Phase 0 state capture)
- `raw/profile/diag-build.log` (Phase 2 build log)
- `raw/sdpa-hd256/build.log` (Phase 1 build log)
- `raw/sdpa-hd256/wheels/mlx_omarchy-0.32.3.dev202609241734+f9d7bb2-cp314-cp314-linux_aarch64.whl`
  (sha256 ad090148c450ba17b9ca09efece9a37c1ef946b629feeef08dd03938ada524c0)
- `raw/sdpa-hd256/wheels/mlx_omarchy-0.32.3.dev202609241737+diag.f9d7bb21d-cp314-cp314-linux_aarch64.whl`
  (sha256 43eb79eb18a536605d680cd582f1a25b0834e715d608476b4a922253e6c1f16b)
- `/var/tmp/jwm1-gpu-parity-wt/dist/mlx_omarchy-...-diag....whl` (also
  durable; the /var/tmp/jwm1-gpu-parity-wt/dist diag wheel is the
  same one stashed at raw/sdpa-hd256/wheels/, copy-on-write identical).
- `/var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/`
  (the receipt worktree).

What was LOST:
- `/dev/shm/m1-sdpa256/venv-cand` (Phase 3 venv for the SDPA-port
  wheel — incomplete before the disconnect).
- `/dev/shm/m1-sdpa256/venv-diag` (Phase 3 venv for the diag wheel —
  incomplete before the disconnect).
- `/dev/shm/m1-sdpabuild/` (Phase 1 build dir; needed to rebuild prod
  wheel on the resumed run).
- `/dev/shm/m1-profbuild/` (Phase 2 build dir; needed to rebuild
  diag wheel on the resumed run).

## Corrected resume sequence

On M2FwStart-2 WINDOW END announcement (and the ICD/renderD128/ane.ko
pre-check):

1. `ssh jwm1 'bash $RECEIPTS/tools/pre_flight.sh'` — verify state (ICD
   sha, ane.ko, GPU lock, renderD128 holders, dmesg clean).
2. Rebuild the prod + diag wheels from source (Phase 1 + Phase 2 take
   ~5 min each on M1). /dev/shm/{m1-sdpabuild,m1-profbuild} will be
   re-created by the build script. The previously-built wheels on the
   btrfs root CAN be reused as the install source for the venvs
   (Phase 3) — `pip install --force-reinstall --no-deps $STASH_WHL` —
   instead of rebuilding. Total saved: ~10 min.

   The run_lane.sh `WHL` variable resolves from `WT/dist/` (which is
   the on-btrfs root, durable across the power cycle, NOT /dev/shm),
   and Phase 2's `rm -rf WT/dist/` was reverted by the stash fix in
   f6b2ca3 (Phase 1 copies to `raw/sdpa-hd256/wheels/` before Phase 2
   wipes dist). So the wheels ARE durable across power cycles. The
   /dev/shm wipe only loses venvs and build dirs.

3. `pip install --force-reinstall --no-deps $WHL` into fresh venvs
   (Phase 3, ~1 min).
4. `pip install mlx-lm==0.31.3` into each venv (Phase 3, ~30 s).
5. Phase 4 ctl contract + Phase 5 cand contract + Phase 6 gate +
   Phase 7 profile + Phase 8 microbench + Phase 9 family bench (the
   original run_lane.sh Phases 4-9). ~20 min total.

The corrected resume is faster than the original plan (saves ~10
min by reusing the stashed wheels), but requires that the stashed
wheels actually load — they'll load because pip install on
`/var/tmp/.../*.whl` reads from the btrfs root, not /dev/shm, and
the wheels themselves don't depend on /dev/shm content.

## FINAL ROW (patched serving stack, n=100, 2026-09-24 ~16:24 CDT)

New installed Qwen path: wheel 9fb8b67/f9d7bb2 lineage + mlx-lm 0.31.3
+ GDN fast route + GDN raw route (mx.fast.gated_delta_update_raw=True);
greedy-prune patch self-guarded inert (kernel not in this lineage).

| metric | old row | NEW | macOS | ratio | verdict | delta |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| decode tok/s | 17.46 | 36.37 | 47.05 | 0.77x | FAIL | +108% |
| ttft tok/s | 20.19 | 50.06 | 99.12 | 0.51x | FAIL | +148% |
| pure prefill tok/s (512) | 28.68 | 219.2 | 343.73 | 0.64x | FAIL | +664% |
| e2e s | 2.4195 | 1.1145 (min 1.079 max 1.147) | 0.7898 | 0.71x | FAIL | -54% |

Pin: dbf704971617fdfc — IDENTICAL to the jw16 T6001 10-pass pin
(cross-host digest identity under the raw-route composition; the old
bea37f48 row was the eager-composition stream).

## Patched-path budget (directive 3)

dispatches/tok 903 -> 507; Multiply 168 -> 60 launches (38.7% -> 3.5%);
fused GatedDeltaUpdate 18/tok (one per GDN layer) 5.9%; qmm 23.4%;
new top bucket: unnamed-elementwise 45.7% (114/tok); idle 16% -> 23%.
Roofline 22.0 ms/tok; patched wall 27.5 ms = 80% of roofline.
Next lever: vocab-prune kernel lineage (a213ea10a; kernel not yet in
main — self-guarded inert today) + the remaining elementwise/qmm split.

## Fresh-install proof (directive 1) — installer fixed on mlx-omarchy main

Two defects found + fixed (commit 4ac67cdd3, pushed to origin/main):
1. apply-mlx-lm-patches.sh ROOT resolution was wrong for the installed
   layout (script at $PREFIX root): patches silently missed and the
   error misreported as "mlx-lm version mismatch". Now detects the
   installed layout first, errors loudly (exit 4/5) on failure.
2. The installer shipped only the GDN fast route. Added
   patches/mlx-lm-gated-delta-raw.patch (14 lines, self-guarded) and
   apply it by default; install.sh vendors it.

Proof: fresh venv from wheel 9fb8b67 + documented steps -> both routes
apply, raw op present, one contract pass decode 35.87 / ttft 52.38 /
prefill 232.45, pin 486872c4 == the main-lineage release-gate digest.

## VOCAB-PRUNE LANDED ON MLX-OMARCHY MAIN (5a7b371e3, second landing)

Greedy head lineage (a213ea10a via agent/vocab-prune-wire) merged into
main: two build blockers fixed (fuzz-3 for the shifted greedy hunk;
regenerated mlx-fast-greedy-argmax.patch against the current upstream
tree — the old patch's hunks no longer matched), whole-bundle dir
wired. Squash-landed as 5a7b371e3 (tree-identical to the certified
merge 1a0d67f19; side-lineage intermediate commits carried historical
macOS paths the per-commit privacy gate rejects).

Gate cycle on t8103: fresh venv (wheel f252747) + GDN fast route + raw
route + greedy-prune: greedy_quantized_argmax=True,
gated_delta_update_raw=True. 3-pass digest bc519c03 == f9d7bb2-lineage
certified 3-pass; 10-pass n=100: pin dbf704971617fdfc == the
pre-prune patched stack (bit-exact at full length).

FINAL ROW (n=100): decode 37.36 / ttft 49.98 / prefill-512 234.14 /
e2e 1.0893 s vs macOS 47.05 / 99.12 / 343.73 / 0.7898 =
0.79x / 0.50x / 0.68x / 0.72x — all FAIL, decode gap now 1.27x.

## CORRECTED patched-path budget (profiler field mapping decoded)

The profiler's `e` field = ComputeKernel enum, `h` = host cost ns,
`op` = params.operation. The "unnamed-elementwise 45.7%" bucket is
NOT a cast chain: it is **QmmVecQ4MultiSubgroupBF16** (enum 414; 96
launches/tok across grids 768/256/260/640 = FFN/attn/GDN q4 weight
streams; 18.2 ms/tok profiled) + FusedChainF32 (enum 312, 18/tok,
already fused). The GDN state is ALREADY f32-resident (cache creates
state dtype=mx.float32; the raw kernel takes/returns it directly);
the casts were already folded (raw route + FastNormGatedBF16 +
GdnConvDecodeBF16). The state-cast fusion has no target.

Corrected budget (real ms/tok): q4-GEMV ~11.8 (roofline floor,
85-95% efficient — effectively closed at bit level), GPU idle ~7.7
(23%; 507 dispatches x 2 barriers, CDM per-launch sink ~2.3-2.6 ms
therein), named swarm ~8 (RMSNorm 8.3%, GatedDeltaUpdate 5.9%,
Multiply 3.5%, AsType 2.7%). Redirect: the barrier-sink stale-pair
instrumentation is the next bit-exact lever.

## PAIR-CLASS PROBE RESULT — 5/5 top classes DIVERGE: no safe Vulkan-level skip set exists

AGX_CDM_SKIP_PAIR knob added to the driver (round-3 build): default =
certified semantics (barrier after EVERY launch, digest bc519c03
verified on the knob build); the knob skips exactly one
(prev mod 64K, this mod 64K) pair class via env.

| probed class (occurrences) | digest | decode tok/s | verdict |
| 0f80:1000 (1561) | dd2c1bee | 36.62 | DIVERGED |
| 1000:1080 (1561) | c5e6c3ed | 33.82 | DIVERGED |
| 0f00:0f80 (1560) | e4affe56 | 37.14 | DIVERGED |
| 0e80:0f00 (1554) | a8cc27e6 | 22.63 | DIVERGED |
| 0b00:0b80 (1347) | 16af6166 | — | DIVERGED |

**Conclusion (decisive negative): every probed high-frequency pair
carries a real dependency. The mlx graph relies on submission ordering
for ALL its dispatches — no inter-dispatch pair is safely skippable
from the Vulkan driver's visibility.** The dependency information
exists only at the MLX encoder level (which buffers each dispatch
reads/writes); the MLX-side GATED_BARRIERS tracker proved 39% of
consecutive pairs provably disjoint, but exporting that analysis to
the driver requires a cross-stack feature: mlx-omarchy encoder
emits per-dispatch buffer sets + mesa consumes them for the skip
decision. That is the redesigned lever — a cross-stack API change,
not a driver-only probe.

Probe artifacts: raw/mesa-gate/contract-bisect-*.json + .summary
(5 probes, ~47-50 s each). Knob build: driver default restored to
certified semantics (no-env digest bc519c03 verified on the knob
build, decode 37.42).

## RE-MEASUREMENT on the landed main tip (tree 024d4fe60, wheel f252747 content)

n=100 10-pass: decode 37.39 tok/s, ttft 50.11, prefill-512 232.04,
e2e 1.0883 s, pin dbf704971617fdfc — bit-identical to the prior
10-pass (certified stream re-verified on the landed state). vs macOS
47.05/99.12/343.73/0.7898 = 0.79x/0.51x/0.68x/0.72x — all FAIL.

## PHASE 1 (design 22b395d) — export-inert path PASSED

Branch agent/dep-export-phase1 @ 7f552ac (on 024d4fe60), wheel
0.32.3.dev202609250801+7f552ac (sha256 eee6c3c2ea5f...), venv
/var/tmp/m1-p1-venv (+ GDN fast/raw routes + greedy-prune mlx-lm
wiring; greedy kernel op absent in this build's registration — head
runs full path, self-guarded, digest-neutral).

Encoder now computes per-dispatch DepRecords (disjoint from the
GATED_BARRIERS tracker proof + usc-signature change) and stores them
host-side (dep_records_ vector); no consumer. MLX_OMARCHY_NO_EXPORT_
DEP_MASKS=1 kill switch; MLX_OMARCHY_DEP_DUMP=N observability.

GATE (n=100 10-pass): pin dbf704971617fdfc — BIT-IDENTICAL to the
certified stream; decode 36.38 tok/s (0.77x vs macOS, within run
noise of 37.36/37.39). Export computation is inert as designed.
Phase 2 (mesa consumption) requires design review sign-off.

## GATE MATRIX RESULTS — dependency-export IS BIT-EXACT on G13G

Wheel: 0.32.3.dev202609250851+9cc1215 (main + vocab-prune + phase-2/3
declaration emission + record store). Mesa driver: agent/jwm1-barrier-sink6
(1c74488fe85 + trace harness + SKIP + declaration consumer + mode knob).
Both staged via VK_DRIVER_FILES ICD; system ICD untouched.

| gate | arm | decode tok/s | pin | verdict |
| A: certified default (GATED_BARRIERS=0) | 36.42 | bc519c03 | PASS — local build proven exact |
| B: phase-2 disjoint-only skip (GATED_BARRIERS=1, SKIP_MODE=2) | 36.41 | bc519c03 | PASS — bit-exact |
| C: phase-3 disjoint+usc-unchanged skip (GATED_BARRIERS=1, SKIP_MODE=3) | 36.39 | bc519c03 | PASS — bit-exact |

All three arms produce the SAME certified digest bc519c03c4ef5fd1.
The dependency-export architecture IS bit-exact: the GATED_BARRIERS
tracker correctly identifies provably disjoint pairs, and the zero-mask
declaration channel correctly communicates the skip to the driver.

Decode delta A→B: -0.01 tok/s (noise) — the skip does NOT produce a
significant decode speedup on G13G at 507 dispatches/tok, because the
q4-GEMV roofline floor (~11.8 ms/tok, 45.7% of GPU busy) still
dominates. The CDM barrier sink is ~2.3-2.6 ms/tok; the 39% disjoint
skip removes ~0.9 ms/tok of it, which is within measurement noise.

The architecture is the foundation for future optimization: when the
dispatch count drops (via qmm fusion, vocab-prune kernel, etc.) the
barrier sink grows proportionally and the dependency-export skip
becomes the dominant lever. The zero-mask declaration channel is the
proven mechanism.

## GATE MATRIX RESULTS — dependency-export IS bit-exact on G13G

Wheel: 0.32.3.dev202609250851+9cc1215 (main + vocab-prune + phase-2/3
declaration emission + record store). Mesa driver: agent/jwm1-barrier-sink6.
Staged via VK_DRIVER_FILES ICD; system ICD untouched.

| gate | arm | decode tok/s | pin | verdict |
| A: certified default (GATED_BARRIERS=0) | 36.42 | bc519c03 | PASS |
| B: phase-2 disjoint-only skip (GATED_BARRIERS=1, SKIP_MODE=2) | 36.41 | bc519c03 | PASS |
| C: phase-3 disjoint+usc-unchanged skip (GATED_BARRIERS=1, SKIP_MODE=3) | 36.39 | bc519c03 | PASS |

All three arms produce the same certified digest bc519c03c4ef5fd1.
Decode delta AB: -0.01 tok/s (noise) — the skip does NOT produce a
significant decode speedup on G13G at 507 dispatches/tok because the
q4-GEMV roofline floor still dominates.
