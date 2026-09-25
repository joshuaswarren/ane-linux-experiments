# H14 (M2/T6021) ANE firmware RPC protocol — recovered statically

Date: 2026-09-22. Pure static analysis; no hardware touched. Consumer: T6021RtkitPort.

Binaries (all in `receipts/2026-09-18-t6021-engine-layout-mined/`):
- `kext-h14j/AppleH11ANEInterface-10.19.2-mac14j-26A428` — macOS 26A428 ANE kext (t6021)
- `fw-h14j-selene/t602x_ane0_fw_selene_rc4x.macho` — t6021 ANE firmware
- `w2/h13_ane_fw_styx_j5x.macho` — H13 control firmware
- `w2/asm/*.asm`, `w2/fw_cmd_table.json` — prior-lane extraction (method validated vs H13)

Detailed findings with per-fact evidence: `notes/00-findings.md`; opcode table: `notes/02-opcodes.md`.

## Summary per item

1. **ANEFWRpcMsg / message framing** — There is no single wire struct. Messages ride six named
   RTBuddy channels (`FW_INIT T2F_CMD T2F_HIPRI T2H_SHMEM T2H_CMD T2H_TERM`, cstring table
   `@0x74c5170`), each a shared-memory ring. The mailbox word is
   `{offset[0:28) | sizeCode[28:36) | sizeClass[36:38)}` with size = code<<{12,13,20,21} by
   class; EOF word = offset==wridx && size==ringSize. Commands are carved out of the ring
   (`ANEFirmwareCommandBuffer` alloc `@0x95e45d4` → ring take `@0x95e1918`).
   HIGH except size classes 1/3 (MEDIUM). `ANEFWRpcMsg` itself (OSObject, instance 0x58 bytes,
   vtable `@0xfffffe00095a6d6c`) is a kext-side wrapper; message classes ANEMessage(0x28),
   ANERequestCompletionMsg(0x40), ANEProgramEventMsg(0x88) etc registered `@0x95a825c`.

2. **Opcode set** — 96 `CSNE_CMD_*` names in selene cstrings 0xa1588–0xa1fef, all present in
   H13 styx too (97 = strict superset): namespace is generation-stable. HIGH.
   Numeric ids from `w2/fw_cmd_table.json`: 0x0000 START, 0x0010 BOOT, 0x0011 PING,
   0x0200 LOAD_PROGRAM, 0x0204 PROCEDURE_CALL, 0x0400–0x0404 PROGRAM/PROCESS ID + INFERENCE_CALL,
   0x7000 BACK_CHANNEL_RPC, 0xff00 DEBUG. Ids 0x400–0x404 + 0xff00 independently corroborated
   by kext immediates (`mov w1,#0x401` etc.) — HIGH; all other ids MEDIUM (single source).
   Full table in notes/02-opcodes.md.

3. **RTKit endpoints** — Channels are owned by an `RTBuddyService` IOService; each channel is
   one rtkit endpoint with doorbell-only semantics (mainline `apple_rtkit` model). Concrete
   endpoint NUMBERS are not in the ANE kext — gap requiring RTBuddyService kext or mbox trace.

4. **Init/handshake** — Not fully recovered. Order evidence: power-up (`SetRTBuddyPowerState`,
   `EnableANEClocksAndPower`) → `InitializeRTBuddyClient`/`InitializeRTBuddyEndpoints`/
   `EnableRTBuddyEndpoints(const char* names, u8 count)` (channel descriptors at dev+0x5c0,
   stride 0x40) → `SetupFWInitBootArgs(ANESharedMemorySurfaceParams*)` → setup cmds via
   `sendSetupCmd` (0x400/0x402 id requests, replies carry values at hdr+0x1c/+0x20) before
   INFERENCE_CALL is legal. Timeout/poll: `aneFWCommandPollTimerHandler`,
   `HandleFirmwareTimeout`, `aneFirmwareCommandTimeout`. MEDIUM.

5. **Buffers/surfaces** — described to fw as DVAs (dart-mapped device addresses; log strings
   "allocated surface at DVA %llx", "dvaOffset"); `aneAddressToHostAddress` reverses the map
   host-side. Shared memory is fw-driven: fw asks on channel 4 (shared-malloc request), kext
   services via `ANESharedMemorySurfaceParams` (layout NOT recovered — gap). HIGH on DVA model.

6. **Completion/errors** — poll-timer based (`aneFWCommandPollTimerHandler`,
   `checkForTimedOutCommand_gated`, `HandleFirmwareTimeout`, `cancelFirmwareCommand`,
   `extendAllCommandTimeouts`), not interrupt-driven. FW→host events are CSNE commands on
   T2H_CMD: CH_ERROR_NOTIFICATION 0x0100, CH_RESET_NOTIFICATION 0x0104, SIGNPOST(_64)
   0x0102/0x0105, TM_SYNC_ERR 0x0108, plus processCommandResponseEyyy. `panicOnRequestTimeout`
   opt exists. Reply param placement symmetric with header (+0x1c/+0x20). MEDIUM-HIGH.

7. **Firmware image** — t6021 uses `t602x_ane0_fw_selene_rc4x` (im4p→Mach-O). Image follows
   RTKit conventions (`__DATA._rtk_boot` @0x104000, `_rtk_boot_l1`/`_fwinfo`/`_rtk_mtab`
   @0x1900xx). Kext load path: `ANE_LoadFirmware` / `ANE_ctrrReloadFw` / `ANE_ExclaveLoad`,
   gated on boot-arg strings "pre-loaded"/"ctrr-disabled"/"ctrr-unlocked". Host regions from
   prior lane stand: RVBAR +0x1050000, RTBuddy +0x1840000. MEDIUM.

## Needs hardware observation / further static work

1. rtkit endpoint numbers for the six channels (RTBuddyService kext or mailbox trace).
2. `ANESharedMemorySurfaceParams` / FWSharedMemoryRequest field layout (SetupFWInitBootArgs body).
3. Per-command payload layouts beyond the generic header (+0x1c/+0x20) and 0x20/0x24 sizes.
4. Header bytes 0x00–0x04 and 0x08–0x18 of the 0x20-byte command header (likely: magic/seq,
   channel/proc fields — constructor site not yet located).
5. Numeric ids other than 0x40x/0xff00 (re-derive from fw dispatcher to upgrade to HIGH).
6. Poll interval + timeout constants; sendSetupCmd flag bits[0:5] semantics (queue selector?).
7. FW_INIT channel handshake contents (what fw reads at first contact).
