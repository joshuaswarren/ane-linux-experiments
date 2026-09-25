# 2026-09-23 — MaxDispatch: per-launch CDM barrier trim (designedusc) — T6001 WIN, INSTALLED

Lane: MaxDispatch. Host: t6001-host (t6001-host, M1 Max, G13C/G13X, t6001-host). Companion leg on
m2-host (T6021) runs in parallel; T8103 arm delegated to M1Decode.

## 1. Attribution (what actually costs)

The per-dispatch fixed cost on the decode gap hosts is NOT Vulkan barriers and NOT MLX
dispatch setup. It is Honeykrisp's per-launch kitchen-sink `CDM_BARRIER`
(`hk_cdm_cache_flush` after every CDM launch, `hk_cmd_dispatch.c`).

Dispatch-floor microbench (`mlx-omarchy/tools/dispatch-floor-bench`, cases
`mlxpair_trivial_1wg` + `barrierfull_trivial_1wg` added on branch
`maxdispatch/floor-bench` commit `4a521535b`, base aae4dfc9), 512-dispatch chains,
5 reps, 2 legs, on t6001-host:

| case (us/dispatch) | sys | wt | nocdm | usc | dusc |
|---|---:|---:|---:|---:|---:|
| trivial_1wg | 5.66 | 5.94 | 0.50 | 1.25 | 4.64 |
| nop_1wg | 5.04 | 4.39 | 0.45 | 1.20 | 4.79 |
| barrier_trivial_1wg (Vulkan c2c) | 4.80 | 4.74 | 0.48 | 1.23 | 4.63 |
| barrierfull (ALL_COMMANDS) | 5.50 | 4.50 | 1.53 | 1.48 | 5.29 |
| mlxpair (exact MLX production pair) | 5.55 | 4.49 | 1.54 | 1.49 | 5.09 |
| empty (no memory write) | 0.74 | 0.70 | 0.55 | 0.64 | 0.61 |

Conclusions:
- wt ~ sys: built baseline reproduces the installed driver (provenance sanity).
- Hard launch floor 0.5 us/dispatch; the kitchen-sink adds ~5 us on trivial
  memory-writing chains (nothing on no-write kernels).
- Vulkan-level barrier SHAPES are indistinguishable — MLX-side barrier gating
  (MLX_OMARCHY_GATED_BARRIERS) cannot pay here; the driver-side per-launch sink is the coin.
- Real dependent chains amplify the sink (prior attribution ccad76a6160: full 25.11 us vs
  none 4.72 vs usc-only 9.34 on mx.add chains, G13X).

## 2. Candidate

`designedusccdmbarrier`: CDM_BARRIER with bits {unk_4, unk_5, unk_6, unk_8} +
`usc_cache_inval` — byte-identical to `HK_PERFTEST=designedusccdmbarrier`
(commit ccad76a6160 on hk/dispatch-attrib). The prior bare-trim regression
(ctx1053 -3.17%, d71c94ec4ec/5deac1c8068) is resolved by the USC invalidate:
this arm WINS the ctx leg (below).

## 3. Paired A/B — t6001-host, one window (log window-20260923T211257Z)

ctl = installed system driver (5deac1c806, sha b1ad6306, kitchen sink).
dusc = same venv/wheel, `VK_DRIVER_FILES=/var/tmp/maxdispatch/t6001/maxdispatch-icd.json`
+ `HK_PERFTEST=designedusccdmbarrier` on the built baseline
(`hk/maxdispatch-t6001` = 5deac1c8068 + arms bf7da2b2ded/feae0d8ee8c, release build,
sha e3f57ba111074b33). Wheel aae4dfc9, patched GDN raw route, venv v072-venv-fused,
Qwen3.8-2B-mlx-4Bit, contract: 10 prompts, 3 warmups, 3 passes, greedy, prefill 512,
32 new tokens; 10 interleaved reps per arm.

| metric | ctl | dusc |
|---|---:|---:|
| decode reps (tok/s) | 63.43 63.64 63.38 63.53 63.65 63.46 63.57 63.43 63.59 63.41 | 68.19 68.30 68.69 68.50 68.37 68.50 68.28 68.28 68.50 68.24 |
| decode median | 63.50 | 68.34 |
| paired delta | — | **+4.876 ± 0.139 (95% CI, n=10) = +7.68%** |
| 3-pass digests | bc519c03 (all 10) | bc519c03 (all 10) |
| 10-pass digest | **dbf70497** (63.35) | **dbf70497** (68.32) |
| logits vs T6001 ref d8f96153 | 0 flips, max|d| 0.0000 | 0 flips, max|d| 0.0000 |

## 4. ctx1024 KV-stream guard leg (the old regression leg)

5 interleaved pairs, 1024-token context, decode 32 (`/var/tmp/maxdispatch/ctx/`):

ctl: 56.79 56.89 56.82 56.71 (median 56.79) — dusc: 60.80 60.75 60.52 60.67 60.70
(median 60.70). **Paired delta +3.92 ± 0.03 (n=5) = +6.90%**, digest `ee718419`
identical in all 10 runs. The bare-trim KV regression does NOT appear with the
usc_inval included.

## 5. Install (win)

Fix build = `hk/maxdispatch-t6001` tip d3fa18e8dd0 (G13X default emission =
designedusc; full sink retained on G13G/G14G/G14X), release, sha
`1e912d3e03d11e559189cbe2aa5551aa0aebd51ba6064d8a1d2c4feed98f0784`,
staged `/var/tmp/maxdispatch/fix/t6001/libvulkan_asahi.so`.

- ICD swap: `/usr/share/vulkan/icd.d/asahi_icd.aarch64.json` →
  `library_path: /usr/local/lib/libvulkan_asahi.so.d3fa18e`
  (binary installed at `/usr/local/lib/libvulkan_asahi.so.d3fa18e`, sha
  `1e912d3e03d11e55`; backup: `/var/tmp/maxdispatch/install/asahi_icd.aarch64.json.pre-maxdispatch.bak`;
  former system .so `git-5deac1c806` sha b1ad6306 remains at `/usr/lib/libvulkan_asahi.so`).
  First swap pointed at `/var/tmp/maxdispatch/...`; relocated to `/usr/local/lib` and
  re-verified: relocate rep 68.45 (bc519c03), live llm-inference completion answered
  through the new path (HTTP 200 chat.completion), service active.
- Post-install system default (no env): 68.52 / 68.26 / 68.31 tok/s (bc519c03),
  10-pass **68.43 dbf70497** — installed default = the winning arm, digest pin held.
- Logits spot under installed default: 0 flips / max|d| 0.0000.
- llm-inference.service restarted, health ok, real completion probe answered.

## 6. Notes / caveats

- First build attempt used debugoptimized: agx_compile.c:3507 self-disassembly assert
  ("Disassembly error hit") on MLX decode shaders — measurement builds must be release.
- M2 floor arms nocdm/usccdmbarrier fail in the bench's GetQueryPoolResults path on
  G14C (timestamp-query coherency depends on the flush) — instrumentation limitation,
  fork-vs-dusc comparison unaffected.
- Profiled decode streams (diag wheel, both arms, 5240 dispatch records each) at
  `/var/tmp/maxdispatch/prof/`; on the diag wheel the stream is host-bound, so the
  +7.7% release-wheel win is read from the paired A/B, not the profile walls.
- Scripts: `ane-linux-experiments/.local/maxdispatch/` (floor matrices, window,
  ctx leg, install, analyzers). Raw artifacts on-host under `/var/tmp/maxdispatch/`.

## 7. Status

- t6001-host: INSTALLED (win), service verified.
- m2-host (T6021/G14X): fix commit 156b408aa81 on `hk/maxdispatch-m2` (base
  7faf04c065 = the installed fork lineage); A/B window rerunning after two
  reboot interruptions (early data: dusc ~77.3-77.4 vs ctl ~72.6 = +6.5%,
  digests identical); install pending its clean window + ctx leg.
- m1-host (T8103/G13G): delegated to M1Decode (installed default already
  carries the G13G trim {4,5,6,7,8} decision-grade PASS; their A/B tests
  designedusc vs that).

## 8. Addendum — T6021 combined handoff (M2Gpu occupancy + barrier trim)

M2Gpu's occupancy feature for the combined T6021 driver: mesa-1 tip 7faf04c065c +
one commit (AGX_OCC_REGALLOC_PRIORITY env in agx_register_allocate.c /
agx_performance.c; bit-exact by construction, digests + 0 flips/0.0 confirmed).
Use build sha 61fb9fe9 (release) — the first build b51efd72 has a spill-path
segfault (cap applied after spill planning; assert agx_register_allocate.c:418)
fixed in 61fb9fe9 via pre-spill capping. Sources/tarball:
m2gpu-mesa1-wt on build-host (m2gpu-occ.tgz, mesa-occ-build.sh,
mesa-rebuild-clean.sh); raw A/B + shaderdb + gdb bt in
receipts/2026-09-23-m2-gpu-decode-levers/raw/. Their first contended A/B:
ctl 63.36 -> p2 64.67 decode (small positive, CIs pending a clean-gap rerun).
Suggested combined T6021 arm for the gap install: designedusc default
(156b408aa81) + AGX_OCC_REGALLOC_PRIORITY=2, or rebuild the tree with both
commits before the install; either way the standing gates apply (dbf70497,
0 flips, paired CIs) plus a spill-path sanity case under high-pressure
compiles before serving traffic.

## 9. Addendum 2 — M2Gpu full three-arm occupancy A/B (bit-exact)

All arms dbf70497 10-pass, bit-exact: ctl 72.6 decode / 713.18 prefill ->
priority=1 72.69 / 738.57 -> priority=2 72.77 / 731.14. Shaderdb under p1:
both big qmm prefill kernels adapted buckets (704->768 threads @135 gprs
3:3 spills; 640->704 @143 gprs 8:4 spills); GDN prefill unchanged (raw
demand at the 256 bucket edge — priority_cap near-noop there). Session
prefill variance ~4.5%; single 10-pass samples, variance question open
until a t6001-host confirm pass runs through this lane's windows.
Receipt b653d3f. Combined-T6021 decision deferred to the gap install:
either barrier-fix alone (staged .so 94203781191dd660) with the occupancy
arm layered as env on M2Gpu's build, or a rebuild folding
AGX_OCC_REGALLOC_PRIORITY into hk/maxdispatch-m2 — both run the standing
gates plus a spill-path sanity case.

## 10. Addendum 3 — combined-install plan (agreed with M2Gpu)

Short gap: barrier-fix alone first (proven +6-7% decode). Long gap: fold
AGX_OCC_REGALLOC_PRIORITY into hk/maxdispatch-m2 and qualify the combined
driver with priority=1 as the install DEFAULT (prefill-conservative:
738.57, 3:3 spills) and priority=2 as the CI-comparison arm. The
t6001-host confirm pass runs priority=1 (settle the +3.6% prefill
variance). Build safety: the spill-path fix (pre-spill capping,
61fb9fe9 or later) must be present — b51efd72 segfaults under
high-pressure compiles.
