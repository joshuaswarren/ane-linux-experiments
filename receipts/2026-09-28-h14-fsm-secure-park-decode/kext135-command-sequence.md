# 13.5 kext (AppleH11ANEInterface) CSNE command decode — kext135-command-sequence

Source: `/var/tmp/t6021-kc/kernelcache.t6020.13.5-22G74.macho` (decompressed fileset kernelcache,
sha256 `9615a486511c7a60b141d7f4291361c5212e908546d6568890029bb90b5431e7`). Member
`com.apple.driver.AppleH11ANEInterface` parsed from LC_FILESET_ENTRY (+8 vmaddr, +16 fileoff,
+24 entry_id off): `__TEXT` vm `0xfffffe0007372450`, `__TEXT_EXEC` vm `0xfffffe00094b76b0`
(481,504 B). 4064 symbols with full mangled names present — all function names below are
symbol-verified, not guessed. Static decode only; no hardware touched, no commits.

## Wire format (every H2T command, verified at all 61 aneCmdSend call sites)

aneCmdSend `H11ANEIn::aneCmdSend(void*, uint len, uint* out, uint, bool, u64, uint, bool, bool)`
@ `0xfffffe00094c28c8`. Callers pass: x0=this, x1=cmd buffer, w2=len, x3=&len-slot, w4=0 or
`[this+0xc4]&2`, x6=0, w7=1/2/4 (1 = synchronous, 2 = normal, 4 = teardown).

Buffer layout (little-endian):

```
+0x00 u32   0 (priority/flags; 0 in every kext builder)
+0x04 u16   command id          <- the id lives here, not at +0
+0x06 u16   0
+0x08 ..    command-specific    (u32 or u64 value / payload)
len  = 0x08 (SUSPEND/POWER_DOWN only) | 0x0c (1-word cmds) | 0x10/0x14/0x18/0x20/0x30/0x38/0x64/
             0x1c0 (LOAD) / 0x214 (CREATE_PROCESS) / 0x268 (cached call) etc.
```

Cross-check with the live fw console (findings.md): fw-side PRINT_ENABLE = op 0x04 len 0x0c
value@+8 and TRACE_ENABLE = op 0x21 len 0x0c value@+8 match the kext bytes below exactly —
same wire format both directions.

## (1) Builder functions and payload layouts

Kext-verified (disassembly + os_log string in the same function):

| id | command | kext builder (symbol @ addr) | payload bytes |
|----|---------|------------------------------|---------------|
| `0x00` | **CSNE_CMD_START** ("START command completed" log `0xfffffe000738c20d`) | `ANE_Init()` `0xfffffe00094e2438` | len `0x0c`; +0..7 = 0; id = `0x0000`; +8 = stale flags word (not re-zeroed) |
| `0x01` | deinit op (unnamed) | `ANE_deInit()` `0xfffffe00094e66f8` | len `0x0c`, zeros, id 1 |
| `0x03` | (unnamed, after PMU_BASE2) | `ANE_Init()` `0xfffffe00094e255c` | len `0x10`, zeros |
| `0x04` | CSNE_CMD_PRINT_ENABLE | `ANE_Init()` `0xfffffe00094e2350` | len `0x0c`; +8 u32 = bool ([fwctx+0x85f] xor [this+0xbf])&1 |
| `0x05` | fw debug dump | `PrintFwDebugInfo` `0xfffffe00094c6b4c` | len `0x40` |
| `0x09` | fw debug dump 2 | `PrintFwDebugInfo` `0xfffffe00094c6ba0` | len `0x20`; +8 u32 = 1; +0x10 u64 param |
| `0x0b` | CSNE_CMD_POWER_DOWN | `ANE_deInit()` `0xfffffe00094e67a4` | len `0x08` — header only, no +8 word |
| `0x0e` | deinit/reg-FW-worker op | `ANE_deInit()` `0xfffffe00094e5ea0`; `ANE_RegisterFirmwareWorkProcessor_gated` `0xfffffe00094ee728` | len `0x0c` |
| `0x1f` | CSNE_CMD_CH_PROPERTY_WRITE | `ANE_Init()` `0xe2694` `0xe2910` `0xe29a8` `0xe2a30` `0xe2aec` | len `0x14`; +8 u64 = property key (literal pool `0x739ff08/18/20/28/30`), +0x10 u32 = value |
| `0x21` | **CSNE_CMD_TRACE_ENABLE** | `ANE_Init()` `0xfffffe00094e23f4` (only sender) | len `0x0c`; +8 u32 = driver logging flags `[this+0xa4]` (macOS hv trace saw 0xE); skipped when flags==0 |
| `0x22` | CSNE_CMD_RESOURCE_INFO_GET | `ANE_Init()` `0xfffffe00094e2724` | len `0x64` (100 B, response-filled) |
| `0x23` | ProgramCreate op (NOT stats) | `ANE_ProgramCreate_gated` `0xfffffe00094fafa4` | large buffer at sp+`0x6b4` |
| `0x24` | **CSNE_CMD_SUSPEND** ("SUSPEND command completed" `0xfffffe000738cb93`) | `ANE_deInit()` `0xfffffe00094e67a4` | len `0x08` |
| `0x25` | **CSNE_CMD_DSID_SET** ("CSNE_CMD_DSID_SET Failed" `0xfffffe000739cd50`) | `McacheDriverClient::powerOnMcacheRequest` `0xfffffe00094f4d9c` | len `0x0c`; +8 u32 = dsid |
| `0x26` | CSNE_CMD_MCACHE_SIZE_GET | `powerOnMcacheRequest` `0xfffffe00094f4b10` | len `0x0c` (response = size, default 0x200000) |
| `0x27` | **CSNE_CMD_SECURE_MODE_START** | `ANE_PowerOn_gated` `0xfffffe00094ecebc` (only sender) | len `0x0c`, **all-zero payload** except id u16@+4 |
| `0x28` | **CSNE_CMD_SECURE_MODE_STOP** ("ANE%d, %s - CSNE_CMD_SECURE_MODE_STOP" `0xfffffe00073888f8`) | `ANE_PowerOff_gated` `0xfffffe00094d0da0` (only sender) | len `0x0c`, **all-zero payload** except id u16@+4 |
| `0x29` | CSNE_CMD_SET_SNE_PMU_BASE2 | `ANE_Init()` `0xfffffe00094e24ec` | len `0x10`; +8 u64 = PMU base PA (`[this+0x3828/0x3830]`) |
| `0x2a`/`0x2b` | CSNE_CMD_IPC_ENDPOINT_SET2 / UNSET2 | `AneIspIPCEndPoints::enableFWIPCEP_gated` sends @`0x95161d4`/`0x9516088` | len `0x30`; buffer = endpoint-table entry; marker u16 `0x2a`/`0x2b` written to `tbl+idx*0xa0+0xbc` immediately before each send [buffer-base mapping not fully resolved] |
| `0x2d` | **CSNE_CMD_SET_DYNAMIC_POWERGATE** | `sendCmdEnableDynamicPowerGating_gated` `0xfffffe00094d006c` (enable), `disableDynamicPowerGating` `0xfffffe00094cfe94` (disable), UC wrapper `ANE_SetDynamicPowerGating_gated` `0xfffffe00094f1914` | len `0x0c`; +8 u32 = 1 (enable) / 0 (disable) |
| `0x2e` | **CSNE_CMD_ANE_DEFAULT_SETTING_SET** | `ANE_Init()` `0xfffffe00094e2c90` (subtype 1) and `powerOnMcacheRequest` `0xfffffe00094f4cac` (subtype 2) | subtype 1: len `0x18`; +8 u64 = 1, +0x10 u32 = 2, +0x14 u32 = ctxSwitchLatencyThreshold `[this+0xd0]`. subtype 2: len `0x20`; +8 u64 = 2, +0x10/+0x18 u64 = intermediate-spill Lo/Hi DSIDs (literal pool `0x739ffe0`) |
| `0x201` | LOAD/UNLOAD_PROGRAM | `ProgramLoad` `0xfffffe00094d1c68` (len `0x1c0`), `ProgramUnload` `0xfffffe00094d16ec/17e4`, `ReleaseProgramMemoryBuffer`, `ANE_ProgramCreate_gated` (id @sp+`0x6b4`) | LOAD = 448-B section payload (tdprop etc.), +8 = `[x20+0x38]` programId |
| `0x202` | CREATE/DESTROY_PROCESS family | `ANE_ProcessCreate_gated` `0xfffffe00094d2118` (len `0x214`), `ANE_ProgramUnprepare_gated` `0xfffffe00094ff908` | +8 = programId, +0xc = processId |
| `0x203` | TERMINATE_PROCESS | `ANE_ProcessCreate_gated` error path `0xfffffe00094d22d0`, `ANE_ProcessDestroy_gated` `0xfffffe00094c1cec` | len `0x10` |
| `0x205`/`0x206` | CSNE_CMD_LOAD_AFPP / UNLOAD_AFPP | `enableFWIPCEP_gated` `0xfffffe0009515f54`/`0xfffffe00095162a8` | len `0x38`; +8 u32 = 1; +0x14 = {0, flag(0\|3)}; +0x20 u64 phys; +0x28 u64 size |
| `0x209`/`0x20a`/`0x20b` | PROCEDURE_CALL family (cache-request/trigger/recycle/invalidate) | `SendRequestToFirmware_gated` `0x950100c/17f8/1a08`, `ANE_ProgramSendCachedRequest_gated` `0x9508300` (len `0x268`), `ANE_ProgramOutputSetEnqueue_gated` (0x20a), `ANE_ProgramUnprepare_gated` (0x20b), `ANE_ProcessDestroy_gated` (INVALIDATE len `0x10`), T2H stats reply `0xfffffe00094d7d0c` (0x20b, +8 u64 = stats buffer size `[this+0x2d28]`) | per-variant id map pending |

Not present as H2T sends in the 13.5 kext: **`0x10` (BOOT)** — the kext's "CSNE_CMD_START" is id
`0x0000`; boot args reach the fw through the shared `cmd_buffer` ("ANE_Init - Firmware Boot-Args",
`cmd_buffer_base` prints), not a 0x10 command. **`0x1d` CH_BUFFER_POOL_CONFIG_SET** — no builder,
no string in this kext (that name is from the macOS 26 kext table). **`0x15` IPC_ENDPOINT_SET** —
superseded by SET2/UNSET2 (`0x2a`/`0x2b` markers). The `0x23` immediates in
`processTargetToHostIOCommand` (`0xfffffe00094d7458`, `0x7cdc`) are w4 arguments to the helper at
`0xfffffe00094c3760` (w1=0x1e/0x1f, w4=0x23/0xe), not command ids — the kext never sends
STATS_BUFFER_SIZE_GET host→fw; the fw asks (T2H) and the kext replies `0x20b`.

## (2) Order from firmware boot to the first PROCEDURE_CALL

Call graph (symbol-verified callers):

1. `H11ANEIn::start` (IOKit match) — mailbox/pmgr/dynamic-power-gate property setup.
2. Client attach (aned UserClient open / kernel client) or any program path calls
   `ANE_PowerOn_gated` ← `ANE_UserClientOpen_gated`, `ANE_AddClientForProgram_gated`,
   `ANE_ProgramCreatePreprocessing`, `ANE_ProgramPrepare_gated`, `ANE_ProgramSendRequest…`,
   `ANE_PowerOnByKernelClient_gated`, `ANE_MemoryMapRequest_gated` (lazy power):
   poll pmgr ps words until ACTUAL byte == `0xff` (loop `0xece40`–`0xece74`), then send
   **`0x27` SECURE_MODE_START** (zero payload).
3. `power_on_hardware` → `ANE_deInit()` (cleanup) → **`ANE_Init()`**: wait fw wake on first
   `rANE_SCRATCH7` (mailbox hello), read Firmware Boot-Args from the shared `cmd_buffer`,
   allocate fw heap, discover IPC channels, wait second SCRATCH7 interrupt ("ANECPU Ready"),
   enable interrupts, then send, in address order:
   `0x04` PRINT_ENABLE → [`0x21` TRACE_ENABLE flags, only if `[this+0xa4]`≠0] → `0x00` START →
   `0x29` SET_SNE_PMU_BASE2 → `0x03` → `0x1f` CH_PROPERTY_WRITE (fw Macho RO mapping) →
   `0x22` RESOURCE_INFO_GET → `0x1f` ×3 (sanity checks, cpuLoadScore Lo, cpuLoadScore Hi,
   ProcedureCall fw log) → `0x2e` DEFAULT_SETTING_SET (ctx-switch latency).
4. First inference: `ANE_ProgramCreate_gated` (`0x23`) / `ProgramLoad` (`0x201`, 448-B payload)
   → `ANE_ProcessCreate_gated` (`0x202`, len `0x214`) → `SendRequestToFirmware_gated`
   PROCEDURE_CALL (`0x209/0x20a/0x20b`, cached variant len `0x268`).
5. Teardown: `powerStateDidChangeTo_gated` → `ANE_PowerOff_gated` (see below);
   `power_off_hardware` → `ANE_deInit`: `0x0e` → `0x01` → `0x24` SUSPEND or `0x0b` POWER_DOWN
   (len 8; selected by `[this+0x92]`: 0 → `0x0b`, ≠0 → `0x24`), then poll ASCWRAP_IDLE_STATUS
   for WFI.

## (3) Secure mode: the explicit answer

**macOS sends SECURE_MODE_START (`0x27`, 12 bytes, all-zero payload except id u16 at +4) on
every ANE power-up, immediately after the pmgr ACTUAL==0xff poll in `ANE_PowerOn_gated`
(`0xfffffe00094ece78`–`0xcebc`).** It sends SECURE_MODE_STOP (`0x28`, identical 12-byte shape)
only in `ANE_PowerOff_gated` (`0xfffffe00094d0d34`–`0xda0`), and only when the powering-off
client context matches `"PearlSEP"` (strncmp at `0xd0d18`) and `[this+0x8a]` is set — i.e. when
the SEP client powers its ANE session off. `0x27` has exactly one call site and `0x28` exactly
one in the whole kext; nothing else (no RESUME_TRANSITION send, no userspace path except the
generic `ANE_SendCommand_gated` passthrough at `0xfffffe00094f1d64`) touches secure mode.

So after boot macOS drives START-then-work, never a bare STOP; STOP is the SEP-detach edge.

Consequence for the parked Linux FSM (findings.md root cause: ELFSM got nonSec→Sec, never
Sec→NonSec, every PROCEDURE_CALL parks): our Linux release sequence never sends either command.
The discriminator to run (zero-risk, PRINT_ENABLE console live):

1. Send `{00 00 00 00 28 00 00 00 00 00 00 00}` (id `0x28` u16 at +4, len 12) after CPU_STATUS
   `0x28` and gated on pmgr islands ACTUAL=`0xf`. Expect fw prints "request Sec -> NonSec
   received" (`0xbb834`), "switched from Sec -> NonSec, ANE goes to RUN" (`0xbde17`),
   sec2NonSecCnt++, then re-send the parked PROCEDURE_CALL and read isHWReady ("ready!"
   `0xbc0e9` or the named failing check).
2. If the FSM ignores `0x28` in its current state, send `0x27` first (macOS power-on shape:
   `{00 00 00 00 27 00 00 00 00 00 00 00}`), then `0x28` — replicating the macOS pair.

## Id-list correction vs the tasking

The requested mapping ("0x27 SECURE_MODE_START, 0x28 SECURE_MODE_STOP, 0x24 SUSPEND,
0x23 STATS_BUFFER_SIZE_GET, 0x1d CH_BUFFER_POOL_CONFIG_SET, 0x15 IPC_ENDPOINT_SET, 0x2e
ANE_DEFAULT_SETTING_SET, 0x2d SET_DYNAMIC_POWERGATE, 0x25 DSID_SET, 0x10 BOOT, 0x21
TRACE_ENABLE") is confirmed for 0x27, 0x28, 0x24, 0x2e, 0x2d, 0x25, 0x21, and wrong for:
`0x23` (= ProgramCreate op; stats-size is a T2H request answered with `0x20b`), `0x1d`
(absent), `0x15` (absent; SET2/UNSET2 instead), `0x10` (absent as a kext send; kext START =
`0x0000`). The findings.md WARNING ("fw 0x28 = STATS_BUFFER_SIZE_GET, do not trust kext ids")
is now suspect in the other direction: the 13.5 kext demonstrably sends `0x28` with the
SECURE_MODE_STOP log string on the identical 12-byte wire format that the fw side verified for
0x04/0x21. The fw dispatch-chain decode at `0x27cb4` should be re-checked before trusting
"fw 0x28 = STATS_BUFFER_SIZE_GET". [INFERENCE]

## Method / repro

Toolkit: `artifacts/M2StaticDecode/2026-09-28-kext135-command-sequence/ane135.py`
(fileset-member parser + segment-mapped disassembler + symtab/strings/xref). Capstone stops at
embedded data mid-segment — scan per function window (`FUNC_STARTS`), not whole `__TEXT_EXEC`
(this silently dropped every ANE_Init site in the first pass). Command ids extracted by
back-scanning `strh w?, [buf+4]` to its feeding `mov w?, #imm` in the 48 instructions before
each `bl aneCmdSend`. Full dumps: `ANE_Init.asm`, `sends3.txt` (61 annotated send sites),
`symbols.txt`. All addresses are kext VM addresses in the 13.5 kernelcache as loaded.


## PMU base and START (follow-up decode, same session)

All in `H11ANEIn::start` (`0xfffffe00094c82c4`) unless stated. Hardware context: fresh-boot
ELFSM is state 1 (RUN), the call is NOT parked; it launches and never completes. The two
macOS-only sends are `0x29` SET_SNE_PMU_BASE2 and `0x00` START (both in ANE_Init).

### [this+0x3828] / [this+0x3830] (SNE PMU base)

- `[this+0x3828]` is **never written anywhere in the kext** (all-function scan) — it is the
  zero-initialized alternative. The ANE_Init send (`0xfffffe00094e2490`–`0xe24ec`) uses
  `x8 = [this+0x3828] ? [this+0x3828] : [this+0x3830]`, so effectively `[this+0x3830]`.
- `[this+0x3830]` is written exactly once, at `0xfffffe00094caaa0` (`str x8,[x19,#0x3830]`),
  with a **hard-coded per-chip immediate** — no ADT/IORegistry property, no IOMemoryMap index,
  no pmgr mapping. Selector chain:
  - `ldr w8,[this+0xec]`; `== 0xe0` -> `0x292280000` (0xca9f8->0xcaa74->0xcaaa0)
  - `== 0xc0` -> `0x350750000` (0x351200000 - 0xb00000)
  - `== 0xb0` -> `0x2d0700000` (0x2d1200000 - 0xb00000)
  - fw-version class `[this+0x3c10] == 0x70` -> `0x23b16fc000`; `== 0x80`/ctx==1 -> `0x8e080002c8`
  - jump table at `0x94ccd44` (w16<=3, from a context word): 0->`0x8e080002c8`, 1->`0x292280000`,
    2->`0x8e080002c8`, 3->`0x228e680270`.
- `[this+0xec]` = u32 IORegistry property **`aneType`** (fallback selector name `ane-type`),
  read at `0x8810`–`0x8870`, default 0. T6021 runs the `0xe0` branch.
- T6021 value: **PMU base2 = `0x292280000`** [INFERENCE on the aneType==0xe0 mapping; the
  branch exists and the value is stored raw]. It is a raw address (no translation, no
  mapInto) — pass it to the fw as-is. Log twin: "aneSubBlockPowerRegsDartMappedAddress::start
  - aneSubBlockPowerRegs mapped - 0x%08x" (`0xfffffe0007381d7b`).
- Send gate: `ANE_Init` sends `0x29` only if bit0 of `[this+0x3814]` is set (`0xe2490`–`0xe2498`).
  `[this+0x3814]` = u32 property **`anePowerManagement`**, default 3 (bit0 set) at `0x91c8`.

### 0x29 SET_SNE_PMU_BASE2 payload (exact)

len `0x10`: `{u32 0; u16 0x29; u16 0; u64 pmu_base2 @+8}` — bytes
`00 00 00 00 29 00 00 00 | <u64 LE base>`. No other fields.

### 0x00 START payload (exact, incl. the stale word)

len `0x0c`: `{u32 0; u16 0x0000; u16 0; u32 stale @+8}`. The buffer is zeroed only on the
TRACE path; `+8` (`[sp+0x150]`) is never re-written before START, so it holds:
- if the `aneFWTrace` u32 property exists (`[this+0xa4]`, read `0xcbeec`–`0xcbef4`, default 0):
  its value (the same word TRACE_ENABLE sent at +8);
- else: the PRINT_ENABLE value = `([ctx+0x85f] != 0) ? (([this+0xbf] ^ 1) & 1) : 0`
  (`0xe2300`–`0xe2318`), where `[this+0xbf]` is a bool property (default 0, `0x93e0`–`0x9414`).
macOS first boot (no aneFWTrace, aneType present): PRINT_ENABLE value = 1 (matches the hv
trace seeing PRINT_ENABLE +8=1), so **START +8 = 0x00000001**.
=> Linux replication: `00 00 00 00 00 00 00 00 01 00 00 00`.

### The five 0x1f CH_PROPERTY_WRITE sends (len 0x14 each)

Format: `{u32 0; u16 0x1f; u16 0; u64 key @+8; u32 value @+0x10}`.

| key (u64 LE) | site | value source |
|---|---|---|
| `0x000010a400000000` | `0xe2694` | literal `1` — "fw Macho read-only mapping" enable flag. **No address/size is passed in the command** — the property only toggles the RO mapping the kext established elsewhere |
| `0x000010a600000000` | `0xe2910` | u8 `[this+0xc0]` ("FW sanity checks") |
| `0x0000180300000000` | `0xe29a8` | u32(u16 `[this+0x1ce]`) — cpuLoadScore Low watermark |
| `0x0000180400000000` | `0xe2a30` | u32(u16 `[this+0x1cc]`) — cpuLoadScore High watermark |
| `0x000000a100000000` | `0xe2aec` | 0 if guard bytes fail, else (`logflags & 0x8000 ? 3 : 1`) — ProcedureCall fw log level |

(The double `0x3fe999999999999a` = 0.8 adjacent in the pool at `0x739ff10` is a packed
literal, not part of any key.)

### 0x2e DEFAULT_SETTING_SET subtype 1 (exact)

len `0x18` (`ANE_Init` `0xfffffe00094e2c90`): `{u32 0; u16 0x2e; u16 0; u64 1 @+8; u32 2
@+0x10; u32 ctxSwitchLatencyThreshold @+0x14}`. `[this+0xd0]` = OSNumber property
**`aneCtxSwitchLT`** (read `0x94cc918`–`0x94cc968`), default **`0xFFFFFFFF`** when absent
(`mov w8,#-1` at `0x94cc910`). Default macOS bytes:
`00 00 00 00 2E 00 00 00 01 00 00 00 00 00 00 00 02 00 00 00 FF FF FF FF`.
