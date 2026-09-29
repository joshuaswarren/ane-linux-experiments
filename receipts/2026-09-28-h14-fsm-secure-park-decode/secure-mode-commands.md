# H14 secure-mode commands decode (2026-09-28)

Companion to `findings.md` (park root cause). All addresses are firmware VM addresses in
`13v5-22G74-selene.macho` (sha256 `a9c4b771294a6b115624d9480a6248d0899a1681a575e865070b87a3248427bc`,
re-verified this session; `__TEXT` file = VM + 0x4000). Disassembly: capstone 5.0.7 with the
symbolized MachO (M2Protocol helper). Kext reference table:
`receipts/2026-09-18-t6021-engine-layout-mined/kext-h14j` (26A428). Every claim below is
instruction-cited; nothing is taken from the kext table unless marked.

## 1. Real opcode -> handler map (dispatch walk 0x270dc-0x2a300)

`CANEController::CmdProcessor` (0x270dc) reads `u16 cmd @ envelope+4` (0x27108), then:

```
027150: ldrh   w23, [x1, #4]          ; cmd id
027154: cmp    w23, #0x2f
027158: b.hi   #0x271f4               ; > 0x2f -> model-op range check
02715c: adr    x8, #0x2a598           ; system jump table, 48 x s32
027168: ldrsw  x10, [x8, x23, lsl #2]
02716c: add    x9, x9, x10            ; x9 = 0x27164
027170: br     x9
```

Model ops: `0x271f4: sub w8, w23, #0x200; cmp w8, #0xe; b.hi 0x2a25c` then jump table at
0x2a658 (15 entries, rel 0x27208). Every system command ends in the shared tail
0x2a25c = `CmdQuickCallback(this, 0)` (0x2a694) -> `CController::Post` (0xe628) sends the
same buffer back; `*outlen = 0`; return 0. CmdQuickCallback sets `u16 result @ buf+6`
to 1/2 only when called with status 1/2; the dispatcher itself clears buf+6 at 0x27140.
Errors inside handlers are `0x1a670` (ERR print) + `0x1a724` + `b self` = **firmware hang**,
never an error return.

Command names below are **the firmware's own** table `CmdStringGet` (0x2acc8 -> 78-entry
{name-id, char*} array at 0xc5dd8), not the kext's.

| op | fw name (0xc5dd8) | handler | verified behavior |
|----|-------------------|---------|-------------------|
| 0x00 | CSNE_CMD_START | 0x27244 | trace(0x3000c), clears [ctrl+0x230], posts **controller-FSM** ([ctrl+0x1a8], table 0xc5388, initial 0) event 0 -> from state 0: 0->3 `StartEvent` 0x25e14; ack |
| 0x01 | CSNE_CMD_STOP | 0x2734c | `CDMediaBusManager::GetEndPointState` (0x1244c) on [ctrl+0x160]; call failure -> hang (line 0x445); success -> 0x29958 (not fully walked) |
| 0x02 | CSNE_CMD_RESET | 0x27404 | len==8 else err; posts controller-FSM event 2 -> from state 1/2: ->1 `ResetEvent` 0x25e0c (from 0/3: no row); ack |
| 0x03 | CSNE_CMD_CONFIG_GET | 0x27470 | len==16, `*outlen>0xf`; reply [+8]=IspTimestampFrequency()*1e6 (0x2ad54, mul 0xf4240), [+0xc]=[ctrl+0x1c0] |
| 0x04 | CSNE_CMD_PRINT_ENABLE | 0x274f0 | len==0xc, `*outlen>0xb`; `[ctrl+0x1a0] = (payload u32 +8 != 0)`; reply [+8] = previous value |
| 0x05 | CSNE_CMD_REG_FILE_LOAD | 0x2a25c | **bare ack, no handler** |
| 0x06 | CSNE_CMD_BUILDINFO | 0x27624 | len==8; buildinfo print 0x24234; ack |
| 0x10 | CSNE_CMD_BOOT | 0x2a25c | **bare ack — BOOT is a no-op in this build** (matches live "no effect") |
| 0x11 | CSNE_CMD_PING | 0x2a25c | bare ack |
| 0x1d | CSNE_CMD_CH_BUFFER_POOL_CONFIG_SET | 0x27174 | routes on payload[0] class byte (0x12ff/0x10ff/0x0000/0x1000 -> 0x28314/0x28714/0x28338/0x2872c) |
| 0x1f | CSNE_CMD_CH_PROPERTY_WRITE | 0x27174 | same router |
| 0x21 | CSNE_CMD_TRACE_ENABLE | 0x27b4c | len==0xc, `*outlen>0xb`; `CRPCClient::PropertyWrite` (0x304b0) id 0x1602, value [x21+8] -> pipe msg tag `0x04000014|seq<<8` type 1 -> enables T2H event stream (live-verified with value 0xE) |
| 0x22 | CSNE_CMD_RESOURCE_INFO_GET | 0x27bcc | fills reply [+8..+0x27] from static template (0x803d0/0x803c8), [+0x20]=1 |
| 0x23 | CSNE_CMD_STATS_BUFFER_SIZE_GET | 0x27c68 | shape A len==0x10: `statsBufferSizeGet([ctrl+0x140], [x21+8], -1)` (0x380dc) -> reply [+0xc]; shape B len==0x28: 0x297bc -> 0x2a214 (`w2=[x21+0x18]`); result==0 -> ack status 3 ([buf+6]=2) |
| 0x24 | CSNE_CMD_SUSPEND | 0x27ce0 | len==8; DMB endpoint state; call failure -> hang (line 0x48f); success paths 0x2a004/0x2a068 (not fully walked) |
| 0x25 | CSNE_CMD_DSID_SET | 0x27da0 | **hangs via `!isProgramLoaded` (0xb3a74) if [ctrl+0x230]!=0** (line 0x39e) |
| 0x26 | CSNE_CMD_MCACHE_SIZE_GET | 0x27e30 | reply [+8] = 0x300000 |
| 0x27 | CSNE_CMD_SECURE_MODE_START | 0x27e88 | see §2 |
| 0x28 | CSNE_CMD_SECURE_MODE_STOP | 0x27ef4 | see §2 |
| 0x29 | CSNE_CMD_SET_SNE_PMU_BASE2 | 0x27f60 | prints payload u64 +8; PCS ([0x4fa358]) slot6 `SetPMUBaseAddress(payload)` — PCS null -> hang (line 0x52b); **then ExeLoop slot34 `powerDownAne` unconditionally**; ack. See §6 |
| 0x2a/0x2b | IPC_ENDPOINT_SET2/UNSET2 | 0x27ff8/0x28034 | gated on [ctrl+0x234] (0x2a hang line 0x7f0); 0x2b TracePost2Host(1,0xc,…) |
| 0x2d | CSNE_CMD_SET_DYNAMIC_POWERGATE | 0x28178 | payload byte +8 -> ExeLoop slot28 `SendDynamicPowerGateRequest` (0x51a8c) -> pipe request type 5 |
| 0x2e | CSNE_CMD_ANE_DEFAULT_SETTING_SET | 0x281e4 | prints u64 count +8 and count u64 pairs from +0x10; **hangs `!isProgramLoaded` if [ctrl+0x230]!=0** (line 0x3b6); apply path 0x28ca0 not walked |
| 0x2f | CSNE_CMD_CPU_LOAD_GET | 0x282b4 | len==0xc, `*outlen>0xb`; 0x2ba9c -> reply [+8]; side-effect-free |

Model ops (table 0x2a658): 0x200 LOAD_PROGRAM 0x27218, 0x201 UNLOAD 0x28348, 0x202
CREATE_PROCESS 0x28374, 0x203 TERMINATE 0x283a0, 0x204 PROCEDURE_CALL 0x283cc, 0x205-0x208,
0x20b/0x20c/0x20e handlers; **0x209, 0x20a, 0x20d (PREMAP_BUFFER) = bare acks**. Events
0x300-0x304 and 0x7000/0xff00 are other-direction classes.

### The 0x28 contradiction, resolved

The macOS 26 kext calls 0x28 SECURE_MODE_STOP; the earlier linear scan of this region
concluded "0x28 = STATS_BUFFER_SIZE_GET (0x27cb4 -> 0x297bc)". The scan was wrong: 0x27cb4
is inside **cmd 0x23's** handler (entry 0x27c68) and is 0x23's own shape-B length compare:

```
027cb4: cmp    x22, #0x28             ; x22 = envelope length; len == 0x28 shape
027cb8: b.eq   #0x297bc
027cbc: cmp    x22, #0x10             ; else len == 0x10 shape
```

The dispatch table itself is unambiguous — entries are s32 offsets from 0x27164 at
0x2a598 + 4*cmd:

```
[0x23] @0x2a624: 04 0b 00 00   -> 0x27c68  (STATS_BUFFER_SIZE_GET)
[0x27] @0x2a634: 24 0d 00 00   -> 0x27e88  (SECURE_MODE_START)
[0x28] @0x2a638: 90 0d 00 00   -> 0x27ef4  (SECURE_MODE_STOP)
```

and the two handlers are identical except the argument to the same virtual call:

```
027e88/027ef4: ldr  x0, [x20, #0x130]      ; CAneEngineExeLoopH14 (created 0x26610, "AneEngine")
027edc/027f48: ldr  x8, [x0]               ; vtable 0xc7e30 (set in H14 ctor 0x490ec)
027ee0/027f4c: ldr  x8, [x8, #0xd8]        ; slot 27 = SendSecureModeRequest (H14 override 0x5197c)
027ee8: mov  w1, #1                 ; START
027f54: mov  w1, #2                 ; STOP
027eec/027f58: blr  x8
```

Verdict: kext names 0x27/0x28 are correct for this firmware; the "STATS" reading was a
misattributed compare. The firmware's own name table (0xc5dd8) agrees.

## 2. SECURE_MODE_START (0x27) / SECURE_MODE_STOP (0x28) wire format

Envelope (transport-verified against the live CONFIG_GET/PRINT/TRACE path):
16 bytes, little-endian: `u32 0 @+0, u16 cmd @+4, u16 result @+6, u32 @+8, u32 @+0xc`.

- **Minimum length check: none.** Neither handler compares x22 (0x27e88/0x27ef4 have no
  `cmp x22`); only the dispatcher's header reads (+4, clear +6) touch the buffer. 16 bytes
  is what the working driver path posts; use that.
- **Payload fields read: exactly one, and print-only.** `ldr w8, [x21, #8]` feeds the
  debug print `[%s] CMD = %#04x [%s] at %lld : val=0x%x` (0xb488f, gated by
  PRINT_ENABLE [ctrl+0x1a0]). The mode is a hardcoded constant: 1 for 0x27, 2 for 0x28.
  Host payload is otherwise ignored.
- **Call chain / what they post:** `CmdProcessor` -> `ExeLoop vtable slot 27`
  (`CAneEngineExeLoopH14::SendSecureModeRequest(u32)` 0x5197c):
  1. `sub w8, w1, #1; cmp w8, #2; b.hs panic` — mode must be 1 or 2 (unreachable from
     these opcodes; constants).
  2. trace events (2,6) and (2,7) via `CRPCClient::TracePost2Host` (0x3000c).
  3. builds `{u64 tag = ((seq++)<<8 & 0xffff00) | 0x1000018, u32 type = 4 @+0x10, u32 mode @+0x14}`
     and `CPipe::Post([engine+0x160], msg, -1)` (0x20090).
  4. The ExeLoop drains its input ring -> `DataProcessor` (0x4f74c) type-4 branch (0x4fa44
     -> 0x4fc34): mode==2 -> STOP branch 0x4fcc4, mode not in {1,2} -> hang (line 0x7a3).
  - **They post NO request group.** The [engine+0x630]/[0x640]/[0x648]/[0x650] fields are
    RTOS event objects (see §3); nothing in this chain writes or signals them.
- **Reply fields written:** none. buf+6 was cleared to 0 at dispatch (0x27140) and the
  quick-ack sends the buffer back unchanged (status 0 = success).
- **Asserts/error returns on the path (all in DataProcessor, all hangs):**
  - START branch (0x4fc54): `ldrb w8, [engine+0x1a2]; cbnz -> hang` — assert
    `aneSecurePhase == false` (0xbbdf7), `CAneEngineExeLoopH14.cpp` line 0x788.
    On pass: prints trace string `secureMode Phase START` (0xbbe0f, trace-gated), PCS
    slot-10 call (no-op stub 0x151c0), if `isAneIdle` (0x4d0c4) then
    `powerUpAne(engine, 0, 1)` (vtable slot 33), sets **phase = 1** (0x4fe58).
  - STOP branch (0x4fcc4): `phase == 0 -> hang` — assert `aneSecurePhase == true`
    (0xbbe26), line 0x795. On pass: `secureMode Phase STOP` (0xbbe3d), PCS stub, if idle
    then `powerDownAne(engine)` (slot 34, 0x51c7c), sets **phase = 0** (0x4fd28).
  - phase is u8 [engine+0x1a2], 0 at boot (zero-filled object; nothing else writes it
    except these two branches). So START-before-STOP is enforced, and double-START or
    STOP-without-START hang the ExeLoop DataProcessor.

## 3. Who posts nonSec->Sec; FSM table 0xc8020; state meanings

**Correction to findings.md:** the request groups are
`[engine+0x640]` = **nonSec->Sec** and `[engine+0x648]` = **Sec->NonSec**
(findings swapped them; the string/branch pairing below is instruction-cited).

They are not request flags but RTOS event objects, acquired in the H14 ctor
(0x49760-0x49854, `CRTOSObjectPool::ObjectAcquire` 0x209c0) into +0x628, +0x630, +0x638,
+0x640, +0x648, +0x650. The only signallers in the whole image:

- `nonsec2SecIsr` (0x4a93c): writes `1` to MMIO 0x285874004, then
  `_RTK_semaphore_signal([engine+0x640])` (0x6aff4).
- `sec2NonsecIsr` (0x4a96c): writes `2` to 0x285874004, signals [engine+0x648].

`CAneEngineExeLoopH14::SignalProcessor(void*, token)` (0x4b92c, vtable slot 22) compares
the wake token against the group fields and is the **only** poster of ELFSM events:

```
04b9ec: ldr x8, [x19, #0x640]; cmp x8, x20; b.eq 0x4ba78
  0x4ba78: print "request nonSec -> Sec received: currState=%d" (0xbb806, state via 0x167a0)
  0x4babc: CFSM::PostCallback(elfsm, 2, 0)
04b9f8: ldr x8, [x19, #0x648]; cmp x8, x20; b.eq 0x4bacc
  0x4bacc: print "request Sec -> NonSec received: currState=%d" (0xbb834)
  0x4bb10: CFSM::PostCallback(elfsm, 3, 0)
  0x4bb18: pSneDrv = [engine+0x660]; EnableTQs (0x33270)   <- runs AFTER the event processes
```

Every other CFSM::PostCallback call site (0x272f0 ev0, 0x27468 ev2, 0x29ffc ev1) targets
the controller FSM [ctrl+0x1a8], not the ELFSM. **No host command — boot/START(0x00),
STOP(0x01), RESET(0x02), CONFIG_GET, BOOT(0x10), PRINT_ENABLE, TRACE_ENABLE, LOAD_PROGRAM
(0x200), CREATE_PROCESS (0x202), PROCEDURE_CALL (0x204) — posts a group or an ELFSM
event.** The nonSec->Sec path is reachable only through the hardware interrupt.

### ELFSM creation and table

Created at 0x49f38-0x49f6c: `CFSM::Create([0x4f8538], table 0xc8020, "ELFSM",
ctx=engine, initialState=1, ring=8, 0x20, traceLevel=0xa)` -> [engine+0x6b0]. Element
stride 0x30, `u32 type @+0`: 1 = declare (stateNbr @+8), 2 = transition
(from @+8, event @+0x10, to @+0x18, guard fn @+0x20, action fn @+0x28), 3 = terminator;
element 0 (0xc8020) is zero padding. **Initial state = 1** (`mov w4, #1` at 0x49f58;
`CFSM::Reset` 0x1651c matches block+8 == [fsm+0x40]).

```
E1  DECLARE 0
E2  T(0 -> 1)                     no action
E3  DECLARE 1
E4  T(1 -> 2)                     no action
E5  T(2 -> 3)  action FSMSwitchSecure 0x578b4      <- lives in state 1's range
E6  T(4 -> 0)                     no action         <- lives in state 1's range
E7  DECLARE 2
E8  T(2 -> 3)  action FSMSwitchSecure 0x578b4
E9  DECLARE 3
E10 T(3 -> 1)  action FSMSwitchNonSecure 0x579a4
E11 T(2 -> 3)                     no action
E12 TERMINATOR
```

Runtime (`CFSM::PostCallback` 0x167ac, synchronous): from the **current state's block** it
walks the following table elements while type==2 and takes the first row whose
**from == posted event id** — note the match is against the row's from-field, *not* against
the current state. Then `ProcessEvent` (0x168cc, receives transition+8): guard [t+0x20]
(0 = none) is called as `guard(engine, depth)` — nonzero -> ERR
"STATUS EXITING FAILED (%d, %s): [%d, %s]->[%d, %s]" (0xb21a4) and reject (return 2);
action [t+0x28](engine); current block := destination block (`[fsm+0x38]`, 0x16a98).
State getter 0x167a0 = `[[fsm+0x38] + 8]`.

**States:** 1 = initial, NonSec/**RUN** (`FSMSwitchNonSecure`: "switched from Sec ->
NonSec, ANE goes to RUN", 0xbde17). 3 = **PAUSE** (`FSMSwitchSecure`: "switched from
NonSec -> Sec, ANE goes to PAUSE", 0xbddc1). 2 = declared intermediate ("switching") —
unreachable from state 1 because E4 needs event 1 and nothing posts event 1. 0 = reset
target (only E6 points at it; E6 needs event 4, also never posted). 4 = vestigial (source
of E6, never declared, no inbound edges).

**The park mechanism, closed end-to-end:** a boot-time nonsec2SecIsr wakes
SignalProcessor with the +0x640 token -> event 2 -> from state 1 the scan matches **E5**
(from=2) -> destination state 3 + `FSMSwitchSecure` (assert !GetTQEn, vtable+0x108
`powerUpAne(engine,0,0)`, MMIO 0x285874000 = 2, `++[engine+0x61c]`). `powerUpAne`
(0x51b80) with w1==0 clears the **isHWReady override** `[engine+0x1a0]`
(set to 1 in the ctor at 0x49750). From then on `isHWReady` (0x50e64) runs its real
checks, and its state-in-{2,3} check (string 0xbc093, checked 0x511a4) fails forever, so
every submission parks (findings.md §Park semantics). No firmware code ever signals
+0x648 (the HW never raises sec2nonsec on our boots), so nothing returns the FSM to RUN.
Counters: `++[engine+0x61c]` (SwitchSecure), `++[engine+0x620]` (SwitchNonSecure).

The reverse action `FSMSwitchNonSecure` (0x579a4): same GetTQEn assert (line 0x65),
`++[engine+0x620]`, `TunableManager::ReloadTunables` (0x30ee8) on [engine+0x680], PCS
slot-9 stub, RUN print (same gates), then clears every priority slot
[prioCtx + n*0x428 + 0xad0] = -1 over [engine+0x198] entries.

## 4. Sec->NonSec path preconditions (0x33270 / 0x579a4)

- `CSneTMDrv::GetTQEn` (0x3328c): `ldr x8, [pSneDrv+0x48]; ldr w8, [x8, #0x2420];
  ubfx w0, w8, #13, #1` — **bit 13 of the CSneTMDrv MMIO window register +0x2420**.
  `EnableTQs` (0x33270) sets it (`orr w10, w10, #0x2000`); **nothing in the firmware ever
  clears it**. We never enable host TQs on T6021 (no TM path), so at the point we would
  send anything the bit reads 0 and the assert passes.
- The assert in both switch actions is `!pExeLoop->pSneDrv->GetTQEn()`
  (`!pExeLoop->pSneDrv->GetTQEn()` at 0xbdda3/0xbddf1, `CAneEngineExeLoopH14FSMDef.cpp`
  lines 80/101), evaluated twice (normal assert-macro expansion). Failure = ERR print +
  0x1a724 + self-loop = **hang**. Note the ordering hazard: the request-loop's Sec->NonSec
  branch calls `EnableTQs` *after* posting event 3, so once that path ever runs, bit13
  stays 1 and any later `FSMSwitchSecure` asserts-hangs. Not our path today, but it makes
  repeated secure-mode cycling a one-way door on this build.
- Phase preconditions: see §2 — START requires phase==0, STOP requires phase==1, both
  enforced by hang, not error return.

## 5. Which command reaches the counter print at 0x4b9e0

None — the site is doubly gated and both gates are structurally closed in this build:

- It sits at `SignalProcessor` entry (0x4b9bc-0x4b9e8, format 0xbb7e2
  "nonSec2SecCnt=%d, sec2NonSecCnt=%d"), i.e. it would fire on **every** ExeLoop wake.
- Gate 1: bit30 of [engine+8] (`tbz w1, #0x1e`). **No instruction in the image writes
  [engine+8]** (the engine+8 store hunt corroborates the notebook's earlier "no writer"
  result; the bit30 ORs at 0x4a710/0x4a758 are MMIO words at 0x285c20818, not engine+8).
- Gate 2: trace-buffer global [0x4f87a8] — written only by `CTraceBuffer::C2` (0x31cd8),
  which has **zero callers**; the singleton is never constructed.

So no opcode (STATS 0x23, CPU_LOAD_GET 0x2f, anything) surfaces the counters; they live at
[engine+0x61c]/[engine+0x620] and only move via the FSM actions. Reading them needs live
memory inspection of the ExeLoop object (the observer/kcore routes used in earlier
sessions), not a host command. Side-effect-free reads that DO work over the command
interface: 0x03 CONFIG_GET, 0x23 shape A, 0x26, 0x2f.

## 6. Recommendation

Target state to restore: the isHWReady override [engine+0x1a0] = 1 (the engine is otherwise
healthy; tiles are parked only because isHWReady's secure-mode check fails).

**Recovery of the wedged engine (before or after re-sending the call):**

```
CSNE_CMD_SET_SNE_PMU_BASE2 (0x29), payload 0:
00 00 00 00  29 00 00 00  00 00 00 00  00 00 00 00
```

0x29 is the only host-reachable path that calls `powerDownAne` (0x51c7c) **unconditionally**
(0x27fe4 -> vtable+0x110), and `powerDownAne`'s first store is `strb #1, [engine+0x1a0]`
(0x51c9c) — the override, restored before any power bookkeeping. No length check, no phase
precondition, no idle requirement (the parked job does not block it, unlike 0x27/0x28 whose
power calls are `isAneIdle`-gated). Expected console line (with PRINT_ENABLE live):
`[...] CMD = 0x0029 [CSNE_CMD_SET_SNE_PMU_BASE2] at %lld : val=0x0`, ack 0.

Then re-send PROCEDURE_CALL (existing sequencer/sections tooling, commit 7e429075) as a
**fresh** submission: `DataProcessor` type-1 -> `isHWReady` returns 1 via the override ->
slot alloc -> launch 0x4e604, with the launch path's own `powerUpAne(engine, 0, 1)`
(0x4f92c) re-powering and reloading tunables. Expect the T2H event stream to diverge from
the park signature: instead of only the parked (2,0) recursion and the silent
"final program event", the accept chain should reach slot allocation and the output buffer
should lose its NaN sentinel.

Because the launch clears the override again, and the ELFSM stays in 3, **every**
submission needs a preceding 0x29 while the FSM is parked:
`0x29 -> CALL`, per call. The original parked request is never retried to completion (its
retry only fires on a completion) — one leaked queue slot, harmless.

Risks, in order:
1. 0x29 first calls `PCS slot6 SetPMUBaseAddress(payload)`; with payload 0 it sets the PMU
   base to 0, and the subsequent `PCS PowerDown` (taken because [engine+0x1a1]==1 after the
   boot-time SwitchSecure) writes through whatever base results. We never sent 0x0c
   SET_SNE_PMU_BASE, so the firmware-side power write path is unproven on our boots. If it
   data-aborts, the firmware wedges (recovery = reboot). Try payload 0 once on a disposable
   boot watching for exception records; if it aborts, retry with the ANE power window as
   the base: `00 00 00 00 29 00 00 00 00 40 84 82 02 00 00 00` (u64 0x28e084000).
2. Do **not** use 0x27/0x28 to fix the park: §2/§3 prove they never touch the ELFSM or the
   groups; START on an idle engine *clears* the override (creates the park precondition),
   and the phase asserts hang on ordering mistakes.
3. Avoid cmd 0x25/0x2e after a program is loaded ([ctrl+0x230] set) — both assert-hang.

**Firmware log lines to expect** (PRINT_ENABLE 0x04 first, TRACE_ENABLE 0x21 value 0xE):
the `CMD = 0x00XX [CSNE_CMD_...]` line per command with `ack 0`; for the recovered CALL the
same accept chain already validated live, then slot allocation instead of a second parked
(2,0); no `[isHWReady]` and no `secureMode Phase` lines — those gates are dead (§5).

## Corrections to findings.md recorded here

- Request groups: +0x640 = nonSec->Sec, +0x648 = Sec->NonSec (findings had them swapped;
  its [0x630] row is the Debug-queue group per 0xbb862).
- 0x28 is SECURE_MODE_STOP (kext table correct); the STATS misread was cmd 0x23's length
  compare at 0x27cb4. `SendSecureModeRequest`/`powerUpAne`/`powerDownAne` H14 overrides
  (0x5197c/0x51b80/0x51c7c) are live code — the base-class stubs at 0x3abec+ are shadowed
  by vtable 0xc7e30.
- The counter print (0x4b9e0) is unreachable (both print gates dead), so "send the command
  that prints the counters" from findings.md's next-steps is not executable; use the 0x29
  route in §6 instead.
