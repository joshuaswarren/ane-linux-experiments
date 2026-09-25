# 2026-09-25 — t6001-host (M1 Max) GPU decode levers: two-row Q4 GEMV (LANDED, INSTALLED) + compute-batch no-split barrier (+5%, but 2 single-record digest flips: REVERTED, needs the rare-race battery); barrier-bit and split costs measured; parity NOT reached

Lane: Jw16GpuLevers. Host: t6001-host (M1 Max T6001/G13C, Omarchy Linux
7.1.6-1-1-ARCH), single GPU owner for the lane; every GPU leg under
`/tmp/m1-gpu.lock` with `llm-inference.service` stopped and restored with a
real completion (`artifacts/w*/completion-*.json`). Denominator: macOS same
laptop (fd8d878 row): decode 180.38 tok/s, prefill 1326.05, TTFT 359.98
(4.91x), e2e 0.2081 s. Starting Linux row: decode 76.45, prefill 734.45,
TTFT 73.26, e2e 0.5864 (digest `bc519c03`).

**Verdict. The GEMV lever is landed on mlx-omarchy main and installed
(bit-exact: 3-pass `bc519c03` x3 in two venvs, 10-pass `dbf70497`, standing
omarchy battery 27 suites + 5 capability-sim profiles, 0 failures). The
no-split driver won +5% on every arm and held its own 10-pass pin, but two
of its nine 3-pass runs flipped one record each (§2.4) while the installed
driver flipped none in 390 records today; per the bit-exact bar the ICD is
back on d3fa18e and the driver is a candidate for the 10x10-pass
interleaved rare-race battery, not an install.**

| arm (wheel x driver) | decode tok/s (3 reps, median) | prefill-512 | TTFT rate | e2e s (median, n=30) | digests |
|---|---:|---:|---:|---:|---|
| base 83eb57a x installed d3fa18e | 69.66 (69.56 / 69.66 / 70.19) | 725.9 | 72.69 | 0.6218 | bc519c03 x3, 10-pass dbf70497 |
| base x nosplit 41ccf96 | 73.19 (+5.1%) | 736.1 | 72.00 | 0.6105 | bc519c03 x2, r3 `a483d947` (see §2.4) |
| cand 3232b1f x installed | 71.34 (+2.4%) | 731.3 | 71.06 | 0.6171 | bc519c03 x3, 10-pass dbf70497 |
| cand x nosplit | 75.13 (+7.9%) (75.05 / 75.13 / 75.16) | 734.7 | 72.72 | 0.5971 | bc519c03 x3, 10-pass dbf70497 |
| **serving venv, cand wheel x installed d3fa18e (FINAL installed state)** | **77.85** (77.48 / 77.85 / 78.00) | 731.7 | 76.29 | **0.5681** | **bc519c03 x3** |
| serving venv, cand wheel x nosplit (window 5, reverted) | 81.25 (81.00 / 81.25 / 81.25) | 727.0 | 74.98 | 0.5604 | r1 `c12461f2`, r2-r3 bc519c03 |

Final installed row (serving venv, 3232b1f wheel, d3fa18e driver): decode
77.85 tok/s (12.85 ms/token; macOS 5.54), prefill 731.7, TTFT rate 76.29,
e2e 0.5681 s. Pass rule (>= 1.00x macOS): decode 0.43x FAIL, prefill 0.55x
FAIL, TTFT 0.21x FAIL, e2e 2.73x FAIL. The serving venv runs ~9% faster
than the fresh venvs on the same wheel and driver (81.25 vs 75.13 with
nosplit, 77.85 vs 71.34 on d3fa18e); its dependency set differs and was
not diffed (budget), so cross-venv rows are not compared with each other. The two levers are real and held the digests;
they are not parity, and the measurements below say where the rest is.

The base wheel here (origin/main 83eb57a, fresh venv: wheel + mlx_lm 0.31.3 +
fast-route + raw patches, the serving venv's patch set) measures 69.66, not
the 76.45 of the fd8d878 row; that row's venv state is not reproducible from
its receipt (the serving venv on arrival held a diag wheel and four stacked
dist-infos, §5). Both arms of every comparison here share one venv recipe.

## 1. Driver actually loaded (assignment item 1)

- ICD json on arrival: `/usr/local/lib/libvulkan_asahi.so.d3fa18e` (sha
  `1e912d3e…`), mesa-1 `d3fa18e8dd0` (G13X per-launch CDM_BARRIER =
  {4,5,6,8}+usc_cache_inval). `libvulkan_asahi.so.b5cd7dbc` (Mesa
  26.3.0-devel git-25bbe37098 = the `cdm-dep-barrier` branch build that
  FAILED the rare-race gate on 09-24) sits beside it, inert, not referenced.
- `d3fa18e8dd0` is on origin as the tip-minus-one of
  `mesa-1 jw16/usc-barrier-study` (549ddbb8a7d = the same mask knob I
  re-derived, §2.2). The shared checkout `~/src/mesa-1` on the device is on
  `cdm-dep-barrier` with uncommitted edits (not mine, untouched).

## 2. Barrier lever (assignment item 2)

### 2.1 Microbench: per-launch cost by CDM_BARRIER flag word and by split

Instrument: `mlx-omarchy/tools/dispatch-floor-bench` (512-dispatch chains,
5 reps, wall per dispatch) on a release build of d3fa18e8dd0 + a perftest
knob emitting an exact flag word (`HK_CDM_BARRIER_MASK=<hex>`, same thing as
549ddbb8a7d's `HK_PERFTEST=maskcdmbarrier`). us/dispatch
(`artifacts/w1/floor/`):

| arm | trivial (no app barrier) | barrier (COMPUTE->COMPUTE) | barrierfull (ALL_COMMANDS) | mlxpair (MLX's pre+post pair) | nop_4096wg |
|---|---:|---:|---:|---:|---:|
| installed d3fa18e (0x178) | 4.62 | 4.61 | 5.00 | 5.04 | 13.89 |
| nosplit build (same packet) | 4.62 | 4.60 | **4.58** | **4.60** | 14.11 |
| no packet (nocdmbarrier) | 0.61 | 0.59 | 1.50 | 1.46 | 10.78 |
| nosplit + no packet | 0.51 | 0.50 | 0.49 | 0.49 | 11.66 |
| 0x008 usc only | 1.19 | 1.21 | 1.51 | 1.58 | 11.77 |
| 0x010 / 0x020 / 0x040 (bits 4/5/6 alone) | 1.31 / 1.24 / 1.21 | 1.28 / 1.25 / 1.22 | ~1.5 | ~1.5 | 11.2-11.8 |
| 0x078 {4,5,6}+usc | 1.33 | 1.37 | 1.54 | 1.54 | 11.79 |
| **0x100 bit 8 alone** | **3.62** | **3.64** | 2.82 | 2.89 | 11.64 |
| 0x108 {8}+usc | 3.90 | 3.92 | 3.10 | 3.15 | 12.05 |
| 0x170 {4,5,6,8} bare | 4.64 | 4.62 | 3.53 | 3.57 | 12.45 |
| 0xfffff kitchen sink | 6.04 | 4.75 | 4.54 | 4.57 | 12.88 |

- The app-level barrier shape does not matter (trivial == barrier), as the
  09-19 receipt found. The **split** (ending the CDM stream per
  vkCmdPipelineBarrier2, a stream link + fresh 64 KiB chunk) costs
  **0.4 us per app barrier** (5.00 -> 4.58, 5.04 -> 4.60), not 9.5 us.
- **unk_8 is the cost**: 3.1 us of the 4.1 us packet cost on trivial chains;
  bits 4/5/6 and the USC invalidate are ~0.7 us together.
- Real GEMV chain (q4-bw-bench `--gap --2b`, 4 RAW-chained GEMVs x 24 weight
  sets, wall): installed 198.7 us/layer; 0x170 198.6; 0x108 200.2; nosplit
  199.0; usc-only 159.8; no packet 158.3. On real kernels the cost is the
  serialization the barrier enforces (~10 us per launch = the lost overlap
  of one kernel's tail with the next one's ramp), not the packet bits.
- Which bits are required is already answered by receipt 93bb431
  (2026-09-23 uscstudy): every one of {4,5,6,8} is individually
  load-bearing (single-bit removal = hundreds of logit flips), and bit 8 is
  both the cost and the protection. My floor matrix agrees on the cost side;
  I did not repeat the corruption battery.

### 2.2 The change: keep the compute batch open across compute->compute barriers

mesa-1 `jw16/usc-barrier-study` @ **41ccf96cc59** (fast-forward of the
existing study branch: the fleet privacy hook scans full history for any
NEW ref and trips on upstream mesa blobs, so no new branch name is pushable
from this lineage; the branch is d3fa18e8dd0 + 549ddbb8a7d mask knob +
this commit). `hk_CmdPipelineBarrier2` returns early when no graphics batch
(`current_cs.gfx`/`pre_gfx`/`post_gfx`) is open; otherwise the old big
hammer. Why it is safe: outside a render pass only a CDM stream can be
open; every launch in it is already followed by `hk_cdm_cache_flush`
(the {4,5,6,8}+usc packet) and `merge_control_streams` re-joined the split
streams at `hk_EndCommandBuffer` anyway — the submitted stream is byte-for-
byte what the merge produced minus the stream link. Graphics->compute and
compute->graphics are ordered by `hk_CmdBeginRendering` ending the compute
batch and by the kernel-side barriers between VDM/CDM commands, both
unchanged. Timestamp splits (`hk_query_pool.c`) and events are unchanged.
State-based, so it covers any stage mask MLX emits.

Build: release, `29a7addc28b40c8c…`, staged at
`/usr/local/lib/libvulkan_asahi.so.41ccf96` (inert: the ICD json is back on
d3fa18e after window 6, §2.4; backup `/var/tmp/levers/asahi_icd.aarch64.json.pre-levers.bak`).

### 2.3 Decode result

Driver alone (base wheel): 69.66 -> 73.19 tok/s (+5.1%); with the GEMV
change 71.34 -> 75.13 (+5.3%). Larger than the 0.4 us x ~400 app barriers
per token (~0.16 ms = 1.1%) the floor bench predicts: the split also cost a
64 KiB pool chunk per barrier (~25 MiB of control-stream pool per token)
and its allocation/bind churn on the host — the host-side cost the
launch-sink2 perf profile attributed to allocation.

### 2.4 Two single-record digest flips on nosplit arms -> driver REVERTED

- base wheel x nosplit r3: `a483d947` — 1 record of 30 (pass 0, prompt 7)
  diverges at token 19 and cascades; 29/30 identical.
- serving venv, cand wheel x nosplit, installed-r1 (window 5): `c12461f2`
  — 1 record of 30 (pass 0, prompt 7) diverges at token 15; 29/30 identical.
- Every other nosplit run pinned: cand x nosplit 3/3 `bc519c03` and the
  10-pass `dbf70497` (100 records); nosplit total 2 flipped records / 290.
  Installed-driver arms today: 0 flipped / 390 records (base-sys x3, cand-sys
  x3, two 10-passes, installed-sys x3).

Shape-wise these are the single-point cascade class that receipt 93bb431
saw once on the installed control (sys-r3 `08e8a69a`, prompt 1 token 20,
1/12), not the 09-24 dep-skip class (reproducible prompt 8 token 5, 21
positions) nor the corruption class (hundreds of flips). But both landed on
the same prompt on the same arm class while the control stayed clean, and
the bit-exact bar has no margin: the ICD was restored to d3fa18e in window
6 (`artifacts/w6/`, service restarted so llama-server reloaded it, health
ok, real completion). The no-split driver goes to Jwm1Parity6 / a
successor as a candidate for the 10x10-pass interleaved battery Main set on
09-24; it is not installed anywhere.

## 3. GEMV lever (assignment item 3)

### 3.1 Candidates, standalone harness, bit compare

`mlx-omarchy/tools/q4-bw-bench` gained `--cand <shader>[:columns]`,
`--cand-def`, `--grid-cap`; base resynced to production. All candidates are
compiled from the production source with two defines; every candidate was
bit-compared against base on all four 2B shapes (7 weight/output pairs,
random x/weights/scales/biases): **0 mismatches** for every arm below.
RAW-chained 2B decode layer, wall, 24 sets (`artifacts/w1`, `w2`):

| arm | rows/slot x slots | us/layer | GB/s | note |
|---|---|---:|---:|---|
| production (1 row per 32-lane slot, 8 slots) | 1x8 | 198.9 | 172.4 | control; cand r1s8 = 198.9 |
| **r2s4** | **2x4 (8 cols/wg, host contract unchanged)** | **186.2** | **184.1** | LANDED |
| r2s8 / r2s16 | 2x8 / 2x16 | 185.3 / 183.1 | 185 / 187 | same within noise, needs host grid change |
| r3s4 / r3s8 | 3x4 / 3x8 | 200.7 / 198.7 | — | no gain |
| r4s2 / r4s4 / r4s8 | 4x… | 228 / 215 / 216 | — | loses (register pressure) |
| unroll-2 prefetch (both blocks' loads first) r2 | 2x4 / 2x8 | 216 / 214 | — | loses |
| grid-stride persistent workgroups r2s8, cap 32..256 | — | 234-355 | — | loses at every cap |
| kernel-only ceiling (no CDM packet, timing only) r1 / r2s4 / r2s8 | | 158.3 / 136.4 / 135.1 | 216 / 251 / 254 | r2 sits above the 241 GB/s read roof of 46346bb |

What the winner does: each slot owns two consecutive rows; the x quads and
`input_sum` load once per block and feed both rows; each row's dot runs the
single-row fma chain in the same order into its own `precise` accumulator
and gets its own `subgroupAdd`, so the arithmetic is identical per row
(the bit compare and the digests confirm). The issue stream was 32 B of x
per 8 B of weights per lane per block; now 32 B per 16 B, with the two row
loads independent in flight. Four rows lose; unroll-2 loses; persistent
grids lose — on this compiler/GPU the sweet spot is two rows.

### 3.2 Landed

mlx-omarchy **main @ 3232b1f5e** (pushed; `ROWS_PER_SLOT=2 SLOTS_PER_GROUP=4`
for the packed-x subgroup word and multi kernels: f16/bf16; f32 and the
tree-reduction builds keep one row). Wheel
`mlx_omarchy-0.32.3.dev202609251914+3232b1f-cp314-cp314-linux_aarch64.whl`
(libmlx `b1e91ebbce892f3e…`). Standing omarchy battery on the device under
the nosplit driver (tests-ON build of the same tree): runtime, primitive,
matmul_family (82,940,463 assertions), fast_ops (1,104,350), fused_chain
(346,272), kv_ops, indexing, reduce, shape, linalg, copy_offset,
distributed, compiled_tape, fft_ops, fft_general, eig, take_fill, conv,
complex, select_layout, fast_regression, scatter_determinism, eq_math,
error_contract, ane_bundle, sdpa_decode_fused, sdpa_causal_ragged — all
PASS, 0 failed (`artifacts/w3/battery-nosplit-*.log`); capability_sim
profiles m1-honeykrisp-fork, m1-stock-no-coopmat, subgroup-size-64,
small-shared-memory, no-cooperative-matrix — all PASS (`artifacts/w4/`).

Decode: cand-sys vs base-sys +2.4% (69.66 -> 71.34); the GEMV family is
~65% of GPU time in the profile but its layer chain moved 6.4%, and the
chain's remaining cost is the per-launch serialization (§2.1), not the
kernel.

## 4. Installed state (assignment item 4)

- ICD: `/usr/share/vulkan/icd.d/asahi_icd.aarch64.json` ->
  `/usr/local/lib/libvulkan_asahi.so.d3fa18e` (unchanged from arrival after
  the window-6 revert; the nosplit .so `libvulkan_asahi.so.41ccf96` stays in
  /usr/local/lib inert, like b5cd7dbc).
- Serving venv `/var/tmp/v072-venv-fused`: on arrival it held the
  **diag** wheel `+diag.af73787` with four stacked dist-infos (pip could
  not reinstall over them, "Version: None"); the stale `mlx/` and
  dist-infos were moved to `/var/tmp/levers/venv-fused-pre-levers/` and the
  3232b1f release wheel installed cleanly (window 5). mlx_lm 0.31.3 with the
  fast-route + raw patches (2 `gated_delta_update_raw` refs) unchanged.
- Installed default (no env), 3-pass contract x3 — see §4.1.
- `llm-inference.service` active after every window, `/health` ok, real
  completion (`chatcmpl-…`, 8 completion tokens) after each
  (`artifacts/w*/completion-*.json`).

### 4.1 Installed-default contract (window 6, no env)

| rep | decode tok/s | prefill-512 | TTFT rate | e2e s median | digest |
|---|---:|---:|---:|---:|---|
| installed-sys-r1 | 77.48 | 731.7 | 76.29 | 0.5681 | bc519c03 |
| installed-sys-r2 | 77.85 | 735.2 | 76.61 | 0.5709 | bc519c03 |
| installed-sys-r3 | 78.00 | 723.3 | 75.60 | 0.5673 | bc519c03 |

Window 5 (same venv + wheel, nosplit driver, before the revert):
81.00 (`c12461f2`, §2.4) / 81.25 / 81.25 (`bc519c03`), e2e 0.557-0.561.

## 5. Not done / handed back

- **Parity is not reached** (0.42x decode). The measured structure of the
  remaining 13.3 ms token: GEMV kernels are now at/above the streaming
  roof (§3.1); ~513 launches x ~10 us of per-launch serialization (§2.1) is
  the largest item and is exactly the dependency-tracked skip that failed
  the rare-race gate on 09-24; the bit trim is closed (93bb431). The next
  lever with headroom is launch count (fusion of the norm/cast/copy swarm,
  ~350 launches/token), not the barrier packet and not the GEMV kernel.
- **Main's queued jw16 macOS window** (Parakeet e2e on the jwm1 harness +
  CoreML ANE encoder re-capture with the corrected computeUnits harness):
  NOT executed — request budget. Runbook is in place: reboot gate is
  already PASS for this box (boot files off-btrfs, receipt
  2026-09-22-m1max-gpu-levers §3), switch = `asahi-bless -n -y --set-boot 1`
  (next boot only, Omarchy stays default), mac side `t6001-host-macos`,
  bundle `mac-reference-bundle-full.tar.gz` sha `82c1a70198fd…` with
  `run-core.sh` (encoder_bench post-2bc9112: computeUnits passed into
  MLModel.load + MLComputePlan placement) and `run-parakeet.sh` (4 CU arms,
  cold + warm1 + rep1 + rep10, the jwm1 271 ms figure = rep10 inference,
  ane arm); deviations to expect are listed in
  receipts/2026-09-23-m1-mac-denominator/harness-notes.md. Stop
  llm-inference before the reboot; on return: health poll + real completion.
- Jwm1Parity6 (T8103): both changes are SoC-agnostic — mlx-omarchy
  3232b1f5e (shader defines only) for the T8103 A/B, and mesa-1 41ccf96cc59
  as a rare-race-battery candidate only (acknowledged by Jwm1Parity6: it
  will not run it against a golden without that battery).

## Artifacts

- `artifacts/w1/floor/*.ndjson` floor matrix (all arms); `artifacts/w1/q4-*.ndjson`
  first candidate screen (bit compare + gap); `artifacts/w1/q4gap-*.ndjson`
  gap chain under barrier masks; `artifacts/w2/` extended screen (unroll,
  rows 3, grid-stride caps, no-packet ceilings); `artifacts/w3/contract-*.json`
  every contract (15) + `battery-nosplit-*.log`; `artifacts/w4/` capability
  sim + first install pass (its "installed-r*" rows ran the stale diag wheel:
  the pip install had silently failed, superseded by w5); `artifacts/w5/`
  the clean wheel install + nosplit installed contracts (incl. the r1 flip);
  `artifacts/w6/` the driver revert + final installed-default contracts; `window-*.log` per window
  with service restore and completion probes.
- Device: `/var/tmp/levers/` (worktrees `mlx` @ 3232b1f5e, `mlx-base` @
  83eb57a99, `mesa-nosplit` @ 41ccf96cc59, `barrier-bench-wt` = d3fa18e +
  mask knob + nosplit on branch agent/jw16-gpu-levers, local only; venvs
  `venv-base`, `venv-cand`; ICD manifests under `icd/`).
