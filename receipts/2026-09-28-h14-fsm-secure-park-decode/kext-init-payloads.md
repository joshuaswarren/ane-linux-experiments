# H14 kext-init payloads: wire formats and fw 13.5 handlers (kext-init-payloads)

Static decode only. No hardware touched. No commits.

Firmware: `/tmp/fw135.macho` (Apple ANE fw 13.5, sha256 prefix `a9c4b771`). Every fw VA below
was re-disassembled from THIS image in this session with `/tmp/fw135-dis.py`. Kext: macOS 13.5
(22G74) kernelcache `/var/tmp/t6021-kc/kernelcache.t6020.13.5-22G74.macho`, member
`com.apple.driver.AppleH11ANEInterface` (`__TEXT` vm `0xfffffe0007372450`, file `0x36e450`).
Kext builder addresses come from `kext135-command-sequence.md` (same session family, symbol-
verified there); the literal-pool bytes were re-read from the kernelcache here.

Emitter: `tools/h14_seq_kext_init.py` (`--self-check` prints `ok`).

## Wire format (kext H2T commands, verified at all 61 aneCmdSend sites)

```
+0x00 u32  0
+0x04 u16  command id      <- written by the sequencer driver at load time; zero in the files
+0x06 u16  0
+0x08 ..   payload
```

Verified against existing packed steps: `/tmp/07.bin` = op `0x27`, 12 zero command bytes;
`/tmp/09.bin` = op `0x29`, 16 bytes, payload `+8` u64 = `0x28e084000` (a prior local experiment
used the host power-register base as PMU base; the kext T6021 value is `0x292280000`, see 0x29).

## fw dispatch

Table 1 @ `0x2a598`: cmds `0x00`-`0x2f`, u32 entries relative to `0x27164`.
Table 2 @ `0x2a658`: cmds `0x200`+, relative to `0x27208`.
Relevant handlers: `0x03`->`0x27470`, `0x1f`->`0x27174`, `0x22`->`0x27bcc`, `0x25`->`0x27da0`,
`0x29`->`0x27f60`, `0x2e`->`0x281e4`, `0x205`->`0x283f8`. Unimplemented slots share tail
`0x2a25c` (complete without work). Register roles in the handlers: `x20` = controller, `x21` =
command buffer, `x22` = in-length.

## Ready-to-send commands

### 0x22 CSNE_CMD_RESOURCE_INFO_GET — len 0x64

- Kext builder: `ANE_Init()` `0xfffffe00094e2724`. No payload fields (all zero).
- fw `0x27bcc`: fills the reply (x21 = cmd base) from a literal template:
  - `+8..+0x17` <- 16-byte literal @ `0x803d0` = `{0xf0, 0x1f0, 0x20, 0x20}` (u32 each)
  - `+0x18..+0x1f` <- 8-byte literal @ `0x803c8` = `{0x80, 0x10}`
  - `+0x20` = 1; `+0x24..+0x63` untouched (zero)
- Log `"resource_info_get: maxProgram=%d, maxProcess=%d, maxProcPerProg=%d, maxCallPerProcess=%d"`
  (`0xb39d7`) prints `0xf0, 0x1f0, 0x80, 0x20`. Field-name mapping beyond `+8`/`+0xc` is
  [INFERENCE]; dump the reply and read the constants.
- No length check, no assert path. Emits `dump_reply=0x64`.

### 0x1f CSNE_CMD_CH_PROPERTY_WRITE — len 0x14, five sends

Format: `{u32 0; u16 0x1f; u16 0; u64 key @+8; u32 value @+0x10}`. The tasking said "0x1f x4";
the kext sends FIVE (the RO-map property precedes `0x22`, four follow it). All five are emitted.

fw router `0x27174`: property = u32`[cmd+0xc]` (`0x271c4`), value = u32`[cmd+0x10]`;
class = `property & 0xff00` (`0x271c8`-`0x271f0`). Key u64s re-verified in the kext literal pool
`0xfffffe000739ff08` this session (`10a400000000`, `10a600000000`, `180300000000`, ...).

| key | kext site (value source) | fw class path | fw effect |
|---|---|---|---|
| `0x000010a400000000` | `0xfffffe00094e2694` (literal 1, "fw Macho read-only mapping") | `0x1000` -> `0x2872c` -> `0x37b4c([ctrl+0x140], prop, value)`, table `0x37dec` | `0x37c4c`: `bfi` bit 2 of u32 flag word `[progMgr+0x988c]` (corroborated by launch-completion.md: `0x10A3/A4/A9 -> +0x988c`) |
| `0x000010a600000000` | `0xfffffe00094e2910` (u8 `[this+0xc0]`, "FW sanity checks") | `0x1000` -> same table | `0x37c6c`: if value != 0, byte `[progMgr+0x9870] = 1`. One-way set; 0 is a no-op |
| `0x0000180300000000` | `0xfffffe00094e29a8` (u32(u16 `[this+0x1ce]`), cpuLoadScore Lo) | `0x1800` -> `0x28314` -> `0x289e0` -> `0x289f8` -> `0x2bb98([ctrl+0x198], prop, value)`, byte table `0x80458` | `0x2bc24`: u32 value -> `[CLoadMonitor+0x54]` |
| `0x0000180400000000` | `0xfffffe00094e2a30` (u32(u16 `[this+0x1cc]`), cpuLoadScore Hi) | `0x1800` -> same | `0x2bc34`: u32 value -> `[CLoadMonitor+0x50]` |
| `0x000000a100000000` | `0xfffffe00094e2aec` (0 if guard bytes fail, else `logflags & 0x8000 ? 3 : 1`) | `0x0000` -> `0x28338` -> `0x26e2c(ctrl, prop, value)`, table `0x27058` | `0x26f60`: u32 value -> `[ctrl+0x23c]` (ProcedureCall fw log level) |

Unknown property id: `0x29a80` logs `ERR: "Unknown property"` (`CANEController.cpp:0x766`,
printed only when `[ctrl+8] >= 0xa`) and completes. In `CLoadMonitor`, unknown id ->
`WRN "Unknown property write 0x%x"` (`CLoadMonitor.cpp:0xae`, `0x2bbf8`). No assert anywhere in
the 0x1f path. Emitted value defaults: RO=1 (kext literal); fw_log=1 (macOS first-boot shape);
sanity=1, load_lo=0, load_hi=0 [INFERENCE — kext field defaults not recoverable statically;
override with `--set`].

Note: kext135-command-sequence.md lists the five 0x1f sites as shorthand `0xe2694`/`0xe2910`/
`0xe29a8`/`0xe2a30`/`0xe2aec`; expanded here to `0xfffffe00094e2694` et seq. The expansion fits
the surrounding `ANE_Init` site numbering (`0x94e255c` < `0x94e2694` < `0x94e2724`).

### 0x2e CSNE_CMD_ANE_DEFAULT_SETTING_SET — two subtypes

Payload: `{u32 0; u16 0x2e; u16 0; u64 nbrOfSettings @+8; nbrOfSettings x {u32 regId, u32 value}}`.

fw `0x281e4`: logs `nbrOfSettings`; loops entries (8-byte stride from `+0x10`, `ldp` at
`0x28254`, log `"regId: %d, value 0x%x\n"` @ `0xb3ab8`); then, only when `[ctrl+0x230] == 0`
(`0x28278`): applies via `[ctrl+0x130]` vtable+0x120(cmd) (`0x28cac`) and
`0x61e68([ctrl+0x178], cmd)` (`0x28cbc`).

- Subtype 1 — len `0x18`. Kext `ANE_Init()` `0xfffffe00094e2c90`:
  `{u64 1, {regId 2, value aneCtxSwitchLT}}`. `aneCtxSwitchLT` = OSNumber property
  `[this+0xd0]`, default `0xFFFFFFFF` when absent (kext `0x94cc910`).
- Subtype 2 — len `0x20`. Kext `McacheDriverClient::powerOnMcacheRequest` `0xfffffe00094f4cac`:
  `{u64 2, {regId 4, value 0x33}, {regId 3, value 0x0e}}`. Bytes verified in kext literal pool
  `0xfffffe000739ffe0` this session: `04 00 00 00 33 00 00 00 03 00 00 00 0e 00 00 00`
  (intermediate-spill DSIDs; which of regId 4/3 is Lo vs Hi is [INFERENCE]).

## Assert / hang set — NOT in the ready-to-send files

All asserts are `"ASSERT: "` (`0xb3521`) + `CANEController.cpp` (`0xb352a`) through `0x1a724`,
then a `b .` self-loop = firmware hang, not a return.

| command | condition | assert string / line | assert VA | self-loop |
|---|---|---|---|---|
| `0x2e` (both subtypes) | `[ctrl+0x230] != 0` (a program IS loaded) | `!isProgramLoaded` :`0x3b6` | `0x2828c` (bl `0x282a8`) | `0x282ac`<->`0x282b0` |
| `0x25` DSID_SET | same gate at `0x27df4` | `!isProgramLoaded` :`0x39e` | `0x27e0c` (bl `0x27e24`) | `0x27e28`<->`0x27e2c` |
| `0x205` LOAD_AFPP | `[ctrl+0x234]` ipcEndpointSetDone | `false == ipcEndpointSetDone` :`0x88c` | `0x28428` (bl `0x28450`) | `0x28454`<->`0x28458` |
| `0x205` LOAD_AFPP | `[ctrl+0x235]` AFPPLoaded | `false == AFPPLoaded` :`0x88d` | `0x2867c` (bl `0x286a4`) | `0x286a8`<->`0x286ac` |
| `0x03` CONFIG_GET | in-length != `0x10` (`0x27470`-`0x27474`) | `insize == sizeof(struct sCSneCmdConfigGet)` :`0x348` | `0x28770` (bl `0x28798`) | `0x2879c`<->`0x287a0` |
| `0x03` CONFIG_GET | reply slot < `0x10` | `*outsize >= sizeof(struct sCSneCmdConfigGet)` :`0x349` | `0x29820` (bl `0x29848`) | `0x2984c`<->`0x29850` |
| `0x29` SET_SNE_PMU_BASE2 | PMU power-controller global ptr @ fw data `0x4fa358` is NULL (`0x27fc4`-`0x27fd0`) | `__null != pPC` :`0x52b` | `0x28a94` (bl `0x28ab0`) | `0x28ab4`<->`0x28ab8` |

Consequences:

- `0x2e` subtype 1/2 assert+hang once a program is loaded. The parked machine HAS ProgramId 0.
  Send `0x2e` only BEFORE `0x200 LOAD_PROGRAM` (macOS sends it in `ANE_Init`, pre-inference).
- `0x25`: kext `powerOnMcacheRequest` `0xfffffe00094f4d9c`, len `0x0c`, `+8` u32 = runtime DSID.
  Same program-loaded hang. Needs a live DSID value; documented, not emitted. fw work path
  `0x28a70`: `[ctrl+0x130]` vtable+0x118(dsid).
- `0x205`: kext `enableFWIPCEP_gated` `0xfffffe0009515f54` (UNLOAD_AFPP `0xfffffe00095162a8`),
  len `0x38`: `+8` u32 = 1, `+0x14` = `{0, flag(0|3)}`, `+0x20` u64 phys, `+0x28` u64 size.
  ISP IPC path with runtime phys/size; fw work path `0x29dd4` (not decoded). Documented, not
  emitted.
- `0x03` is safe ONLY at exactly len `0x10`; any other length hangs the fw. Emitted at `0x10`.
- `0x29` is in the `kext` ordering only. fw effect when `pPC` exists:
  `[pPC->vtable+0x30](pPC, base)` then `[ctrl+0x130]` vtable+0x110 (`0x27fd8`-`0x27ff0`).

## Orderings emitted by tools/h14_seq_kext_init.py

- `init` (default; the tasking order): `01` 0x22, `02` 0x1f RO-map, `03` 0x1f sanity,
  `04` 0x1f load-lo, `05` 0x1f load-hi, `06` 0x1f fw-log, `07` 0x2e sub1, `08` 0x2e sub2.
  Run before LOAD_PROGRAM/CREATE_PROCESS.
- `kext` (exact `ANE_Init` address order): 0x29, 0x03, 0x1f RO-map, 0x22, 0x1f sanity,
  load-lo, load-hi, fw-log, 0x2e sub1, 0x2e sub2.
- `safe` (no assert path reachable at correct lengths): 0x22 + 0x1f x5 only. This is the set
  that may also go at the currently parked machine (program loaded).

`0x04 PRINT_ENABLE`, `0x21 TRACE_ENABLE`, `0x00 START` are outside this task's set; decode and
exact bytes live in kext135-command-sequence.md.

## Defaults and [INFERENCE] items

- `sanity=1`, `load_lo=0`, `load_hi=0`, `fw_log=1`, `ctx_lt=0xFFFFFFFF`, `pmu_base=0x292280000`.
  First two/three are kext field defaults not recoverable statically; `pmu_base` is the kext
  T6021 `aneType==0xe0` branch (`0x292280000`, stored raw at `0xfffffe00094caaa0`). A prior
  local step (`/tmp/09.bin`) used `0x28e084000` instead. Override: `--set pmu_base=0x...`.
- `0x22` reply field names beyond `+8`/`+0xc`: [INFERENCE] (constants dumped, names from log).
- regId 4 vs 3 as spill Lo/Hi: [INFERENCE].

## Method / repro

- fw dispatch tables + handlers: `python3 /tmp/fw135-dis.py <lo>-<hi>` over `0x27174-0x27218`,
  `0x27470-0x274f0`, `0x27bcc-0x27c68`, `0x27da0-0x27e30`, `0x27f60-0x27ff8`, `0x281e4-0x282b4`,
  `0x283f8-0x2845c`, `0x28314-0x28378`, `0x2872c-0x28770`, `0x289e0-0x28a70`, `0x28a70-0x28ac4`,
  `0x28ca0-0x28d00`, `0x29820-0x29860`, `0x29a58-0x29ae0`, `0x2bb98-0x2bc10`, `0x2bc24-0x2bc48`,
  `0x26e2c-0x26e90`, `0x26f60-0x26fa0`, `0x37b4c-0x37c40`, `0x3f670-0x3f6e0`; jump tables read
  raw from file offset VA+0x4000 (`0x37dec` rel `0x37bb8`, `0x37e70` rel `0x37be8`, `0x27058`
  rel `0x26e54`, byte table `0x80458`; reply template `0x803c8`/`0x803d0`).
- Kext literal pools: kernelcache parsed for `LC_FILESET_ENTRY` (cmd `0x80000035`; vmaddr +8,
  fileoff +16, entry_id offset +24, NUL-terminated inline); member segments map
  `0xfffffe000739ff08` and `0xfffffe000739ffe0` into `__TEXT`.
- Emitter round-trip: `python3 tools/h14_seq_kext_init.py --self-check` -> `ok`; emitted files
  re-parsed and byte-compared against the tables above.
