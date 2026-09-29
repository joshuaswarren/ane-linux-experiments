# First correct ANE inference on the M2 Max (T6021), 2026-09-29

Boot 8f468602, kernel 7.1.13-ARCH-polltx, ANE firmware fw 13.5
(sha256 a9c4b771...), rtclient module sha256 570b3c2b....

Result: one bare PROCEDURE_CALL of the compiled `binary_add_1x512x1x1`
program returned y == a + b, bit-exact over all 16384 fp16 elements of
the 32 KiB output buffer. Inputs: a[i*32] = ramp starting at -8.0, b
starting at -0.5 (511 nonzero elements, stride 32 fp16). y[0] = -8.5.
The buffer was the 0x7e00 sentinel before the call and none of it
remains. y is not a copy of a. Independent check: numpy on the raw
buffers, on the M2 and again offline on the saved copies.

Evidence: private notebook artifacts `first-inference-8f468602/`
(buffers s04b00/01/02, dmesg, verify_y.txt, SHA256SUMS). Script:
`drivers/t6021/lab/run-fixdesc.sh` (copy of /tmp/run_fixdesc.sh).

Hardware state after the call: TQ status word 0x285c20804+q*0x2c reads
0x81 (idle) for all eight queues (queue 5 read 0x70 before the fix),
last committed TD 0x285c20458 = 0x00010000, TQEn 0x803000, DART LLT
error words changed only in low bits (0x00a00000 / 0x7bef4b7e / 0x33e).

## Root cause of the days-long "tiles never fire"

Our Descriptor section was 244 bytes. The task stream at ANEC offset
0x1000 is a 16-byte zero frame followed by the task, and the task
header (word 4 = 0x003d0000) declares 61 words. The full stream is
65 words = 260 bytes. The builder copied only firstTaskBytes (244)
from 0x1000, so the last 16 bytes were lost: the output address record
(0x1508, header 0x22808542) and one word of the slot-6 record. The TQ
fetched a short task, left the idle state (status 0x70) and waited for
the rest. Apple's load-proven conv Descriptor confirms the layout:
408 B = 16 B frame + 98 task words (header 0x00620000).

Fix: `tools/h14_first_add_sections.py` `build_descriptor()` now copies
FRAME_BYTES + FIRST_TASK_BYTES (260) and checks header task_words.
The tdprop segment size follows (0x104).

## What else the run used (each is a change from earlier boots)

- Operation section refs {slot 4, tag 5 (a)}, {slot 5, tag 4 (y)},
  {slot 6, tag 6 (b)}: `build_operation()`. Without them the record
  patch area is empty.
- `fw_start_dapf=1` (five DAPF windows). Needed for command 0x29 with
  the real PMU window. NOT yet shown to be needed for a bare call.
- No 0x27, 0x28, 0x29 and no property 0x10A8 in this run. The
  secure-mode and TD-count theories in the older receipts did not
  matter for this result.

Not yet done: which of DAPF and the refs is minimal; repeated submits,
new inputs, close/reopen, fresh-boot repeat; the installed (no scratch
module) path; Parakeet encoder and Qwen reference on the M2.
