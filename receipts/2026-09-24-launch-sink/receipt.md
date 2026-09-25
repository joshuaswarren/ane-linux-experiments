# 2026-09-24 — t6001 (M1 Max) decode: launch-sink levers — prefill-in-decode routing audit closed (premise false); dependency-tracked CDM barrier FAILED the rare-race gate, install reverted

Lane: launch-sink (launch-sink worker). Host: t6001-host (T6001/G13C,
Omarchy, kernel 7.1.6-1-1-ARCH). Starting stack: serving venv
`/var/tmp/v072-venv-fused` (untouched), driver = installed
`/usr/local/lib/libvulkan_asahi.so.d3fa18e` (sha256 `1e912d3e03d11e55…`;
lineage = mesa-1 `feae0d8ee8c` per the maxdispatch worktree PROVENANCE — the
.so name is a binary hash prefix, not a git sha). Model
`SiddhJagani/Qwen3.8-2B-mlx-4Bit`; contract = 10 prompts, warmup 3, greedy,
32 new tokens, prefill 512 (`~/bench-scripts/qwen38-mlx-bench.py`).

**Verdict: LEVER 1 measured-CLOSED — the "prefill kernels in decode" premise is
false; no prefill-shaped dispatch exists inside single-token decode cycles and
there is no dispatch-depth defect (513 dispatches/token = the bitwall
prediction exactly). LEVER 2 measured-FAILED and REVERTED — the
dependency-tracked per-launch CDM barrier (mesa-1 cdm-dep-barrier @ 25bbe37,
build b5cd7dbc) ran +4.83% bit-clean on short gates but diverged the 10-pass
pin in 3 of 7 runs while the control pinned dbf70497 in 10 of 10, including a
reproducible divergence fingerprint (prompt 8, token 5) and one hung control
leg; per Main's directive the backup ICD was restored, the service re-verified
with a real completion, and the lever is recorded as a rare-race failure.
System state: ICD = d3fa18e (backup), service active + completion verified.**

## 1. Lever 1 — "prefill kernels in decode": premise measured false (CLOSED)

Re-analysis of the ebd377c profile (`/var/tmp/profdecode-out/profile.jsonl`,
187,004 dispatches) shows QmmPrefillCoopmatM16 3.1/tok + GatedDeltaPrefill
0.9/tok never occur inside a decode step:

- Token cadence: LogSumExpBF16 (sampler) fires once per token; inter-token gap
  = **513 dispatches exactly for 326 of 339 tokens**. The 9-11 large gaps
  (1601/1637/1270) are the prompt transitions.
- A mid-run 513-dispatch cycle is 100% decode-shape kernels (QmmVecQ4Multi,
  FastRmsNorm, GatedDeltaDecode, GdnConvDecode, QmmVecQ4Word, FusedChain,
  Swiglu, FastRope, SDPA family). 513 = the post-fold bitwall prediction
  exactly — no dispatch-depth defect.
- All 2,574 prefill-shaped dispatches sit in 11 bursts of exactly 36
  GatedDeltaPrefill (18 GDN layers x 2) spaced 18,017-18,019 dispatches apart
  = once per prompt boundary, each the next prompt's prefill leg (~1,600
  dispatches, T = 11-19 tokens; the coopmat QuantizedMatmul batch M = 10-17
  matches the encoded prompt lengths).
- The T==1 vs T>1 routing is by contract (`gated_delta_update`: q.shape[1]==1
  -> gated_delta_update_raw/GatedDeltaDecodeBF16; T>1 -> prefill kernel; qmm:
  matrix_m==1 -> QmmVec GEMV, m>1 -> coopmat). Decode steps use decode kernels
  everywhere.
- The old receipt's figures were a fixed-513 slicing artifact: each ~35-token
  prompt cycle contains one ~1,600-dispatch prefill leg that the slicing
  spread across ~3 "cycles" (dirty clusters at cycles 7-9, 42-44, ... every
  35). The bench's decode window starts after the first token (prefill is
  inside ttft), so no decode-metric win exists. Nothing to fix, nothing
  installed.

## 2. Lever 2 — dependency-tracked per-launch CDM barrier: FAILED rare-race gate, REVERTED

### 2.1 Mechanism and build

honeykrisp flushed the full designed CDM barrier set after every launch
unconditionally (`hk_cdm_cache_flush` in `hk_dispatch_with_usc_launch`).
The change (mesa-1 branch `cdm-dep-barrier`, commit 25bbe37 on device
`/dev/shm/mesa-d3`, twin 92ac13acd85 on the workstation; lives only in local
checkouts — origin push is blocked by the fleet privacy hook over host names
in this lineage's messages/blobs): `hk_CmdPipelineBarrier2` marks
`cmd->state.cs.cdm_barrier_pending`; the next CDM launch carries the full
designed set and clears the flag; unordered launches skip the barrier;
`hk_EndCommandBuffer` lands an unconsumed barrier on the trailing edge;
`hk_queue_write` keeps its explicit flush; GL gallium untouched;
`HK_PERFTEST=alwayscdmbarrier` restores the old stream. Paired upstream env:
`MLX_OMARCHY_GATED_BARRIERS=1` (in the installed wheel) makes MLX emit
vkCmdPipelineBarrier only for tracker-proven range overlaps.

Build: release, base d3fa18e8dd0, sha256 `b5cd7dbc978242034fbf2dfb…`, built
natively on the device in /dev/shm. (debugoptimized builds trip a pre-existing
`agx_compile.c` disassembly selftest gap — `#ifndef NDEBUG` — which is why the
shipped lineage builds release.)

### 2.2 Gate results

Screen (3-pass): ctl 74.01 `bc519c03`; armD (new build + alwayscdmbarrier)
73.79 `bc519c03` — build-equivalence; cand (new build default + gated MLX
barriers) 77.61 `bc519c03`.

Install gate, first pass: flips gates x3 = **0/0/0**; 10-pass ctl = **dbf70497
exact**; 10 paired reps = **+3.574 ± 0.152 tok/s (95% CI, n=10) = +4.83%**
(sd 0.213). cand 10-pass mismatched once (cand10b, 1 divergent pair of 100).

### 2.3 Rare-race battery (Main-directed) and failure

Main challenged the 1/4 candidate miss as a possible rare race, not noise, and
set the standard: 10 interleaved candidate/control 10-pass pairs on the
system-default install; candidate divergences must not exceed control's;
otherwise restore the backup ICD at once. Battery (window4, interleaved):

| arm | 10-pass runs | dbf70497 PIN | DIVERGED |
|---|---:|---:|---:|
| control (system default, no env) | 5 | **5** | **0** |
| candidate (gated) | 4 (then cancelled) | 2 | **2** |

Plus all earlier runs today: candidate 10-pass total 3 DIVERGED of 7;
control 5 of 5 PIN (plus the historical pin reproductions).

Divergence fingerprint: w4_c1cand diverges at (pass 0, prompt 8) from token 5,
21 positions; w4_c2cand diverges at (pass 3, prompt 8) from token 5, 21
positions — the **same prompt, same token, same cascade length in two
different runs**: a reproducible knife-edge that the candidate's timing flips
and the control never does. Not the gross-corruption class (320/320 flips),
but reproducibly gated on the candidate's barrier skips — exactly the rare
race Main predicted. Separately, the battery's leg 9 (a CONTROL leg) hung for
20+ minutes before the stop, on a box that had completed 8 identical legs at
~63 s each — recorded as an associated stability observation, cause unknown.

### 2.4 Install state: REVERTED

- Per the directive, the backup ICD was restored:
  `/usr/share/vulkan/icd.d/asahi_icd.aarch64.json` ->
  `/usr/local/lib/libvulkan_asahi.so.d3fa18e` (sha `1e912d3e03d11e55…`,
  verified by reading the json back). The candidate .so
  (`b5cd7dbc…`) remains at `/usr/local/lib/` alongside it, inert.
- Service `llm-inference.service` active, `/health {"status":"ok"}`, real
  completion verified post-restore: finish=stop, content "Hello", 30
  completion tokens (2026-09-24 ~07:10 CDT).
- What this closes: dependency-tracked CDM-barrier skipping keyed on MLX's
  emitted barriers is NOT bit-exact on G13X at 10-pass scale. Either MLX's
  disjointness tracker misses a real dependency class or the hardware needs
  the barrier between unordered launches for reasons beyond data-flow overlap
  (texture/usc state visibility — cf. the d3fa18e commit note that the USC
  invalidate "covers uniform/texture-state change between launches"). A future
  lane would need to instrument which unordered pair produces the stale read
  before any skip is safe. The +4.83% was real speed; it does not meet the
  bit-exact bar.

## 3. Hygiene

flock /tmp/m1-gpu.lock held for every window; llm-inference stopped inside
each window and restarted by traps (health ok after every window). API key
read from the documented file, never printed. No reboots; HF cache and
v072-venv-fused untouched. /dev/shm build trees (mesa-cdm, mesa-d3, bundle)
deleted after the revert; `/dev/shm/cdm-dep/out/` on the device keeps the window logs and contract JSONs (tmpfs-volatile). Battery
cancelled at 9 of 20 legs once the directive's restore condition was met
(candidate divergences > control's zero).
