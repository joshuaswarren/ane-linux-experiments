# M2 handshake resume: firmware runs, parks before READY (2026-09-25)

## Boot path
- ESP restored to stock a3f533b9 from macOS: source verified, written,
  re-read after a read-only remount, all a3f533b9.
  `bless --mount /Volumes/Omarchy --setBoot` moved the default from
  /dev/disk4s1 to /dev/disk2s2. Reboot reached Linux.
- USB reboot proven with no hands. ESP holds 43ec6090 (PROXY60 marker at
  0x659b0), taken SHA-gated from
  /var/tmp/m2-b9/boot.bin.live-43ec6090.bak. A Linux reboot enumerated the
  proxy ACM on jwm1 (1209:316d) in 21 s; a panic-counter reset plus
  p.reboot() from jwm1 brought the next boot, and Linux returned on 43ec.
  Every boot has a 60 s proxy window. Stock a3f533b9 stays verified at
  /var/tmp/m2stub-backup/.

## macOS denominators
Qwen GPU is already complete (receipt d3dc1ae): decode 179.0 tok/s,
prefill-512 1109.82, TTFT 367.68 tok/s, e2e 0.2129 s. The Qwen ANE
reference is still missing; a rerun hits the known err=11
decoder-compile blocker and was skipped.

## What the firmware does
On the proven release path (VENC rails to 0x3ff, TCR15=2, rtclient
map-only, scratch clear, CPU_CONTROL 0 then 0x10) the core leaves the
stopped state: CPU_STATUS goes 0x2a to 0x28. It never writes READY
(0x08042006) to either candidate word (0x1840064 or 0x184006c), and the
mailbox outbox stays empty. The 24 MHz clock block ticks
(engine+0x1160008 advanced at ~24 MHz), so a dead counter is not the
cause. The debug block reads zero even with the core released, so the
program counter cannot be sampled through it.

## Tests run, all negative
- GPIO clock-enable. The Asahi ISP driver, which uses the same READY/WAKE
  GPIO protocol, sets a clock-enable at gpio+0x20 before release. For the
  ANE that is engine+0x1840068. Writing 1 there hung the fabric. The
  2-minute watchdog rebooted to Linux. The ascdbg log loses its last
  second across a hard reset, so the on-disk tail is not the faulting
  access; the live stream pins it to that write, the only one in the
  group not already proven safe. Not repeated. The 13.5 kext does not
  write a GPIO clock-enable on this path, so the hypothesis was wrong.
- Engine table. The kext writes engine+0x938/0xa18/0xaf8 = 0x01ff01ff
  before ANE_Init. Those writes read back 0. No READY.
- Translation. The three ANE DARTs were not programmed alike: inst0's
  TTBR read 0 (invalid) while inst1 and inst2 shared a valid one. m1n1's
  own ANE driver copies TTBR0 to every instance ("DMA fails w/o"), so
  this was a real gap. Setting inst0's TTBR to match and TCR15=2 on all
  three, done BEFORE the release on a fresh boot, still gave no READY:
  status 0x28, gpio7 0, recv0 0 after 8 s. The gap was real and is fixed;
  it is not the cause.
- Mailbox wake. A message through the bound mailbox API, sent after the
  translation fix, stayed queued for 60 s (A2I_CTRL 0x00020001, recv 0,
  scratch7 0). A doorbell does not rouse the parked firmware.

## The remaining blocker
RVBAR reads 0x0000010000000001: bit 0 set, so it is locked, and the mode
bits (0x0081<<48) are absent. The kext would write
0x8100000000000001 if the lock were clear. The firmware executes without
those bits, so they do not gate fetch; the open inference is that they
gate the interrupt or timer delivery that would wake the firmware from
its wfi. That inference is not tested, because the bits cannot be set
from here:

- iBoot locks RVBAR before m1n1 runs. The proxy window already reads the
  locked value, so a stage-2 write is too late.
- A completed power cycle of the ane_cpu island does not clear the lock
  (receipt 2026-09-23-m2-fwstart §7: ACTUAL went to 0 and back, the box
  stayed up, RVBAR still locked). The ps-off and reset-pulse variants
  hung the fabric. No safe pmgr operation clears it.

The mode bits are therefore only settable by iBoot, on a macOS-style
boot, before it locks the word. Confirming that iBoot writes them, and
capturing the value, needs the hypervisor trace of a macOS boot, which
stalled earlier on the kernelcache load. That trace is the next step,
and it is a separate effort from this lane's Linux-side work.

## State
- Linux up on 43ec6090, ESP unchanged, stock fallback verified.
- No firmware READY, no HELLO, no EPMAP, no CSNE. The handshake has not
  begun, because the firmware never announces itself.

## IRQ mask, wrapper diff, and the wake source (Main, 2026-09-25)

RVBAR mode bits withdrawn as the cause: macOS runs on the same locked
word, so they cannot be the difference.

- IRQ unmask, null. Fresh boot, DARTs equalized (TTBR 0x1000e055 on all
  three), 0x1400a00..0x1400a14 written 0xffffffff and read back
  0xffffffff, GPIO clock-enable not touched. After release: CPU_STATUS
  0x2a to 0x28, READY poll timed out at 0 after 8 s, recv0 0.
- Wrapper page 0x1400000..0x1401000, three words changed across the
  release: 0x1400044 went 0 to 0x10 (our CPU_CONTROL write), 0x1400048
  went 0x2a to 0x28, and 0x1400818 went 0x00040001 to 0x00040003. The
  rest of the page was identical. 0x1400818 is the coprocessor status
  word the ISP driver polls for zero before it will release; ours never
  reads zero.
- Wake source, from the payload. The park wfi at vm 0x71bc branches to
  itself: it is the idle loop, not a halt. Before it the firmware arms
  software event 6, a bit in a BSS bitmap, not an IRQ number. The
  interrupt it sleeps on is its own physical timer: it writes
  CNTP_TVAL_EL0 and sets CNTP_CTL_EL0 = 1 at vm 0x654cc, and writes
  CNTFRQ_EL0 at vm 0x66010 when the value is nonzero. That is ARM PPI 30,
  raised by the core's own timer, and it fires only if the generic timer
  counter is clocked. A mailbox doorbell does not wake the core either,
  so interrupt delivery to the core is dead broadly, not just the timer.
  The timer clock is enabled on macOS by the ANE init that the Asahi boot
  skips, and it is not a register in the set matched so far.

## Rank 2, same boot
Pre-write masks all 0. Wrote 0xffffffff to 0x1400a00..0x1400a14; all six
read back 0xffffffff and still read 0xffffffff 60 s later, so nothing is
actively clearing them. READY 0x1840064 stayed 0 through a 30 s poll,
status 0x28, recv0 0. A doorbell then sat queued 60 s (A2I_CTRL
0x00020001, I2A 0x00020001, recv 0, scratch7 0); after the full 60 s the
module reports status=0x08 with the masks still 0xffffffff. Post-park
unmask changes nothing, and the doorbell never drains.
