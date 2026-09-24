# Mesa per-launch CDM barrier dep-tracked SKIP — failure analysis + instrumentation prerequisite

**Branch**: `cdm-dep-barrier` (the failed-gate SKIP, sitting uncommitted in
jw16mbp1-linux's `~/src/mesa-1` as a +55-line local diff on top of
`f2cc0d3a` AGX_SUBMIT_TRACE).
**Receipt cited**: `receipts/2026-09-24-t6001-launch-sink/receipt.md` —
"+4.83% bit-clean on short gates but diverged the 10-pass dbf70497 pin
in 3 of 7 runs vs ctl 5/5 (reproducible fingerprint: prompt 8 from
token 5)".
**Hardware**: G13X (jw16 / M1 Max). G13G (jwm1 / M1) does NOT carry this
diff; the proven G13G trim 4..8 bits (73974760e06) ships in
production. Per Main's directive: reverted; not installed.

## What the dep-tracked SKIP changes (5 files, +55 lines)

- `hk_cmd_buffer.{c,h}`: adds `bool cdm_barrier_pending` to `hk_compute_state`;
  `hk_CmdPipelineBarrier2` sets it; `hk_EndCommandBuffer` consumes it (lands
  the barrier on the trailing edge of the open compute stream if any).
- `hk_cmd_dispatch.c`: `hk_dispatch_with_usc_launch` consumes `cdm_barrier_pending`
  — when set, emits a single `agx_cdm_barrier` BEFORE the launch and clears
  the flag. The `hk_cdm_cache_flush` call (which did `agx_cdm_barrier +
  cache flush`) is removed from the unconditional path.
- `hk_device.{c,h}`: new `HK_PERF_ALWAYSCDMBARRIER` perf-test bit
  (BITFIELD_BIT(5)) to restore the unconditional flush for A/B.

Net effect: between consecutive compute launches with no
`vkCmdPipelineBarrier2` in between, NO `agx_cdm_barrier` is emitted.
The prior `agx_cdm_launch` is followed immediately by the next
`agx_cdm_launch`.

## Why it bit-cleans on short gates but fails on long ones

The dep-tracked SKIP relies on a single claim: **"Compute launches
before the barrier were already flushed by the previous launch's
gating."** (comment in `hk_cmd_buffer.c`).

That claim holds in the simple case (single CS, all launches write
through the same buffer set, app orders everything via
`vkCmdPipelineBarrier2`). It does NOT hold when:

1. **Cross-CS launches**: a launch in CS-A writes buffer X; a launch
   in CS-B reads buffer X without an intervening
   `vkCmdPipelineBarrier2` that mentions buffer X. CS-B's
   `cdm_barrier_pending` is independent of CS-A's; the barrier skip
   on CS-B lets it read stale buffer X.

2. **USC / texture cache state**: the GPU has a separate texture
   sampler / USC (Unified Shader Cache) that the
   `hk_cdm_cache_flush` (removed in the SKIP) used to invalidate.
   `agx_cdm_barrier` alone does NOT flush the texture cache. If the
   previous launch wrote texture data and the current launch reads
   it as a texture, the SKIP serves stale texture bytes. The
   `d3fa18e` commit note flagged this category — USC/texture state
   visibility is the open suspect.

3. **Sparse / indirect-draw launches** (CDP, indirect dispatch): the
   indirect buffer is GPU-resident; a previous launch may have
   written it; the barrier skip lets the next launch read
   uninitialized GPU memory.

4. **First launch after a stream split / merge_control_streams**: the
   barrier is gated on `cmd->state.cs.cdm_barrier_pending` which lives
   on the command buffer, not the CS. If a CS was split (the comment
   in `hk_cmd_buffer.h` notes "Lives on the command buffer, not the
   hk_cs, so it survives CS splits and merge_control_streams" — that
   statement may not be true; the SKIP likely misses barriers that
   should be emitted between the split halves).

## Why prompt 8 token 5 is the fingerprint

Qwen3.8 decode runs prompt 8 (one of 100 in the contract corpus) and
the stale read manifests at the 6th generated token. Likely cause: by
token 5 the running cache state has consumed enough prior
launches that one of them missed a needed USC flush on a texture
write from a much-earlier launch. The first ~5 tokens don't trip
the bug because the cache is still cold; once a stale texture
write is in the USC, every subsequent texture read sees it until the
next explicit flush.

## Instrumentation prerequisite (the open work)

To qualify the SKIP without re-treading the dead end, the next
agent needs to instrument WHICH unordered pair produces the stale
read first. Three options, ranked by invasiveness:

**Option 1 (least invasive, recommended)**: extend AGX_SUBMIT_TRACE
(`f2cc0d3a`) to also log `agx_cdm_barrier` calls with their
buffer set diffs. On the FAILED gate (prompt 8 token 5), capture
the sequence of barrier calls + buffer sets across the run; identify
which buffer (texture vs buffer) is read stale. Then either:
  - if it's a texture: re-introduce `hk_cdm_cache_flush` for the
    texture path only (gated on a `texture_stale` flag derived
    from the launch's input buffer types).
  - if it's a cross-CS read: re-introduce the barrier between CS
    splits, gated on the CS split detection.
  - if it's an indirect-dispatch read: re-introduce the barrier for
    indirect dispatch only.

**Option 2 (medium)**: bisect the barrier skip — try a SKIP that
emits the barrier only every Nth launch, sweep N from 1 to large;
find the largest N that still passes the 10-pass gate. Per-batch
launch budget already documented in the t6001 launch-sink receipt
(231 us / firmware boundary per the m1max measurement; per-launch
CDM barrier ~4.6-5.1 µs; not all barriers are equal).

**Option 3 (most invasive)**: full data-dependency tracking on the
buffer sets: at every launch, compare the launch's input buffer
set against the prior launch's output buffer set (read-after-write
detection). Only skip the barrier when the two sets are disjoint
(safe to SKIP) or when they don't overlap the texture/usc domain.
This is what "dependency-tracked" should have meant in the first
place; the current SKIP uses `vkCmdPipelineBarrier2` as a
proxy for "did the app declare a memory dep?", which under-counts
the cases above.

## Files / pointers for whoever picks this up

- Source: `cdm-dep-barrier` branch in `~/src/mesa-1` on jw16mbp1-linux;
  5 files local diff (`hk_cmd_buffer.{c,h}`, `hk_cmd_dispatch.c`,
  `hk_device.{c,h}`); the commit message and base are
  `f2cc0d3a` (AGX_SUBMIT_TRACE).
- Receipt: `receipts/2026-09-24-t6001-launch-sink/receipt.md`
  (sibling lane, jw16 t6001 launch-sink).
- Cited fingerprint: prompt 8 from token 5; the mlx-omarchy
  decoder that uses this Mesa ICD is the regression detector (its
  generated-IDs diverge vs ctl at that point).

## My status: NOT pursuing

I will not touch this branch (per Jw16GpuSubmit's correction —
qualifying the existing diff would re-tread the dead end). I am
documenting the prerequisite so the next agent doesn't waste time
re-discovering it. Per the parity-no-early-quiescence rule,
end turns with work in flight — my forward motion right now is
the Mesa vkCreateInstance VK_ERROR_UNKNOWN fix on
`agent/jwm1-vkcreate-buildid-override` (delivered) and this
analysis (in progress).
