# H14/T6021 W4-fix — doorbell pinned from the kext: no mailbox register file exists; SCRATCH-write lane is machine-fatal (receipted); first live fw→host register bytes captured (2026-09-19)

Verdict: **transport lane advanced by falsification + first capture.** (1) The
assumed mailbox at ANE+0x1608xxx does not exist anywhere in the K14 kext text —
the h14g host→fw transport is MBI: SCRATCH registers + a fw-published channel
table + per-channel doorbell bits at **ANE+0x1844000**. (2) The SCRATCH
handshake WRITE path is **machine-fatal in RTBuddy mode**: the first write32 to
SCRATCH0 (+0x1840048) SError-aborted jw14m2 (CPU4, 0xbe000000, unclean reset) —
receipted by netconsole with per-stage flush points; the driver's write path is
deleted. (3) The read-only build is stable across load→unload→reload (3×
transport-on loads, box alive), and the **fw→host message pair at
ANE+0x1170000/0x1170004 is live in-kernel**: `i2a=00000002_216c8e1b →
…e92` between attach and drain on every load — the first fw→host bytes
receipted. CSNE_CMD_PING stays fenced: the INIT-channel doorbell bit is still
unknown (it comes out of the channel table this lane could not reach).

## 1. Static decode (K14 = AppleH11ANEInterface 10.19.2 mac14j, carved KC)

Everything below is h14g-specific and cited to a disassembly address in
`receipts/2026-09-18-h14-w2-protocol-decode/` tooling (`kx.py`/`disx.py` over
`kext-h14j/AppleH11ANEInterface-10.19.2-mac14j-26A428`).

**The CPU block moves for h14g.** `initializeANESoCConfig`
(0x…9612f1c-0x…9615d38) dispatches per chip-id and stores register offsets into
the device object; the two h14g blocks (chip 0x80 @0x…9613634, second @0x…9613fc0)
both build **0x1400044** (`mov #0x44; movk #0x140 lsl 16` — NO 0x200000 orr) into
dev+0x4a0, plus `{0x1844000, 0x1400048}` into dev+0x498/0x49c and 0xc000 into
dev+0x574. Phase-1 §2's "0x1600044" was a misattributed variant: 0x1600044 is
built only by the h16g/h17/h18g blocks (0x…9613458/0x…961399c/0x…9613bd8…).
m1n1 `hw/asc.py` cross-ref: CPU_CONTROL +0x44 / CPU_STATUS +0x48 keeps the
m1n1 shape at ANE+0x1400000 (runtime RUN-write site 0x…95d2968, CPU_STATUS
poll 0x…95ecfb4), but the m1n1 mailbox (INBOX/OUTBOX +0x8110/+0x8800) has **no
h14g analog**: zero 0x1608xxx / 0x1408xxx constants in the entire
__TEXT_EXEC.__text (full mov/movk scan over all 0x14/16/18-high families).

**The h14g register map (all ANE-window offsets, from the config q-blobs:**
`x23 = dev+0x438` @0x…9612f70; blobs @0x…7503a40/0x…7503a50/0x…7503a60
(common tail 0x…9613eb4-0x…9613ef0) and @0x…7503860 (h14g block 0x…961364c)):

| fields | values | meaning (runtime sites) |
| --- | --- | --- |
| dev+0x438..0x457 | 0x1840048, 0x184004c, 0x1840050, 0x1840054, 0x1840058, 0x184005c, 0x1840060, 0x1840064 | **MBI SCRATCH0-7** = ANE+0x1840048..+0x1840064. Phase-1 §2's "GPIO0-7 all 0" was a read of THIS block — correctly zero pre-attach |
| dev+0x458..0x467 | 0x1904000, 0x1840074, 0x1840078, 0x1840070 | aux block + RTB control regs (unread this lane) |
| dev+0x488/0x48c | 0x1170000, 0x1170004 | **fw→host u64 message pair** (reads 0x…95ee6a8, 0x…9605d20/54) |
| dev+0x490/0x494 | 0x184c000, 0x1850000 | host→fw message: read peer / write (echo pair 0x…9606e38→0x…9606f0c) |
| dev+0x498/0x49c | 0x1844000, 0x1400048 | **doorbell** / CPU_STATUS |
| dev+0x4a0 | 0x1400044 | CPU_CONTROL |

**The SCRATCH handshake (0x…95eaa94-0x…95eaf00) and the doorbell registration
belong to the fw-sideload boot mode, not RTBuddy host attach.** Flow: cmd
buffer base → SCRATCH0/1 (0x…95eaa94/0x…95eaad0), wake 0xf7fbdff9 → SCRATCH7
(0x…95eab24), poll SCRATCH7 == **0x80402006** ("channel description table
ready", 0x…95eab74), table base read back from SCRATCH0/1 (0x…95ead04),
entries at stride 0x100 with {type +0x40, doorbell bit +0x44, size +0x48,
phys +0x50} (0x…95eade8-0x…95eae58), each registered with the doorbell
setter **0x…95ebdd0-0x…95ebe10 = write32(1 << bit) to ANE+0x1844000**; host
ack SCRATCH3 = 0x80402006 (0x…95eaee4). `rtbuddyEndpointSendMessage`'s tail
(0x…95f3bf4-0x…95f3c30, from W2) never touches MMIO — it packs the 48-bit ring
word and calls the record's gate (rec+0x28, vtable +0x1e8).

**The RTBuddy-mode gate lives behind another kext.** `EnableRTBuddyEndpoints`
(0x…95fec30) builds a matcher and waits up to **10 s** (x1 = 0x2_540be400 =
10^10 ns into helper 0x964c038; sibling sites use 0x5f5e100 = 10^8 and
0x1dcd6500 = 5×10^8 — time constants, NOT addresses; the "physical address"
reading of 0x2_540be400 is retracted) for a service object x23, then gate =
[x23+0x88], registers HandleRTBuddyMessage (pacia 0x…95feff0, key 0x1810) as
the rx handler and 0x…95ff634 at gate+0xd0. The gate's +0x1e8 send
implementation is in whatever kext publishes that service — not in this
carried binary. Next lane: carve the full `kernelcache.release.mac14j` (on
disk, mined lane) for the publishing kext (RTBuddy/mailbox provider).

## 2. Live run — the wall, receipted (jw14m2-linux, 11:04:47-11:06:28)

Runbook executed per W3 §4 (stage-1 userspace RMW ok, eight islands verified,
ane_cpu auto-clear ok). rtkit_transport=1 then ran the (since-deleted)
SCRATCH-handshake attempt. Netconsole flush points (sender 192.168.3.103:6668,
receiver /var/log/fleet-netconsole.log on omp-studio-local; extract:
`receipts/2026-09-19-h14-w4fix-netconsole-seam.log`):

```
[3263.936341] MBI scratch0 pre=00000000 … scratch7 pre=00000000   (8 reads clean)
[3263.936373] MBI cmd buffer phys=0x0000011717404000 dma=…        (last flush)
[3263.936378] SError Interrupt on CPU4, code 0x00000000be000000 -- SError
```

The very next instruction was the first host **write32 to SCRATCH0
(ANE+0x1840048)**. Reads of the same registers stub clean (zeros, in-kernel,
pre-write); writes take an async external abort with selene running → kernel
SError → watchdog reset. This is the same protection class as the +0x1608xxx
family (W3): **the fw-owned control surface rejects host writes in RTBuddy
mode.** The SCRATCH handshake is iBoot/fw-sideload-mode init ("kext writes
SCRATCH0-7 pre-release", phase-1 §2.5 — now data-confirmed). Machine came
back clean on its own (fresh boot 11:06:28, journal marks the unclean
shutdown); no retry.

## 3. The safe build — load, capture, reload (11:09-11:12)

Driver changes (omarchy-ane `feat/t6021-ane-driver-w4` @ c802069, pushed):
+0x1608xxx mailbox constants replaced by the h14g map (CPU_CONTROL
0x1400044/CPU_STATUS 0x1400048, SCRATCH, doorbell, message pair);
`ane_t6021_mbi_boot()` is read-only (8 SCRATCH reads + message-register
reads, log-only); the SCRATCH write path and the m1n1-mailbox MGMT send/recv
paths are deleted; CSNE submit and MGMT sends refuse with -EOPNOTSUPP until
the channel table pins the INIT/MGMT doorbell bits; first_resume now sets
`booted` and logs SCRATCH0-7 under their real names.

Receipt (transport-on load, 342.7 s uptime frame; full trail:
`receipts/2026-09-19-h14-w4fix-clean-load-trail.log`):

```
ANEGATE pass; ASC status whitelist next
ANERD rvbar=00000001  vers=000e3044  rtb_status=00000001 rtb_7c=00000030
ANERD scratch0..7 = 00000000 (×8)
MBI scratch0..7 pre = 00000000 (×8)
MBI msgregs attach: i2a=00000002_216c8e1b a2i_rd=00000000 a2i_wr=00000000
MBI wall: SCRATCH/msgreg surfaces are read-only (host write = SError, 2026-09-19)
MBI msgregs drain:  i2a=00000002_216c8e92 a2i_rd=00000000 a2i_wr=00000000
loaded ane_t6021 unknown (RTKit transport ON; 8-domain power gate; CSNE_CMD submission = W4)
```

**First live fw→host bytes**: the +0x1170000/0x1170004 pair reads
`{hi=0x00000002, lo=0x216c8e1b → 0x216c8e92}` ~200 µs apart — the lo word
ticks on every load (0x4c0f64d8→0x4c0f652b on the third load); the fw is
running and updating a host-visible register inside its window. Shape
(hi=2 = channel/type? lo = counter/pointer?) undecoded. load → rmmod →
reload ×3 with transport on, exit 0, box alive (uptime continuous), no
SError in dmesg or netconsole.

Cross-build note: the dev box's `struct module` does not match the on-box
kernel (`Invalid module format` at insmod) — build on-box in
`/var/tmp/ane-t6021-w4` (sources synced, `make`), module sha256 on-box build
`02f116c1…` (cross artifact 9b341a8a… is dead weight, not deployed).

## 4. Acceptance vs ticket

- "Doorbell register pinned": pinned as far as the kext text allows — the
  MMIO doorbell is ANE+0x1844000 bit-set (config + setter cited), but in
  RTBuddy mode the reachable TX is the gate object from the awaited service
  (§1); the INIT/MGMT doorbell bit is not on this silicon's host-attach
  path until that service's kext is decoded.
- "HELLO attempt receipted or evidenced wall": **both** — wall receipted
  (SCRATCH-write SError seam, §2), safe build deployed and stable (§3),
  first fw→host register bytes captured (§3).
- CSNE_CMD_PING: not attempted — W4 submit is fenced (-EOPNOTSUPP); ringing
  a guessed bit on a surface where the wrong write kills the machine is the
  failure mode this lane exists to prevent.

## 5. Next lane

1. Carve the provider kext from `kernelcache.release.mac14j`: find who
   publishes the service `EnableRTBuddyEndpoints` waits for (matcher block at
   0x…95fec60-0x…95feca0) and disasm gate vtable+0x1e8 — that function is the
   real RTBuddy-mode doorbell writer.
2. Decode the +0x1170000/0x1170004 message shape from the kext's pair reads
   (0x…95ee6a8 context) — the live counter makes it the first candidate
   fw→host notification surface.
3. Only after 1: attempt the MGMT/INIT doorbell with a table- or
   kext-evidenced bit; then CSNE_CMD_PING per W4.

Open-source exemption: no screenshots; pushed branch c802069, this receipt,
and the two netconsole extracts are the artifacts. jwm1, jw16 untouched.
