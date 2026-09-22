# m1-host encoder levers: attribution correction, T8103 readback re-land, GPU-drain profile, bdscale A->B state (2026-09-22)

Branches: `agent/ane-inprocess-submit` (mlx-omarchy worktree
`ANE-REPO-WORKTREE/.local/ane-v064-wt`, commits this receipt) +
rebind fix `289a763` (ane-linux-experiments-parakeet-perf). m1-host = T8103.

## 1. Attribution correction: there are NO unplaced GPU feeder matmuls

The wall-decomposition receipt's "47 attention-scores-family matmuls
NOT covered by the placed islands (2373-2979 ms)" is an instrumentation
artifact. MLX_OMARCHY_STMT_TRACE pass (trace-20260922T063136, m1-host, all
gold bit-exact) shows every matmul statement executes inside
`_run_island_a`/`_run_island_c`: `execute()`'s finally-block attributes
each island's marshal+submit wall to the matmul statement (e.g. stmt 204
= attention_scores_1, 139.9 ms wall = island A submit wall). All 72
encoder matmuls (24 rel-pos + 24 content + 24 PV) are island-placed.
The batched-matvec placement lever is a no-op.

The real j1 stack per layer pair: island-A marshal ~85 ms (GPU drain of
conv/proj/FFN feeder work) + one-time const init (~351 ms per process;
`const_values` caches, so a persistent runner pays it once) + submit
device phases.

## 2. GPU-drain profile (Main item 3): what the GPU does between islands

One fused_e2e pass under the profiler build
(/var/tmp/wheelx libmlx, MLX_OMARCHY_GPU_PROFILE; run prof-20260922T065819,
enc_ane 5368 ms - profiler build is slower; shares still indicative).
Encoder window (first 0.45 s and last 1.0 s excluded), kernel identity =
`e` enum index against commit 1b72eb4d3 compute.h:

| kernel | n | total | share |
| --- | ---: | ---: | ---: |
| Custom (custom MLX kernels incl. the coopmat/batched-matvec family) | 1068 | 1655.4 ms | 62.3% |
| MatmulF32 | 50 | 347.7 ms | 13.1% |
| CopyGeneralF16/F32 | 1147 | 285.1 ms | 10.7% |
| ElementwiseF32 + ReduceF32 + casts | ~1200 | ~280 ms | 10.5% |

GPU busy is only 2658 ms of a 5136 ms window (52%): the pass is half GPU
idle, half CPU-issue/ANE-wait. The feeder's GPU time is dominated by the
custom kernels the coopmat linear path already dispatches (the runner's
`_linear_f16_coopmat_kernel` is the default linear path). MatmulF32
(50 dispatches, ~7 ms each) is the next candidate for coopmat conversion.

## 3. T8103 cached-BO readback: silently lost after reboot, re-landed and made boot-persistent

m1-host rebooted ~21:26 Sep 21; the stock writecombine ane.ko came back
(no parameters dir, attn readback 4.4 ms median vs 0.67 cached).
Second occurrence of this regression class. Fixed for good:

- m1-host and m1max-host: cached-BO build installed at
  `/lib/modules/$(uname -r)/updates/ane.ko` + `depmod -a`;
  `modprobe -n -v` resolves it (m1-host 7.1.13-3-2-ARCH sha of source tree
  ane_drv a2265b0b; m1max-host 7.1.6-1-1-ARCH, source ~/src/omarchy-ane
  agent/ane-cached-bo-mapping afb23dd).
- rebind_and_verify.sh (commit 289a763) now gates on writecombine=N and
  keeps insmod only as fallback.

Interleaved module A/B on m1-host (kab-20260922T065043, 1 warm + 3 meas per
arm, same runner/shim/source, module swapped between arms, both arms ALL
GREEN: status match, 104/104 prefix, mel 5b54f4a9 / hidden 38c73261 /
transcript db501a8c bit-exact every run):

| arm | encoder_ane median | device exec median |
| --- | ---: | ---: |
| B cached (writecombine=N) | **3485.3 ms** | 257.5 ms |
| A stock writecombine | 3627.2 ms | 408.2 ms |

Cached is -141.8 ms encoder_ane (-3.9%), exec -150.7 ms; consistent with
yesterday's 3468-3476 cached windows. Operational hazard found while
running this: `/tmp/m1-gpu.lock` gets deleted+recreated while held, so
`flock -n` loops acquire the "lock" repeatedly (14 duplicate script
instances raced before I killed them; one cached-vs-stock comparison ran
with modules swapped mid-run and produced a bogus 5134 ms outlier - that
number is void). Windows should flock one persistent inode.

## 4. bdscale fused A->B (Main item 2): runner support landed; capture-free on-device package blocked by manifest dialect

Facts established:

- Both hosts' staged sources (m1-host /var/tmp/IslandsExec-m1-host, m1max-host
  /var/tmp/EncoderParityAne) have `matrix_bd_5 = mul(matrix_bd_3, 1/16)`
  - the select's b producer is a MUL on both, never an add. The strict
  `add` validation means FUSED_AB=1 can NEVER init against these sources.
- **The m1max-host "fused -107 ms / -78 ms" results are VOID.** In the last
  night's fused battery (fused-20260921T213736), NEITHER arm shows an
  out_ab submit in its island log and neither arm crashed at init - the
  FUSED_AB=1 arm ran unfused; the measured delta is arm-ordering noise,
  not the fusion. The fused A->B package has never actually executed in
  any recorded run.
- Fill constant: var_8_to_fp16 = fp16 0xBEEF = -1.7334 (FINITE, not
  -inf). The fused select substitutes masked = fill for masked = s1+fill;
  identity therefore holds only where the fill lane is inert for the
  fixture (believed true; unverified directly).

Landed (commit on agent/ane-inprocess-submit):

- `vulkan_encoder.py`: fused_ab accepts a mul-produced b ("bdscale
  lineage"): per layer it finds the unique consumer add of the select
  output (validated at init), feeds s1 = the scores matmul value,
  s2 = the scaled relpos crop, and the out_ab z replaces the consumer
  add's output while the select and add are skipped. Also fixes
  fused_ab_adds set/dict type bug.
- `manifest.cpp`: root manifest accepts `artifactFormat` (must be
  "anec"); rebuilt shim on m1-host (libane_inproc_v2.so,
  a9f3f153d4e43c55a7cfba90d90948067e607585b947ad07c9911c17149338ef).

Remaining blocker, precisely: the staged out_ab package is the RAW h13
export dialect (root keys artifactFormat/dispatchPlan/logicalResults/
physicalOutputs/programs/schema/target/tensors; schema
mil-hwxc.h13-anec-package.v2), while the shim/worker bundle parser
(bundle.cpp + manifest.cpp) speaks the snake_case bundle dialect
(manifest_version/graph_hash/task_descriptors/...). The shim refuses the
raw package ("unknown field 'dispatchPlan'"). Conversion requires
h13_package_to_bundle.py, whose provenance gate needs the compiler
receipt source.json that is NOT in the staged package. Unblock: EHC
regenerates/re-exports out_ab with its source.json (or the exported
bundle dialect manifest), then the bdscale path measures end-to-end on
m1-host with ab-fusedab-j1.sh (staged at /var/tmp/encwall-decomp/).

## mac-desktop bounce (capture side)

ANECompilerService was still PID 2400 all morning (checked 06:15-13:00
window); hourly poller running (hub proc bounce-poll-encbc,
.work/2026-09-22-encoder-fusion-bc/poll-bounce.sh). B->C / C->O hwx
capture remains gated on Joshua's `sudo kill 2400`.

## Next lane steps

1. On bounce: run postbounce-probe.py, decode softmax/LN task streams,
   build B->C then C->O packages (assignment target).
2. EHC: export out_ab in bundle dialect (or provide source.json) -> run
   ab-fusedab-j1.sh on m1-host; also re-baseline m1max-host "fused" with a run
   that actually submits out_ab.
3. Convert the 50 MatmulF32 dispatches to the coopmat route (profile §2).

## Addendum (same session, later windows)

### Pointwise-conv coopmat route: identity-exact, wall parity

The two per-layer MatmulF32 families are the ConvModule pointwise 1x1
convs: conv1 [2048,1024,1] (8 MB as f32) and conv2 [1024,1024,1] (4 MB),
run through apply_conv's f32 upcast (24x2 dispatches ~7+4 ms, ~264 ms
GPU/pass plus ~300 MB f32 weight copies). Landed a fast path: 1x1
groups=1 fp16 convs dispatch through _linear_f16_coopmat_kernel +
_leftover_chain_kernel (x [1,C,T] -> lhs [T,C], W -> rhs [Cout,C]).
Identity: gold bit-exact (hidden 38c73261, transcript db501a8c,
mel 5b54f4a9) in every run. Interleaved A/B (kab-20260922T072635,
1 warm + 3 meas/arm, both arms ALL GREEN): coopmat 3509.6 vs f32
3498.6 ms encoder_ane median - parity (+11 ms, window noise). The GPU
busy it removes sits inside issue-bound gaps; keep the route (frees
264 ms GPU busy + the f32 copies for when the pass becomes GPU-bound
after B->C/C->O fusion) - it does not move today's wall.

### bdscale fused A->B: executes end-to-end for the first time; verdict DO NOT LAND on this host

With EHC's converted out_ab bundle (provenance-gated
h13_package_to_bundle export; staged at bundles-fused/out_ab,
manifest_version 4 bundle dialect) the fused arm runs: out_ab submits
24x/pass alongside islands A/C (fusedab-20260922T072751). Results,
same-window interleaved 1 warm + 3 meas/arm:

| arm | encoder_ane median | out_ab submits | hidden hash | transcript |
| --- | ---: | ---: | --- | --- |
| A unfused | 5486.6 ms | 0 | 38c73261 (gold) | match |
| B fused | 6922.5 ms | 24 | 2db8a063 | match |

(Both arms inflated ~2 s vs the quiet-window 3.5 s baseline by
concurrent lane load; the paired delta is the decision number.)
Verdict: transcript and 104-prefix correct, but (a) encoder_hidden
diverges from gold (1-ULP phantom deltas from the ANE add's
ties-toward+inf rounding vs the GPU f32 add - the caveat EHC's
contract note predicted), failing the strict bit-exact gate, and
(b) +1436 ms paired: on T8103 the GPU add+select pair it removes was
never a cost, while out_ab's 2x2.25 MB fp16 + 1.1 MB bool input
marshal per submit is. FUSED_AB stays OFF on this host; the lever
that matters remains B->C / C->O capture.

## Addendum 2: module provenance audit (Main-requested)

- 4ebcfc10 was a superseded build sha (m2-proxyclient-prep bring-up log
  already noted this); the in-process receipt naming it is stale.
- The pre-audit m1-host module (82411a46, built from the a2265b0b ane_drv.c
  tree) and a rebuild from exact afb23dd branch sources compile to the
  IDENTICAL object: ko sha 84a87acebd8004179a558ee84b3ffb4912426b7a8f0
  32c765a323b56b9fd7b9e either way — behavior never differed.
- m1-host now runs the clean afb23dd-source build: ko 84a87ace..., source
  ane_drv.c 28406348c8df9e62f47d5f97671c5c22d00fd2d7e4f208afe7f9e76f1e0
  b318e (= afb23dd:ane/src/ane_drv.c), installed at
  /lib/modules/7.1.13-3-2-ARCH/updates/ane.ko + depmod, modprobe-loaded,
  writecombine=N. m1max-host unchanged: updates ko 182a97e4e0f04fdf2a7b21c53f3
  8d8c7a1cc8e79e12fb86559e2cd3f98932d8 from its afb23dd HEAD tree.
- Rebind verification: load gate PASS; full fused_e2e battery gold
  bit-exact (38c73261 / db501a8c, status match) under the new module.
  CAVEAT, pre-existing not a regression: ac-native-golden-test's
  verdict_exact_criterion FAILs identically under the old and new
  builds (same mismatch counts 162265/8369/108391 vs fresh numpy fp32
  GEMM references, ~1-ULP scale) — harness-vs-device skew, not module
  behavior. The 104-pin gate is the e2e battery, green.
