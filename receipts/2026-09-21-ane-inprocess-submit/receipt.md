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
