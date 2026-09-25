# H14 ANE firmware RPC protocol — static findings (2026-09-22)

Binary under analysis (all addresses below):
- Kext: `receipts/2026-09-18-t6021-engine-layout-mined/kext-h14j/AppleH11ANEInterface-10.19.2-mac14j-26A428`
  (macOS 26A428, t6021). Text base `0xfffffe0000000000` + `__TEXT_EXEC.__text`.
- FW: `receipts/2026-09-18-t6021-engine-layout-mined/fw-h14j-selene/t602x_ane0_fw_selene_rc4x.macho`
- H13 control FW: `w2/h13_ane_fw_styx_j5x.macho`

Confidence: HIGH = read directly from binary at cited address; MEDIUM = prior-lane
artifact or single corroboration; LOW = inference, needs hardware confirmation.

## 1. Transport: RTBuddy channels over RTKit, not raw rtkit messages

Kext cstring table `@0xfffffe00074c5170` names **six channels**:

```
FW_INIT  T2F_CMD  T2F_HIPRI  T2H_SHMEM  T2H_CMD  T2H_TERM
```
(HIGH; the T2F_*/T2H_* prefixes = target-to-fw / target-to-host.)

Each channel is a **shared-memory ring**, not a 64-bit payload mailbox.
Evidence `HandleRTBuddyMessage` `@0xfffffe00095feff0` (w2/asm/HandleRTBuddyMessage_real.asm):

- Channel descriptor array at `dev+0x5c0`, stride 0x40; fields: `+0x08` ring size,
  `+0x18` ring object (→ `+0x38` base pointer), `+0x20` write index, `+0x28` queue object.
- Ring message = one 64-bit word, decoded `@0x95ff0d4-0x95ff100`:
  - bits [0:28) — offset into ring buffer
  - bits [28:36) — size code
  - bits [36:38) — size class: 0 ⇒ `code<<12`, 1 ⇒ `code<<13`(inferred), 2 ⇒ `code<<20`,
    3 ⇒ `code<<21` (csel chain `@0x95ff0e0-0x95ff100`). HIGH for class 0/2, MEDIUM for 1/3.
- EOF / drain marker: incoming word with `offset == wridx && size == ringSize` logs
  "queue drained" and sets `desc[0x38]=1` (`@0x95ff218-0x95ff27c`). HIGH.
- Send side `rtbuddyEndpointSendMessage @0xfffffe00095f3990`: packs
  `w = (off & 0xFFFFFF) | (len << 24)` (`bfi x8, x21, #0x18, #0x18` `@0x95f3bf4-8`),
  calls queue vtable `+0x1e8` (`@0x95f3c14-30`). Retry wrapper
  `rtbuddyEndpointSendRetry`, logging wrapper `rtbuddyEndpointSendWithLog`. HIGH.
- Commands are **carved out of the ring itself**: `ANEFirmwareCommandBuffer` alloc
  helper `@0xfffffe00095e45d4` (mallocs 0x38-byte wrapper, then takes a region from
  ring at `dev+0x968`/`dev+0x980` via `@0xfffffe00095e1918`). So T2F_CMD payload
  bytes live in ring memory and only the (offset,len) word is enqueued. HIGH.

Mapping to mainline `apple_rtkit` (`/tmp/asahi-dt/include/linux/soc/apple/rtkit.h`):
these channels ride RTKit endpoints owned by an `RTBuddyService` IOService
(cstring `@0x74c48f6`; kext looks it up by name). RTBuddy protocol itself is not in
mainline; treat each channel as one rtkit endpoint with doorbell-only msg semantics.
**The concrete rtkit endpoint numbers are NOT recoverable from the ANE kext alone**
(they are owned by RTBuddyService) — hardware/mbox trace or the RTBuddyService
kext needed. MEDIUM assumption: endpoints are small contiguous ids.

## 2. Command header (sCSneControllerCmdHdr)

From `sendSetupCmd @0xfffffe00095e4314` (log tag string "sendSetupCmd" `@0x74c3a41`):

| off | width | field | evidence |
|-----|-------|-------|----------|
| +0x04 | u16 | CSNE cmd id | `strh w9,[x8,#4]` with 0x400/0x401/0x402/0x403 `@0x95e4398/0x95e43e4/0x95e4480/0x95e4440` |
| +0x06 | u8 | flags: bits[0:5] preserved from prior byte, bits[5:7] set to 1 (0x20 mask) | `bfxil w24,w9,#0,#5; strb w24,[x8,#6]` `@0x95e439c-a4` |
| +0x07 | u8 | zeroed | `strb wzr,[x8,#7]` |
| +0x1c | u32 | param0 (returned for 0x400 replies) | `str w9,[x8,#0x1c]` `@0x95e449c`; reply read `@0x95e4548` |
| +0x20 | u32 | param1 (0x402/0x403 two-arg cmds) | `@0x95e4404` / reply `@0x95e45c0` |

Typical whole command message sizes: **0x20 or 0x24 bytes** (alloc sizes `mov w1,#0x20/0x24`
`@0x95e4378/0x95e43c4`). Buffer bytes [0x00..0x04) and [0x08..0x1c) were not written
by this function — they are zeroed or filled by the fw command buffer constructor;
exact contents = gap (see README). All HIGH (direct stores).

## 3. Opcode table

- Name set: **96 `CSNE_CMD_*` names in selene cstrings 0xa1588–0xa1fef** (listing in
  notes/02-opcodes.md). H13 styx fw contains **97**, a strict superset (extra:
  `CSNE_CMD_IPC_ENDPOINT_TYPE_DATA_CHAINING`, which also exists in selene as a const
  name, not a command). Conclusion: the command namespace is generation-stable
  H13→H14. HIGH.
- Numeric ids: `w2/fw_cmd_table.json` (prior lane artifact): 0x0000 START …
  0x0404 INFERENCE_CALL, 0x7000 BACK_CHANNEL_RPC, 0xff00 DEBUG_COMMAND_DATA_CHECK.
- Independent corroboration in the kext: immediates `#0x400..#0x404` appear both at
  send sites (`mov w1,#0x401 @0x959ff74`, `#0x402 @0x95a04cc`, `#0x403 @0x95a06c4`)
  and in `sendSetupCmd` dispatch; `#0xff00` at `@0xfffffe0009623b58`. → ids
  **0x400–0x404 and 0xff00: HIGH**; remainder of the table: MEDIUM (trust prior
  decode, not yet independently re-derived from the fw dispatcher).

Key ids for a driver port (MEDIUM unless noted): START 0x0000, BOOT 0x0010,
PING 0x0011, POWER_DEVICE_ON 0x0013, POWER_DEVICE_OFF 0x0014,
IPC_ENDPOINT_SET 0x0015, IPC_ENDPOINT_SET2 0x0198* (name only, id unverified),
PROCEDURE_CALL 0x0400 (HIGH), RETURN_PROGRAM_ID 0x0401 (HIGH),
REQUEST_PROCESS_ID 0x0402 (HIGH), RETURN_PROCESS_ID 0x0403 (HIGH),
INFERENCE_CALL 0x0404 (HIGH), BACK_CHANNEL_RPC 0x7000, DEBUG 0xff00 (HIGH).
(*id 0x198 is a guess from name position — treat as unknown; use name-anchored
search in the fw dispatcher instead.)

## 4. FW→host dispatch

`HandleRTBuddyMessage @0x95feff0`, per channel index:
- idx 2,3 → `0x95ee0d4(dev,ptr,len,0)` — buffer delivery (shmem/HIPRI data) — HIGH
- idx 4 → `0x95f9400` — fw→host shared-malloc requests (processSharedMallocRequest*) — HIGH
- idx 5 → `0x959c194` — command responses (adjacent to processTargetToHostIOCommand
  `0x959c290`) — MEDIUM-HIGH
- idx 6 → `0x95e26a0` — fw debug/logging pump with a 50 ms pacing gate
  (`cmp x8,#0x2faf080` ns `@0x95ff508-14`) — MEDIUM

Notification payload structs seen in kext symbols (names only): `sCSneCmdChResetNotication`,
`sCSneCmdChSignpostNotication`, `sCSneCmdChSignpost64Notication`, matching fw cmds
`CSNE_CMD_CH_{RESET,SIGNPOST,SIGNPOST64}_NOTIFICATION` — fw→host events arrive as
CSNE cmds on T2H_CMD and are handled in `processTargetToHostIOCommand`.

## 5. Buffers / shared memory

- Surfaces are described to fw as **device-VA (DVA)** — log strings:
  "allocated surface at DVA %llx", "Error: Could not allocate at the requested
  dvaOffset", "dartMapMemoryDescriptor failed" (`__cstring @0x74c48xx region`). HIGH.
- `ANEHWDevice::aneAddressToHostAddress(y)` exists — fw addresses are translated
  through the DART mapping table host-side. HIGH (symbol).
- Shared memory publication to fw is fw-driven: fw sends a shared-malloc request on
  channel 4, kext services it (`processSharedMallocRequestEndpoint`,
  `sharedMemoryRequestCb`, `FWSharedMemoryRequest`; param struct
  `ANESharedMemorySurfaceParams`, cstring `@0x74c436c`). Layout NOT yet recovered
  (function-level disasm pending; see README gap list). MEDIUM.

## 6. Completion / errors

- Completion is **polled + signposted, not interrupt-driven**: symbols
  `aneFWCommandPollTimerHandler`, `checkForTimedOutCommand_gated`,
  `HandleFirmwareTimeout`, `aneFirmwareCommandTimeout` (`@0x74c4aa6`),
  `cancelFirmwareCommand`, `extendAllCommandTimeouts(j,y)`, plus
  `panicOnRequestTimeout` flag (`@0x74c95be`). HIGH that polling is the mechanism;
  the poll interval constant not yet extracted.
- `ANERequestTimeoutMsg`, `ANEHWDeviceTimeoutMsg`, `ANEFirmwareClientLoggingMsg`
  message classes (cstring `@0x74bea65-0x74beac5`) — timeout/logging surfaced as
  kext-internal messages. HIGH.
- Per-command completion reply: responses arrive on T2H_CMD (channel 5) as a
  CSNE command whose hdr.cmd matches the original cmd id or a `*_NOTIFICATION`
  id; the reply param0 lands at hdr+0x1c (symmetric with sendSetupCmd). MEDIUM.

## 7. Firmware image

- t6021 blob: `t602x_ane0_fw_selene_rc4x` (im4p-wrapped Mach-O; extracted macho on
  disk). Name selection strings in kext: "pre-loaded", "ctrr-disabled", "ctrr-unlocked"
  (`__cstring @0x74c4940` region) + symbols `ANE_ctrrReloadFw`, `ANE_LoadFirmware(Pv,j,j,P)`,
  `ANE_ExclaveLoad(j,y)` — the CTRR (cache/CTRR lock) state decides reload path. MEDIUM.
- FW image layout (selene macho sections): `__DATA._rtk_boot` @0x104000,
  `_rtk_boot_l1` @0x190100, `_fwinfo` @0x190000, `_rtk_mtab` @0x190180, standard RTKit
  stack/tunables/patchbay sections. Entry/boot args follow the RTKit convention
  (`_rtk_boot`); the kext passes `FW_INIT`-era boot args via
  `SetupFWInitBootArgs(ANESharedMemorySurfaceParams*)` (symbol `@kext14.syms`) —
  function body not yet decoded; field layout of ANESharedMemorySurfaceParams NOT
  recovered. MEDIUM/gap.
- Known host-accessible regions from the earlier lane stand: RVBAR block +0x1050000,
  RTBuddy +0x1840000 (see receipts/2026-09-18-t6021-engine-layout-mined).

## Not recoverable statically (needs hardware or RTBuddyService kext)

1. Concrete rtkit endpoint numbers for the six channels (owned by RTBuddyService).
2. Per-command payload layouts beyond the 0x1c/0x20 params and the 0x20/0x24 sizes.
3. ANESharedMemorySurfaceParams / FWSharedMemoryRequest field layout.
4. Whether sendSetupCmd flag bits[0:5] are an endpoint/queue selector (likely — verify).
5. Poll-timer interval and exact timeout constants.
6. Initial FW_INIT handshake field values (what boot args the fw actually reads).
