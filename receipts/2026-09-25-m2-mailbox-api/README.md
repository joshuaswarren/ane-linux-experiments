# M2 mailbox API send: message queued, never drained (2026-09-25)

## Baseline (no writes by this lane tonight beyond the one send)
- DT reg cells: 0x2/0x85408000/0x0/0x4000 -> mailbox base 0x285408000 size 0x4000.
- ANE DT reg cells: engine 0x284000000/0x2000000, pmgr, set. Offsets used
  (SEND0 0x1408800, SEND1 0x1408808, RECV0 0x1408830, CTRLs 0x110/0x114)
  are ANE-aperture-relative, NOT mailbox-base-relative.
- Mailbox device 285408000.mailbox bound to apple-mailbox; ANE 284000000.ane
  has NO driver bound (supplier link to the mailbox exists).
- Pre-send: A2I_CTRL 0x00020001, I2A_CTRL 0x00020001, SEND0 0, RECV0 0,
  CPU_STATUS 0x28, IRQ53 recv 0 on all CPUs.

## Send (bound-API contract, no raw doorbell poke)
Module ane_mbox_api_send.ko (built on-box against
/lib/modules/7.1.13-ARCH-m2mbox, vermagic match):
- slot 0 PRINT_ENABLE 12 B: 00 00 00 00 04 00 00 00 00 00 00 00,
  staged at ring IOVA with IOMMU_CACHE.
- msg0 (A2I_SEND0) = 0x0c000000 (cursor 0, len 12);
  msg1 (A2I_SEND1) = 1 (endpoint id).
- No write to +0x1844000 (races the bound 285408000.mailbox driver).

Result: SEND0 reads back 0x000000000c000000 (accepted), A2I_CTRL stays
0x00020001 at 0/30/60 s (FULL bit16 set, EMPTY bit17 set, level 1).
RECV0 0, I2A_CTRL 0x00020001, SCRATCH7 0, CPU_STATUS 0x08 during poll,
IRQ53 0 throughout. The message sits in the A2I FIFO; the firmware
never drains it.

## SHAs
- Cross-built (rejected, struct-module mismatch):
  f8e42f081f5f2e623d8215f33701b6ce2fac8e4d5a6942408f2158f3b80aa755
- On-box build, first (t=0 poll-exit bug): 6433f4bd547306f39b26b628d72d23546f50b47bce000aa11aca7c891da17bea
- On-box build, fixed poll: 9994cc549b6718202f56d253ebe6cd4404ebfda0f619b54a27f29f4e489c053a

## Conclusion
Delivery confirmed queued, consumption confirmed absent. The firmware
is not listening on the mailbox because it never reached the
channel-table/second-interrupt state. The gate stays upstream: the
boot-task name loop exit before the endpoint build.
