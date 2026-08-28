# Static ANEC graphs and batched submission on Linux

## Static ANEC graphs

The Linux path runs reusable static graphs through the ANEC format. The
stack is the `eiln/anecc` converter plus a patched `eiln/libane`
(`patches/libane-ane.c`, `patches/libane-ane.h`). Three fixes made it work:

1. The libane ANEC header offset moved from `0x800` to the converter's
   `0x1000`.
2. Submissions pin queue 1.
3. Completion polls an output sentinel.

Verified behavior on Linux:

- Retained multi-op `.ane` graphs execute. `mul`, `concat`, and the fused
  tinygrad Conv+GOC graph all return exact expected values.
- `ane-patch-mul-to-add.py` flips task registers in the compiled payload.
  One MUL graph becomes an ADD graph without recompiling.
- `ane_exec_loop` is a new libane call. It swaps the state input buffer
  object with the state output buffer object each dispatch. Recurrent or
  attention state stays resident on the device: `3*2*2*2 -> 24` and
  `3+2+2+2 -> 9`.
- `ane_bind_kernel` is a new libane call. It binds a new fp16 kernel
  payload at runtime. An identity kernel bound into `gemm.ane` passes its
  input through.

Receipts: `receipts/ane-static-graph-loop.log`.

## Batched submission: partially verified

`ane-batch.py` chains task descriptors in one submission. The submit ioctl
carries `td_count` and the driver passes it to the task manager.

- Two, three, four, and eight identical descriptors per submission produce
  numerically correct output when each count is tested as the first
  submission after a clean reboot and bring-up ladder.
- Clean first-submission results are in
  `receipts/ane-batch-perboot-clean.log`: n=3 measured 1.64ms and 1.63ms,
  n=4 measured 0.12ms and 1.64ms, and n=8 measured 1.66ms and 0.48ms total.
- A clean two-TD test with different weight blobs produces the first output
  but leaves the second at the `+inf` sentinel. Per-TD weight batching is
  not verified.
- Timing is not stable. The same n=2 configuration measured 1.61ms, 0.75ms
  and 2.16ms total across three clean boots. No model-throughput headline
  is quoted.
- Earlier failures were contaminated. A first run tried n=1,2,4,8 in one
  process. n=4 hung. Every later submission inherited the queue wedge. That
  did not prove a hardware limit, so no descriptor ceiling is claimed.
