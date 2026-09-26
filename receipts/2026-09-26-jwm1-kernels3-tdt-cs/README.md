# jwm1 TDT single-CS lever: investigated, void — production TDT already records one CS per chunk

Owner: Jwm1Kernels3, 2026-09-26. Task: "change the runtime so the TDT slot's
fold/fold_proj/control dispatches record into one command stream ... Merge and
install if it wins."

**Verdict: the change does not exist to make — the production chain already
satisfies it. Nothing was merged or installed (nothing won, nothing changed).**
The investigation replaced the assumed win with a quantified account of where
the TDT stage time actually goes. Findings landed on mlx-omarchy main
`2d3a77b99` (extended chain-dep-bench + RESULTS addendum).

## Evidence

### 1. CS/submit structure (raw/tdt-trace.err)

`MLX_OMARCHY_TRACE_DISPATCH=1` over the full golden `run_tdt_chain` fixture
(192 slots, slots_per_chunk=64), gate venv:

- 1152 `[rtmod] DISPATCH` lines = 6 per slot x 192 slots
- **3 `[rtmod] SUBMIT-ENTER` = one command stream per 64-slot chunk**
- 4 COMMIT-NOOP, 1 JOIN (final host readback)

The slot's six dispatches (chains x2, fold, fold_proj, window, control)
already record into ONE command buffer with in-CS barrier dependencies. The
estimated -250 us/slot assumed cross-CS timeline-semaphore hops that do not
exist.

### 2. Host vs GPU split (raw/tdt-split.py, raw/tdt-split-out.json)

Python lazy-graph build (enqueue) vs `mx.eval` (C++ record + submit + GPU +
readback): enqueue 3.4-9.3 ms total (18-48 us/slot) vs eval 627-681 us/slot
warm. **GPU-bound**, not host-record-bound.

### 3. In-CS cost isolation (raw/cdb-extended-20260926.jsonl)

Extended `tools/chain-dep-bench` (mlx-omarchy `2d3a77b99`), one GPU window,
31 reps/case: timestamp writes ~27 us each (6 writes add ~160 us GPU span);
grid-20 (640-thread) dependent dispatches ~25 us each of span; RAW vs WAW,
distinct pipelines, fresh descriptor sets: no difference (74.3-75.3 us span
across all variants). CS-boundary semaphore hops remain ~128 us/hop.

## Where the TDT stage time goes (per slot, unprofiled warm)

~630-690 us GPU = chains x2 + window bandwidth work (~440-480 us, already at
the macOS-implied ~79% of nominal BW) + 5 dependent hops (~25 us each, ~125
us, in-CS barrier resolution = honeykrisp) + grid-1 trio real work (~35 us;
trio fusion falsified 4.7x slower, `agent/jwm1-parity10-tdt`).

Runtime-owned addressable: **none**. Hop costs are mesa-owned
(joshuaswarren/mesa-1 honeykrisp): both the in-CS ~25 us dependent-dispatch
floor and the ~128 us CS-boundary hop. The mesa lane should take them.

## Cross-receipts

- Corrects the fix-lever list in
  `receipts/2026-09-25-jwm1-kernels2-clean/ADDENDUM-chain-dep.md`;
  Jwm1Kernels2 accepted and appended the correction (ane-linux-experiments
  main `b0016b54`).
- T6001 corroboration: Jw16Levers8 measured the same structure on jw16
  (fused TDT 173-200 ms stage wall, 12 whole-pipeline SUBMITs; receipt
  cb3ccf79) — CS-layout is a non-lever on T6001 too.
- Bench tool + RESULTS addendum: mlx-omarchy main `2d3a77b99`
  (branch `agent/jwm1-tdt-turnaround`, fast-forward from `acafbe4ee`).

## Environment at measurement (verified live 2026-09-26)

- jwm1 gate venv `/var/tmp/jwm1-parity3-venv`: mlx-omarchy wheel
  `0.32.3.dev202609252026+7c0bd851` (the harness's pinned baseline; no wheel
  changed by this work)
- omarchy-ane module: **5ecff86** (modinfo version), unchanged
- system mesa: `jwm1-barrier-ab` @ `160b7af8aeb` (another lane's installed
  A/B state; all same-window comparisons above are internally consistent)
- M2 catcher: untouched, m2proxy pids alive (666, 887, 55605); no reboot;
  GPU lock `flock /tmp/m1-gpu.lock` held for every window
- Pins: no runtime or wheel change was made, so the pinned digests
  (486872c410629f1d / bc519c03c4ef5fd1 / dbf704971617fdfc) are untouched by
  construction; last receipts holding them: bf14ba86/d4a8161d, and 226d12da
  reports digest 486872c4...aa5c bit-exact on the v0.7.4 line.
