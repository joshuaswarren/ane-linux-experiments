# In-process ANE island submission, j16 and j1 (2026-09-21)

Branch: `agent/ane-inprocess-submit` (mlx-omarchy overlay worktree,
commits 098956f32, 9b86f8d73) + this receipt in ane-linux-experiments
(branch `agent/encoder-wall-decomp`, commit ee53fd6).

## Change

The worker's own submission code is linked into the harness process —
no worker child, no pipe IPC, no per-submit framing:

- `mlx/backend/omarchy/ane/ane_inproc.cpp` — C shim over the
  submission path. Links `worker_libane.cpp` + `bundle.cpp` +
  `manifest.cpp` (the worker's code: libane device via dlopen,
  `load_bundle` parse/validate, dispatch plan, `ane_pack_rows` /
  `ane_unpack_rows` tile layout — NOT a reimplementation from ane.h).
  `make_libane_device` comes from `worker_libane.cpp`. Each bundle's
  `manifest_index` is offset by the programs already claimed (same
  remap as `AneWorker::open`), because the three island bundles reuse
  manifest indexes and one device needs unique keys.
- `tools/coreml/ane_inproc.py` — ctypes client (`InProcessAne`).
- `tools/coreml/vulkan_encoder.py` — `AneIsland` gains
  `ANE_ISLAND_MODE=inprocess` (`ANE_INPROC_SHIM` env names the .so,
  default `libane_inproc.so` beside the runner). `resident-batch`
  (worker `--serve` child) remains the default and the fallback.

Build (j16, same pinned omarchy-ane 6fa243a headers as the worker):

```
g++ -O2 -fPIC -shared -DMLX_OMARCHY_ANE_DEVICE=1 \
  -I$B -I$JSON_INC -I$JSON_INC/nlohmann -I/var/tmp/ane-6fa-src/libane \
  ane_inproc.cpp $B/mlx/backend/omarchy/ane/worker_libane.cpp \
  $B/mlx/backend/omarchy/ane/bundle.cpp \
  $B/mlx/backend/omarchy/ane/manifest.cpp \
  -o libane_inproc.so -ldl
```

shim sha256: j16 `4548a7975b37a5cdf13ef18ecc2c088bd5f444c3e6a37604648700f2a4215f02`,
j1 `7232fa50e92a41075a863473264bb6a7352db913f9d07b7fa8406625d3c124a1`.

## Safety contract (preserved by other means in-process)

- The submit executes on one persistent C++ thread; the host thread's
  wait is bounded by the open batch's absolute deadline
  (`ANE_ISLAND_BATCH_DEADLINE_MS`, 120000) or a per-submit deadline
  (20000). The host thread is never blocked unbounded.
- The host quarantine file `/run/lock/mlx-omarchy-ane/quarantine`
  (non-empty = quarantined for this boot) is checked at open and
  before EVERY submit; a non-empty file adopts quarantine and refuses.
- On a deadline miss the device completion state is uncertain, exactly
  like a killed worker child: the shim writes the boot id into the
  quarantine file (best-effort; unprovisioned hosts keep the
  in-process quarantine), returns timeout, and refuses every later
  submit. No retry. A clean device failure quarantines the session
  the same way.
- The submit thread may still be inside the blocking ANE ioctl at
  timeout; a kernel ioctl cannot be killed safely, so the thread and
  its session are deliberately leaked at close (bounded by process
  lifetime), documented in the shim header.

## j16 (T6001) results — LANDED

Interleaved A/B (`ab-inproc-j16.sh`, 1 smoke + 1 warm + 6 meas per arm,
identity in `inproc-20260921T175342/identity.txt`, runner
`vulkan_encoder_inproc.py` both arms, mode via env):

| metric | A resident-batch (worker) | B inprocess | delta |
| --- | ---: | ---: | ---: |
| encoder_ane median (6 meas) | 2783.6 ms | **1908.5 ms** | **−875.1 ms (−31.4%)** |
| total pipeline median | 4142.1 ms | 3241.4 ms | −900.7 ms |
| island-attn-a-kt submit wall / pass | 799.1 ms | **202.9 ms** | −74.6% |
| island-pv submit wall / pass | 284.9 ms | **74.7 ms** | −73.8% |

Both arms all green: status match, 104/104 prefix, all three gold
hashes bit-exact (mel 5b54f4a9, hidden 38c73261, transcript db501a8c)
in all 14 runs. llama-server (port 8002) stopped before the measured
window and restored after, `/health` → `{"status":"ok"}` verified.

Baseline context: this session's resident-batch median (2783.6) is
itself below the morning's 3452-3487 — the inprocess win is measured
against a fresh interleaved baseline, so the comparison is fair.

## j1 (T8103) results — LANDED

e167 mesa built natively on j1 (recipe from GPUHardwareContinuation):
mesa-1 @ 2c3b45be219 ("Revert agx: handle flush-to-zero in precise fp32
division, log and sine" — confirmed driver-equivalent to the pre-rewrite
e1677564284 tree by diffing src/asahi against the j16 worktree: comment
text only), meson flags per recipe; extras needed on j1: meson from its
own git checkout (no pip), mako/markupsafe via PYTHONPATH, and
spirv-llvm-translator installed (passwordless sudo) to provide
LLVMSPIRVLib. Artifact durably at /var/tmp/mesa-e167-j1/
(libvulkan_asahi.so + icd.json), used via
VK_DRIVER_FILES=/var/tmp/mesa-e167-j1/icd.json. Stock mesa 26.2.3
segfault reconfirmed (rc=139 at ~8 GPU submits) before the switch.

Interleaved A/B (`ab-inproc-j1.sh`, 1 smoke + 1 warm + 6 meas per arm,
identity in inproc-20260921T181818/identity.txt):

| metric | A resident-batch (worker) | B inprocess | delta |
| --- | ---: | ---: | ---: |
| encoder_ane median (6 meas) | 5216.0 ms | **3776.4 ms** | **−1439.6 ms (−27.6%)** |
| total pipeline median | 6561.4 ms | 5136.7 ms | −1424.7 ms |
| island-attn-a-kt submit wall / pass | 1257.5 ms | **409.6 ms** | −67.4% |
| island-pv submit wall / pass | 422.3 ms | **124.8 ms** | −70.5% |

Both arms all green: status match, 104/104 prefix, all three gold
hashes bit-exact in every run.

## Follow-on cut (Main request): profile + resident tiles

j16 inprocess profile (inproc-20260921T181921, smoke + 3 meas, all
gold-bit-exact; meas encoder_ane median 1944.2 ms — consistent with the
battery). Per-pass device-phase split inside the submit wall:

| island | submit wall | send | exec | read | shim overhead |
| --- | ---: | ---: | ---: | ---: | ---: |
| island-attn-a-kt (24 submits) | 207.2 ms | 24.0 | 47.0 | 44.9 | ~91 ms |
| island-pv (24 submits) | 74.7 ms | 18.9 | 15.2 | 4.5 | ~36 ms |

The remaining wall is ~55% device phases (pack+ioctl+unpack) and ~45%
shim-side allocation/copy. Landed (commit 1d7783929, NOT yet
runtime-benchmarked): (a) resident tile surfaces per
(program, channel, direction) in the libane device — zeroed once at
first use, reused across submits; safe because ane_pack_rows /
ane_unpack_rows never write the inter-row/inter-plane padding, so the
first-use zeroing stays valid; (b) per-submit send/exec/read timing
exposed through the shim (TimingDevice + ane_inproc_timings) and
recorded as dev_send_ns/dev_exec_ns/dev_read_ns in the runner log.
Next (not started): zero-copy readback into the caller's MLX buffer
(unpack directly into the preallocated output buffer instead of a shim
Buffer + memcpy).

## Marshal / GPU-feeder lane (instrumentation + overlap trial)

Runner instrumentation (feeder checkpoints at island boundaries, per-op
CPU issue wall, per-input marshal drains — commit with this receipt):

- The pass is CPU-issue-bound, not GPU-bound: between-island CPU issue
  wall is ~56-78 ms per layer pair (~1.5 s/pass), while the GPU drain at
  the island marshal eval is only ~25-38 ms per layer pair (L01-A
  q_v drain 29.4 ms; other inputs <1.5 ms).
- Op wall between islands is dominated by matmul: 47 statements,
  1029 ms/pass (conv 128 ms, layer_norm 18 ms, linear 17 ms).
- Overlap trial: MLX_OMARCHY_PIPE_OPS= (all-ops async_eval issue) =
  1788.6 ms vs 1761.5 ms conv-only — no gain; async issue does not
  shrink the synchronous apply() wall.
- Conclusion: the remaining encoder_ane wall lives in the pure-Python
  statement interpreter's apply() path (esp. the two per-layer matmul
  statements). The lever is moving/fusing those ops (EncoderHardware-
  Continuation's A→B fusion) or mx.compile — not submit transport,
  which is now ~0.1 s/pass.

Batteries (1 smoke + 1 warm + 3 meas, inprocess, all gold-bit-exact +
104/104): instrumented conv-pipe 1761.5 ms; all-ops pipe 1788.6 ms
(note: instrumentation adds per-statement wall overhead vs the 1524.3
uninstrumented median).

## Follow-on landing (same session, measured)

Battery 3 (tiles commit 1d7783929): inprocess 1905.6 ms — noise-level vs
1908.5, all green; tile cache kept (harmless, removes per-submit
alloc+zero). Battery 4 (zero-copy, commit 5d1ef2126): encoder_ane median
**1524.3 ms** — −384.2 ms vs inprocess-with-copy (−20%), −1259 ms vs the
worker baseline (−45%); submit walls attn 207.2 → 98.6 ms/pass, pv 74.7
→ 45.2 ms/pass; 1 smoke + 1 warm + 6 meas, all gold-bit-exact + 104/104.

Overhead question answered: the ~91 ms/pass shim overhead was staging
copies (input assign + values-map copy + output Buffer + memcpy into the
caller buffer). Borrowed input spans + output sinks removed almost all of
it — attn pass is now 98.6 ms wall vs ~92 ms device phases, so the
remaining cut lives in the device phases themselves (pack + ioctl +
unpack), not in the shim.

## Marshalling lane verdict + all-ops pipe landing

Device-placement question answered: creation is GPU-anchored
(mx.set_default_device(gpu) precedes every statement) and CPU matmul of
the island shapes costs ~47 ms while the GPU equivalent is ~2-4 ms — but
the decisive measurement is different. Per-statement traces with
eval-after probes (MLX_OMARCHY_STMT_TRACE=1) show the slow statements
(the 47 attention-scores-family matmuls NOT covered by the placed
islands) block 30-110 ms inside apply() with eval-after ~0.1 ms: the
array is already materialized when apply returns. That is async-queue
backpressure — the issuing thread stalls while the GPU drains the
previously scheduled conv-only work. It is neither CPU-device execution
nor Python interpreter overhead.

Consequence: issue EVERYTHING asynchronously. All-ops pipe
(MLX_OMARCHY_PIPE_OPS=) measured encoder_ane median 1228.7 ms (3 meas)
and the confirmation battery with the new default 1260.1 ms (6 meas) —
vs 1717-1868 ms conv-only instrumented and 1524.3 ms conv-only
uninstrumented. All runs gold-bit-exact + 104/104. Landed as the
inprocess-mode default (worker modes keep conv-only; commit 6aa310528).

Cumulative j16: encoder_ane median 2783.6 -> 1260.1 ms (-54.7%),
total pipeline 4142.1 -> 2578.2 ms. The residual wall is real GPU
compute of the non-placed matmuls — the A->B fusion (EncoderHardware
Continuation) is the remaining lever, plus a j1 replay.

## Fused A->B integration (EHC package, Main-directed)

MLX_OMARCHY_FUSED_AB=1 splices EHC's out_ab package (p0 apple-parity-
broadcast add, p1 boolean select; bd composed in-memory) in place of the
GPU add (matrix_bd) + GPU mask select: the add statement is skipped, the
select dispatches to the out_ab ANE package consuming s1/s2/fill/mask
and emitting z. Package staged into each host's bundles dir as out_ab
and loaded through the same in-process shim alongside the resident
bundles. Commit 601df6695.

- j16: fused 1755.9 vs unfused 1863.3 ms encoder_ane median (-107 ms,
  -5.8%), 1 smoke + 1 warm + 6 meas, both arms all pins green.
- j1: fused 3546.7 vs unfused 3538.9 ms — parity (the j1 GPU
  add+select was already cheap relative to its feeder). Both arms all
  pins green. NOTE: j1's numbers are contention-sensitive — three
  same-day windows on similar code swung 3776/5216 -> 32755/13391/
  12277/13391/3538 ms; only same-window interleaved deltas are
  trustworthy on that host right now.

## Matmul kernel probe (Main question)

The exact runner chain (fp16->fp32 upcast, [8,375,64]@[8,375,64]T,
fp16 downcast) runs 0.83 ms isolated = 173.9 GFLOPS; direct fp16 matmul
0.48 ms = 298.2 GFLOPS; fp16 1024^3 = 1471 GFLOPS. The kernel is
healthy — the per-statement 30-110 ms walls are async-queue drain
points, not slow kernels and not CPU execution. No mlx-omarchy backend
matmul fix indicated; remaining lever is op placement (A->B fusion) and
issue cadence (all-ops pipe on j16; pathological on j1 e167 — see
below). Microbench: mmbench.py in this directory.

## j1 e167 driver note

The driver survived at /var/tmp/mesa-e167-j1/ (icd.json +
libvulkan_asahi.so sha-verified against the build tree) but the first
fused-j1 attempt segfaulted with stock mesa because the derived battery
script lacked the VK_DRIVER_FILES export — re-added. Other lanes have
also staged rev-* mesa variants into that directory; the icd.json still
points at the e167 build.

## Mask-lowering respell gate (EHC logical_and -> fp16 mul)

Runner parser extended for the protobuf-reexported MIL text (string()
attr literals, inlined quoted constants; commit 703cf142d). Gate on j16,
FUSED_AB=1, interleaved 1 smoke + 1 warm + 6 meas: respelled source
1538.6 ms vs current source 1564.6 ms encoder_ane median (-26 ms),
both arms all pins green (104/104, gold bit-exact). The trailing bool
boundary cast stayed off the ANE path per EHC's contract. Identity:
respell-20260921T195419. PASS reported to EHC for their receipt.

## j1 fused A/B — clean post-rebind window (lock-gated)

Ran via a lock-gated wrapper (waited 27 min for /tmp/m1-gpu.lock, then an
exclusive window): fused 3618.9 vs unfused 3573.4 ms encoder_ane median
(parity, +45 ms within window noise), total 4974.0 vs 4904.0 ms. Both
arms all pins green (1 smoke + 1 warm + 6 meas). Verdict: fused A->B is
platform-neutral — the -107 ms win is j16-only; j1's GPU add+select was
never a meaningful cost. Identity: fused-20260921T202356.

## j1 fresh decomposition (3573 ms stack, clean exclusive window)

decomp-20260921T202639 (inprocess, fused off, 1 warm + 3 meas, all pins
green; encoder_ane median 3611.6 ms). Per-pass buckets:

- ANE submit walls: 352.1 ms total (attn 279.9 + pv 72.3); inside them
  device phases send 58.6 / exec 40.2 / read 225.2 — read dominates
  (attn 203.1 ms = 8.5 ms per readback, vs j16 ~0.6 ms).
- Marshal (GPU drain at island-input eval): 1942.9 ms — dominant.
- Feeder CPU issue wall: 3480.8 ms (overlaps GPU), op split: matmul 47
  stmts = 2373.1 ms, const 1983 stmts = 745.2 ms (!), conv 282.4 ms.

j1 levers, in order: (1) feeder matmul GPU work (~1.9 s of the pass is
GPU drain behind CPU issue — same A->B/C->O fusion lever as j16, and
j1's GPU is ~2.3x slower per feeder op); (2) const materialization:
~2000 consts cost 745 ms/pass of host array creation + upload — a
per-process const cache or chunked blob upload is a backend-level win;
(3) island readbacks: attn read 8.5 ms/submit on j1 vs ~0.6 ms on j16 —
worth one probe of the libane read path (tile unpack vs ioctl) on T8103.

## Landing: readback fix + const batching (j1), Main items (2)+(3)

(3) READBACK ROOT-CAUSED AND FIXED: split timing in the libane device
(ANE_READ_SPLIT=1, worker_libane.cpp) attributes the T8103 readback to
the memcpy out of the mapped tile: ~20 ms for the 4.5 MB attention
scores tile (~225 MB/s), unpack only 0.2-0.4 ms. Cause: ane_drv.c maps
every BO writecombine (pgprot_writecombine) — uncached reads on T8103.
Fix: map cached (drop the writecombine call), rebuild ane.ko, reload.
Probe: attn submit read 30 ms -> 0.67 ms (~45x). Data correctness is
gated by the full battery (stale cache lines would corrupt gold):
j1 fused battery on the cached module (exclusive window, lock-held):
fused-off 3468.7 / duplicate-arm 3478.0 ms encoder_ane median, 6 meas
per arm, ALL PINS GREEN (104/104, gold bit-exact) — cached reads return
correct data on this fabric. CAVEAT: the cached ane.ko is NOT
persistent across reboots; rebind runs must insmod
/var/tmp/ane-6fa-src/ane/ane.ko (sha 4ebcfc10...; stock writecombine
module otherwise loads). Upstream fix: make the cached mapping the
driver default (or per-BO flag) in omarchy-ane ane_drv.c.
j1 measured effect vs the pre-fix same-config window: encoder_ane
3573-3611 -> 3468-3478 ms; total pipeline 4904-4940 -> 4770-4833 ms.

(2) CONST MATERIALIZATION: blobs are now uploaded once per (blob file,
dtype) as a single device array; each const is a slice view (Blobs
.dtype_view + batched _eval_const path). Measured const statement wall
on j1: 745.2 -> 351.2 ms (-53%). Most of the remainder is host-side
np/memmap work; the upload count dropped from ~1983 to a handful.

## Cached mapping made permanent (Main directive)

omarchy-ane branch agent/ane-cached-bo-mapping (commit afb23dd on the
j16 repo): ane_drv.c maps BOs cached by default, module param
writecombine=1 opt-out, with the DART-coherency + 45x rationale in the
comment. j16 rebuilt from the branch (~/src/omarchy-ane/ane/ane.ko),
module reloaded (writecombine=N), verification battery on T6001: fused
1233.0 / unfused 1310.9 ms encoder_ane median — all pins green; cached
mapping costs nothing on T6001. j16 llama-server restored, health ok.
j1: /var/tmp/ane-6fa-src/ane/src/ane_drv.c synced to the committed
version (with the param), ane.ko rebuilt (756624 bytes, 21:41).
Rebind script (workstation ane-linux-experiments-parakeet-perf
native-divisor-t8103/rebind_and_verify.sh, commit 0d383ab) now insmods
/var/tmp/ane-6fa-src/ane/ane.ko instead of the stock
j1-ane-restore copy; ParakeetPerformance notified (they execute it).
