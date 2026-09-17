# A0 cached read-back, residency, and GPU-interference levers on jw16 (2026-09-17)

Verdict: **A0 MEASURED AND GATED — land the two-line modparam change.**
Residency re-priced (its headline saving was read-path, not spawn). GPU
interference re-attributed (not concurrency; mostly memory-system, partially
killed by lever 1). Pins held bit-for-bit on the certified green
configuration. Host handed back clean: module `96d5a88`, `llm-inference`
active, lock inode 12. jwm1 untouched; `63c1d3cf` never merged, not touched.

## 0. Coherency determination (before any timing, per Main's guard)

The ANE's DART path on T6001 is **I/O-coherent with the CPU caches**, and the
correct fix is cached-everywhere, not explicit maintenance:

1. **Device side**: the ANE sits behind `iommu@285800000`, compatible
   `apple,t6000-dart` (live DT `/proc/device-tree/soc/ane@284000000/iommus`
   → phandle 0x10b). Same driver class every DMA-API device on this SoC uses;
   on arm64/Asahi those devices are dma-coherent, so `dma-iommu` programs
   their descriptors with `IOMMU_CACHE` — cacheable + inner-shareable
   (`io-pgtable-arm`: `IOMMU_CACHE` → `ATTRINDX=Cacheable`, `SH_IS`).
2. **Userspace precedent**: eiln's pre-GEM driver (`4566c89^`) mapped BOs
   cacheable (`alloc_page` + default `drm_gem_mmap` prot) while DMAing them
   through the same `iommu_map(IOMMU_READ|IOMMU_WRITE)` path — months of
   correct execution on M1. `pgprot_writecombine` arrived in the GEM-shmem
   rewrite (`4566c89`, "use gem shmem backing") with no stated correctness
   rationale; before it, the CPU→device direction already ran cached.
3. **Empirical confirmation** (this session): the paired change
   (`IOMMU_CACHE` descriptors + cacheable CPU vmas) passes byte-identity in
   both directions with alternating input patterns and 16-rep buffer reuse
   (below). If the DART were non-coherent, pattern-alternating reuse would
   diverge; it does not, across 6 programs and 2 boots of runs.

The variant therefore ships as a **runtime modparam** (`map_mode`, default 0
= today's WC+NC behaviour; bit0 = `IOMMU_CACHE`, bit1 = cacheable CPU vma),
built from a clean `96d5a88` worktree → modinfo version **`96d5a88-dirty`**,
sha256 `2c999baf…`. A/B is by `echo N >
/sys/module/ane/parameters/map_mode`, not rebuild.

## 1. Byte-identity matrix (probe `ane-probe2 verify2`, new command)

Two alternating input patterns per rep: rep N fills pattern N&1. Stale
CPU→device lines surface as the device computing the previous pattern's
output; stale device→CPU lines surface as the host reading the previous rep's
bytes. Both break the per-pattern reference hash. Programs: 64-el add/mul
control (ctrl0/ctrl1) + island-attn-a-kt p0 ("a0", the 4.62 MB scores tile)
and p1 ("a1") + island-select-8head-scratch417 ("sel") + island-pv ("pv"),
all from `bundles-rx`/first-exec stacks.

- `orig` (WC+NC) vs `var0` (variant, mode 0): **6/6 [identical]** — the
  module swap is inert at default.
- `orig` vs `mode1` (WC CPU + `IOMMU_CACHE` descriptors): **2/2 [identical]**
  (ctrl0, a0).
- `orig` vs `mode3` (cached + `IOMMU_CACHE`): **6/6 [identical]** at
  reps=16, all `STABLE (diverged=0)`.
- `mode2` (cached CPU + NC descriptors) deliberately **not run**: it is the
  known-wrong attribution cell with real wedge risk (stale TD fetch → `-110`
  → T6001 failsafe), and after mode3 passed everywhere it had no
  decision value left.
- Wedge counter (`tm completion failed|preserving resources|tm execution
  failed`) = 0 before, during, and after every mode.

## 2. Lever 1 — A0 uncached read-back: MEASURED, pins held

Root cause: `ane_drv.c:512` mapped every BO vma `pgprot_writecombine`
(reads bypass CPU caches, ≈200 MB/s DRAM path) and `ane_drv.c:80` mapped the
DART descriptors without `IOMMU_CACHE` (non-cacheable + outer-shareable).
Probe read-back, per-call medians (20 reps, same boot, isolated):

| program | out tile | read WC+NC | read mode3 | × |
| --- | ---: | ---: | ---: | ---: |
| a0 attn-a-kt p0 (scores) | 4.62 MB | 23 274 µs | **133 µs** | 175× |
| a1 attn-a-kt p1 | 2.31 MB | 11 673 µs | **72 µs** | 163× |
| sel select-8head | 2.31 MB | 11 638 µs | **90 µs** | 130× |
| pv island-pv | 770 KB | 3 933 µs | **42 µs** | 94× |

Device exec walls unchanged (a0 1181→1184 µs, sel 1045→1048, pv 612→620:
compute untouched); submit floor unchanged (control ≈38–41 µs, mode3 sanity
run).

### Production, certified green configuration (pins gate)

`fused_e2e`, PLACED=ABC, resident-batch, certified runner bytes
(`jw16-r4/vulkan_encoder_r4.py`, bundles-sf, strict-fill libane), gate.py:

| gate | pins-orig (WC+NC) | pins-mode3 (cached) |
| --- | --- | --- |
| status / emissions / prefix | match / 104 / 104 | match / 104 / 104 |
| transcript | **db501a8c** | **db501a8c** |
| encoder_hidden | **38c73261** | **38c73261** |
| bounds pass / rel_l2 | true / 0.02304396964609623 | true / **0.02304396964609623** |
| mel bit-exact / cpu_tensor_events / timeouts | true / 0 / 0 | true / 0 / 0 |
| **ane_exec_ms** | **2575.2** | **2364.8** |
| encoder_ane wall_ms | 4985.7 | 4827.8 |

**A0 lever: −210.4 ms ane_exec (−8.2%), −157.9 ms encoder wall, every pin
byte-identical (rel_l2 equal to all 17 digits).** The timing-only harness
(the E2E296-era runner, below) shows the same lever at −189 ms resident and
−1278 ms launch, i.e. the resident-batch figure is the conservative one.

## 3. Lever 3 — residency re-priced: the 2×2 (timing-only harness, same session)

`ANE_ISLAND_MODE=launch` vs `resident-batch`, `ANE_ISLAND_MODE` × mapping
mode, E2E296-era runner (fold-regression numeric signature — **timing-only
certification**, status `diverged` on all four legs by construction). All
four legs produced **identical** `encoder_hidden.npy` (dadd090d…) and
`token_ids.json` (6908093c…) hashes: submission mode × mapping mode moved no
bytes.

| leg | subs | ane_exec ms | encoder wall ms |
| --- | ---: | ---: | ---: |
| base-resident (WC+NC) | 1 | 2533.9 | 5020.9 |
| base-launch (WC+NC) | 72 | 3907.9 | 7371.1 |
| cached-resident (mode3) | 1 | 2344.6 | 4843.2 |
| cached-launch (mode3) | 72 | 2630.4 | 5994.7 |

Reading:
- **Residency's headline saving was read-path all along.** Launch vs
  resident on the WC stack: 3907.9 − 2533.9 = **1374 ms**; on the cached
  stack: 2630.4 − 2344.6 = **285.8 ms**. ≈1.09 s of the launch penalty was
  the uncached mapping being paid per fresh process (fresh BOs, single
  cold read each), not spawn/load/file-I/O. What residency is *really*
  worth after lever 1 is ≈286 ms — matching the code-level prediction
  (spawn + bundle load + ~12 MB/layer file I/O).
- Correction to the gap-attribution framing (Main-requested, explicit):
  resident-batch avoids **none** of the 30 % read-staging or 18 % IPC
  shares — the worker still memcpys through the BO and the runner still
  packs/unpacks over the pipe in both modes. Those shares die via lever 1
  (cached read) and future fused programs, not via residency.
- Per-island 24-round sums, resident mode: A 1230.5→1067.7 (−162.8),
  B 897.3→884.0 (−13.3), C 406.0→392.8 (−13.2); launch mode: A −874.1,
  B −296.3, C −107.2. The scores tile dominates, as the isolation predicted.
- **Cross-island value residency is priced as BLOCKED without new
  programs**: every ANE→ANE edge inside a layer is interrupted by a GPU op
  (A's two outputs → GPU add → B's `matrix_bd_5`; B out → GPU softmax → C's
  `probs`; C out → GPU o-proj → next layer). The compiler's channel
  contracts bind B/C inputs as host-staged surfaces, so worker-side chaining
  would need fused/minted programs (FFN-chain lane). The constant-input skip
  (B's `ninf_rt` ≈2.25 MB + broadcast `cond` are bit-identical every round
  and their BOs persist between resident rounds) is the one legal worker-side
  extension: bounded above by B's write-in share, ≈3 ms/layer ≈ **70–80
  ms/pass**, unmeasured here — not worth a worker protocol change on its
  own; fold it into the fused-program lane.
- WheelR4V062's independent anchor agrees: o-proj placement costs
  +727.2 ms wall / +275.2 exec on jw16 resident-batch (a loss) — placement
  overheads, not submit counts, are what the split architecture pays.

## 4. Lever 2 — GPU interference: re-attributed; phase-separation is a no-op here

- **Not concurrency.** The runner `mx.eval`s every island input before the
  submit; the eval transitively drains the sequential encoder graph, so ANE
  rounds already run on an idle stream. "Batch multiple layers' submits
  while the GPU is idle" is already the de-facto shape, and true
  cross-layer batching violates the dependency graph (layer *i* FFN feeds
  layer *i+1* attention).
- **Partly cache-state on the WC read path** — that share died with lever 1
  (measured above).
- **Residual, measured**: clean resident rounds (isolation, GPU-idle loop)
  summed ≈1375 ms/pass vs pins-mode3 ane_exec 2364.8 ms → **≈990 ms/pass of
  production inflation remains after the read path is cached** (was
  ≈1254 ms). Since exec walls are mapping-invariant and staging reads are
  cached, the residual is DMA-vs-GPU memory-system contention and host
  scheduling during staging/exec — the split architecture's own cost.
  **The fix for the residual is the fused-program lane (FFN chain, priced
  ≈1.7–2.0 s), not scheduling.** No scheduling/DVFS knob was tested: with
  concurrency ruled out and the cache-state share measured, the remaining
  candidates are not addressable from the runner.

## 5. What each lever does NOT cover

- A0 cached read: does not touch the ≈18 % IPC share (pack/unpack/pipe), the
  GPU-busy time outside islands, or the residual ≈990 ms contention; needs
  the omarchy-ane KMD change deployed by the loader unit (modparam default
  stays 0 until flipped).
- Residency: ≈286 ms is the whole remaining prize; cross-island value
  residency needs new programs; constant-skip ≈70–80 ms is unmeasured.
- Interference: no concurrency knob exists; residual ≈990 ms belongs to the
  fused-program lane.
- All timing-only harness numbers (§3, §4) inherit the E2E296 runner's
  `rel_l2 2.82`-class fold signature; only §2's pins-gated pair certifies
  numerics, and it does so bit-for-bit.

## 6. Artifacts and host state

- KMD variant: jw16 `~/src/ane-cachedread-wt` (worktree at `96d5a88`, uncommitted
  31+/7− diff = the modparam), `ane/ane.ko` sha256 `2c999baf…`, version
  `96d5a88-dirty`. Local copy: `ane-linux-experiments/.local/ane-submit-probe/`
  (`run-pinwindow.sh`, `run-pins-e2e.sh`, `run-cachedread-matrix.sh`,
  `run-roundtrip-e2e.sh`, `run-window.sh`, `ane-probe2.c`).
- Reports: jw16 `/var/tmp/ane-submit-probe/pins-e2e/{pins-orig,pins-mode3}/`,
  `.../roundtrip-e2e/{base,cached}-{resident,launch}/`, `cachedread-out/`
  (`all-hashes.txt`, `hashes.*`, `decomp.{orig,mode3}.txt`), `window.log`,
  `pinwindow.log`.
- Hand-back: module `/sys/module/ane/version` = `96d5a88` (original
  `/usr/local/lib/omarchy-ane/ane.ko` restored by the trap), map_mode param
  gone, `llm-inference` active, `/tmp/m1-gpu.lock` inode 12 held by its own
  llama-server, 0 wedge lines. Boot unchanged (`a4946…` lineage, no reboot
  consumed). WheelR4V062's and AneEntryPointBisect's staging untouched;
  select-scratch417/bundles-sf respected.
- Session negatives (cost, not device): double-`flock` self-deadlock (inner
  + wrapper) burned one window; `verify2`'s first matrix produced a vacuous
  pass (hash-presence gate added); `systemctl is-active` exit-3 broke an
  `&&` launch chain; the driver's `sys.path.insert(0, --pkg)` shadowed an
  incomplete `coreml` package until `--pkg` pointed at the complete one.
