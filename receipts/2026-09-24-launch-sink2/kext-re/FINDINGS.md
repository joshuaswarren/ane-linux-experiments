# AppleH11ANEInterface 9.512.0 (macstudio, macOS 25G83) — CSNE cold-start command sequence

Field-for-field static extraction. Analysis target:
`receipts/2026-09-18-t6021-engine-layout-mined/kext-h13/AppleH11ANEInterface-9.512.0-macstudio-25G83`
(arm64e MH_KEXT_BUNDLE, cputype 0x0100000C, cpusubtype 0xC0000002).

NOTE ON THE STATED ASSET: `BootKernelExtensions.kc` in the repo root is **x86_64**
(Darwin 25.6.0, xnu-12377.161.14~5/RELEASE_X86_64; header cputype 0x01000007) and does
NOT contain the ANE kext (zero hits for `AppleH11ANEInterface`/`CSNE`/`SET_SNE_PMU_BASE2`
anywhere in its 67.5 MB; its 204 LC_FILESET_ENTRY names include no ANE kext). The
extracted 9.512.0 arm64e slice above is the correct artifact and is what this document
decodes. The captured cold-start log (`/tmp/asc-capture-artifacts/run-205806/logstream.txt`)
is from this same kext version.

All addresses below are the slice's own VMAs (KC-load bases:
`__TEXT` 0xfffffe000744bf30, `__TEXT_EXEC` 0xfffffe0009284260, file off 0x48000).
Function names come from the preserved `kext13.syms` (LINKEDIT) symbol table.

## 1. Command packet format (ANEFirmwareCommand, as copied to the wire)

`aneFirmwareCommandSend` (0xfffffe000932a114, name via 0x931f8cc wrapper log string)
copies the first `size` bytes of the command object VERBATIM into the shared command
buffer, after zeroing the u16 at object+0x06:

```
0x932a5d0  ldr  x1, [x21]          ; x1 = command object
0x932a5d8  strh wzr, [x9, #6]!     ; object+0x06 (u16) = 0
...
0x932a5f4  (if pretranslate flag clear)
0x932a5f4  ldur w2, [x29,#-0x64]   ; size
0x932a5f8  mov  x0, x23            ; dest = slot in cmd buffer
0x932a5fc  bl   bcopy              ; memcpy(slot, object, size)
```

Packet layout (little-endian):

| off | size | field                          | evidence |
|-----|------|--------------------------------|----------|
| 0x00 | u32 | 0 (zero)                       | `strh`/`stp xzr` at every builder |
| 0x04 | u16 | **opcode**                     | `ldrh w9, [x9, #4]` read + "opcode: 0x%04X" log at 0x932a334-0x932a368 |
| 0x06 | u16 | 0 (zeroed by sender)           | `strh wzr, [x9,#6]!` 0x932a5d8 |
| 0x08 | ... | opcode-specific payload        | per-command below |

Response for sync commands overwrites the same stack object (e.g. CONFIG_GET response
u32 read back at object+0x08; RESOURCE_INFO_GET response u32 at object+0x10).

## 2. Cold-start order (ANEHWDevice::ANE_Init, 0xfffffe00092b4730 .. >=0x9322678)

All sends go through the wrapper at 0xfffffe000931f69c ->
`aneFirmwareCommandSend` core 0xfffffe000932a114. Call args:
`(this, cmdObj, size, &inOutSize, 0, 0, 0, epClass=2)` — w7=2 at every cold-start site.

Preceding context (same function, address order): cmd buffer alloc + log
`"cmd_buffer_base: 0x%llx, size: %llu"` (string vma 0xfffffe0007472cba, ref 0xfffffe0009321248)
— the captured run shows 0x1fb08000 / 262144. The command-buffer slot allocator is
0xfffffe00092cc34c(dev->[0x478], size) returning a byte offset (−1 = "No Memory");
packets land at cmdBufBase + offset.

Sends, in execution order (all in ANE_Init):

| # | site (bl) | opcode | name | size (req==resp) | payload bytes after the 8-byte header | condition |
|---|-----------|--------|------|------------------|----------------------------------------|-----------|
| 1 | 0x932200c | 0x0004 | CSNE_CMD_PRINT_ENABLE | 0x0C | 4 zero bytes | always |
| 2 | 0x93220e0 | 0x0021 | CSNE_CMD_TRACE_ENABLE | 0x0C | u32 [dev+0xC8] (unit-test mode value) | only if [dev+0xC8] != 0 |
| 3 | 0x9322124 | 0x0000 | CSNE_CMD_START | 0x0C | 4 bytes (0, or stale [dev+0xC8] if #2 ran) | always |
| 4 | 0x932224c | 0x0029 | **CSNE_CMD_SET_SNE_PMU_BASE2** | 0x10 | u64 PMU base (below) | if [dev+0x3A20]!=0 and PMU base != 0 |
| 5 | 0x932233c | 0x0003 | CSNE_CMD_CONFIG_GET | 0x10 | 8 zero bytes | always |
| 6 | 0x9322468 | 0x001F | CSNE_CMD_CH_PROPERTY_WRITE ("Macho read only mapping") | 0x14 | u32 0, u32 0x10A4, u32 1 | if [dev+0xE038+0x41] bit0 == 0 |
| 7 | 0x932252c | 0x0022 | CSNE_CMD_RESOURCE_INFO_GET | 0x64 | 92 zero bytes | always; response u32 @+0x10 checked vs [dev+0x3650]; feeds fNumANEs log |

Opcode names are double-sourced: (a) the kext's own completion logs pair 1:1 with each
send's failure path (PRINT_ENABLE log 0xfffffe0007473033 -> site #1's path; START log
0xfffffe0007473070 -> site #3's path; SET_SNE_PMU_BASE2 log 0xfffffe00074730a6 fires
unconditionally after send #4 with its res; RESOURCE_INFO_GET error log after #7), and
(b) the prior lane's firmware-side table
`receipts/2026-09-18-t6021-engine-layout-mined/w2/fw_cmd_table.json` (0x0 START,
0x3 CONFIG_GET, 0x4 PRINT_ENABLE, 0x1F CH_PROPERTY_WRITE, 0x21 TRACE_ENABLE,
0x22 RESOURCE_INFO_GET, 0x29 SET_SNE_PMU_BASE2 — no conflicts).

After #7: fNumANEs log (`"fNumANEs: %d fANEMaxCacheRequestSharedEvents: %u"`, string
vma 0xfffffe000747318b, ref 0xfffffe0009322678) — end of the discovery exchange.
Later in ANE_Init (post-discovery): CH_PROPERTY_WRITEs for FW sanity checks,
cpuLoadScore low/high watermarks, ProcedureCall FW log, FW perf mode, SEP handshake,
then CSNE_CMD_ANE_DEFAULT_SETTING_SET and CSNE_CMD_INIT_SHARED_EVENT_INFO (sites
0x9322b4c..0x9323240; names from their logs).

## 3. CSNE_CMD_SET_SNE_PMU_BASE2 — full 16 bytes as constructed

Builder at 0xfffffe00093221ec-0xfffffe000932224c:

```
0x93221fc  ldr  x8, [x19, #0x3A40]     ; PMU base candidate A
0x9322200  cbnz x8, ...                ; if 0 ->
0x9322204  ldr  x8, [x19, #0x3A48]     ; candidate B (platform table)
0x9322208  cbz  x8, skip               ; both 0 -> command NOT sent
0x932220c  stp  xzr, x8, [sp, #0x70]   ; obj+0x00 = 0, obj+0x08 = PMU base (u64)
0x9322210  mov  w9, #0x29
0x9322214  strh w9, [sp, #0x74]        ; obj+0x04 = 0x0029
0x9322218  mov  w8, #0x10
0x932221c  str  w8, [sp, #0xE0]        ; inOutSize = 0x10
0x9322238  mov  w2, #0x10              ; size = 0x10
0x9322248  mov  w7, #2
0x932224c  bl   0x931f69c              ; send
```

Wire bytes (16):

```
offset  0: 00 00 00 00     u32 0
offset  4: 29 00           u16 opcode = 0x0029
offset  6: 00 00           u16 0 (sender-zeroed)
offset  8: <pmu_base>      u64 LE, PMU window physical base
```

PMU base provenance: [dev+0x3A48] is set by the per-platform config switch
(function block 0x9346000-0x934a000; platform string per case: "h13" 0x9347464,
"h14" 0x934714c, "h15" 0x93484b8, "h16" 0x9347e58, "h17" 0x9347278, "h18" 0x9347800).
Examples decoded: h14 case -> 0x23B110000 + 0x5FC000 = **0x23B70C000** (= m1n1 ps_map
"ane"), h17 -> 0x300700000, a multi-die entry -> 0x2292280000. [dev+0x3A40] (preferred
when non-zero) is produced at 0x9337ffc-0x933805c: the platform base at [dev+0x3A48]
is mapped (0x4000 bytes, `bl 0xbf45e9c`) and wired (args incl. flags 0x1011), the result
stored to dev+0x3A40. On the captured macstudio run the PMU window sits at
0x28e08c000 (= pmgr 0x28e080000 + 0xC000, matching m1n1 ps_map "ane0").

## 4. Send path: slot allocation, copy, doorbell, EP bits

Per command (`aneFirmwareCommandSend` core 0x932a114):

1. Request object allocated from pool (0x8035ac0 kalloc type) at 0x932a14c-0x932a154.
2. EP selection: `csel w27, w7, [dev+0x194], eq` with w7=2 (0x932a190) — dev+0x194==2 on
   cold start so w27 = 2.
3. FW-state gate: [dev+0xE038] (dev+0xDFC8 block +0x70) — "Firmware in timeout state"
   abort path reads the opcode directly from [obj+4] (0x932a334).
4. Slot: `bl 0x92cc34c(dev->[0x478], size)` at 0x932a3f4 -> byte offset in the command
   buffer; -1 -> "ERROR: DeviceMemoryManager: No Memory" (0x932a584).
   dst = [[dev+0x498]+0x38] + offset (0x932a408-0x932a424).
5. Packet copy: bcopy(dst, obj, size) at 0x932a5f8 (see section 1).
6. Doorbell: 0x932aa30-0x932aa68 builds
   `bl 0x9325e20(this, ep, slotOffset, size, respSize, syncFlag)` where
   `ep = u32[dev + table[sel]]` — table at 0xfffffe000748fde8 = {0xDFC8, 0xDFD0,
   0xDFD4, 0xDFD4}, sel = w4 arg = 0 on cold start -> **ep = *(u32*)(dev+0xDFC8)**.
   dev+0xDFC8 is filled at 0x9321c58-0x9321c70 by the property lookup
   (helper 0x9323ae4) for IOP channel name **"IO"** (string 0xfffffe0007489333);
   dev+0xDFCC = **"IO_T2H"** (0xfffffe0007489336). These are runtime IOP channel ids,
   not kext constants.
7. 0x9325e20 = `IOProcessorChannelSendRetry(ep, dst, size, respSize, flag)` (name string
   in its timeout log at 0x9325f0c): retries (w21 = [dev+0x194]*0x32 attempts), and per
   attempt calls 0x92cbae8 = `IOProcessorChannelSend(channel, epArg, dst, respSize)`.

`IOProcessorChannelSend` (0x92cbae8) — the actual doorbell write:

```
0x92cbb2c  ldrsw x23, [x19, #0x24]      ; current doorbell slot (round-robin)
0x92cbb38  ldr  x8, [x19, #0x18]        ; doorbell message ring base
0x92cbb3c  lsl  x9, x23, #6             ; 64-byte entries
0x92cbb54  str  x22, [x0, #8]           ; entry+0x08 = dst ptr (packet slot)
0x92cbb58  str  x21, [x0, #0x10]        ; entry+0x10 = respSize
0x92cbb5c  dsb  st
0x92cbb60  ldrsw x8, [x19, #0x10]       ; seq toggle
0x92cbb68  orr  x8, x8, x20             ; | epArg
0x92cbb6c  str  x8, [x0]                ; entry+0x00 = {ep|toggle} word  <- ring
0x92cbb70  ...                          ; channel lock (blraa vtable)
0x92cbb88  dsb  st
0x92cbb8c  ldp  w9, w8, [x19, #0x20]    ; doorbell counters
0x92cbbb0  csinc w8, wzr, w8, eq        ; wrap at [x19+0x14]-1
0x92cbbbc  str  w8, [x19, #0x24]        ; advance doorbell slot
```

Doorbell message entry (64 B): +0x00 u32 `{ep | seq-toggle^1}`, +0x08 u64 dst pointer
(kernel VA of the packet slot in the 0x1fb08000 buffer), +0x10 u64 respSize.

Direct doorbell variant (`ANEHWDevice::doorBellRing` fragment at 0x9323ac4):

```
0x9323ac8  ldr  w1, [x9, #0x158]        ; channel index (per-platform, e.g. d0 const
                                        ; stored to dev+0x158 in the config switch)
0x9323ad0  lsl  w2, w9, w8              ; w2 = 1 << ep      <-- EP BIT MASK
0x9323ae0  b    0x9353050               ; ringDoorbell(chObj, idx, epBit)
```

The kext itself contains no raw ANE-aperture doorbell MMIO store: doorbells go through
XNU's IOProcessorChannel (AppleSIO/iop), which owns the register. Bare-metal analogue
for the replay lane (m1n1 `m1n1/hw/ane.py`): ANE GPIO doorbells GPIO0..7 at ANE base
+0x1840048 .. +0x1840064 (the aperture mapped at 0x284000000, 32 MiB, in the capture).

## 5. Sync/wait

Cold-start sends are synchronous (`aneCmdSendSync` wrapper family; the response
overwrites the stack command object — CONFIG_GET clock fields read back at
0x9322368-0x9322384, RESOURCE_INFO_GET response u32 at object+0x10 vs [dev+0x3650] at
0x9322568). The FW->driver event header is `sCSneControllerCmdHdrCh` and doorbell
responses arrive via `FWSharedEventDoorbellRing` (sym 0x40f0007497bffff).

## 6. Reproduction tooling

- `/var/tmp/kext-re/kextmap.py` — slice mapping (segments/sections, vm<->file)
- `/var/tmp/kext-re/parse_syms.py` — kext13.syms decoding (bytes[2:6] LE = file offset,
  `&~3` for text starts; tag byte0 0x0f/0x0e)
- `/var/tmp/kext-re/fndis.py` — function map + annotated disassembler
- `/var/tmp/kext-re/build_xrefs.py` — ADRP/ADD pointer xref index (xrefs.pkl)

Verified anchors: PRINT_ENABLE/START/PMU_BASE2/fNumANEs log strings resolve to exactly
one code ref each inside ANE_Init; opcode pairing cross-checked against
fw_cmd_table.json; h14 platform value equals m1n1 ps_map["ane"] (0x23b70c000).

## 7. Boundaries of this extraction (no fabrication)

- The EP number (`*(u32*)(dev+0xDFC8)`) and doorbell channel index ([dev+0x158]) are
  runtime IOP/DT values; the kext stores lookup-by-name ("IO", "IO_T2H"), not constants.
- The raw doorbell MMIO register is in XNU's IOProcessor layer, not in this kext; the
  kext-level contract (message entry + `1<<ep` bitmask API) is decoded above.
- [dev+0xC8] (TRACE_ENABLE payload) is zero on the captured normal boot.
