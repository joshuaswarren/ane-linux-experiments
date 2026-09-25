# CSNE channel setup — open, arm, doorbell sink, GPIO0-7 (AppleH11ANEInterface)

Companion to `FINDINGS.md` (command sequence). Answers round-2: what OPENS the "IO"
channel, what state gets armed, what the doorbell physically is, and the GPIO0-7 role.

Sources:
- H13 kext: `receipts/2026-09-18-t6021-engine-layout-mined/kext-h13/AppleH11ANEInterface-9.512.0-macstudio-25G83`
  (this lane's decode; addresses are slice VMAs).
- H14 lane (prior, validated): `receipts/2026-09-22-h14-rpc-protocol/notes/00-findings.md`
  — AppleH11ANEInterface 10.19.2 transport = **RTBuddy channels over RTKit**.
- m1n1: `~/src/m2-m1n1/m1n1/hw/ane.py`, `m1n1/fw/ane.py`.

## 1. What OPENS the "IO" channel — it is FW-published, not kext-created

The kext does not open the channel by writing registers. Sequence in ANE_Init
(all H13, direct reads):

1. FW is powered/loaded/started (the `FW App image...` phase, ANEFirmwareManager).
2. Kext waits for **two interrupts from the ANECPU**. Log strings
   (`__os_log`): `"Got second int from ANECPU (channel description table ready)"`
   @0xfffffe0007472dc1 and `"No second int from ANECPU"` / `"...Retrying power up,
   retries=%d"` @0xfffffe0007472d1d/d40. The second interrupt means: the firmware
   has published its **channel description table**.
3. Table publication: the kext reads two u32s from the FW interface object
   (`ldr x0,[x28,#0x130]; ldr w1,[x19,#0x100]` and `ldr w1,[x19,#0xFC]`, calls
   0x9352efc twice at 0x93215e0-0x93215f8) and combines them
   `orr x1, w, r<<32` — a 64-bit physical address of the FW-shared table. It maps
   it (`bl 0x93236b0` @0x9321608) and copies `count*0x100` bytes into a fresh
   buffer stored at **[dev+0x3BA0]** (`memcpy` @0x9321618; count from [FW-iface],
   byte size at [dev+0x3BA8] @0x93215cc). Evidence chain @0x9321510-0x932161c.
4. Kext resolves channels **by name** in that table: helper 0x9323ae4 walks
   0x100-stride entries, `strncmp(entry_name, name, 0x20)` per entry (0x9323b30-48),
   returns the match index. Lookups: **"IO"** (cstring 0xfffffe0007489333) at
   0x9321c58-70 → result stored **[dev+0xDFC8]** (= the EP used by every CSNE send);
   **"IO_T2H"** (0xfffffe0007489336) at 0x9321ce8-f4 → **[dev+0xDFCC]**.
5. Per-channel client objects are created into the array **[dev+0x3BB0][ep]**
   (8 bytes per ep; consumed by the doorbell fn 0x9325e20
   `ldr x0,[x19, w25, uxtw #3]` @0x9325eac and the suspend-drain loop 0x93280e4
   `"Received %u messages on channel %s after Suspend is completed"`).

Order relative to the CSNE sequence: the table-ready handshake and name lookups
(site 0x9321c58) precede the entire command block (first send at 0x932200c) inside
ANE_Init. Nothing CSNE goes out until "IO" resolves.

H14 generation (10.19.2): the same contract becomes explicit RTBuddy/RTKit — six
named channels `FW_INIT T2F_CMD T2F_HIPRI T2H_SHMEM T2H_CMD T2H_TERM`, kext looks
up `RTBuddyService` by name, each channel = one rtkit endpoint with doorbell-only
message semantics (prior lane HIGH confidence; endpoint numbers owned by
RTBuddyService, not in the ANE kext).

## 2. What gets armed (ring state)

H13 per-EP channel object [dev+0x3BB0+ep*8] fields used by the send path:

| field | role | touched by |
|-------|------|-----------|
| +0x10 | seq toggle (xor'd into entry word) | IOProcessorChannelSend 0x92cbb60-6c |
| +0x14 | entry count (wrap bound) | 0x92cbba4-b8 |
| +0x18 | 64-byte message-entry ring base | 0x92cbb38-44 |
| +0x20/+0x24 | doorbell slot counters (round-robin) | 0x92cbb8c-bc |
| +0x28/+0x2c/+0x30 | stats (sends, +0x2c incremented per send) | 0x92cbbd8-e8 |

Per send: entry = ring + [ch+0x24]*0x40; entry+0x08 = dst ptr; entry+0x10 =
respSize; `dsb st`; entry+0x00 = ([ch+0x10]^1)|epArg; `dsb st`; [ch+0x24] advances
round-robin. These fields are client-side bookkeeping created during the channel
object construction (post table-ready); the kext never reads device registers into
them — the authoritative ring/doorbell hardware state lives on the FW/iop side.

H14 generation: channel descriptor array at dev+0x5c0 stride 0x40 (+0x08 ring size,
+0x18 ring object -> +0x38 base, +0x20 write index, +0x28 queue object), command
bytes carved out of the ring itself, only a 64-bit `(offset|len)` word is
enqueued (`bfi x8, x21, #0x18, #0x18`; bits[0:24) offset, [24:32) len code). HIGH
(prior lane).

## 3. Doorbell sink — what the firmware actually sees

- The command bytes are NOT pushed through aperture MMIO. Per command: slot
  allocated in the 0x40000-byte ANECPU shared buffer (DeviceMemoryManager
  `Allocate` 0x92cc34c; buffer object [dev+0x498], kalloc'd 0x40000, memset,
  IOVA 0x1fb08000 in the capture) and the packet is memcpy'd to
  `base + offset`. Only the doorbell-message ENTRY (above) is produced toward
  the FW.
- The entry write lands in the iop channel machinery (IOProcessorChannelSend
  wrapper 0x92cbae8 in-kext; the sink behind it is XNU's closed IOProcessor
  layer — `com.apple.kpi` imports, no iop code in open-source XNU). On Apple
  hardware that layer delivers **one RTKit endpoint (doorbell) message per
  channel** — established for the 10.19.2 generation by the prior lane (rtkit
  msg semantics per channel; RTBuddy owns the endpoints), and consistent with
  the H13 entry format (offset+size+resp in shared memory, msg only rings).
- **Replay consequence for the M2 bare-metal lane:** ANE-aperture register
  writes alone are invisible to the firmware. The FW is an RTKit image
  (`_rtk_boot`, `_rtk_mtab` sections in selene/styx); it must be woken with an
  RTKit mailbox/doorbell message on the channel's endpoint after the shared
  buffer is filled. m1n1's own ANE driver never faces this because it bypasses
  RTKit and drives the task-queue MMIO directly — it is not a CSNE replay
  reference for the mailbox path. Asahi `apple_rtkit` (already in the prior
  lane's tree at /tmp/asahi-dt) is the working doorbell mechanism.

## 4. GPIO0-7 @ ANE+0x1840048

m1n1 `hw/ane.py`:

```
# for acks w/ rtkit
GPIO0 = 0x1840048, Register32
...
GPIO7 = 0x1840064, Register32
```

- They sit in the ANE CPU block of the aperture and are the ANE firmware's
  RTKit ack/doorbell lines (m1n1 comment). m1n1's driver declares them but its
  shipped ANE path never writes them (it bypasses RTKit); they are the hardware
  the FW itself uses for its rtkit-level handshakes.
- The macOS kext contains no reference to these offsets (no 0x1840048-family
  immediates anywhere in __TEXT_EXEC) — they are not part of the kext's channel
  send path.
- Replay guidance: treat GPIO0-7 as FW-internal ack lines, not the host→FW
  doorbell. The host→FW wake is the RTKit mailbox doorbell of the ANE's
  mailbox/iop node (ADT: ane0 node has no doorbell property; the mailbox is the
  RTBuddy/iop layer — RTBuddy block at ANE+0x1840000 per prior lane). GPIO0-7
  matter only if you emulate the FW's rtkit ack side.

## 5. Replayable CHANNEL-SETUP sequence (bare metal, M2)

1. Power/clk: enable ane + dart-ane ps gates (m1n1 `power_up`, ps writes 0xF to
   PS+0x00..0x30), apply static tunables (m1n1 `apply_static_tunables`).
2. Load FW image (rtkit boot sections) and start the CPU (RVBAR ANE+0x1050000).
3. Wait for the FW's endpoint/channel negotiation: on macOS this is the "second
   interrupt = channel description table ready"; in rtkit terms it is the
   standard START/endpoints handshake (fw announces endpoints, host acks each).
   Bare-metal equivalent: answer the rtkit management endpoint (EP 0) messages
   and accept the announced endpoint set (asahi apple_rtkit does this).
4. Resolve the command endpoint by name from the FW-published table if present
   (macOS names: "IO" for T2F commands, "IO_T2H" for replies); with asahi
   rtkit, use the announced endpoint ids instead.
5. Map the shared command buffer (macOS: 0x40000 bytes, IOVA 0x1fb08000),
   carve the CSNE command packet at a slot offset.
6. Wake the FW with a doorbell message on that endpoint (rtkit msg — this is
   the missing piece that bare register writes do not provide), then poll/read
   the reply slot or the T2H channel (macOS completion is poll+timeout driven,
   `aneFWCommandPollTimerHandler` family; responses carry the original opcode).

Gaps (not statically recoverable, flagged honestly): concrete rtkit endpoint
numbers for the CSNE channels (owned by RTBuddyService/XNU iop — read them at
runtime from the FW's announced endpoint set on your target), and the exact
field layout of the FW-published channel description table beyond entry stride
0x100 with the name at +0x00 (dump it at runtime after boot on the target).

## Evidence anchors (H13 slice unless noted)

- "Got second int..." oslog 0xfffffe0007472dc1; code 0x9321510-0x932161c
- table alloc `count<<8` -> [dev+0x3BA0]: 0x93215c4-0x93215dc
- phys addr combine + map + memcpy: 0x93215e0-0x9321618
- name lookups "IO"/"IO_T2H": 0x9321c58-0x9321c70 / 0x9321ce8-0x9321cf4
  (helper 0x9323ae4 = strncmp scan, stride 0x100)
- channel objects [dev+0x3BB0][ep]: doorbell 0x9325e94-0x9325eac; drain
  0x93280e4-0x93281a4
- per-send entry write + dsb + counter: 0x92cbb2c-0x92cbbcc
- DMM slot alloc + memcpy: 0x932a3f4 (alloc), 0x932a5f8 (bcopy)
- prior-lane h14 transport: receipts/2026-09-22-h14-rpc-protocol/notes/00-findings.md §1
