# ANS2 panic signature on first macOS boot after Linux (2026-09-25)

## Panics
Two Retired panic-full files, both the first macOS boot after a Linux
session; the immediate retry boots clean:
- panic-full-2026-09-25-054908.0002.panic
- panic-full-2026-09-25-101854.0002.panic

## Signature (10:18 file, quoted verbatim)
- `RTBuddy(ANS2)::_setManagedStateGated "No response received in 20s,
  ANS2 not started? (4)"`, iopStatus 0x4, powerStateChangeLocked true.
- Mailbox: IDLE_STATUS 0x0000000a, INBOX0_CTRL 0x00100101, OUTBOX0_CTRL
  0x00020001. AP->IOP log: one TX 0x0060000000000220, then all-zero RX.
  The host's word sits in the inbox; the firmware never drains or replies.

## Reading
Same shape as our ANE park: message queued, never consumed, outbox
armed-empty. An ASC that Linux touched fails firmware start on the next
warm boot, and macOS's own storage coprocessor fails exactly the way
ours does. The shared state hypothesis: our m2mbox kernel, m1n1 43ec, or
the ANE experiments leave a coprocessor power/clock/interrupt setting
common to all ASCs that iBoot's warm-reboot path does not clear. What
macOS does on the second boot to bring the ASC out of that state is the
open question, and it may be the same missing step for the ANE.

Separate event: the 11:01 reset counter (btn_rst force_off, boot failure
count 1) is not a panic and not a force-off by hand; do not attribute it.
