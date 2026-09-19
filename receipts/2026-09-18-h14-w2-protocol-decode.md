# H14/T6021 ANE RPC protocol decode — W2, static only (2026-09-18)

Verdict: **protocol decoded end-to-end from the extracted binaries; no device touched.**
The kext↔selene RPC is RTKit (MGMT EP 0) for control, then six application endpoints
(EP1..EP6, ring-queue channels "INIT/T2FC/T2FH/T2HS/T2HC/T2HT") whose doorbell is a
packed u64 ring notification; the payload on those rings is the CSNE command stream,
whose complete opcode set is recovered from the firmware's own id→name table and
cross-validated against the fw dispatch switch and the kext header struct. All sizes
and offsets below are cited to a disassembly address, a config-table address, or an
assert string; `[inference]` marks anything not directly evidenced.

Inputs: `receipts/2026-09-18-t6021-engine-layout-mined/` (K14 kext
`AppleH11ANEInterface-10.19.2-mac14j-26A428`, fw `t602x_ane0_fw_selene_rc4x.macho`,
ADT `dtree-j414c.txt`). Artifacts of this lane: `receipts/2026-09-18-h14-w2-protocol-decode/`
(this file's directory: `fw_cmd_table.json`, decoded asm of every function cited, the
decode tooling `disx.py`/`kx.py`/`fwxref.py`). Tooling note: the kext's symtab
n_value fields are extraction-mangled and were NOT usable as addresses; all function
addresses below were recovered by string-xref anchoring (name strings → adrp/add
sites → function starts), then verified by prologue pattern (`bti c; pacibsp`).
63c1d3cf ancestry check: N/A — commit absent in both repos.

## 1. Kext self-log naming map (evidence scaffold)

The kext logs its own function names; the name→code binding is what makes every
address below trustworthy. Example: string "SetupEndpoints" @`0x…74c47f9` is
materialized by `adrp/add` at `0x…95fe764` inside the function at `0x…95fe660`
(cstring `__TEXT.__cstring`, text `__TEXT_EXEC.__text` = `0xfffffe0009500070+0x14b798`).

## 2. RTKit control plane (unchanged from phase 1, confirmed)

- ASC cpu block ANE+0x1600000, CPU_CONTROL +0x1600044 (RUN=0x10), mailbox at
  ANE+0x1608000 family (A2I ctrl +0x110, I2A ctrl +0x114, slots +0x800/0x830)
  — phase-1 receipt §2; unchanged by W2.
- MGMT (EP 0) message types bits[59:52]: HELLO=1, HELLO_REPLY=2, STARTEP=5,
  SET_IOP_PWR_STATE=6, EPMAP=8 (LAST bit 51), SET_AP_PWR_STATE=0xb; versions 11-12
  (Asahi `rtkit.c`). The first exchange bytes for W1 are in
  `omarchy-ane rtkit/h14_rtkit_hello.py` (updated this lane, §7).

## 3. Endpoint map (D2)

**Service**: `ANEHWDevice::InitializeRTBuddyEndpoints` [`0x…95ff824-0x95ffb80`]
picks the RTBuddyService channel name "ANE1Endpoint" (`0x…74c483f`) when socGen==1
else "ANEEndpoint" (`0x…74c484c`), then opens endpoint ids **1..6** (loop `w1 = cnt+7`
from `cnt=-6`, six iterations; the open helper `SetupEndpoints`/endpoint-open at
[`0x…95fe660`] guards `cmp w1, #7; b.lo` — endpoint id must be < 7). Each open
returns an RTBuddyEndpoint object stored in the per-EP record array
`this+0x5c0 + ep*0x40` (record: `+0x18` endpoint obj, `+0x20` u32 ring write offset
(zeroed), `+0x38` byte enabled=1).

**Per-EP config table** [`__DATA_CONST.__const` @ `0x…814e520`, 40 B/entry, read raw]:

| EP | ring size (+8) | name fourcc (+0x10) | ASCII | table enabled (+0x20) |
|----|---------------|---------------------|-------|-----------------------|
| 0  | —             | 0x30303030          | "0000" (empty slot) | — |
| 1  | 0x10000 (64K) | 0x494e4954          | "INIT" | 1 |
| 2  | 0x40000 (256K)| 0x54324643          | "T2FC" | 0 |
| 3  | 0x40000 (256K)| 0x54324648          | "T2FH" | 0 |
| 4  | 0x10000 (64K) | 0x54324853          | "T2HS" | 0 |
| 5  | 0x20000 (128K)| 0x54324843          | "T2HC" | 0 |
| 6  | 0x10000 (64K) | 0x54324854          | "T2HT" | 0 |

(fourcc stored byte-reversed: 0x54324643 = bytes `43 46 32 54` = "CF2T" = "T2FC"
reversed.) Channel-name semantics beyond the fourcc: `[inference]` — T2* reads as
"target-to-host" family, matching the fw→host delivery of EP2/EP3 below; INIT (EP1)
is the controller-channel pair for CSNE_CMD_* submission.

**Ring/queue format** (host→fw send): `rtbuddyEndpointSendMessage(ep, cmdState&)`
[`0x…95f3990-0x95f3cdc`]: bounds `size <= rec[+8]` (config ring size); ring write
cursor `w25 = rec[+0x20]`, wraps to 0 when `cursor+size > size`
(`csel w25, w10, wzr, lo` @`0x…95f3b04`); `memcpy([rec[+0x18]]->+0x38 + w25,
cmdState, size)` @`0x…95f3b20` — the ring buffer base is endpoint-obj+0x38;
then doorbell (below). `rtbuddyEndpointSendInPlace(ep, offset, size, …)`
[`0x…95f3314-0x95f3544`] skips the copy: packs descriptor
`u64 = (offset & 0xffffff) | (size << 24)` @`0x…95f3474-78` and invokes the record's
command gate (rec[+0x28], vtable slot +0x1e8).

**Doorbell word (fw↔host mailbox payload for app EPs)** — 54-bit packed:
`offset[43:0] | size_code[51:44] | unit[53:52]`, unit: 0=code bytes, 1=code·4K,
2=code·1M, 3=code·2M. Decoded in `HandleRTBuddyMessage` [`0x…95feff0`]:
`sbfx #0,#0x2c` offset, `ubfx #0x2c,#8` size code, `ubfx #0x34,#2` unit, size
reconstruction csel-chain @`0x…95ff0d0-0x95ff104`; the identical packing is built by
SetupEndpoints' size-class encoder @`0x…95fe8b0-0x95fe8ec` (`bfi x10, x9b, #0x2c, #8`,
`bfxil x10, x8, #0, #0x2c`, base `1<<52`/`1<<53` selected by whether size < 1 MB).
Receive side validates `offset+size <= rec[+8]` @`0x…95ff128-0x95ff130`.

**fw→host dispatch**: `HandleRTBuddyMessage(self, ep, msg)` accepts ep ∈ [1,6]
@`0x…95ff030-3c`; for **EP 2 and EP 3** (T2FC/T2FH) it delivers
`0x…95ee0d4(self, ring_base+offset, size, 0)` @`0x…95ff148-60` — that function
increments this+0x200 (fw→host cmd counter) and enqueues the ring pointer into the
async work queue (`this+0x9b0` hashtable, @`0x…95ee180-95ee1e0`), later drained by
`processTargetToHostIOCommand`. **EP 6** (T2HT) is polled:
`drainRtbuddyEndpointQueues` [`0x…95ec074`] walks ep records, and on ep6 calls
`receiveMessage` (endpoint obj vtable +0x148) returning the 48-bit
`offset[23:0]|size[47:24]` descriptor (@`0x…95ec108-0x95ec114`).

**Doorbell registers / interrupts**: mailbox registers are the ASC block of phase 1
(ANE+0x1608110/0x1608114 controls, +0x1608800/+0x1608830 slots). ADT j414c: `ane0`
`interrupts: [884]`, `dart-ane0` `interrupts: [885]` (AIC2, level-high per overlay
3d34cfb); RTBuddy ack GPIO block +0x48..+0x64 per phase-1 §2. The kext registers
`aneSlewRateInterruptHandler` as an IOInterruptEventSource handler (symbol +
`rtbuddyEndpointSendInPlace` branch target `[x21+0x404]` device-flag checks);
`[inference]` 884 is the ANE ASC mailbox interrupt the mailbox doorbells ride.

## 4. CSNE_CMD command set (D4) — complete, fw-native

**Opcode table recovered from the firmware**: selene `__DATA.__const` @ **vaddr
0xea430**, 96 entries × 16 B = `{u16 pad; u16 id; u32 name-ptr (fw vaddr); u32 tag}`
(tags: 0x200000 normal, 0x300000 debug-only). Full dump:
`fw_cmd_table.json` artifact. The fw's own dump loop loads it
(`x25 = 0xea000+0x430`, entry compare `ldr x12,[x9]` vs `w8=[x23,#4]` @`0x…39e54-60`,
printed with fmt "%2d: CMD: %#04x [%s]\n" @0xa33fa, ref `0x…39d88`).

| id | command | | id | command |
|----|---------|--|----|---------|
| 0x0000 | START | | 0x0100 | CH_ERROR_NOTIFICATION |
| 0x0001 | STOP | | 0x0101 | CH_POWER_CONTROL |
| 0x0002 | RESET | | 0x0102 | CH_SIGNPOST_NOTIFICATION |
| 0x0003 | CONFIG_GET | | 0x0103 | CH_SIGNPOST_NOTIFICATION_GROUP |
| 0x0004 | PRINT_ENABLE | | 0x0104 | CH_RESET_NOTIFICATION |
| 0x0005 | REG_FILE_LOAD | | 0x0105 | CH_SIGNPOST64_NOTIFICATION |
| 0x0006 | BUILDINFO | | 0x0106 | CH_SIGNPOST64_NOTIFICATION_GROUP |
| 0x0007 | TIMEPROFILE_START | | 0x0107 | CPU_LOAD_NOTIFICATION |
| 0x0008 | TIMEPROFILE_STOP | | 0x0108 | TM_SYNC_ERR_NOTIFICATION |
| 0x0009 | TIMEPROFILE_SHOW | | 0x0200 | LOAD_PROGRAM |
| 0x000a | FW_RUN_MODE | | 0x0201 | UNLOAD_PROGRAM |
| 0x000b | POWER_DOWN | | 0x0202 | CREATE_PROCESS |
| 0x000c | SET_SNE_PMU_BASE | | 0x0203 | TERMINATE_PROCESS |
| 0x000d | SET_SNE_RPC_CHECK_CMD | | 0x0204 | PROCEDURE_CALL |
| 0x000e | RPC_ENABLE | | 0x0205 | LOAD_AFPP |
| 0x000f | PLATFORM_INFO | | 0x0206 | UNLOAD_AFPP |
| 0x0010 | BOOT | | 0x0207 | PROGRAM_INTERFACE_VERSION_CHECK |
| 0x0011 | PING | | 0x0208 | PROCEDURE_CALL_CACHE_REQUEST |
| 0x0012 | CONFIG_GET_EXT | | 0x0209 | PROC_CALL_TRIGGER_CACHE_REQUEST |
| 0x0013 | POWER_DEVICE_ON | | 0x020a | PROC_CALL_RECYCLE_OUTPUT_BUFFER |
| 0x0014 | POWER_DEVICE_OFF | | 0x020b | PROC_CALL_INVALIDATE_CACHE_REQUEST |
| 0x0015 | IPC_ENDPOINT_SET | | 0x020c | PROC_CALL_WITH_CUSTOM_BARS |
| 0x0016 | IPC_ENDPOINT_UNSET | | 0x020d | PREMAP_BUFFER |
| 0x0017 | CH_INFO_GET | | 0x020e | PROC_CALL_CACHE_REQ_WITH_CUSTOM_BARS |
| 0x0018 | CH_BUFFER_RECYCLE_MODE_SET | | 0x020f | PROC_CALL_CACHE_REQ_WITH_SHARED_EVENTS |
| 0x0019 | CH_BUFFER_RECYCLE_START | | 0x0210 | FORCE_DISABLE_CACHE_REQUESTS |
| 0x001a | CH_BUFFER_RECYCLE_STOP | | 0x0211 | PROCEDURE_CALL_WITH_SIGNAL_EVENTS |
| 0x001b | CH_BUFFER_RETURN | | 0x0212 | SET_ACTIVE_CACHE_REQUEST_IN_GROUP |
| 0x001c | CH_BUFFER_POOL_CONFIG_GET | | 0x0213 | SET_SIGNAL_EVENTS |
| 0x001d | CH_BUFFER_POOL_CONFIG_SET | | 0x0300 | PROGRAM_EVENT |
| 0x001e | CH_DATA_FILE_LOAD | | 0x0301 | USER_EVENT |
| 0x001f | CH_PROPERTY_WRITE | | 0x0302 | DBG_EVENT |
| 0x0020 | CH_PROPERTY_READ | | 0x0303 | DATA_CHAINING_EVENT |
| 0x0021 | TRACE_ENABLE | | 0x0304 | PREFETCH_DSID_EVENT |
| 0x0022 | RESOURCE_INFO_GET | | 0x0305 | SECURE_MODE_EVENT |
| 0x0023 | STATS_BUFFER_SIZE_GET | | 0x0400 | REQUEST_PROGRAM_ID |
| 0x0024 | SUSPEND | | 0x0401 | RETURN_PROGRAM_ID |
| 0x0025 | DSID_SET | | 0x0402 | REQUEST_PROCESS_ID |
| 0x0026 | MCACHE_SIZE_GET | | 0x0403 | RETURN_PROCESS_ID |
| 0x0027 | SECURE_MODE_START | | 0x0404 | INFERENCE_CALL |
| 0x0028 | SECURE_MODE_STOP | | 0x7000 | BACK_CHANNEL_RPC |
| 0x0029 | SET_SNE_PMU_BASE2 | | 0xff00 | DEBUG_COMMAND_DATA_CHECK (0x3 tag) |
| 0x002a | IPC_ENDPOINT_SET2 | | | |
| 0x002b | IPC_ENDPOINT_UNSET2 | | | |
| 0x002c | CH_DATA_FILE_LOAD2 | | | |
| 0x002d | SET_DYNAMIC_POWERGATE | | | |
| 0x002e | ANE_DEFAULT_SETTING_SET | | | |
| 0x002f | INIT_SHARED_EVENT_INFO | | | |
| 0x0030 | EXCLAVE_MODE_START | | | |
| 0x0031 | EXCLAVE_MODE_STOP | | | |
| 0x0032 | QUIESCE_STATE | | | |
| 0x0033 | CPU_LOAD_GET | | | |
| 0x0034 | SECURE_MODE_RESUME_TRANSITION | | | |
| 0x0035 | RESUME | | | |

Names cross-checked against the kext cstring block `CSNE_CMD_START`..`CSNE_CMD_
DEBUG_COMMAND_DATA_CHECK` (`0x…74c2e11-0x…74c3887`, same order — the kext carries
the same enum as literals).

**Cross-validation (fw dispatch switch)**: fw compares a 16-bit header load against
the same ids — `ldrh`+`cmp` sites: 0x404 @0x4af60, 0x208 @0x55db4/0x56e88/0x57ac0/
0x5834c/0x58388/0x586e8/0x587b4, 0x204 @0x58f10, 0x200 @0x4e46c, 0x201 @0x47390/
0x473d4/0x6e028/0x75758/0x7722c, 0x203 @0x49264, 0x20c @0x4b14c/0x54090, 0x20e
@0x70808/0x70854, 0x20f @0x57df0/0x70f64, 0x300 @0x3a800, 0x209 @0x4c1d4. So the
**fw-side `sCSneCmdHdr.id` is u16 at header offset 0**.

**Wire header structs**:
- Kext-side `sCSneControllerCmdHdr` — 0x24 bytes (0x20 copied as q0/q1 + u32@0x20,
  in the wrapper `0x…95f3fc4` @`0x…95f404c-0x95f4054`: `ldp q0,q1,[x21]` → obj+0x28,
  `ldr w8,[x21,#0x20]` → obj+0x48); `id` is **u32 at +0x8** (read in
  `processTargetToHostIOCommand` @`0x…959cc0c/959cc18`, compared against the
  expected-id field `this+0x8d0`). `[inference]` the kext controller header wraps
  (not equals) the fw u16-id header; the ring copy is byte-transparent so the fw
  parses its own u16@0 layout out of the same bytes.
- `sCSneCmdProcedureCall` — fields from fw assert strings: `programId`, `procedureId`,
  `numIoBuffers` ("CANE_SUB_PACKET_CMD_PROCEDURE_CALL program id %d, procedureId %d,
  numIoBuffers %d"), `priority` ∈ [0,7] (`(pCmd->priority >= 0)&&(pCmd->priority <= 7)`),
  `size % sizeof(sCSneCmdProcedureCall) == 0` (commands form arrays in the ring),
  content-type selector `eCSneCmdProgramProcedureContentType_{0,3,4}`.
- `sCSneCmdProcedureCallCopyContainer` — custom-bars variant:
  `customExecuteOrderArrayOffset + nbrOfCustomExecuteOrder*4 <= sizeof(container)`.
- Cache-request family: `cmd->priority ∈ [2,7]`; trigger vs group ordering via
  u64 `execTimestamp` / `lastTriggerExecTimestamp` with top-nibble wraparound mask
  `0xF000000000000000`; buffer-recycle rings: `pCmd->readRingBufferAddr/Len`,
  `writeRingBufferAddr/Len` (both must be non-zero pairs).
- Response-size family: `sCSneCmdConfigGet`, `sCSneCmdPlatformInfo`,
  `sCSneCmdPowerSupplyControl`, `sCSneCmdStatsBufferSize(V0)`, `sCSneCmdTraceEnable`
  (`*outsize >= sizeof(...)`) — GET-class commands write into a caller-provided
  response buffer.
- fw channel rings (`CIOPRingBuffer`, `./ffw/ffw/CIOPRingBuffer.cpp`): header
  `{version>>16 == IOP_RINGBUFFER_VERSION | _V2, _wrptr < dataBufSize,
  _rdptr < dataBufSize, _size == dataBufSize}` — i.e. `{u32 hdr/version; u32 wrptr;
  u32 rdptr; u32 size; data[]}`; exact field order `[inference]` from assert text.

## 5. Shared-memory handshake (D3)

- `ANEMessage` — kalloc 0x28 (40 B) host-side OSObject (mod-init type-view block
  `0x…95a825c+`: ANEMessage 0x28, ANEPowerOnMsg 0x28, ANENotificationMsg 0x28,
  ANERequestCompletionMsg 0x40, ANEProgramEventMsg 0x88, ANEDebugEventMsg 0x50,
  ANEPowerMsg 0x30, ANEFwToFwSignalMsg 0x28, ANEFWRpcMsg 0x58). Fields read in
  `handleSharedMemoryRequest_gated(msg)` [`0x…95f98c8-0x95f9c8c`]:
  `u32 cmd @+0xc` (== 7 selects the shared-memory path @`0x…95f99a4`),
  `u32 op @+0x24` (0/1/2 = map-op selector @`0x…95f99b0-c0`), `u64 param @+0x30`
  (loaded for op==0 @`0x…95f99c8`). Handler sets `this+0x8cc` busy byte, calls
  `disableLowLatency`, builds two completion blocks (retarget stack frames
  `x29-0x88`/`x29-0xa8`).
- `FWSharedMemoryRequest` — OSObject, **0x58 bytes** (kalloc-type view registered
  @`0x…95f5a14` and @`0x…95fd588`, name string `0x…74c438a` "FWSharedMemoryRequest";
  MetaClass/gMetaClass/superClass symbols present). Field-level layout:
  **[PARTIAL]** — construction sites route through PAC-authenticated allocators;
  only the size and the class wiring are proven. Its role (request record for
  surface map/unmap between ANEMessage and dartMapMemoryDescriptor) is
  `[inference]` from call-graph position.
- `processTargetToHostIOCommand(self, hdr, buf, size)` [`0x…959c194-0x959d85c`,
  0x16c8 B]:
  1. increments `this+0x208` (fw→host command counter);
  2. translates the fw's buffer IOVA: `0x…95f73cc(self, buf, 0xc, &range, 0)` →
     `range = {u64 base@0, u64 size@0x38}`; failure sentinel `0xbadadd…` check
     @`0x…959c214-28`;
  3. reads `sCSneControllerCmdHdr.id` (u32@+8), compares to `this+0x8d0`
     (expected/in-flight id — the synchronous command/response matcher);
  4. bounds-checks payload extents `hdr+0x30` and `hdr+0x40` against
     `range.base + range.size` @`0x…959c794-959c82c` → so the command block
     carries payload offsets at +0x30/+0x40;
  5. on id match routes through `0x…95f3fc4` (alloc ANEMessage-class object, copy
     hdr bytes, enqueue `this+0xd0` for the gated handler), which is where
     `ANE_HandleRPCRequestFromFWE(…, ANESharedMemorySurfaceParams*,
     sCSneControllerCmdHdr*, u8 ch)` picks up shared-memory requests
     (surface params resolved via `FindSharedMemorySurface`/
     `SharedMemorySurfaceTargetPhysicalAddressToHostVirtualAddress` symbols).
- Mapped-surface plumbing: `dartMapMemoryDescriptor` /
  `dartUnmapMemoryDescriptor` / `makeMemoryVisible` /
  `AllocateSharedMemorySurface_gated` / `SetupFWInitBootArgs` (all symbols;
  boot-args surface = ANESharedMemorySurfaceParams, the fw learns its heap/IO
  windows from SCRATCH0-7 pre-release per phase-1 §2.5).

## 6. ANE DART quartet (D5)

From `dtree-j414c.txt` (ADT), node `dart-ane0` @line 11508:
- `compatible: "dart,t8110"` (kernel `apple_dart_of_match` binds t8110 rows only →
  overlay carries dual-compatible per b877b87), `device_type: "dart"`,
- **four reg windows**: `0x85800000 / 0x85810000 / 0x85820000 / 0x85804000`,
  each sz 0x4000 (as printed by the dtree tool; live overlay uses the
  0x2_85800000 family, proven on device by 3d34cfb),
- `page-size: 0x4000` (16K), `vm-base: 0x10000000000`, `vm-size: 0x30000000000`,
  `sid: 0xf00000000` (stream-id mask), `dart-options: 37`, `bypass-15: nil`
  (stream 15 no bypass), `error-reflector: 0x29e09c000`,
- `interrupts: [885]`, `clock-gates/power-gates: [507]`, `flush-by-dva: 0`,
- child `mapper-ane0` (`device_type: "dart-mapper"`, `compatible:
  "iommu-mapper"`, `reg: 0`, phandle 363) — and `ane0` carries
  `iommu-parent: [363]`: **all ANE DMA goes through dart-ane0 stream/mapper 0**.
- `ane0` node: `device_type: "ane"`, `interrupts: [884]`, reg
  `0x84000000+0x2000000` (engine window as printed; live base 0x2_84000000),
  `0x8e080000+0x4034` (pmgr islands), `0x8e08c000+0x4000` (SET window per ADT).
- `dapf-instance-0` (DART protection filters) rows: `0x28e084000`,
  `0x28e080260`, `0x38545c000`, `0x406468000`, `0x228545c000` (each len 3-0x33) —
  stream-scoped filter windows beyond the engine block
  `[inference: fw-visible aux regions, die/stream-tagged addressing]`.
- `instance:` prop decodes to transaction types `TRAD DARTLLT TRAD DARTBRW TRAD
  DARTBWR FPAD DAPFLLT` (read/LLT translation, read bypass, write bypass, filter).

**Which dart maps which fw stream**: single die (die-id 0), one ANE dart, mapper
reg 0, sid mask 0xf00000000 with stream-15 bypass disabled — the fw's DART-visible
streams are the four translation instances above (LLT translate / read bypass /
write bypass / filter) on the one dart; per-endpoint channel rings do not get
separate darts. `[inference]` on the stream-number ↔ channel split (not decoded:
would need the fw page tables at runtime).

## 7. W1-prep: exact byte sequences for `h14_rtkit_hello.py`

Updated in `omarchy-ane rtkit/h14_rtkit_hello.py` (docstring; no code change needed
— the exchange loop already echoes EPMAP dynamically). Sequence against the decoded
protocol:
1. RX on I2A (+0x1608830/0x8838): `{msg0, msg1=ep}` with `ep==0`, `msg0` bits[59:52]==1
   → HELLO, `min=msg0[15:0]`, `max=msg0[31:16]` (expect 11/12 for selene).
2. TX on A2I (+0x1608800/0x8808): `HELLO_REPLY` = `(2<<52) | (ver<<16) | ver` with
   `ver = min(12, max)` — one u32 pair, ep=0.
3. fw then streams EPMAP (`(8<<52) | (base<<32) | bitmap` + LAST bit 51): reply
   `(8<<52)|(base<<32)` with MORE (bit 0) or LAST (bit 51) per entry. Expected
   bitmap includes the RTKit service EPs **and** app EPs 1..6 (INIT/T2FC/T2FH/
   T2HS/T2HC/T2HT) — the kext's EP set above; STARTEP (5<<52|ep) per enabled ep.
4. App-channel traffic after that is NOT MGMT: per-EP ring doorbell u64
   `offset[43:0] | size_code[51:44] | unit[53:52]` (§3), payload = CSNE commands
   (§4) — e.g. first documented RPC: `CSNE_CMD_PING` (0x11) or `CSNE_CMD_BUILDINFO`
   (0x06) on the INIT channel, response via T2F* channels.
5. All writes remain inside the A2I mailbox slots; no other register is touched.

## 8. Method + tooling (for reproducibility)

- `disx.py` — Mach-O section/symbol loader; kext `n_value` payload decoding
  (see below), annotated arm64 disasm.
- `kx.py` — kext-wide `adrp/add` xref index (string-anchored function discovery).
- `fwxref.py` — same for the position-independent selene fw (linear resync scan).
- `fw_cmd_table.json` — the 96-entry CSNE opcode table as parsed from 0xea430.
- `asm/*.asm` — full annotated disassembly of every function cited above.
- Known-tooling-fact: the K14 kext symtab `n_value` fields are mangled by the
  extraction (payload = `(v>>16)&0xffffff` matches section offsets for ~70% of
  symbols only; low 2 bits noise). Symbols were used ONLY as a name inventory;
  every address in this receipt comes from xref-anchored disassembly.

## 9. What remains (honest gaps)

- `ANEFWRpcMsg`/`FWSharedMemoryRequest` field-level layouts: sizes (0x58/0x58) and
  class wiring proven; individual field offsets not recovered — construction paths
  run through PAC'd allocators and stub-routed calls. Marked [PARTIAL] rather than
  guessed.
- Endpoint fourcc semantics (which CSNE channel rides which T2F* ring) beyond
  EP2/EP3=fw→host commands and EP6=poll: `[inference]`.
- sCSneCmdHdr full field order beyond `id@0 (u16)` and the assert-evidenced fields.
- All of it needs the W1 live exchange to confirm endianness/layout on wire.

Commit plan: this receipt + artifacts on ane-linux-experiments `main`;
protocol constants added to `omarchy-ane feat/t6021-rtkit-w2`
(rtkit/h14_rtkit_hello.py W1-prep doc update). Static only — jw14m2 untouched.
