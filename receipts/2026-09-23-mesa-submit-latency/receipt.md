# Honeykrisp submit-path latency: profile, breakdown, candidate (2026-09-23)

Lane: MesaSubmit (submit+wait round trip behind the Parakeet TDT floor).
mesa-1 branch `hk/submit-latency` (base: honeykrisp install rev 7faf04c).
Tool: `tools/vk-submit-lat/` (single C file, embedded SPIR-V, one compute
queue + one timeline semaphore — the TDT host-loop pattern).

## 1. Source profile of the per-submission path

`vkQueueSubmit` → `vk_queue_submit` (common, `src/vulkan/runtime/vk_queue.c`)
→ `hk_queue_submit` → `queue_submit` (`src/asahi/vulkan/hk_queue.c`).

Per TDT-style submit (one CS, one timeline signal, no waits):

- Common layer: wait compaction + timeline point unwrap. **No ioctls.**
- hk: `alloca` sync array (wait + signals + 1 queue-progress signal —
  every submit signals `queue->drm.syncobj` at `++timeline_value`, so a
  TDT submit carries **2 out-syncs**: the app timeline + queue progress).
- hk: `util_dynarray` payload (one malloc + free per submit) with
  `drm_asahi_cmd_header` + `drm_asahi_cmd_compute`.
- `max_commands_per_submit()` returns **1** (BATCH perf path: 64, disabled
  over a CTS flake suspicion with lossless compression) — the TDT submit
  is exactly one command anyway, so the looped path is dead for TDT.
- **1× `ioctl(DRM_IOCTL_ASAHI_SUBMIT)`** (`agx_submit`, `drmIoctl`
  EINTR-retrying wrapper). No per-submit allocations beyond the dynarray.

Host wait (greedy TDT must read back the argmax decision each step, so
every step ends in a host sync):

- hk registers **only** `vk_drm_syncobj` (`hk_physical_device.c:1343`),
  which is timeline-capable: `vkWaitSemaphores` →
  `vk_drm_syncobj_wait_many` → **1× `ioctl(DRM_IOCTL_SYNCOBJ_TIMELINE_WAIT)`**
  with `WAIT_ALL|WAIT_FOR_SUBMIT`, absolute deadline — a **sleeping wait**
  in the kernel. The wake comes from the asahi kernel driver signaling the
  syncobj point after firmware completion notice.
- No threaded submit queue (`vk_queue_init` default = immediate mode) —
  no extra context switch per submit.
- Empty submits (sync-only) take `queue_submit_empty`: 2 `syncobj
  transfer` ioctls per transfer — not on the TDT path (real CS per step).

**No userland-visible progress counter exists in the UAPI**
(`drm_asahi_queue_create` exposes queue_id only): the host cannot observe
job completion before the kernel publishes the syncobj signal. Therefore
the only userland levers on the round trip are (a) how the host waits
(sleep + wake vs poll) and (b) per-submit CPU cost (already µs-scale).

## 2. Breakdown method

`vk-submit-lat` decomposes on jwm1 (all arms interleaved under one lock):

| mode | measures |
| --- | --- |
| `noopsleep` | blocking wait on already-signaled point (ioctl floor) |
| `submitonly` | back-to-back submits, one final wait (throughput + backpressure) |
| `rtsleep` | submit + blocking wait — **the TDT pattern** |
| `rtpoll` | submit + busy-poll `vkWaitSemaphores(timeout=0)` — signal visibility without host sleep/wake |
| `rthybrid` | poll 300 µs then block — **app-level preview of the candidate** |
| `emptyrt` | empty submit + blocking wait (sync-only round trip) |
| `nanowake200us` | scheduler wake reference |

rtsleep − rtpoll ≈ host wake-up premium paid by the sleeping wait.
rtpoll floor = firmware pickup + kernel completion publish (not reachable
from userland).

## 3. Candidate

mesa-1 `hk/submit-latency` (commit c0da9a1896c): opt-in bounded poll
before blocking syncobj waits. `HK_SUBMIT_POLL_US=<µs>` (default 0 = off,
byte-identical single-call path) sets `vk_device.sync_wait_poll_us`;
`vk_drm_syncobj_wait_many` polls the same ioctl with timeout 0 within the
budget, then falls back to the original blocking call with the original
absolute deadline. ETIME → VK_TIMEOUT preserved; non-ETIME errors surface
immediately; WAIT_ANY/WAIT_ALL/WAIT_PENDING flags unchanged. Standalone
control-flow test (5 cases) in receipts-raw; full validation is the jwm1
build + golden.

## 4. Measurements (jwm1, window TBD)

[placeholder — filled after the measurement window]

## 5. Verdict

[placeholder]
