# Encoder island cost — receipt (2026-09-22)

Owner: EncoderIslandCost (sub, mlx-openai-operator tree).
Scope: capture-path execution + per-island device cost + m1-host feeder efficiency.
Non-goals honored: no A->B fusion, no pipelining, no M2.

## 1. Capture path — LANDED

- mac-desktop ANECompilerService (PID 2400, wedged 13 days) was SIGKILLed by
  Joshua at 09:52 CDT; postbounce-probe.py run immediately.
- Post-bounce the compiler now REPORTS instead of silently refusing: the
  "content-triggered silence" was a wedged-daemon artifact for phase-1
  validation, and progressive deeper-phase failures after that.
- Probes established the ANE program rules (each verified by compiling
  purpose-built MIL, dtype-probe{,2,3,4}/):
  - int32: banned in any DYNAMIC tensor (input, intermediate, output).
    Compile-time consts (axes, pads, int32 blob consts) are fine.
  - fp32: banned everywhere (input_features and the encoder_hidden output
    cast both rejected).
  - fp16 floor_div, reduce_min, greater/less, logical_not, select, cast
    bool->fp16: all supported.
  - logical_and: unsupported -> respelled cast/cast/mul/cast ({0,1} mul).
- Rewrite (rewrite-fp16-v2.py + in-place blob fix + tail fix, stages
  fp16-single-v2..v10):
  - attention_mask int32 -> fp16 program input;
  - lengths chain (reduce_sum/add/add/sub/floor_div) -> fp16, consts as
    fp16 scalars; casts 25/126/150/151 deleted;
  - all_masked_rows -> fp16 reduce_min + greater(min, 0.5);
  - var_281 arange(0..374) const: int32 blob (weights.bin offset 2386176,
    payload at 2386240) converted to fp16 IN PLACE (payload 750 B zero
    padded to 1500), BLOBFILE offset unchanged; a raw append or a sidecar
    file both fail ("Cannot retrieve file blob properties" / silent) —
    the BLOBFILE offset points at the 0x40 DEADBEEF descriptor record.
  - outputs: linear_217_cast_fp16 [1,375,640] fp16 + output_mask_f
    [1,375] fp16 (the dead fp32 encoder_hidden cast in the tail was the
    last InvalidMILProgram trigger — unused ops are still validated).
- Result: model.hwx COMPILED — 460,423,168 B, callback_status=0, 51 s,
  hwx-fp16-single-v10 on mac-desktop (also /tmp/encoder-v10.hwx).
- Decoded by EncoderFusionBC (receipt 9bfa8b4): 13701 tasks, ~571/layer,
  softmax = in-graph ~15-task L2-resident micro-pipeline, LN = 2 tasks.
  THE SINGLE-PROGRAM LOWERING GOAL IS MET.

## 2. Whole-program device run (staged; blocked on host availability)

- hwxv2-to-anec conversion DONE on the workstation:
  python3 tools/hwxv2-to-anec.py --input-height 3000 --input-width 1
    --output-height 375 --output-width 1 model.hwx /tmp/encoder-fp16.anec 128 640
  => 458,018,816 B, 13701 TDs, input surface 0xbf800, output 0x78300.
- Parity tensors staged (capture/parity/): feat-f16, mask-f16, gold-f16
  from m1max-host /var/tmp/EncoderParityAne/capture (hidden gold 38c73261 family).
- Runner: .local/ane-run-encoder.py (libane pyane_init/src_size/send/exec/
  read, staging ordinals per EHC: sends 4+dst_count+i, reads 4+i).
- RESULT (m1-host, T8103, 7.1.13-3-2-ARCH, writecombine=N): anec LOADS
  (ane_init OK; libane declares surfaces in[0]=in[1]=24576000 B,
  out[0]=out[1]=15368192 B — synthetic 4096-B-tile spans, not the hwx's
  true 768000/6000/480000 B logical bindings). exec REFUSED: ane_exec
  rc=-1 after ~1004 ms, outputs all-zero (0.0 nonzero frac). Matches
  EHC's container-header caveat: the hwxv2 converter's single-IO
  assumption misdescribes the Apple TD wiring. Script + facts staged at
  m1-host:/var/tmp/ane-exec-enc2.py and m1max-host:/var/tmp/. Container
  repackaging with true TD wiring is the EHC/FusionBC runner-side lane;
  the compiled+decoded single-program hwx itself stands.
- BLOCKER: m1max-host (m1max-host) dark since ~10:26 (no-route; TLB2MCTG
  one-shot suspected crash-loop; power-cycle flagged to Main/GpuTlbLatency).
  m1-host was in macOS for M2UartProxy, returned to Linux 10:47.

## 3. Per-island device cost (task 2)

- Method: bench_island_ane16.py per-submit rec fields (write_ns/read_ns/
  marshal_ns/stage) over the interleaved battery; module check
  = /sys/module/ane/parameters/writecombine == N and
  modinfo ane -> updates/ane.ko (agent/ane-cached-bo-mapping afb23dd).
- Context from receipts/2026-09-22-m1-host-feeder-levers: the cached-BO
  readback (4.4 ms -> 0.67 ms) was re-landed boot-persistent on BOTH
  m1-host and m1max-host after the Sep 21 reboot regression. The TLB2M
  kernel jaunt is a fresh regression vector: ane.ko is absent on the test
  kernel entirely; the stock-kernel module must be re-verified.
- Whole-program task-stream accounting (from encoder-v10-tasks.ndjson,
  local): 13701 tasks, tile-DMA src_total sums to 3.37 GB/pass internal
  surface traffic — the 48-island driver-visible read/write subset is what
  the shim measurement quantifies. MEASUREMENT PENDING HOST.
- STATUS: blocked on stock kernel (see 2). writecombine + read_ns
  before/after to be appended when m1max-host returns.

## 4. m1-host feeder GPU (task 3)

- m1-host is booted to macOS for M2UartProxy bring-up (FleetMacOSUnattended
  Access announce); Linux SSH unreachable all session. Profile of the top
  3 feeder kernels (coopmat-linear/GLU/chain), occupancy check vs the
  Qwen lanes' 3.3 TF/s coopmat route, and f16-activation/tile fixes are
  queued for the Linux return.
- STATUS: blocked on host.

## Artifacts

- capture/model.hwx (sha256 020428fca545648f...), capture/model.mil,
  capture/weights/weight.bin (295dccd4...), capture/SHA256SUMS.
- capture/parity/{feat-f16,mask-f16,gold-f16}.npy.
- .local/rewrite-fp16-v2.py, .local/stage-v{4,5,6}.py, .local/ane-run-encoder.py,
  .local/cut-bisect.py, .local/probe-range.py (all pushed to mac-desktop
  /tmp/hwx-r4/ as well).
- mac-desktop: /tmp/hwx-r4/fp16-single-v10/, /tmp/hwx-r4/hwx-fp16-single-v10/.
- FusionBC: encoder-v10-tasks.ndjson, encoder-v10-softmax-ln-windows.json
  (commit 9bfa8b4).
