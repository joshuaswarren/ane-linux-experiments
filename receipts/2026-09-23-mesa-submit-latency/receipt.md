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

## 4. Measurements (jwm1, 2026-09-23, three same-window interleaved batteries)

Raw: `raw/window-3batteries.log` (514 lines, all arms + all golden passes),
`raw/samples.cand-p300.{rtsleep,rtpoll}` (2000 samples each, ns).
Bench arms run back-to-back under one `/tmp/m1-gpu.lock` hold; golden
passes interleaved base/cand within each battery. All percentiles below
are warm medians of the blocking-wait round trip (`rtsleep` = submit +
blocking timeline wait, n=2000).

### Microbenchmark breakdown (base = 7faf04c)

| mode | base | cand knob off | cand poll 300 µs |
| --- | ---: | ---: | ---: |
| rtsleep mean | 161.5–173.2 µs | 166.5–170.7 µs | **132.6–134.4 µs (−20%)** |
| rtpoll mean | 146.8–153.1 µs | 139.9 µs | 129.3–131.1 µs |
| noopsleep mean | 0.49 µs | 0.62 µs | 0.66 µs |
| emptyrt mean | 1.26–1.33 µs | 1.29–1.35 µs | 1.32–1.36 µs |
| submitonly | 19.6–20.8 µs/submit | 20.0 µs | 20.5–20.8 µs |
| nanowake(200 µs) | 255 µs p50 | 255 µs | 255 µs |

- A/A sanity: knob-off candidate ≡ base (166.5 vs 170.1 µs, inside noise).
- The blocking wait on an **already-signaled** point costs ~0.5 µs — the
  ioctl floor is negligible; the ~170 µs rtsleep is firmware pickup +
  kernel completion publish + host wake. Busy-polling recovers ~35 µs of
  host wake per round trip (rtsleep − rtpoll).
- Per-submit userland cost is ~20 µs; sync overhead per TDT submission is
  ~170 µs — **~5% of the 3.3 ms golden per-submission wall**, not the
  1.3–1.5 ms the derived number suggested.

### Parakeet golden (warm medians; every run status=match, 104 emissions,
### transcript sha db501a8c… bit-exact in all 16 runs across 3 batteries)

| battery | build identity | base TDT | cand TDT | Δ |
| --- | --- | ---: | ---: | ---: |
| A | pre-backoff .so (fresh cache for cand) | 495.5 ms | 439.9 ms | −55.6 ms |
| B | **same .so both arms (A/B noise floor)** | 475.0 ms | 458.7 ms | **−16.3 ms** |
| C | backoff .so | 484.2 ms | 485.5 ms | +1.3 ms |

Battery B is a build-identical A/B: **the same-window noise floor at
n=6 warm runs/arm is ~±16 ms**. The candidate's true effect predicted
from the bench (35 µs × 146 submissions ≈ 5 ms) is below that floor and
is not resolvable in the golden. The −55.6 ms in battery A was noise.

## 5. Verdict

**No install.** The mechanism works (rtsleep −20%, A/A clean) but the
end-to-end win (~5 ms on a ~480 ms TDT bucket, ~1% of total pipeline)
is below the measured noise floor; the acceptance bar ("install only on
a win") is not met. System default remains
`/usr/local/lib/libvulkan_asahi.so.7faf04c` (sha 09e3527d), untouched
throughout; candidate staged only at
`/var/tmp/mesa-submit-lat/libvulkan_asahi.so.cand-09bc5d20` (+ `cand.icd.json`).

Preserved for later use: `hk/submit-latency` (mesa-1, commits
c0da9a1896c, 229e872ba07 + fixes) is a zero-default opt-in
(`HK_SUBMIT_POLL_US=<µs>`) — any launcher can enable it without a wheel
change if a future loop shape (e.g. device-chained decode) makes the
wake path dominant.

Notes:
- The "19.6 s first-ever cand run" in batteries A/C is a **build-identity
  artifact**, not the poll knob: tarball builds lack git metadata
  (driver version string loses the `git-…` suffix), so the mel frontend's
  per-driver caches miss and ~17.7 s of one-time kernel translation is
  paid once per build identity. It reproduced identically for cache-cold
  builds regardless of knob state; battery C's cold run showed it with
  the backoff active. Install candidates must be built from a git
  checkout for stable identity.
- The miss backoff (229e872ba07) is kept as defense-in-depth: poll
  budgets would otherwise burn on long waits (shader-compile sync
  storms); with backoff the candidate's bench numbers are unchanged
  (132.6 µs) while long-wait phases fall back to sleeping after one
  budget.

Commits: mesa-1 `hk/submit-latency` = 7faf04c + c0da9a1896c + 229e872ba07
(+ `asahi/hk: backoff state is plain 8-aligned uint64…`). This repo:
`agent/mesa-submit-latency` = tool (764ee01), runbook (ec34d3e, 72bf154,
f042cf4 + fixes), receipt (43d9701 + this).
