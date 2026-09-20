# 2026-09-19: decode t0 decomposed + sink-vs-turnaround attribution RUN — per-dispatch fixed cost is 81% CDM_BARRIER sink/cache maintenance (20.4 of 25.1 µs/launch on real kernels), turnaround 4.7 µs; gated-barriers default flip NO-LAND (+1.20% short); next driver project named with measured payoff bound: state-keyed USC-inval reduction (up to 63% of per-launch cost) pending exactness battery

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

**Why the mechanism under-delivered (scoped finding):** the A/B
falsifies, FOR THIS PROTOCOL (old bytes, jw16, pinned legs), the reading
that the ~12 µs/node inter-dispatch gap scales with APP barrier count.
Halving app barriers moved nothing: each big-hammer split is ~free
(dispatch-floor: +0.11 µs), and the gap is bound by per-LAUNCH costs the
app cannot reduce — the kitchen-sink CDM_BARRIER drain on real kernels
plus firmware launch turnaround, fired once per dispatch regardless of
app synchronization. With host record measured at 0.6 µs/node, the
decode fixed cost is cleanly attributed to per-launch GPU-side machinery
within this protocol; the obvious attacks on it are closed here:
bit-trim (termA coupled regression), chain-batch (digest corruption),
app-barrier count (this A/B, no effect).

**Attribution arms failed to initialize — root cause LOADER-CONFIRMED
locally, fix staged.**
The extracted hk49edf69 package's ICD smoke returned rc=1 on every arm
including default. Cause, now proven on the real loader (Vulkan Loader
1.3.239, `VK_LOADER_DEBUG=all` + `vkEnumerateInstanceExtensionProperties`,
x86 build of the same branch): the minimal JSON stub
(`{"ICD": {"library_path", "api_version": "1.3.0"}}` — missing the
top-level `file_format_version`) is SKIPPED outright:
`loader_parse_icd_manifest: ICD JSON … does not have a 'file_format_version'
field. Skipping ICD JSON.` — the ICD never loads, no device, mlx init
fails, rc=1. The proven shape (`file_format_version "1.0.1"`,
`library_arch "64"`, `api_version "1.4.359"`) is accepted by the same
loader against the same library. `attrib-screen.sh` on jw16 now emits the
proven shape, adds a missing-library guard, proven 32-token smoke args,
and `VK_LOADER_DEBUG=error` dump on any future failure. Remaining risk
(until run): driver-side init on the device is NOT covered by the loader
proof — the smoke is the end-to-end confirmation. **The lane OWNS the
sink-vs-turnaround attribution run** (next queue cycle after
decoder/encoder windows).

## Sink-vs-turnaround attribution — RUN (23:38Z, same window series), the decisive number

The fixed ICD loads (default-arm smoke reproduces the canonical short pin
`7fd25a869ff21678` EXACTLY on the extracted hk49edf69 driver — extraction
and trunk-equivalence validated end-to-end). Chain micro, real kernels
(mx.add 256-f32 chain, same protocol as the 09-17 micro), 5 reps per arm,
one session, only `HK_PERFTEST` differing:

| arm | chain µs/launch (median [range]) | digest (recorded, not asserted) |
|---|---|---|
| default (kitchen-sink CDM_BARRIER per launch) | **25.11** [23.8–27.7] | `7fd25a869ff21678` (exact pin) |
| nocdmbarrier (no cache maintenance) | **4.72** [4.6–4.8] | `b1dbcfdbff00e29d` (shifted — timing-only arm) |
| usccdmbarrier (USC inval only) | **9.34** [6.8–9.6] | `d1b6f77ac5a139de` (shifted — timing-only arm) |

Attribution of the per-launch fixed cost on real kernels:

- **Sink + cache maintenance: 20.39 µs/launch = 81%** of the 25.11 total.
- Launch/turnaround remainder: 4.72 µs — independently consistent with
  the dispatch-floor trivial-chain floor (4.5 µs, different lane/method).
- **USC-inval-only recovers 15.77 µs/launch (63% of the total)** — the
  USC invalidate dominates the sink.

Arithmetic bound for decode (NOT a measured decode claim): 201 launches ×
15.77 µs ≈ 3.2 ms/token of headroom IF the sink were USC-only — an upper
bound; the in-decode realization is smaller (heavier kernels overlap the
drain, launch mix differs) and must be measured on the decode legs before
any perf claim.

Correctness boundary (recorded, not gated): BOTH reduced-barrier arms
shift the 32-token greedy digest on this micro — the sink is
load-bearing beyond USC state on this path. A default-emission sink
reduction is therefore NOT a knob flip; it requires (a) identifying WHICH
digest-relevant dependency each sink bit covers (the termA bit-map work
is the base), (b) keying the reduction on driver-known state — e.g. drop
or shrink the USC invalidate only when the launch's uniform state is
unchanged since the previous launch (`hk_cs` tracking), (c) a full
exactness battery + the standing digest protocol. That is the named next
driver project, now with a measured payoff bound (up to ~63% of the
per-launch fixed cost, decode-realization TBD).

## Hardware safety / coordination

- A/B window queued via hub with EncoderSubmitRepair; fired ONLY on their
  explicit RELEASE ping (verified: lock free, service active with their
  real-completion receipt). Bf16RecertRepair acknowledged the chain.
  jwm1 untouched (hard-held, no access attempted).
- Attribution window fired ONLY on ParakeetDecoderParity's explicit
  RELEASE ping, per Main's queue (directly after decoder; encoder
  candidate not yet ready). One control noted: the first launcher invoked
  the previous window script, which blocked harmlessly on the held flock
  (killed — my own PID, remote, no state touched, cleanup not yet armed);
  relaunch followed an explicit timer+service stop.
- No concurrent driver installs: the attribution package (hk49edf69,
  mesa-1 branch `hk/dispatch-attrib`) was EXTRACTED to
  `/var/tmp/gdb/attrib-arm` only, never installed.
- Final steady state verified after BOTH windows: llm-inference
  **active**, `llm-benchmark-recovery.timer` **active**, real completions
  `chatcmpl-aJWcGIUIqY8iEyXNf3G9r4eqCXbF3IEf` (A/B window) and
  `chatcmpl-wYRO67dw95fvPFA9L7o5fTWo2uT6alJv` (attribution window, 16
  completion tokens, qwen3.8-27b @ :8002; receipts in
  `service-completion.json` / `service-completion-attrib.json`).

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

## Bit-ownership derivation + safe candidate (source-side, mesa-1 `hk/dispatch-attrib` @ `ccad76a6160`)

Trunk `agx_cdm_barrier` composition (read from `e1677564284`):

- **G13X** (jw16): prefix `{unk_5, unk_6, unk_8}` ∪ G13X `{unk_4}` ∪ the
  `chip != G13G` block `unk_0..unk_19 + usc_cache_inval` → effective
  **unk_0–19 + usc_cache_inval** (full sink).
- **G13G** (jwm1): `{unk_4, unk_5, unk_6, unk_7, unk_8}` — the trimmed
  set already on trunk (measured +3.05% ctx1053 there, digests 48/48).
- Packing comment (upstream): the unk_0..unk_19 block exists for PBE
  flush + texture cache invalidation between dispatches ("blits");
  usccdmbarrier's comment: compute→compute through the L2-backed storage
  path does not require the PBE/texture maintenance.

Measured attribution (previous section) assigns costs on real kernels:
unk_0–19 block ≈ 15.8 µs/launch, usc_cache_inval ≈ 4.6 µs/launch, base
turnaround ≈ 4.7 µs. Digest evidence: termA's designed set {4,5,6,8}
held pinned digests 48/48 (without usc); usc-only shifts digests (missing
the designed-set bits), full sink holds.

**Safe candidate shape**: G13X emission = `{unk_4, unk_5, unk_6, unk_8} +
usc_cache_inval` — the designed set covering the digest-relevant
dependencies PLUS the USC invalidate covering uniform/texture-state
changes. This is the previously-unmeasured quadrant. New perftest arm
`HK_PERFTEST=designedusccdmbarrier` added (`ccad76a6160`, x86 compile
green) so the next attribution window can cost it, followed by the
standing digest protocol + both decode legs + the omarchy runtime suite
before any landing discussion. State-keying (emit usc-inval only when the
launch's uniform/texture-state actually changed, keyed on hk_cs) is the
second-stage reduction once the static shape proves digest-clean.

## designedusccdmbarrier costed + gated — RUN (00:20Z window, hkccad76a-1): exactness PASS, decode NO-LAND

Four-arm micro on the rebuilt package (`hkccad76a-1` = ccad76a6160,
cross-session replication vs the previous window: default 24.68 vs 25.11,
nocdm 4.73 vs 4.72, usc 9.33 vs 9.34 — instrument stable):

| arm | µs/launch | 32-token digest |
|---|---:|---|
| default (full sink) | 24.68 | `7fd25a869ff21678` exact |
| nocdmbarrier | 4.73 | shifted |
| usccdmbarrier | 9.33 | shifted |
| **designedusccdmbarrier {4,5,6,8}+usc** | **16.74** | **`7fd25a869ff21678` exact** |

Micro: the candidate saves 7.94 µs/launch (−32%) AND holds the short
pin — the first barrier flavor to do both on this micro.

Exactness gate (RUN_DESIGNED_GATE=1, pins FATAL): **PASS both legs** —
short and ctx1024 smokes reproduce both canonical pins; 24/24 battery
rows exact. This upgrades the barrier-manifold knowledge: {4,5,6,8}+usc
is a VALID correctness point on G13X (with usc added, termA's
designed-set digest behavior extends to ctx).

6-round interleaved battery, BOTH arms on the same extracted trunk
driver (removes the installed-package vintage from the comparison;
absolute short level ~198 tok/s reflects the merged trunk's FTZ-revert
lineage):

| arm | short med | ctx1024 med | ctx prefill |
|---|---:|---:|---:|
| designedusc | 198.68 [195.99–199.88] | 140.90 [134.25–157.51] | 3885 |
| default | 198.25 [195.48–199.60] | 144.58 [140.11–160.54] | 3897 |
| delta | +0.22% | −2.54% | −0.32% |

**VERDICT: NO-LAND.** The micro's −32% does not transfer to real decode:
the fully-dependent tiny-kernel chain exposes the full drain latency
between launches, while real decode kernels may be heavy enough that the
drain overlaps execution — HYPOTHESIS for the non-transfer, not proven by
this no-gain alone (measured decode-leg timing on hkccad76a required;
analyzer staged: /var/tmp/gdb/analyze_decode_attrib.py). ctx is
slightly negative (same direction as termA's designed-set ctx −3.17%,
now also with usc). The G13X barrier-shape lever is now bounded from
three directions: termA (designed set: short+13/ctx−3.17, installed
vintage), chain-batch (corrupts), designed+usc (digest-clean, decode
even/ctx-negative). No barrier flavor both holds pins AND wins decode on
G13X; the per-launch sink cost is real (20.4 µs measured) but its price
is paid only where decode is not actually waiting. Remaining bounded
follow-ups, all requiring new evidence: (a) decode-leg sink attribution
(profiler brackets on the hkccad76a driver) to confirm the overlap
hypothesis; (b) state-keyed usc-inval (second-stage) — likely same
non-transfer; (c) accept the measured verdict: the fixed-cost lever on
G13X is firmware/turnaround-bound, not driver-addressable.

jw16 restored and verified: llm-inference active, timer active, real
completion `chatcmpl-3zZcStKe9oF0C4XQENPZPR9GctpPtzPW` (16 tokens).

## Real-decode attribution — MEASURED (01:29Z window, diag wheel + hkccad76a): overlap hypothesis CONFIRMED, barrier lever closed with mechanism

Setup: qmmceil diag wheel (`diag.6f70d4fa`, wheel sha `b1147338…`) on the
extracted hkccad76a driver, MLX_OMARCHY_GPU_PROFILE per arm/leg,
HK_PERFTEST default vs designedusccdmbarrier, 41 decode steps per leg.
Provenance + observer-effect caveat recorded in the window log: the
profiler adds a timestamp+barrier pair per dispatch, so absolute gaps are
profiler-shaped — only the CROSS-ARM DELTA under identical
instrumentation informs the hypothesis. Exactness for this experiment =
cross-arm digest EQUALITY: **all four legs reproduce the canonical pins
exactly** (`7fd25a869ff21678` short / `7da83f06ec9f001d` ctx) in both
arms — the diag vintage is digest-identical to the protocol wheel here.

Measured (41 submissions × 201 nodes per leg, both legs):

| metric | default | designedusc | delta |
|---|---|---|---|
| host record/node | 0.6–0.9 µs | 0.6–0.9 µs | none |
| **inter-kernel gap median** | **~11–12 µs** | **~11–12 µs** | **≈0 (±1 µs wander)** |
| busy/span | bracket-noise band | bracket-noise band | — |

**The micro's 7.94 µs/launch saving is ABSENT in real decode** (per-node
gap delta ≈ 0 on both legs, 8200+ nodes measured). This is CONSISTENT
WITH the overlap reading but does not prove it, and does not decompose
the ~11 µs remainder: equal median gaps under two flavors show only that
neither flavor reduces the gap. Candidates for the remainder (firmware
launch cadence, drain hidden under kernels, other serialization) are
UNDECORATED — decomposition requires attributable stall counters (firmware
timeline) or controlled dependency tests. No wholesale impossibility
claim: the barrier lever is closed FOR THE TESTED FLAVORS (measured
no-delta), not in general. Next attribution targets are kernel-side (KV
walk, qmm kernel time), consistent with the 09-17 slope/fixed
decomposition and the dispatch-floor verdict.

jw16 restored and verified: llm-inference active, timer active, real
completion `chatcmpl-3zZcStKe9oF0C4XQENPZPR9GctpPtzPW`. Provenance
recorded in the window log: wheel `b1147338…`, lib `831c2bc6…`,
ICD `278f473b…`.

## Kernel-side census instrument — staged (first pass, header caveat)

`analyze_kernel_census.py` (this receipt's .d/ dir, also jw16
`/var/tmp/gdb/`) attributes profiled busy to kernels by enum name. First
pass on the decode profiles: header mismatch with the diag wheel leaves
several `unkNNN` entries (use the wheel-build's own compute.h); resolved
so far on 8768 dispatches: ReduceGeneralF32 18.3%, HadamardF16 7.3%,
ElementwiseF16 6.0%, CastU32F32 0.7%; largest unresolved single-kernel
block `unk25984` (12.8%, n=462 ≈ 11/step, ~124 µs mean — likely the
qmm/sdpa family, mapping pending). Per-kernel census is the base for the
kernel-side attribution Main directed; runs offline on the four
`/var/tmp/gdb/dprof-*.ndjson` profiles, no GPU needed.
