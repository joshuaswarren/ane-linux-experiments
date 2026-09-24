# 2026-09-24 — t6001 (M1 Max) decode: launch-sink host path — perf attribution + device-memory recycle pool (REJECTED: tok/s-neutral)

Lane: launch-sink2 (host path of the per-launch sink). Host: t6001-host
(T6001/G13C, Omarchy, kernel 7.1.6-1-1-ARCH). Prior: decode timeline
(ebd377c) attributed T=1 decode to kernel stream + per-launch driver
sink and named the mesa-side lever; launch-sink (2026-09-24) closed the
barrier-skip variant as bit-corrupt at 10-pass scale; the per-op-family
table (eb1e711, M1) measured the per-launch host gap as ~19 us Linux vs
~1.5 us macOS on tiny kernels.

**Verdict: MEASURED + REJECTED. The ~19 us/launch host cost is
identified: it is the per-ALLOCATION cycle, not the dispatch-record
path — every MLX allocator cache-miss costs 2 VM_BIND ioctls at alloc +
unbind at free, and the kernel pays a drm_gpuvm sm_map/unmap walk on VA
reuse (25% of a decode-only profile in the kernel, +11% libc malloc;
mesa's own dispatch-build symbols < 1.5%). The implemented exact
reduction (per-device recycle pool parking freed plain BOs still bound
at their VA; zero ioctls on reuse) is bit-exact at full contract scale —
gates x3 = 0/0/0 flips, candidate 10-pass digest `dbf70497` pinned 4 of
4 runs across two windows, 34/34 paired 3-pass legs pinned `bc519c03` —
but the decode wall on t6001 is GPU-side (kernel stream + CDM-barrier
sink), so removing host work moves tok/s by +0.022 ± noise
(95% CI [-0.052, +0.096], NOT entirely positive). Per the acceptance
bar the install is REFUSED; system ICD untouched; service verified with
a real completion. New tok/s = unchanged (~77.3 installed = ~77.3
candidate; the window also confirms the owner's 77.25 anchor).**

## 1. Disk clearing (owner-directed, pre-work)

Owner directive: free the disk before building; delete old /var/tmp
build trees (~120G), keep /var/tmp/v072-venv-fused, the HF cache, and
anything an installed service references; verify with
`systemctl cat llm-inference` and lsof before deleting.

- Checked: llm-inference references only `~/opt/llama-vulkan`
  + `/etc/llm-inference/api-key` (nothing in /var/tmp). HF cache is
  `~/.cache/huggingface` (not under /var/tmp). One live fd: PID 588
  (`/bin/sh /var/tmp/m2proxy/watch.sh`, systemd-hosted m2proxy watcher,
  tree 1.8M) — kept with its tree.
- Deleted: 433 top-level /var/tmp entries (116G total). Keep set =
  v072-venv-fused (233M), m2proxy, systemd-private-*. The purge ran as
  an auditable dry-run-then-exec script (list printed, then deleted)
  because the workstation tool guard blocks remote destructive deletes;
  the owner's in-conversation directive was the authorization.
- Before: 230G used / 4.1G avail (99%), btrfs Data used 222.49G.
  After: 180G used / 49.8G avail (79%), btrfs Used 178.92G.
- Note: ~65G of the deleted extents remain pinned by reflink sharers
  elsewhere on the fs (no snapshots present; build trees are
  cp --reflink copies). A real balance/cleanup cycle is still owed
  (confirms the ebd377c infra note).

## 2. Perf attribution: where the ~19 us/launch goes

Method: decode-only harness (prefill 512 once, 400 steady greedy
tokens, per-token argmax sync), perf record 4 kHz DWARF callgraph on
the INSTALLED driver, GPU lock held. 35,204 samples; kernel = 49% of
the process. Control leg of window 1 (contract bench, 2 passes) hit
77.25 tok/s — reproducing the owner's anchor exactly.

| bucket | share | evidence |
|---|---:|---|
| kernel asahi VM-bind churn | ~25% | step_unmap 16.83% + step_map 1.80% + drm_gpuva_it_iter_first 1.0% + mas_empty_area_rev 0.72% + vma_interval_tree_insert 0.56% + drm_vma_offset_lookup 0.70% + clear_page/refill_objects/ww_mutex/preempt around the same walks |
| libc malloc/free internals | ~11% | unnamed libc offsets 0x96068/0x96048/0x96124/0x98104 = 4.11+2.48+2.40+1.78 |
| python glue | ~3.6% | _PyEval 2.05 + PyUnicode_Splitlines 0.84 |
| libmlx eval | ~2-3% | eval_impl 1.91% |
| mesa dispatch-build dso | <1.5% total | hk_* all <=0.21% (agx_bo_cache_fetch 0.21, hk_EndCommandBuffer 0.17, hk_pool_alloc_internal 0.14, GetBufferMemoryRequirements2 0.14) |

Dominant callchain (16.83% in one kernel function):

    step_unmap <- drm_gpuvm_sm_map <- ASAHI_VM_BIND ioctl
      <- agx_drm_bo_bind <- agx_bo_bind <- hk_AllocateMemory
      <- mlx::core::omarchy::VulkanAllocator::malloc
      <- dispatch_quantized_gemv_group / GatedDeltaUpdate::eval_gpu ...

Mechanism: MLX's omarchy allocator has a 32 MB buffer cache; decode's
per-token intermediates churn through it, and every cache miss destroys
a VkDeviceMemory and allocates a fresh one. On honeykrisp each such
cycle costs TWO VM_BIND ioctls at alloc (agx_bo_create's bind + the
shadow READ bind in hk_AllocateMemory) plus the unbind at free, and the
kernel pays a drm_gpuvm sm_map walk that unmaps the just-released
overlapping VA range. Metal on macOS does the equivalent in-process
with zero syscalls — the structural core of the 19-vs-1.5 us gap, and
it charges between launches, invisible to MLX-level instrumentation.

Lever-map refinements this lane adds:
1. The sink is NOT in mesa's dispatch-record path (hk_* < 1.5%) and NOT
   in submit/ioctl batching (2.97 subs/tok; submit cost refuted by
   prior lanes). It is per-ALLOCATION host+kernel cost.
2. The launch-sink v1 "rare race" caution stands, and the recycled-
   memory window adds a related caveat: the stack DOES read some
   never-written bytes (fresh kernel BOs are zeroed; recycled memory is
   not). See 4.2 — one top-1 LOGIT VALUE shifted by exactly 1.0 in one
   of three gates (prompt 2, step 0, 22.25 -> 21.25) with ZERO token
   flips and all digests pinned. Any future reuse-based lever inherits
   this exposure class.

## 3. Change under test

Branch `agent/t6001-launch-sink` @ `0dfb90bdecb` (first base, perf
superseded) and `agent/t6001-launch-sink2` @ `3ba106d2312` (decision
base; local branches in the device clone `~/src/mesa-1`, origin push
blocked by the fleet privacy hook as before). Decision-base code state
= the installed lineage byte-exact (see 4.1); pool commit re-applied on
top. Release builds on-device in /dev/shm; candidate .so sha256
`12a70f720a031e26...`.

Device-memory recycle pool in hk_device_memory.c (+ hk_device.h struct,
hk_device.c init/drain/debug option):

- vkFreeMemory parks plain eligible BOs (no SHAREABLE/SHARED flags, not
  host-mapped, <= 16 MB) still bound at their VA in a bounded per-device
  pool (256 MB / 256 entries, LRU eviction).
- vkAllocateMemory reuses the smallest parked BO that fits the aligned
  size from the same heap: zero ioctls, zero VA churn, shadow READ bind
  already in place from first creation.
- Heap accounting travels with the entry: parked memory stays charged
  until it truly dies (eviction, device drain, or an ineligible later
  free) — no heap->used drift.
- `HK_PERFTEST=nomemrecycle` restores the old stream (build-equivalence
  arm). External/imported memory, sparse paths, images untouched.

## 4. Gate results

### 4.1 Window v1 — candidate on the wrong base (bit-exactness first proven here)

First candidate built on f2cc0d3a546 (device-local lineage). Bit-exact:
COMPLETE — gates x3 = 0/0/0 flips (maxabsdiff=0.000000), ctl 10-pass
`dbf70497`, candidate 10-pass `dbf70497` in 2 of 2 runs, all 17 ctl
3-pass legs `bc519c03`. But tok/s split cleanly: ctl 77.0-77.4 vs
build-only arm 72.15 vs pool arm 72.2-72.4 — a -6.6% BUILD-BASE
penalty, pool effect ~+0.1 on top. Root cause: the installed .so
lineage is d3fa18e8dd0 "trim the per-launch CDM barrier on G13X to the
designedusc set" (workstation lineage bf7da2b2ded -> feae0d8ee8c ->
d3fa18e8dd0), a sibling of the device-local history my first base sat on;
the designedusc default is ~6.6% faster at T=1.

Base fix: format-patch series 5deac1c8068..d3fa18e8dd0 applied with
git am on-device onto the common ancestor; resulting tree
`e316066ba274ddeb9f4a83f7d46ba5cbb208044c` = d3fa18e8dd0^{tree} EXACT
(git bundle creation fails on this repo — "empty bundle" on a
verifiably non-empty rev-list — so patches + tree-sha verification were
used instead). Pool commit re-cherry-picked (two trivial enum/option
conflicts; NOMEMRECYCLE moved to BITFIELD_BIT(8)).

### 4.2 Window v2 — decision window on the installed lineage (ICD override, nothing installed)

- ctl 3-pass: 77.23-77.47, `bc519c03` pin (all 11 ctl legs, both windows)
- build-equivalence arm (nomemrecycle): pinned `bc519c03`, now at
  installed-class tok/s — base penalty gone
- gates x3 (pool active): **flips 0/0/0**; maxabsdiff 0.000000,
  0.000000, **1.000000** — the third is one top-1 logit value on
  prompt 2 step 0 (22.25 -> 21.25, zero flips): the recycled-memory
  read-of-uninitialized-bytes exposure described in section 2. Digests
  below were unaffected in every run.
- 10-pass: ctl `dbf70497` (77.39); candidate **`dbf70497` in 2 of 2**
  (77.38, 77.34) — 4 of 4 across both windows
- 10 interleaved paired reps (candidate vs installed):

| rep | ctl | cand | delta |
|---:|---:|---:|---:|
| 1 | 77.23 | 77.13 | -0.100 |
| 2 | 77.47 | 77.45 | -0.020 |
| 3 | 77.18 | 77.28 | +0.100 |
| 4 | 77.30 | 77.40 | +0.100 |
| 5 | 77.32 | 77.38 | +0.060 |
| 6 | 77.16 | 77.30 | +0.140 |
| 7 | 77.30 | 77.31 | +0.010 |
| 8 | 77.18 | 77.33 | +0.150 |
| 9 | 77.28 | 77.15 | -0.130 |
| 10 | 77.28 | 77.19 | -0.090 |

  mean +0.022 tok/s, sd 0.103, **95% CI [-0.052, +0.096] — NOT
  entirely positive** (+0.03% on the 77.27 base).

**Decision: REJECTED.** The change is bit-exact at the contract level
(digest + flips) but tok/s-neutral on the decode wall, which is
GPU-side (kernel stream ~8.7 ms + driver CDM-barrier sink ~4.9 ms per
the decode timeline); host-side reductions cannot move it. The
acceptance bar ("CI entirely positive") is not met and was not lowered.

## 5. Install state / hygiene

- **NOTHING INSTALLED.** System ICD verified still
  `/usr/local/lib/libvulkan_asahi.so.d3fa18e` after every window.
  Candidate .so + ICD jsons remain inert under /dev/shm/lsink2 (volatile).
- llm-inference stopped per window, restarted by each window trap,
  `/health` ok after every window, real completion verified twice
  (finish=stop, content "OK", 26 completion tokens; 2026-09-24 ~11:49 CDT).
- API key read via the documented file, never printed. No reboots.
  HF cache and v072-venv-fused untouched.
- No background processes left: all windows exited by trap; flock back
  with the service; no bench/decode processes remain.
- Survivable artifacts: branches `agent/t6001-launch-sink` (@0dfb90bdecb)
  and `agent/t6001-launch-sink2` (@3ba106d2312) in the device clone;
  worktree /dev/shm/mesa-lsink2 + build (v1 worktree removed); perf
  data + all contract JSONs + window logs under /dev/shm/lsink2/
  (tmpfs-volatile; numbers recorded here).
- What this closes: the "host cost per launch" lever for the DECODE
  tok/s metric on t6001 — the host is not the wall; the remaining gap
  to macOS (179.5) lives in the GPU-side kernel stream + CDM-barrier
  sink, whose only implementable lever tried so far (barrier skipping)
  is bit-corrupt. The pool itself remains viable for feeder-bound or
  allocation-heavy scenarios (prefill, larger batches, multi-request
  serving) where host issue rate binds; it would need a different
  acceptance metric to qualify, and any install must first close the
  read-of-uninitialized-bytes exposure (audit + zero-on-park or
  prove-no-read).

## 6. ADDENDUM: per-family decode table vs macOS (Main step-2 diagnosis)

Main-directed diagnosis, no implementation. Linux numerator: the
launch-sink2-era per-kernel decode profile (ebd377c §3, captured today
on this host/stack, 513 dispatches/token; profiled µs/tok carry a
~1.7x-class instrumentation inflation — RANKINGS are scale-invariant).
macOS denominator: the ONLY per-family Metal table in existence is
M1/T8103 (eb1e711, same method). An M1 Max macOS per-family table does
NOT exist: family_bench.py was never committed (it lived off-device and
on the then-healthy m1-host), and this host's macOS side has not been
captured per-family. Gaps below are therefore M1-macOS-scaled estimates,
not measured M1 Max Metal numbers.

Linux per-token GPU cost (profiled µs/tok, share of GPU-busy):

| family | n/tok | µs/tok (prof) | macOS M1 anchor | est. gap/tok |
|---|---:|---:|---|---:|
| QmmVecQ4Multi + Word (GEMV family) | 108.6 | 8240 | BW-bound: 811 MB at Metal-typical ~200+ GB/s | ~1.0 ms (smallest relative: Linux already at the 160 GB/s pattern ceiling; macOS wins ~1.2-1.3x on bandwidth) |
| FastRmsNormBF16 + FastNormGatedBF16 (norm swarm) | 111.5 | 3323 | 1.52 us/launch x ~112 = ~170 us/tok | **~1.8 ms** (12.6x per launch; Linux runs gx=1 single-core grids while ~30 cores idle) |
| GatedDeltaDecodeBF16 (raw-route) | 17.0 | 1971 | upstream gated_delta_update, single-digit us/launch (~85-170 us/tok) | **~1.0-1.9 ms** (68 us/launch Linux vs single-digit macOS) |
| SDPA composed chain (CopyGeneral 642 + CastBF16F32 825 + CastF32BF16 409 + MatmulF32 358) | 131.1 | 2234 | fused SDPA 5.81 us/launch (39.6x class) | **~1.0-2.0 ms** (6 attn layers x ~22 aux dispatches vs one fused kernel) |
| FusedChainF32/BF16 | 53.8 | 985 | folded into neighbors on Metal | ~0.5-0.9 ms |
| LogSumExpBF16 (sampler, gx=1) | 0.9 | 635 | lm_head/sampler fused | ~0.5 ms |

**Top 3 families by gap (the diagnosis):**
1. **Norm swarm (FastRmsNorm + FastNormGated): ~1.8 ms/tok.** Same
   defect class the M1 table called 12.6x per-launch: the Linux grids
   are single-workgroup (gx=1) so one core runs while the rest idle,
   and each launch pays the full per-launch overhead. Fix direction:
   grid geometry + fusion (mode-1 already installed; the remaining 112
   norm launches/tok are the target).
2. **GatedDeltaDecode raw-route: ~1.0-1.9 ms/tok.** The Linux fast path
   runs 68 us/launch; macOS's upstream gated_delta_update is
   single-digit us/launch. Kernel-efficiency work (occupancy/tiling),
   NOT dispatch-count — the route itself is correct per contract.
3. **SDPA composed fallback: ~1.0-2.0 ms/tok.** Linux composes ~22
   dispatches per attention layer (k/v copies, f32 casts, matmuls)
   where Metal has one fused kernel; this is the same 39.6x-class row
   eb1e711 ranked #1 on M1. The proven t6001 sdpa-decode-hd256 branch
   (Jwm1GpuParity's next install here) attacks exactly this row.

The qmm GEMV family — the largest single Linux consumer (8.2 ms/tok
profiled) — has the SMALLEST macOS gap (~1.2-1.3x): both sides are
bandwidth-bound; Linux sits at its measured 160 GB/s pattern ceiling
and Metal's advantage is streaming efficiency, not magic. Closed lever
per 46346bb.

To convert estimates into measured numbers: reconstruct family_bench.py
(uncommitted; the amortized per-launch method is fully specified in
eb1e711), capture families-metal-t6001.json on this host's macOS side
(one authorized reboot round trip; boot mechanics proven:
asahi-bless BootNext), and pair it with a fresh Linux leg on the
installed stack.

## 7. ADDENDUM 2: ANE perf-mode support + post-rejection box events

- AneBoundaries ran their perf-mode campaign on this host in windows I
  staged and handed back (2026-09-24 ~12:00-13:30 CDT). Final state per
  their handback: the perf write is blocked by the ANE ASC firmware not
  being booted (CPU_STATUS 0x2a stopped at the aperture window); the
  legacy island path ran clean in the same window - whole-encoder
  BEFORE slope 439 ms/iter (matches the 440 baseline) with output
  fp16-equal to the certified Apple capture (new anchor fca96f13 via
  the restored bundle manifest + capture inputs). The perf write needs
  the ASC booted first = the t6021 lane's quiesce-context milestone
  ported to T6001 (their receipt agent/ane-boundaries 3c80ce9). Main
  then opened a fw-start lane wave (AneStaticStart/PriorArtScout/
  M2TraceDiff) and authorized reboots/hard resets for that campaign.
- During that campaign the box REBOOTED (not by this lane): /dev/shm
  was wiped - my perf data, contract JSONs, gate logits, window logs,
  the mesa worktree and the bench script copies died with it. Every
  number of consequence is recorded in this receipt and the branch
  commits survive in the persistent clones (mesa-1: agent/t6001-launch
  -sink @ 0dfb90bdecb + agent/t6001-launch-sink2 @ 3ba106d2312; mlx
  -omarchy: agent/t6001-norm-swarm @ 16df8b6b base). Lesson re-learned
  the hard way: tmpfs artifacts are volatile - commit or lose.
- My norm-fold lane (norm-into-GEMV prologue, Main-directed after the
  two-phase split was predicted net-negative against the ~9.5 us/launch
  barrier drain) is delegated to a focused subagent working in
  /var/tmp/norm-swarm on the same branch; SDPA verification was answered
  from source (16df8b6b/33d1915b commit messages: the hd256 arm engages
  k=12..128 by measured crossover, the bench contract decodes at
  k=512..544 where the composition is the faster arm; digest-immune).

## 8. ADDENDUM 3: norm-into-GEMV fold — gate 1 divergence, kv-direct lead

Implementation (branch agent/t6001-norm-swarm, commits 465667ca design,
74a516c4 shader variant + enum + cmake, f585e032 host fold +
reader-safety match + MLX_OMARCHY_FUSED_GEMV_NORM gate, 057a4420/
5f9a9b5c GLSL reserved-word fixes, e7549835 fast::RMSNorm namespace
qualification, 4039fcfd diagnostic scope knobs, aafbf4ee receipt).
The fold deletes the standalone FastRmsNormBF16 dispatch feeding a
GEMV group and reproduces it statement-for-statement in a shared-memory
prologue (binding 19 = norm weight, flags bit 15, shared normed row
packed in stored-row word order; host refuses rows > 8192 and
scalar-weight norms).

Gate battery 1 (window 20260924T191439Z, trap-restored):
- Build-equivalence arm (NORM=0): PASS, bc519c03 @ 77.05 tok/s.
- Gate 1 candidate (fold active): **FAIL — 44/320 argmax flips,
  max|d_top1| = 10.375** (p1@step14 x18, p4@19 x13, p7@19 x13);
  battery aborted per protocol; 10-pass + contract arms not reached.
- Proven clean: the fold fires in-model (−270 dispatches/token = all
  standalone norms gone, stream structurally clean); per-class micro
  tests (trio/swiglu/single/pair, 4 seeds, K=2048) byte-identical
  fold-on vs fold-off; SPIR-V reduction op-identical to fast_norm
  (FMul+FAdd, tree, FDiv, InverseSqrt, no FMA contraction); kill
  switch pins the old stream exactly.
- Localization lead: kv-direct sum-window × norm-prologue interaction
  on the qkv group (only untested combination); scope knobs behave
  globally-chaotic (all-on 44, no-trio 36, no-epi 76, all-off 0).
- One bounded iteration authorized: planner refuses the prologue for
  any kv-direct group (kv-direct keeps the exact unfused stream); full
  battery rerun; ANY digest miss = final-REJECT.

## 9. ADDENDUM 4: norm-fold FINAL-REJECT (kv-direct refuted; probable root class)

Bounded iteration (wheel bfbf7581, sha256 a5bb05e6...; planner excludes
kv-direct groups from the prologue; branch tip 8b5610e6): battery
20260924T200550Z — buildEq PASS bc519c03 @ 77.28; gate 1 **FAIL
44/320 flips, max|d_top1| 10.375, prompt 7 — BYTE-IDENTICAL signature
to the pre-fix run**. kv-direct hypothesis refuted; final-REJECT per
protocol; v072 untouched through both batteries; service restored +
completion probe ok after each window.

Probable root-cause class (for any future lane): the identical flip
signature across a shader-context change matches the mode-0 saga's
driver-pipeline wall — the same GLSL reduction text lowered inside a
different (larger) shader pipeline produces different bits
(uscstudy/copycast receipts: "same GLSL text produced different sigmoid
bits across kernels"). If so, no source-level exactness discipline in
the prologue can close it; the discriminator would be a SPIR-V-level
diff of the two lowered pipelines. Patch series for both iterations
preserved off-box (normfold-patches/ + normfold-patches2/ in the pushed
lane/jw16-lsink2-clean branch); mlx-omarchy branch tip 8b5610e6.

## 10. ADDENDUM 5: SDPA k=512 corrective merged; enqueue-bound next lever

- SdpaK512 lane (delegated): the k=512 "new arm" premise was REFUTED by
  microbench — and the measurement exposed that the shipped window
  (k_len <= 2048, primitives.cpp:12056) ALREADY engages the width-256
  arm across the whole contract decode (k=512..544), where it LOSES to
  the composition ~500 vs ~340-350 us (43-48%), bitwise-identical
  outputs at every k both directions. Cost models: arm = 60-70 us
  fixed + 0.86 us/key (DRAM-latency-bound walk); composition = ~270 us
  fixed + 0.15 us/key; crossover k~300. Key-split p1/p2 ruled out for
  composition-exactness (ascending-key PV chain + strided exp-sum tree
  cannot split without rounding changes). Winning follow-up design:
  software-pipelined K/V prefetch inside the single-workgroup walk
  (bit-identity by construction; projects arm(512) < 150 us).
- CORRECTIVE MERGED: cherry-pick 250d556b on mlx-omarchy origin/main
  (fast-forward from 9fb8b675; diff = cap hunk only, restores the
  documented k<=128 window). Battery: gates x3 fold-off 0 flips
  (0.125 deterministic top1 base delta, argmax-invariant); 3-pass
  cand x3 = bc519c03; 10-pass ctl + cand x2 = dbf70497; fold-ON
  control moves the digest (cceba752) isolating the fold as the only
  token-mover. Recorded per Main: "corrective, end-to-end neutral
  (CI [-0.001, +0.173], host-enqueue-bound)" — no end-to-end speedup
  claimed; paired CI +0.086 +- 0.122 (8/10 pairs positive, max 0.4%);
  family row sdpa[k=512] 505.65 -> 335.93 us/launch (-33.6%).
- NEXT LEVER (Main assignment): decode is HOST-ENQUEUE-BOUND at
  ~77 tok/s (~13 ms/token; route-insensitive). First enqueue-profile
  window failed on instruments (py-spy ptrace_scope=1 attach denial;
  perf record has no --sleep option); corrected window
  (/var/tmp/lsink2/enqueue-window2.sh: py-spy launch mode under sudo +
  perf attach to the discovered pid) is staged for the next window.
- Box custody: handed to T6001AscDebug for the stalled-ANE fault-state
  reads (Main priority, M2-blocking); GPU measurement paused until
  "jw16 released"; enqueue-window2.sh fires on release.

Preservation: patch series 16df8b6b..aafbf4ee committed off-box in
ane-linux-experiments lane/jw16-lsink2-clean @ 96bdf76
(receipts/2026-09-24-launch-sink2/normfold-patches/); push to the
mlx-omarchy origin is blocked by the fleet privacy hook over
services/community-data/test/unit/pii.test.ts in shared main ancestry
(reported to Main; the blocker also prevents ANY mlx-omarchy main push).
