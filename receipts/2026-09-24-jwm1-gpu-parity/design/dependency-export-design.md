# LANE PROPOSAL — cross-stack dependency-gated CDM barrier (design for review, no build)

Status: DESIGN ONLY. No mesa build. Landed for review per Main.
Grounding: every file/API reference below is from the trees read this
session (mlx-omarchy rel/v0.7.3+ worktree /var/tmp/jwm1-gpu-parity-wt,
mesa-1 1c74488fe85 + barrier-sink worktree).

## 1. Problem

The honeykrisp driver emits an unconditional `agx_cdm_barrier` +
`hk_cdm_cache_flush` after EVERY compute launch
(hk_cmd_dispatch.c: hk_dispatch_with_usc_launch, tail). The t6001
launch-sink lane proved removing it entirely diverges (bit-corrupt);
the G13G reproducer on jwm1 this session confirms on T8103 (skip arm:
pin 5e093035 vs certified bc519c03, decode -29%).

The pair-class probe closed the driver-only approach decisively:
skipping any single high-frequency launch pair diverges the digest
(6/6 top classes diverged). The dependency info the driver needs —
which buffers each launch reads/writes — exists only at the MLX
encoder level, which already computes it: `CommandEncoder::
batch_needs_barrier(reads, writes)` over `TrackedRange{buffer,
offset, end}` (encoder.cpp:475-500, GATED_BARRIERS=1 path, proving
39% of dispatch pairs provably disjoint).

## 2. Root-cause hypothesis for the divergence (design-review item 1)

Buffer-disjointness alone was insufficient in the naive skip. The
original per-launch sequence is `agx_cdm_barrier` +
`hk_cdm_cache_flush` — TWO effects: (a) compute-ordering between
launches, (b) USC/texture-state cache visibility for the NEXT
launch's register configuration. The probe divergence is consistent
with (b) being unconditionally required whenever the launch's
USC/texture register configuration changes
(agx_cdm_launch_word_0 packs texture_state_count /
sampler_state_count / uniform_register_count /
preshader_register_count — visible in hk_dispatch_with_usc).

Design-review question: does `hk_cdm_cache_flush` alone (without the
preceding `agx_cdm_barrier`) suffice for (b) when buffer ranges are
provably disjoint? If yes, the skip becomes: emit
`hk_cdm_cache_flush` only, gated on (a)+(b). If no, the design needs
the barrier's ordering bits separated per the d71c94ec G13G designed
set {4,5,6,8}.

## 3. Cross-stack API shape

### 3a. MLX-omarchy side (encoder → driver signal)

The encoder already decides per-dispatch whether a Vulkan-level
barrier is needed (GATED_BARRIERS=1 path calls
vkCmdPipelineBarrier2 only on overlap). The driver sees that
decision — hk_CmdPipelineBarrier2 sets cdm_barrier_pending — and the
naive "skip unless barrier pending" is exactly what diverged. So the
API must carry MORE than the barrier/no-barrier bit:

New: the encoder appends, for each compute dispatch, a 3-word
dependency record into a device-visible "dependency side-band" buffer
(a small ring the encoder allocates alongside the command stream):

  struct HkDepRecord { uint32_t disjoint;    /* 1 = buffer ranges
                                                provably disjoint vs
                                                everything since the
                                                last explicit barrier */
                       uint32_t usc_changed; /* 0 = launch reuses the
                                                previous launch's USC/
                                                texture register config */
                       uint32_t reserved;    };

Producer: `CommandEncoder::dispatch_compute` (encoder.cpp:475
region) — `disjoint = !batch_needs_barrier(view, view)`;
`usc_changed = (info->texture_state_count !=
prev_info.texture_state_count) || (sampler_state_count != ...) ||
(push_count != ...) || (nr_preamble_gprs != ...)` — one branch, no
new passes: the tracker data is already computed there.

Consumer API (mesa): `hk_dispatch_with_usc_launch` gains a
`const struct HkDepRecord *dep` parameter (or reads the ring via a
device-visible offset carried in the launch — implementation choice
in review):

  - explicit vkCmdPipelineBarrier2 recorded  -> full
    agx_cdm_barrier + flush (unchanged; explicit barriers always win)
  - dep->disjoint && !dep->usc_changed       ->
    hk_cdm_cache_flush ONLY (skip agx_cdm_barrier)
  - otherwise                                 ->
    agx_cdm_barrier + flush (unchanged)

Kill switch: `MLX_OMARCHY_EXPORT_DEP_MASKS=0` forces the encoder to
emit disjoint=0 for every dispatch (driver behavior identical to
today); mesa side keeps the HK_PERF_ALWAYSCDMBARRIER bit.

### 3b. Side-band mechanics

The ring must be consumed in lockstep with launches. Lowest-risk
shape: the encoder allocates the ring via the existing
allocator-quarantine path, maps it host-visible (it already mmaps
tracked buffers), and passes the per-dispatch record by value:
extend `hk_dispatch_with_usc(dev, cs, info, usc, grid,
local_size)` with `uint32_t disjoint, uint32_t usc_changed` — plain
function arguments, NO shared memory protocol needed (the values are
computed on the host at record time; the driver consumes them at
record time too — both run in the same recording thread; nothing
crosses the GPU boundary). This makes the API change a function
signature extension through two call sites, not a memory protocol.

### 3c. Files touched (complete list)

mlx-omarchy (branch agent/dep-export, ~6 files):
- overlay/mlx/backend/omarchy/encoder.h       (+6: HkDepRecord-free —
  two uint32 args; env getter export_dep_masks())
- overlay/mlx/backend/omarchy/encoder.cpp     (+12: compute + pass
  disjoint/usc_changed at the dispatch_compute site)
- overlay/mlx/backend/omarchy/compute.cpp     (+4: thread the two
  args into hk_dispatch_with_usc)
- the three call sites of dispatch_compute that route through
  dispatch() (copy/fill paths unchanged — they already use
  GATED_BARRIERS' own Vulkan barriers)

mesa-1 (branch agent/dep-cdm, ~3 files):
- src/asahi/vulkan/hk_cmd_dispatch.h/.c: extend
  hk_dispatch_with_usc(_launch) signatures with the two uint32s;
  replace the unconditional barrier+flush tail with the 3-way
  decision above; HK_PERF_ALWAYSCDMBARRIER bit retained
- src/asahi/vulkan/hk_cmd_buffer.c: unchanged (explicit-barrier path
  from 5a7b371e3-era SKIP work reused)

Total: ~30-40 lines across both stacks. No shader changes. No
memory-protocol changes.

## 4. Gate plan (after design review)

1. mlx-only build: export on, driver stock (ignores the args) ->
   contract digest MUST equal dbf70497 (export alone is inert).
2. mesa consume + disjoint-only skip (usc_changed ignored): expected
   DIVERGE (proves usc_changed is load-bearing — design-review item 1
   answered empirically).
3. full skip (disjoint && !usc_changed): target digest dbf70497 + a
   decode gain (predicted: removes ~39% of ~507 barriers/token =
   ~1.9 ms/tok of the ~2.3-2.6 ms CDM sink -> decode ~+7%, 37.4 ->
   ~40 tok/s; parity still FAIL but the CDM sink closes).
4. fresh-install + real-completion proof, land both repos.

## 5. Risks

- Item-1 answer may be "flush alone is insufficient" -> design falls
  back to the d71c94ec barrier-bit separation on G13G (measured
  +3.05% bit-exact, already shipped in the installed ICD lineage) —
  the lane still lands the encoder-export plumbing which the bit
  separation consumes.
- The batch_needs_barrier proof is range-granular within a buffer;
  mlx reuses one big buffer for many tensors, so "39% disjoint" may
  overstate at sub-range granularity — the digest gate is the arbiter.
