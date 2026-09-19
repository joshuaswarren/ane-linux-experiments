# 2026-09-19: decode t0 decomposed — host record 0.6 µs/node, per-dispatch cost is per-launch GPU machinery; TOP-1 gated-barriers default flip screened on jw16 and NO-LAND (+1.20% short, below the >3% rule); app-barrier count falsified as the lever; sink attribution ICD arms failed init (still unmeasured)

Date: 2026-09-19. Lane: GpuDispatchParity. Hosts: dev box (local source/build
only, lavapipe) and jw16mbp1-linux (M1 Max G13C C0, driver
`mesa-honeykrisp-omarchy 26.3.0.devel.hk5deac1c-2` untouched throughout —
no packages built, no installs, no ICD arms). Repos: `joshuaswarren/mesa-1`
(trace only) and `joshuaswarren/mlx-omarchy` (implementation).

## Why this lever: the trace

Every previously-named attribution of the decode fixed overhead ("barrier
sink + dispatch chain", +1.68 ms/tok vs native, 09-17 post-twopass) pointed
at mesa's emission path. Re-tracing it against the closed families:

1. **Mesa dispatch path is measured lean.** `hk_CmdDispatch` reuses one
   `hk_cs` per command buffer; per launch it packs CDM_LAUNCH + the
   kitchen-sink CDM_BARRIER (`hk_cdm_cache_flush`). App-level
   `vkCmdPipelineBarrier2` is the "big hammer" (cs split + merge-with-jump
   at EndCommandBuffer); the split machinery measured ~free
   (`barrier_trivial` 4.63 vs 4.52 µs/node, 09-10 dispatch-floor). The
   per-dispatch floor on G13G is ~4.5 µs end-to-end (2.5 µs device cadence
   + ~2 µs host record) — through a raw Vulkan app.
2. **The mlx chain micro is not the raw floor**: 27.7 µs/launch (jw16) /
   20.2 (jwm1) through the backend. Two candidate explanations — host-paced
   recording vs GPU turnaround — were never discriminated for decode.
3. **Discrimination from existing data, no new GPU time**: the qmmceil lane's
   phase profiles (`/var/tmp/qmmceil/out/profile-{short,ctx}.jsonl`,
   diagnostics wheel 6f70d4fa) contain per-dispatch `host_cost` (exact,
   unperturbed) and GPU t0/t1 brackets for 2 decode steps per window
   (submissions 4-6, n=201 each):

   | window | sub | n | host record med/node | GPU span | busy | inter-dispatch gap med (p90) |
   |---|---|---:|---:|---:|---:|---:|
   | short | 4-6 | 201 | **0.58-0.67 µs** | 12.9-13.8 ms | 8.4-10.8 ms | **12 µs** (21-57) |
   | ctx | 4-5 | 201 | **0.58-0.71 µs** | 12.7-13.1 ms | 8.9-10.5 ms | **11 µs** (18-52) |

   **Host-paced theory is dead**: the backend records a decode node in
   ~0.6 µs. The decode token's ~25.7 µs/dispatch fixed cost (t0 5.17 ms /
   201 dispatches, 09-17) lives in GPU-side inter-kernel machinery: the
   driver's per-launch sink + the backend's TWO unconditional
   `vkCmdPipelineBarrier` per node (pre+post, ungated mode), each a
   Honeykrisp big-hammer cs split with its own barrier drain, plus
   profiling brackets in the measured spans (~21-23 µs/bracket-pair per
   dispatch-floor; the brackets are in the profiled spans, not in clean
   walls).
4. Prefill (subs 1-3) shows the same machinery at larger binding counts
   (host record 33-36 µs/node — descriptor-update dominated, different
   regime; gap med 12 µs short / 28 µs ctx).

So the named lever's first half — "barrier elision keyed on existing
dependency tracking" — is an APP-VISIBLE requirement (the driver cannot
know app-level independence; chain-batch proved blindly dropping the
barrier corrupts; bit-trim is coupled-closed), and the app side ALREADY
implements it: `MLX_OMARCHY_GATED_BARRIERS` (TOP-1, decode-gap plan
2026-09-06) — one dependency-tracked barrier per real hazard instead of
two unconditional ones per node. It shipped default-off "pending the M1
A/B" which had never run. This lane runs that A/B under the standing
protocol and, on a win, flips the default.

## The change (mlx-omarchy `agent/gated-barriers-default`)

- `CommandEncoder::gated_barriers()` default ON via new
  `env_flag(name, default_value)` overload; `MLX_OMARCHY_GATED_BARRIERS=0`
  restores the unconditional pre+post path.
- Test parser in `test_runtime.cpp` tracks the shipped default (unset =
  gated), keeping both modes asserted.
- `docs/install-omarchy.md` barrier section updated.
- Semantics of the gated mode (all pre-existing, reviewed this lane):
  conservative RAW/WAW/WAR overlap test with bindings tracked as both
  read+write (never skips a real hazard; may barrier a read-read pair);
  `!head_synced_` forces a full dependency barrier at each batch's first
  node, which is what keeps pre-submit host writes (host-materialized
  scalars) visible; `flush_noncoherent` runs pre-submit; gated submissions
  end with a device-to-host visibility barrier.
- Scope notes for the correctness review: barriers are scheduling-only —
  no shader recompilation, no fp/trig lowering changes (SIMDMAT state
  untouched); prefill/coopmat dispatches flow through the same gated path
  and their numerics are pinned by the battery's digest gates.

### Local focused proof (dev box, lavapipe, `-DMLX_BUILD_CPU=OFF` gate recipe)

| suite | gated default | `=0` (ungated) |
|---|---|---|
| omarchy_runtime_tests | **41/41, 22678 asserts** | 41/41, 22678 asserts |
| omarchy_copy_offset_tests | 26/26 | 26/26 |
| omarchy_primitive_tests | 101/103 | 101/103 |

The 2 primitive failures are `RandomBits ... has no CPU implementation`
exceptions — identical in both modes, an artifact of the CPU backend being
off in the documented gate recipe, unrelated to this change.
`InsertWaits`/hazard-chain cases (RAW/WAW/WAR value + counter asserts) pass
in both modes.

## Battery (jw16, this lane's window)

- SAME wheel both arms: `mlx_omarchy-0.32.2.dev202609152131+1deb70f1`
  (libmlx pin `6d61d44a…` fatal per run) — the arms differ ONLY by the env
  var, which is exactly the landed difference (default flip changes no
  codegen). `bench_decode.py` sha `f5062d88f34b0845`, model
  `Qwen2.5-0.5B-Instruct-4bit @ a5339a41`, `MLX_DISABLE_COMPILE=1`,
  `HF_HUB_OFFLINE=1`, 6 interleaved rounds per arm, pins
  `7fd25a869ff21678` (short) / `7da83f06ec9f001d` (ctx1024) fatal on every
  row; prefill captured per leg.
- Arms: `gated` = `MLX_OMARCHY_GATED_BARRIERS=1`, `base` = unset (the
  wheel's built-in default, ungated).
- One `/tmp/m1-gpu.lock` hold (inode 12); `llm-benchmark-recovery.timer`
  stopped first (it had restarted llm-inference mid-window during the
  encoder's window at 17:36:54) and restored after; llm-inference stopped
  before, restarted after with a real-completion receipt. Installed
  driver untouched (`hk5deac1c-2`).

[BATTERY-RESULTS]

## Land decision

Rubric (fixed before the battery, per the standing land rule):

- **WIN** = gated short-decode median beats base by >3% (the ±3% row-wander
  threshold used to reject device-load-coh7, fma-ceiling-unroll and the raw
  wait series) with all 24 rows + 4 warmups digest-clean, ctx1024 not
  regressing beyond wander (≥ −3%), prefill legs not regressing beyond
  their observed wander (±5% ctx, ±3% short). On WIN: merge the default
  flip to mlx-omarchy main, push, finalize this receipt.
- **NO WIN / regression** = restore default-off (delete the branch),
  receipt records the negative result and the next source lever.

Native comparison (explicit, per chip, jw16 = M1 Max): native short
286.96 tok/s, native ctx1024 283.79 tok/s (09-17 post-twopass pins). Both
arms' medians are reported as % of these.

## Battery result: EXECUTED 22:58–22:59:41Z — 24/24 rows digest-exact, VERDICT NO-LAND

| arm | short med (tok/s) | ctx1024 med (tok/s) | ctx prefill med | short prefill med |
|---|---:|---:|---:|---:|
| gated | 180.13 [178.38–180.26] | 140.79 [132.94–153.44] | 3901 | 458.3 |
| base | 177.98 [171.24–180.48] | 136.55 [130.24–146.55] | 3864 | 456.9 |
| delta | **+1.20%** | +3.01% | +0.94% | +0.3% |

% of native (jw16/M1 Max pins): gated short 62.8% / base 62.0%; gated
ctx1024 49.6% / base 48.1%.

**WIN required short >+3%; measured +1.20% → NO-LAND.** Gated's tight
[178.4–180.3] rows vs base with one 171.2 low row overlap heavily;
ctx1024 +3.01% sits at threshold inside that leg's documented ±5–10%
wander; prefill neutral. Per the same rule that rejected
device-load-coh7, fma-ceiling-unroll, and the raw wait series: no
measured win → no land. The default flip is REVERTED (local branch
deleted; nothing was pushed to mlx-omarchy).

**Scope (per Main's steering): this is an OLD-BYTE mechanism
qualification on the pinned `1deb70f1` wheel — the same bytes every prior
jw16 battery used, so deltas are protocol-comparable — NOT
corrected-release parity.** A release-parity claim would require
rebuilding the candidate wheel from corrected current bytes (main lineage
≥925cfa64) with the flip and rerunning this identical battery; moot for a
NO-LAND verdict, required first if the mechanism is ever revisited.

**Why the mechanism under-delivered (the real finding):** the A/B
falsifies the reading that the ~12 µs/node inter-dispatch gap scales with
APP barrier count. Halving app barriers moved nothing: each big-hammer
split is ~free (dispatch-floor: +0.11 µs), and the gap is bound by
per-LAUNCH costs the app cannot reduce — the kitchen-sink CDM_BARRIER
drain on real kernels plus firmware launch turnaround, fired once per
dispatch regardless of app synchronization. With host record measured at
0.6 µs/node, the decode fixed cost is now cleanly attributed to
per-launch GPU-side machinery, and the obvious attacks on it are closed:
bit-trim (termA coupled regression), chain-batch (digest corruption),
app-barrier count (this A/B, no effect).

**Attribution arms failed to initialize**: the extracted hk49edf69
package's ICD smoke returned rc=1 on every arm including default
(ICD/loader init failure, not timing data), so the sink-vs-turnaround
split on real kernels remains UNMEASURED. Timing-only scope; no
functional claims carried. Named follow-ups: (1) fix extracted-ICD init
and run the HK_PERFTEST attribution for the sink/turnaround split;
(2) kernel-count reduction via fusion (the encoder lane's A+C candidate
is the live path); (3) if the sink share is confirmed large, a
precision-preserving sink replacement is the only remaining driver-side
lever — new compiler work requiring its own exactness battery.

## Hardware safety / coordination

- Window queued via hub with EncoderSubmitRepair; fired ONLY on their
  explicit RELEASE ping (verified: lock free, service active with their
  real-completion receipt). Bf16RecertRepair acknowledged the chain.
  jwm1 untouched (hard-held, no access attempted).
- No concurrent driver installs: the attribution package (hk49edf69,
  mesa-1 branch `hk/dispatch-attrib`) was EXTRACTED to
  `/var/tmp/gdb/attrib-arm` only, never installed.
- jw16 steady state restored and verified: llm-inference **active**,
  `llm-benchmark-recovery.timer` **active**, real completion
  `chatcmpl-aJWcGIUIqY8iEyXNf3G9r4eqCXbF3IEf` (16 completion tokens,
  qwen3.8-27b @ :8002; receipt `/var/tmp/gdb/service-completion.json`).

## Artifacts

- jw16: `/var/tmp/gdb/{window-gdb.sh,cb_ab_gdb.py,window-gdb.log,ab-gdb.json,service-completion.json,finished-gdb.txt,attrib-*}`
  (harness byte-identical to the screened `cb_ab_1deb.py`, sha256 prefix
  `2d95227a5c6bad1a`; attribution package
  `~/src/mesa-pkg-jw16-attrib-20260919/mesa-honeykrisp-omarchy-26.3.0.devel.hk49edf69-1-aarch64.pkg.tar.xz`,
  build log `~/log/jw16-mesa-attrib-build.log`, EXIT=0).
- mesa-1: branch `hk/dispatch-attrib` @ `49edf697c5c` (PUSHED — the
  HK_PERFTEST CDM knob instrumentation rebased onto `e1677564284`;
  default emission byte-identical; x86 compile check green 620/620).
- mlx-omarchy: local branch `agent/gated-barriers-default` DELETED with
  the NO-LAND revert; the flip diff is reproduced in this receipt and in
  the window artifacts.
- Profiler evidence (pre-existing): `/var/tmp/qmmceil/out/profile-{short,ctx}.jsonl`
  on jw16; analyzed with the parse in this receipt's git history.
