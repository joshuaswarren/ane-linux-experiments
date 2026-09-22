# GPU weight-stream latency: TLB cause proven, driver change landed, kernel change staged

2026-09-22 · GpuTlbLatency · hosts jw16 (M1 Max, 7.1.6-1-1-ARCH), jwm1 (M1, 7.1.13-3-2-ARCH)

## Tool

`tlb_bench` (this dir): pointer-chase microbench, Honeykrisp compute.
Each invocation walks a 256 MB ring doing 512 serialized 16-byte steps;
`words[idx+3]` holds the next index, so every step depends on the previous
load and time/step is per-load latency including page-table walks. Access
shapes are baked into the chase data. `--memtype local|host` selects the
Vulkan memory type. 7 reps, median, flock /tmp/m1-gpu.lock, honeykrisp
tip 7faf04c065c (`/var/tmp/mesa-divverdict-jw16/tip.so` on jw16,
`/var/tmp/mesa-e167-jwm1/tip.so` on jwm1).

Modes: `dense` = consecutive 16 B steps (page change every 1024 steps);
`stride16k` = one step per ~16 KiB page (4097-step stride, coprime with
the ring); `stride2m` = one step per ~2 MiB; `hot16k` = every step inside
one 16 KiB page. `_spread` = per-lane start offsets spaced across the
whole 256 MB ring (the GEMV regime: concurrent lane streams spread over
the weight stream) vs the default tight start (lanes adjacent).

## Results (ns per serialized step, median)

### jw16, M1 Max, device-local

| mode | 1024 lanes | 4096 | 16384 | 65536 |
|---|---|---|---|---|
| dense | 1340 | 1107 | 1665 | 5026 |
| stride16k | 855 | 1012 | 1096 | 4816 |
| stride2m | 971 | 902 | 1283 | 4391 |
| hot16k | 680 | 657 | 681 | 4214 |
| dense_spread | 746 | 904 | 6650 | 55689 |
| stride16k_spread | 1669 | 1933 | 8963 | 48164 |
| stride2m_spread | 1624 | 1760 | 14900 | 71054 |
| hot16k_spread | 1287 | 1617 | 13152 | 78702 |

Host-visible memory type: identical within noise (full logs above and in
`jw16-tlb-bench-newdriver.log`). Same conclusion on jwm1
(`jwm1-tlb-bench.log`): dense_spread at 16384 lanes = 32700 ns/step
(vs 4134 tight), local == host.

## Findings

1. **Page-crossing penalty is real and large.** One step per new 16 KiB
   page costs +170-350 ns over a page-resident step (stride16k vs hot16k,
   low lane counts).
2. **TLB thrash dominates at spread geometry.** When concurrent lanes
   cover the whole buffer, latency per step explodes: 1.7 us -> 6.6 us
   (16k lanes, M1 Max) and 4.1 us -> 32.7 us (M1). Aggregate achieved
   bandwidth collapses to ~40-60 GB/s regardless of lane count, versus a
   ~310 GB/s copy roof — matching DecodeM1MaxOccupancy's decode-geometry
   ceiling. The per-16 KiB-page working set (256 MB / 16 KiB = 16384
   pages) exceeds what the GPU TLB holds; every access walks.
3. **Not a memory-type effect.** Device-local vs host-visible Vulkan
   memory types are equal within noise on both hosts — there is no
   cacheability/attribute lever exposed through the Vulkan memory model.
   Any attribute fix would have to be UAT PTE MEMATTR-level, and the
   driver already uses cached attributes for these mappings.
4. **A 6 MB weight stream = 384 16 KiB PTEs.** 2 MiB UAT L1 block
   descriptors would cut that to 3, removing the walk pressure entirely.

## Landed (driver, joshuaswarren/mesa-1, branch `agent/gpu-tlb-2m-align`, commit `41c269d4b3e`)

`agx_bo_create`: BOs >= 2 MiB get 2 MiB VA alignment, so a kernel with
block mapping can use L1 block descriptors for large BOs with no further
driver change. Built (`meson setup -Dvulkan-drivers=asahi`, 646/646),
smoked: `q4-bw-bench --quick` bit-exact (21/21 eq checks, 0 mismatches),
GEMV med_ns old vs new — qkv 14250->14584, o 13834->14666,
gate_up 31791->32708, down 32333->32417 — i.e. unchanged within run
noise (gate_up: 155 vs 151 GB/s), as expected for an alignment-only
change. Logs: `gemv-old.txt`, `gemv-new.txt`.

## Staged, needs reboot window (kernel)

`staged-uat-block-pte.patch` — 2 MiB block mapping for
`drivers/gpu/drm/asahi/pgtable.rs` `map_pages` (compile-untested; no
kernel source tree or reboot available this session). Before it can
help, two prerequisites must also land:

1. Contiguous physical backing: BOs are shmem-backed (`gem.rs`
   shmem::Object, sg_vec paths in mmu.rs); a 2 MiB block PTE needs a
   physically contiguous, 2 MiB-aligned range. Requires an order-7/CMA
   style allocation path for large BOs.
2. `unmap_pages` / `reprot_pages` / coredump walkers must recognize
   block PTEs, and `mmu.rs` step_map must pass block-aligned runs.

Reboot (both hosts run stock asahi kernels) is required to test.
**Asking Main** for a reboot window decision; jwm1 rebooted today anyway
(dwc3 wedge) so a kernel swap could ride a future window.

## Honesty notes

- `tlb_bench` timestamps were abandoned for wall-clock (honeykrisp
  timestamp queries returned equal values in some paths); ms_med is
  wall around submit+wait, GPU-bound (tight-mode dispatches ~0.3-2.6 ms).
- The kernel patch has NOT been compiled or run. It is a design-complete
  draft, not a landed change.
