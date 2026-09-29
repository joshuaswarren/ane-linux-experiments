# ExeLoop launch and completion decode — H14, macOS 13.5 firmware (boot 874b3bd2)

Static decode of `/tmp/fw135.macho` (sha256 a9c4b771…, 5,004,072 B; VA = file off − 0x4000 for
__TEXT 0..0xc4000; __DATA 0xc4000..0x4fc000 = file off + 0x4000) plus live reads of
`/tmp/m2elfsm/heap.t0.bin` (24 MiB @ VA 0x20fc000000) and `/tmp/m2elfsm/fwbuf.t0.bin` (7 MiB).
Function names are from the firmware symbol table (resolved via LC_SYMTAB). Every claim carries
its instruction address; live values carry dump offsets. No hardware, no ssh, no commits.

**Dump-reliability caveat (methodology, verified):** in `fwbuf.t0.bin`, image-backed __DATA
reads as stale zeros — e.g. the CRPCClient global at VA 0x4f8790 and `CPowerControlService::instance`
at VA 0x4fa358 both read 0 in the dump, yet the objects provably exist (traces fired; the live
instance is reachable from the controller object). Owned-region objects (fwbuf ≳0x500000) and the
heap dump read live. All instance reads below therefore go through live objects (controller,
engine, progMgr), never through image .data globals.

Named functions used throughout (symbol table):

| Addr | Symbol |
|---|---|
| 0x4f74c | `CAneEngineExeLoopH14::DataProcessor(ulong, ulong, void*)` (vtable+0x90) |
| 0x5148c | `CAneEngineExeLoopH14::SendHWRequest(uint, sAneRequest*, uint, uint)` |
| 0x52504 | `CAneEngineExeLoopH14::handleCallProcedureWithBar(void*, uint, sCSneCustomBarInfo*)` |
| 0x4e604 | `CAneEngineExeLoopH14::pushToHW(uint, uint, sAneRequest*)` |
| 0x4e404 | `CAneEngineExeLoopH14::pushSingleUseCacheRequestToHW(sAneRequest*, uint, bool)` |
| 0x50e64 | `CAneEngineExeLoopH14::isHWReady(sAneRequest*)` |
| 0x4adf4 | `CAneEngineExeLoopH14::reportFinishEvent(uint)` |
| 0x4a3d0 | `CAneEngineExeLoopH14::EventIsr(void*)` |
| 0x51b80 / 0x51c7c | `powerUpAne(bool,bool)` / `powerDownAne(void)` |
| 0x5197c | `CAneEngineExeLoopH14::SendSecureModeRequest(uint)` (vtable+0xd8) |
| 0x34250 / 0x345e8 | `CSneTMDrvH14::StopTqEnable(uint,uint,uint)` / `enqueueTM(sAneEngineRequest*,uint,uint,uint)` |
| 0x33270 / 0x3328c | `CSneTMDrvH14` TQ-enable setter / `GetTQEn` |
| 0x37190 | `CAneProgramManager::SetupEngineRequest(sCSneCmdProcedureCall const*, sEngineRequest*, uchar, uchar, uint, sCSneCustomBarInfo*)` |
| 0x375dc / 0x37848 | `CAneProgramManager::RunProc(...)` / `RunProc2(...)` |
| 0x34a44 | `CAneProgramManager::AneCallBack(sEngineRequest*, eEngineRequestCallBackEvent, void*)` |
| 0x41718 | `CAneProgramManagerH14::CreateProcess(uint, sCSneCmdCreateProcess const*)` |
| 0x270dc | `CANEController::CmdProcessor(ushort, ulong, ulong*)` (model-op table 0x2a658) |
| 0x27244 | START (0x00) handler; 0x27f60 = SET_SNE_PMU_BASE2 (0x29) handler |
| 0x25ca8 / 0x25e0c / 0x25e14 | `CANEController::PowerOnEvent` / `ResetEvent` / `StartEvent` |
| 0x578b4 / 0x579a4 | `FSMSwitchSecure()` / `FSMSwitchNonSecure()` (CAneEngineExeLoopH14FSMDef.cpp) |
| 0x6228c / 0x62694 / 0x627b0 / 0x6300c / 0x62a9c | `CPowerControlService::Create` / `AneH14::SetPMUBaseAddress` / `AneH14::PowerUp` / `AneH14::PowerDown` / `AneH14::GetPowerStatus` |
| 0x3000c / 0x30244 | `CRPCClient::TracePost2Host(ulong, int, u8×5)` / ktrace record writer |
| 0x2f33c | `CRPCClient::ProgramEvent(uint,uint,uchar,uchar,void*)` |

## 1. Launch path (0x204 PROCEDURE_CALL, priorityId 5, boot 874b3bd2)

**Dispatch.** CmdProcessor 0x270dc → model-op table 0x2a658 rel 0x27208 → handler chain →
`handleCallProcedureWithBar` 0x52504 (ExeLoop vtable+0x1a8), which prints
`"Call Procedure command  (Prog %d, Process %d, procedure%d CustomBars %d)"` (0xbc37d, at 0x52554),
allocates a 0x3d0-byte `sAneEngineRequest` via 0x5162c (0x52564) and fills:
`[req+0x3d0] = [[mInstance+0x9878]+0x48]` (0x5257c–88), `[req+0x3d4] = [cmd+0xc]` (0x5258c),
`[req+0x3d8] = byte 0xc07c0[[cmd+0x18]]` (0x525a0–ac).

**Priority → queue.** Map table 0xc07c0 = `[7,6,5,4,3,2,1,0]`: raw cmd priority 2 → **priorityId 5**
(also the TQ queueId — `StopTqEnable` asserts `queueId < 8`, 0xb6a64). Live check: shadow frame
+0x3d8 = 5.

**Program-manager stage.** `RunProc` 0x375dc emits T2H **(2,26)** at 0x37648 (args
`[cmd+8],[cmd+0xc],[cmd+0x20]`) then calls `SetupEngineRequest` 0x37190 (0x37668), which:
translates the call's buffer list (entries at `cmd+0x80`, 0x30 stride, count `[cmd+0x28]`, cap
0x40 — 0x3721c–a8), memsets the request (0x372b0), calls H14 `CreateProcess` through progMgr
vptr+0x40 (0x372c4–d4; H14 vtable 0xc7ca0 slot +0x40 = 0x41718), and on success (0x372ec):
`[req+0x220] = [progMgr+0x9888]`, `[req+0x328] = [progMgr+0x9890]` (0x372f0–14),
`[req+0x370] = flags` (0x372f8–30c). `[req+0x328]` is the **TD count for the TQ kick**; its
source field `[progMgr+0x9890]` reads **0xffffffff in the live dump** (progMgr H14 instance at
heap 0x15fe0c0 — vptr 0xc7cb0 verified). `RunProc` failure path (SetupEngineRequest ≠ 0) posts
`ProgramEvent` + T2H **(2,27)** (0x37674–c4).

**Queueing.** `SendHWRequest` 0x5148c (ExeLoop vtable+0xc8): T2H **(2,2)** on entry (0x514ec),
allocates, copies 0x3d0 bytes, stores `+0x3d0/+0x3d4/+0x3d8`, bumps `[engine+0x118]`, posts event
`0x1000018` to the work queue (0x20090, 0x51558), T2H **(2,3)** on success (0x51580).

**Worker submit — `DataProcessor` 0x4f74c (vtable+0x90).** Asserts processor stat
`[engine+0x588] == 0` ("incorrect processor (%d) stat value (%d) at enter stage", 0xbd9de),
requires event id 0x18 (0x4f7dc), payload word −1 ∈ 0..4 via table 0x4ff44. **Type 1 = submit**
(0x4f810): computes `jobId = [engine+0x18c]*[req+0x3d8] + [req+0x3d0]` (0x4f818–24) and emits
T2H **(2,0)** with args (priority, jobId, 0, 0, 0) at 0x4f8a0 — **the observed 0x200 record
"(5, 0xa, …)" = priority 5, jobId = 2·5+0 = 10**. Then:
`isHWReady` 0x50e64 (0x4f8b8) — short-circuits true if override byte `[engine+0x1a0] != 0`
(0x50e78), else bounds-checks jobId < `[engine+0x198]` (=0x10 live), prioId < `[engine+0x184]`
(=8), and the job table `[engine+0x688][jobId]+0x30` — **passed**;
slot alloc (`alloc` 0x4e2e0 at 0x4f8ec): free-count `[engine + prio·4 + 0x6c4]` ∈ {0→slot 0,
1→slot 1, 2→slot 0, 3→fail −1}; on success stores count=3 and `[frame+0x3e8] = −1`; prints
`"Priority %d Slot %d"` (0xbbd6c) — slot **0** (frame +0x3e8 = 1 live, see below);
`[engine vtable+0x108](engine, 0, 1)` (0x4f928); helper 0x4deb8; then **`pushToHW` 0x4e604**
(0x4f95c) with (prioId=5, slot=0, req); finally 0x4ea7c (0x4f968).

**`pushToHW` 0x4e604 — where the hardware kick lives (and didn't happen).**
1. seqno = uniq+1, must be ≤ 0x40 ("idx >= 0 && idx <= 64", 0xbc297) → `[req+0x3e8] = 1` (0x4e6c8).
2. Per-seq entry = `align64([engine+0x6a8]) + seq·0x280 + 0x40` (0x4e6d8–f0). Live:
   `[engine+0x6a8] = 0x20fd68bb50` → entry **0x20fd68be00**, stored at `[req+0x10]`. This
   **0x280-byte per-seq record in firmware heap memory** (not the program Descriptor section) is
   the task-descriptor handle the TQ path uses; its live content: `07a00001 fbc00000` then zeros.
3. `[req+0x248] = −1` (0x4e6f8); byte `[engine+0x208] = 0` selects the dbgEvent-index side path
   (global 0x4f87f8 — null → skipped, 0x4e8f8–904).
4. **TQ doorbell gate at 0x4e704:** if `[req+0x328] != −1` →
   `CSneTMDrvH14::StopTqEnable(queueId, tdCount=[req+0x328], seqno)` (vtable+0x70 = 0x34250),
   which writes `[0x285c00000 + 0x0200048c] |= 0x10` (0x34274–7c) and the per-queue doorbell
   **`[base + 0x02000818 + queueId·0x2c] = 0x80000000 | (tdCount & 0xffff) | ((seqno & 0xff)<<16)`**
   (0x34280–9c). For queueId 5: **0x285c008F4**.
   **Live: shadow frame +0x328 = 0xffffffff → the doorbell was SKIPPED. No MMIO write occurred
   in this launch.** (`[engine+0x208]=0` only bypassed the dbgEvent bookkeeping; both paths
   converge at the 0x4e704 gate.)
5. Flags `[req+0x3ec]` bits 0/1/2 must be clear (`isLastTDFetched/isLastTDCompleted/isAborting`
   asserts, 0x4e72c–0x4e734 → 0xbbb21/bbb04/bbb3c); bits 5–7 cleared.
6. Mutex; **shadow copy**: 0x428 bytes req → `engine + prio·0x850 + slot·0x428 + 0x6e8`
   (0x4e748–64) — i.e. a 16-frame job array at `engine+0x6e8`, frame = prioId·2+slot;
   `[frame+0x3e0] = uniq` (0x2ad74 timestamp, live 0x93fbdd78).

**The other submission path (for contrast).** `pushSingleUseCacheRequestToHW` 0x4e404 copies the
job to the shadow frame and calls `enqueueTM` (vtable+0xc0 = 0x345e8), which pushes a 7-word
descriptor **directly at MMIO 0x285c20400**: `{addr_lo, addr_hi, ptr_lo, ptr_hi, 0x97,
size>>2, queueId}` (0x34620–58) — this is the TM-descriptor push used by the cache-request path,
not taken by our 0x204 launch.

**Observed T2H record map.** `TracePost2Host(type, code, a1..a5)`; record +0x0c u16 =
`code | type<<8` (0x3039c–a0), args at +0x10..+0x30 (0x303a4–ac), timestamp +0x38.

| u16 | (type,code) | Site | Emitter (file) | Args |
|---|---|---|---|---|
| 0x106 | (1,6) | 0x290b8 | CANEController.cpp cmd dispatch | [env+8], [env+0xc] |
| 0x108 | (1,8) | 0x2919c | CANEController.cpp | [env+8], [env+0xc], [env+0x20] lo/hi |
| 0x109 | (1,9) | 0x294e4 | CANEController.cpp | same |
| 0x21a | (2,26) | 0x37648 | CAneProgramManager::RunProc | [cmd+8], [cmd+0xc], [cmd+0x20] |
| 0x202 | (2,2) | 0x514ec | SendHWRequest entry | 0,0,0,0,0 |
| 0x200 | (2,0) | 0x4f8a0 | DataProcessor submit (launch) | 5, 10, 0, 0, 0 |
| 0x21e | (2,30) | 0x34b54 | AneCallBack (pre-ProgramEvent) | [req+0x318], [req+0x31c], [req+0x310] |
| 0x21f | (2,31) | 0x355b0 | AneCallBack (after `ProgramEvent` 0x2f33c at 0x35584) | same |
| 0x203 | (2,3) | 0x51580 | SendHWRequest success | 0,0,0,0,0 |
| 0x21b | (2,27) | 0x376c4 / 0x37938 | RunProc / RunProc2 failure-callback path | [req+8],[req+0xc],[req+0x20] |

Ordering note: (2,0) lands between (2,2) and (2,3) because the worker that drains the
0x1000018 event runs concurrently with `SendHWRequest`'s tail (preemptive RTOS scheduling on the
SNE) [INFERENCE on exact interleaving; all four sites are verified].

## 2. Completion path

**Interrupt.** `CAneEngineExeLoopH14::EventIsr` 0x4a3d0 is registered on **IRQ line 4** in the
ExeLoop constructor: `CISRManager::Register(4, EventIsr, engine, 0, 1)` at 0x494c0–dc
(instance global 0x4f8548); line 6 = `DbgEventIsr` 0x4a598 (0x49500), line 8 = `TqStopIsr`
0x4a680 (0x4953c); the sec/nonsec switch ISRs (0x4a93c/0x4a96c) ack via MMIO
**0x285874004 = 2** (0x4a974–84).

**What it reads.** The TM (TMD) hardware event FIFO at 0x285c20400-block:
count `[0x285c20428] & 0x7f` (≤ 64, assert "eventCount <= 64" 0xbb6c8), entry word at
`[0x285c2042c]` per iteration, pop by reading `[0x285c20430]`, re-enable `[0x285c20488] |= 2`
(0x4a404–b0). Event word bits 31:24 = type; **type 5 = TD finish** → `reportFinishEvent(seqno =
bits 23:16)` (0x4a440–54 → 0x4adf4), which maps seqno → (priority, slot) via 0x4b044
(asserts `foundIndex < 8`, `slot < 2` — 0xbb66d/bb67c) and inspects slotCtx flags
`[slotCtx+0xad4] bit3`, `[slotCtx+0x919] bit7`, `[slotCtx+0x930]` (0x4ae3c–f4).

**What it signals.** Events are pushed into rings at `[engine+0x5f0]` / `[engine+0x5f8]`
(32-byte entries; head/tail/size at +0x48/+0x50/+0x58, wrap counter +0x64) and the ISR posts the
worker semaphore `[engine+0x628]` via 0x6aff4 (0x4a540–44). The ExeLoop worker
(`HandleEventInt` 0x4bebc / the FIFO-drain loop at 0x4f0ec–0x4f230, same logic inlined in the
worker function) dequeues and drives `DataProcessor` event 0x18 payload types 2–5 (table
0x4ff44): 2 = `handleAbortCacheRequest` 0x4ff58, 3 = idle report
(`[engine+0x1a0]` → `[payload+8]`, sem `[engine+0x658]`), 4 = secure-mode state guard (asserts
ELFSM state ∉ {2,3}, line 0x77f), 5 = `[engine vtable+0x150]` power-gate call. Job completion
reaches the host through `CAneProgramManager::AneCallBack` 0x34a44 →
`CRPCClient::ProgramEvent` 0x2f33c (posted at 0x35584), bracketed by T2H **(2,30)** /
**(2,31)**.

**Preconditions for the hardware to raise it — all four unmet in boot 874b3bd2:**
1. **TQ doorbell rung** — skipped (§1, `[req+0x328] = −1`). Without it the TQ never fetches the TD.
2. **TQs enabled** — `EnableTQs` 0x33270 (sets bit13 of `[0x285c00000+0x02000420]`; `GetTQEn`
   0x3328c reads the same bit) is called from exactly one place: the ELFSM event pump at
   0x4bb18, immediately after the "Sec → NonSec" transition (`FSMSwitchNonSecure` 0x579a4,
   console "switched from Sec -> NonSec, ANE goes to RUN"). The switch counters
   `[engine+0x61c]` (nonsec→sec) and `[engine+0x620]` (sec→nonsec) are **0 / 0** in the dump —
   neither switch ever ran, so **TQEn = 0**. (`FSMSwitchSecure`/`NonSecure` both assert
   `!GetTQEn()` while switching — 0x578cc–0x57930 / 0x579d8–0x57a0c.)
3. **Power** — `powerUpAne` → PCS `PowerUp` returns 0 with the PMU base unset (§4): no-op.
4. **SneTMDrv register base** — `[pSneDrv+0x48] = 0x285c00000`, non-null ✓ (a null base would
   have hung the firmware on the "baseAddr" assert 0xb6a3e in every TQ access).

Conclusion: the TD never executes; the TMD FIFO stays empty; IRQ 4 never fires. The event we
never saw is the completion side of §2 — `reportFinishEvent`/`AneCallBack` T2H records and the
`ProgramEvent` — which cannot exist until 1–3 are fixed. This is consistent with (and supersedes
the mechanism for) the falsified "secure park" theory: the engine is not parked by a secure-mode
switch (counters 0); it was never un-parked in the first place.

## 3. Live state from the dumps (boot 874b3bd2)

Engine object at heap offset **0x17EA410** (VA 0x20fd7ea410), vtable **0xc7e30** ✓.

| Field | Live value | Meaning |
|---|---|---|
| engine+0x1a0 / 0x1a1 / 0x1a2 (bytes) | 00 / 01 / 00 | override=0; "powered" flag — **ctor default 1** (strb at 0x4a058 in the ExeLoop ctor), NOT evidence of a power-up; phase=0 |
| engine+0x208 / 0x218 | 0 / 0 | dbgEvent-select byte / dbgEvent table |
| engine+0x184 / 0x188 / 0x18c / 0x198 | 8 / 0x200 / 2 / 0x10 | maxPrio, job-table size, jobs-per-priority (jobId = 2·prio+base), maxJobs=16 |
| engine+0x588 / 0x5ac | 0 / 0 | DataProcessor stat ok / counters |
| engine+0x61c / 0x620 | **0 / 0** | nonsec→sec / sec→nonsec switch counters — **neither switch ever ran** |
| engine+0x6a8 | 0x20fd68bb50 | per-seq record table base (64 × 0x280 B) |
| counts[0..7] @ engine+0x6c4 | 0,0,0,0,0,**1**,0,0 | prio 5 bit0 set = job in flight (alloc wrote 3 at 0x4f8f8-alloc, launch/completion path left 1) |
| prio5 slot0 shadow frame @ engine+0x2994+0x6e8 = heap 0x17ed488 | +0x3d8=5, **+0x3e8=1 (seqno)**, +0x3ec=0, +0x3e0=0x93fbdd78, **+0x328=0xffffffff**, +0x370=3, +0x220=0, +0x3d0/3d4=0, +0x3f0=0, +0x10=0x20fd68be00, +0x238/0x240/0x248=0 | in-flight job; +0x328=−1 is the doorbell-skip reason |
| frame +0x00..+0x2c | +0x08=0x20fd5ffde0, +0x18=0xc00c0080, +0x20=0x00fbedc0, +0x24=0xf4000000, +0x28=0xf4000000, +0x2c=0x01000000 | request head (user VA, attr word, IOVA-ish pair) |
| per-seq entry 0x20fd68be00 (0x280 B) | `07a00001 fbc00000` then zeros | TD record for seqno 1 |
| SneTMDrv [engine+0x660] = heap 0x16145c0 (VA 0x20fd6145c0) | vtable 0xc75c8 ✓, name "SneTMDrv", **+0x48 = 0x285c00000**, +0x40=0xffffffff | register base non-null |
| progMgr H14 heap 0x15fe0c0 | vptr 0xc7cb0 ✓, +0x9858=0x14, +0x9888=0x800000000, **+0x9890=0xffffffff** | TD-count field still invalid → every 0x204 copies −1 into req+0x328 |
| PCS instance fwbuf 0x57e3f0 (VA 0x200057e3f0, from controller+0x180) | vptr **0xc8818** (AneH14, not dummy), name "PowerControlH14", +0x48=**1** (created), **+0x58=0 (PMU base NOT set)**, +0x60=0 (set-count 0) | see §4 |
| controller fwbuf 0x6602d0 | vptr 0xc5d70, +0x130=engine ✓, +0x180=PCS ✓, +0x1a8=0x200065e6a0 (ANEFSM), +0x1a0=1 (cmd print on), +0x230=1 | |
| ELFSM core heap 0x16347d0 | magic ✓, name "ELFSM", table 0xc8020, current 0xc80b0 → state id [0xc80b8]=**1 (RUN)**, core+0x40=1 | matches prior observation |
| controller FSM core fwbuf 0x65e6a0 | name "ANEFSM", table 0xc5388, current **0xc5418** → state id [0xc5420]=**1** | see §5 |

## 4. powerUpAne 0x51b80 and the PMU base

`powerUpAne(bool clearOverride, bool withDpe)`:
1. `PCS = [0x4fa358]` (0x51b9c–a4) — the image .data global (live value reachable via
   controller+0x180; the dump's copy of the global itself is stale-zero, see caveat).
2. `clearOverride == 0` → `[engine+0x1a0] = 0` (0x51bd8); logs "ANE powering up for job
   submission, isAllIdle: %d" / "ANE pre powering up…".
3. `cbz PCS → 0x51c68` (0x51c04): a null PCS skips all PCS work.
4. If `[engine+0x1a1] != 0` → **exit** (0x51c08–0c) — the ctor-default 1 (0x4a058) makes
   `powerUpAne` a no-op until something clears the flag.
5. `PCS->vptr+0x38` = `AneH14::PowerUp` 0x627b0 (0x51c10–1c). **PowerUp:** dummy check
   (`[pcs+0x48]==0` → assert "mPowerControlServiceCreated" 0xc0228); **`[pcs+0x58] == 0` →
   log "PMU address is not set" (0xbfd11) and return 0 without touching any hardware**
   (0x627cc–0x62878, return value `pmuBase != 0`); a set base must equal the constant
   **0x28e084008** else assert "pPMUAddress == (size_t*)(0x28e084008 + (0x0))" (0xbfd28); then
   `GetPowerStatus(PowerDomain_Id_H14_ANE_TD)` must read 0 and `…_ANE_BASE` must read 0
   (asserts "false == GetPowerStatus(...)", 0x6289c/0x628e0) before the PMU-mailbox power
   sequence proceeds.
6. `PowerUp == 0` → `powerUpAne` **exits at 0x51c20 without setting `[engine+0x1a1]` and
   without the SneTMDrv tail call** (`vptr+0x50` = `CSneTMDrvH14::Reset` 0x340f4, which
   initializes the 8 TQ config registers `[0x285c00800 + q·0x2c] = 0x201` from table 0xafdd0 =
   `[1,2,3,4,5,6,30,31]`, 0x34140–70).
7. Only on success: `[engine+0x1a1] = 1` (0x51c28), optional `TurnOnDPE` (vptr+0x48 = 0x63364,
   0x51c38–44), then the `Reset` tail call (0x51c48–64).

`SetPMUBaseAddress` 0x62694 (vptr+0x40, called by the 0x29 handler at 0x27fd4–e0): requires
`[pcs+0x48] != 0` (true, =1); a **null argument** logs "PMU Address is NULL" and does nothing
(0x626b8, 0xbfc4b); a real argument is **only logged** ("PowerControlSet: pAddr=%p") — the
field stored is the firmware constant **`[pcs+0x58] = 0x28e084008`** (0x62700–0c); ERR
"PMU address already set" if `[pcs+8] ≥ 0xa` on a second set; 1 ms delay. The 0x29 handler then
calls `powerDownAne` (ExeLoop vtable+0x110, 0x27fe4–f0), which clears `[engine+0x1a1]`
(0x51cbc) — i.e. after 0x29 the flag is 0 and the next `powerUpAne` proceeds past step 4.

**Answer to the question:** yes — the live PCS has **PMU base 0** (`[pcs+0x58] = 0`, set-count
`[pcs+0x60] = 0`). With it, `PowerUp` returns 0 having done **nothing** (no MMIO, no mailbox
access — "write to PA 0" never happens; the code returns before any store), `powerUpAne` exits
early, and the SNE-side PMU mailbox at 0x28e084008 is never programmed, so the
ANE_TD / ANE_BASE power domains are never enabled by the firmware. A TD that somehow reached a
TQ would never run, and no completion event could ever be raised. The PMU base must be set by
command **0x29** before any power-up path can work.

## 5. Controller START (0x00)

Handler 0x27244: T2H (0,1) then (0,2) (u16 0x001 / 0x002, 0x2724c–70 / 0x272f4–318),
`"CSNE_CMD_START"` FSM-state trace (0x243e8), `[ctrl+0x230] = 0` (0x272dc), then **posts event 0
to the controller FSM** `[ctrl+0x1a8]` via 0x167ac with completion callback 0x2a694 (the send-
response routine) at 0x272e0–f0.

`CANEController::StartEvent` **0x25e14 is a no-op** (`mov w0,#0; ret`) — so is `ResetEvent`
0x25e0c. The state objects (static, image): `{0x25ca8 PowerOnEvent, id 1}` @0xc5410 and
`{0x25e0c ResetEvent, id 2}` @0xc5470. The real init lives in **PowerOnEvent 0x25ca8**: builds
the PoolMan (0x1f764), 0x168-byte object, buffer pools, prints "[%s] CTRL READY" (0xb49d0) and
ends with T2H (2,0) all-zero args (0x25df0).

**Live controller FSM** ("ANEFSM" core at fwbuf 0x65e6a0 — owned region, reliable): table
0xc5388, current **0xc5418**, i.e. **state id 1, the PowerOnEvent state** — exactly where the
boot firmware's own PowerOn left it. START was never sent in this boot, so no transition has
occurred since. What START's event 0 does from state 1 cannot be read from the dump (the
transition table at 0xc5388 is image .data → stale zeros in fwbuf); the prior decode's
"event 0 → state 3 via StartEvent" remains the working model **[INFERENCE]**. Since StartEvent
is a no-op, START's observable effects are the (0,1)/(0,2) traces, the FSM state move, and the
response — not device initialization.

**Does the job path require that state?** No gate was found: the traced PROCEDURE_CALL path
(`handleCallProcedureWithBar` → `RunProc`/`SetupEngineRequest` → `SendHWRequest` →
`DataProcessor` → `isHWReady` → `pushToHW`) checks only ExeLoop-local conditions
(`isHWReady` bounds/override, alloc count, `[req+0x328]`, SneTMDrv base). The binding gates are
the §2 preconditions (doorbell tdCount, TQEn, PMU base), none of which consult the controller
FSM. [INFERENCE on exhaustiveness — no state read appears anywhere in the decoded path.]

The ExeLoop FSM is in **state 1 = RUN** (heap core 0x16347d0, current 0xc80b0, id 1, core+0x40=1)
— the queue/worker machinery is running; it is the power/TQ domain that never came up.

## 6. Recommendation — minimal command sequence and expected observables

Envelope format: `u32 0 @+0, u16 cmd @+4, u16 result @+6, payload @+8…`; length passed
separately. All values little-endian.

1. **START (0x00), length 0x0c** — 12 bytes, payload zeros:
   `00 00 00 00 00 00 00 00 00 00 00 00`
2. **SET_SNE_PMU_BASE2 (0x29), length 0x10** — `00 00 00 00 29 00 00 00 <u64 PA>`.
   The PA **must be nonzero** ("PMU Address is NULL" otherwise); its value is only logged — the
   firmware stores its constant 0x28e084008. Use the kext's real SNE PMU base PA if known;
   otherwise any nonzero placeholder reproduces the firmware-side effect. (kext order: START
   then 0x29.)
3. **Re-send 0x200 LOAD_PROGRAM and 0x202 CREATE_PROCESS** (kext order), then verify with a
   fresh dump that **`[progMgr+0x9890] != 0xffffffff`** (progMgr H14 instance: heap
   0x15fe0c0 + 0x9890). This field is the source of `[req+0x328]` (SetupEngineRequest
   0x37310–14); while it is −1, **every 0x204 will silently skip the TQ kick again** — this,
   not the doorbell register, is the primary fix target.
4. **Re-run the 0x204 PROCEDURE_CALL** (raw priority 2).
5. If the job still doesn't run: replay the remainder of the kext init — 0x1f CH_PROPERTY_WRITE
   (fw Mach-O RO mapping) ×4, 0x22 RESOURCE_INFO_GET, **0x2e ANE_DEFAULT_SETTING_SET**
   (`updateDefSetting` 0x51de4 drives PCS `PowerUp`/`updateDSI`), and note that the
   Sec→NonSec switch (which is what runs `EnableTQs`) is driven by `SendSecureModeRequest`
   (vtable+0xd8) from the controller's secure-mode handlers: **phase 1 from the cmd at
   0x27ee4, phase 2 (cmd 0x28) at 0x27f50**.

**Observables on success, in order:**
- After 0x29: console "PMU base is 0x%llx"; PCS +0x58 → 0x28e084008, +0x60 → 1;
  `[engine+0x1a1]` → 0 (powerDownAne).
- After 0x2e (or the next power-up path): PCS `PowerUp` passes the base gate and the
  GetPowerStatus checks; `[engine+0x1a1]` → 1; SneTMDrv `Reset` writes 0x201 to
  0x285c00800+q·0x2c for q = 0..7.
- Sec→NonSec: `[engine+0x620]` 0→1, console "switched from Sec -> NonSec, ANE goes to RUN",
  then `EnableTQs` sets bit13 @ 0x285c00420 (TQEn readable via `GetTQEn`).
- Next 0x204: `[req+0x328] != −1`; doorbell `0x285c008F4 = 0x80000000 | tdCount | seq<<16`;
  T2H (2,0) again with a fresh seqno ≤ 0x40.
- Completion: TMD FIFO events → IRQ 4 → `EventIsr` → `reportFinishEvent` → AneCallBack
  T2H **(2,30)/(2,31)** + `ProgramEvent` to host; output buffer at IOVA 0xfbbe8000 leaves its
  NaN sentinel; counts[5] bit0 clears.

## Doorbell and TQ enable prerequisites

### A. Writers of `[progMgr+0x9890]` — the bypass TD count (source of `req+0x328`)

Layout: `CAneProgramManager` keeps a state struct at **+0x9858**. `SetupEngineRequest` 0x37190
saves `x10 = this+0x9858` (0x371d0–d8) and copies **fixed** slots: `[x10+0x30]` (+0x9888) →
`req+0x220` (0x372f0–f4), `[x10+0x38]` (**+0x9890**) → `req+0x328` (0x37310–14). The addressing
is fixed, not program-indexed — **the slot is global per-progMgr**, unlike the per-program
tables (call-type records at `progMgr+0x8048`, 0x18 stride — `getProcedureCallType` 0x369a0–a8).

**The only writer in the entire image is `CAneProgramManager::propertyWrite` 0x37b4c, case
property 0x10A8** (`str w19, [x22,#0x38]` at **0x37c8c**, x22 = this+0x9858). Verification:
exhaustive scans — no `movz/movk` of 0x9890 anywhere; every `mov w,#0x9858` site
(0x34a80 AneCallBack, 0x37108 msgHandler, 0x371d0 SetupEngineRequest, 0x37b68 propertyWrite,
0x381d8 statsBufferSizeGet, 0x3935c, 0x423c4 H14::RunProcInternal, 0x42e18 updateReqBarTable,
0x43678 RunProcCacheRequest) is a read except the propertyWrite case. `myInit` 0x37b48 is an
empty `ret`. None of the model-op handlers (0x200–0x20e), LOAD_PROGRAM (`AddProgram` 0x36dc4),
CREATE_PROCESS (0x41718) or 0x23 STATS touches it.

Routing: CH_PROPERTY_WRITE (0x1f) handler 0x27174 reads **property = u32@[env+0xc]**, **value =
u32@[env+0x10]**, and dispatches on `property & 0xff00`: group 0x1000 → 0x2872c =
`CAneProgramManager::propertyWrite([ctrl+0x140], property, value)`. 0x10A8 falls in table
0x37dec (props 0x10A0–0x10C0; 0x10A0→+0x9858, 0x10A1→+0x9888, 0x10A3/A4/A9→+0x988c,
**0x10A8→+0x9890**, 0x10C0→+0x988c/strb +0x9889).

**Why −1 after LOAD returned ProgramId 0:** nothing in LOAD_PROGRAM/CREATE_PROCESS writes the
slot; it only ever holds what a 0x1f property write put there. We never sent a 0x1f routed to
the 0x1000 group (our single 0x1f was the fw Mach-O RO mapping — different property group), so
the slot still holds its power-on −1.

**Value to write:** the TD count the TQ doorbell packs (`(tdCount & 0xffff) | seq<<16 |
0x80000000`). Derived from our sections — **`/tmp/fa-sections/tdprop.bin` offset 0x00, u32 LE
`01 00 00 00` = 1** (also echoed at +0x0c; +0x20 = 0xf4 = descriptor.bin size). So value = 1.

Exact next command (set TD count before the 0x204):

```
00 00 00 00 1f 00 00 00 00 00 00 00 a8 10 00 00 01 00 00 00   (len 0x14)
  +0x04 cmd 0x1f | +0x08 unused by handler (0) | +0x0c property 0x10A8 | +0x10 value 1
```

### B. Every path that sets TQEn bit13 @ 0x285c00420

- The bit-set instruction `orr w10, w10, #0x2000` occurs **exactly once** in the image
  (0x33280, inside `EnableTQs` 0x33270), and the only code building register offset
  0x02000420 is 0x33274 (EnableTQs) and 0x33290 (`GetTQEn` 0x3328c). There is **no shadow
  copy** in the SneTMDrv object — `GetTQEn` always reads the MMIO register.
- **EnableTQs has exactly one caller: `SignalProcessor` 0x4b92c at 0x4bb18**, immediately after
  it posts FSM event 3 (Sec→NonSec) to the ELFSM (0x4bb04–10). So yes — the Sec→NonSec pump is
  the only caller.

**The secure-mode cycle, fully walked:**

- Host commands: **0x27** (handler 0x27e88) → `SendSecureModeRequest(1 = PHASE_START)`;
  **0x28** (0x27ef4) → phase 2 (PHASE_STOP) at 0x27f50. `val = [cmd+8]` is logged only.
  `SendSecureModeRequest` 0x5197c asserts phase ∈ {1,2}, emits T2H (2,6)/(2,7) and posts event
  0x1000018 to the work queue.
- **DataProcessor type-4** (0x4fa44): requires ELFSM state ∉ {2,3} (either → assert-hang);
  `[payload+8]`: 1 = START (0x4fc54), 2 = STOP (0x4fcc4), else 0x4fd30.
  - **START** (0x4fc54): requires `[engine+0x1a2] == 0`, else assert "aneSecurePhase == false"
    → **hang (double-START hazard)**; prints "secureMode Phase START"; calls **PCS
    `PowerDown` 0x6300c** (vptr+0x50, 0x4fe1c–2c); `isAneIdle` 0x4d0c4 → if idle
    `vtable+0x108(0,1)`; sets `[engine+0x1a2] = 1` (0x4fe58). **No MMIO writes.**
  - **STOP** (0x4fcc4): requires `[engine+0x1a2] == 1`, else assert "aneSecurePhase == true" →
    **hang (STOP-without-START hazard)**; prints "secureMode Phase STOP"; if `[engine+0x678]`:
    PCS `SwitchDynamicPowerGate` 0x63474 (vptr+0x50, 0x4fcf8–0x4fd0c). **No MMIO writes.**
- **SignalProcessor pump** (0x4b92c, x1 = request message x20): on [engine+0x640] echo → prints
  "request nonSec -> Sec received" → **posts FSM event 2** (0x4bab0) → **FSMSwitchSecure
  0x578b4**: asserts `!GetTQEn()` (twice), `vtable+0x108(0,0)`, **writes 0x285874000 = 2 (ANE
  PAUSE)** (0x5794c–5c), `[engine+0x61c]++`; waits msg echo on **[engine+0x648]** (0x4bac0) →
  posts **FSM event 3** (0x4bb04) → **FSMSwitchNonSecure 0x579a4**: asserts `!GetTQEn()`, PCS
  `TurnOnDPE` (vptr+0x48), "switched from Sec -> NonSec, ANE goes to RUN", `[engine+0x620]++` →
  **EnableTQs** (0x4bb14–18) → waits [engine+0x630] (0x4bb1c).
- **ISRs** (registered at 0x49588–0x495e0 after the ctor writes **0x285874004 = 3**,
  0x49580–84): **nonsec2SecIsr 0x4a93c on IRQ line 10 (0xa)** — acks **0x285874004 = 1**
  (0x4a950–54), posts **[engine+0x640]** (0x4a958–5c); **sec2NonsecIsr 0x4a96c on IRQ line
  11 (0xb)** — acks **0x285874004 = 2** (0x4a980–84), posts **[engine+0x648]** (0x4a988–8c).
  ([engine+0x630] is posted by the DbgEvent/TqStop-path ISR tail at 0x4a65c–6c after setting
  bit2 of a mask register — not part of the secure cycle.)

**What raises sec2NonsecIsr:** not a firmware MMIO write. The firmware's only writes in the
0x285874xxx block are 0x285874000 = 2 (`FSMSwitchSecure`, the n2s/PAUSE direction), the
0x285874004 acks (3 init / 1 n2s / 2 s2n), and 0x285874008 = 3 (`CSneTMDrvH14::Reset` tail,
0x341f4–f8). After the PAUSE write and the n2s IRQ, the **s2n (line 11) interrupt is raised by
the ANE hardware itself** — the firmware only acks and waits for it. `powerUpAne`'s `w2=1` path
calls only PCS `TurnOnDPE` — no 0x285874000 write. So host **0x27 then 0x28** (exactly one of
each, in that order — the phase asserts hang on a repeat/orphan) drives the cycle: 0x27 →
PowerDown → PAUSE → n2s IRQ → [0x640] → FSM event 2; then the ANE raises s2n → [0x648] → FSM
event 3 → EnableTQs; 0x28 closes the phase flag. (The kext init list contains no 0x27/0x28, so
on macOS the s2n IRQ may fire autonomously during init and reach the same pump path
[INFERENCE].)

**SneTMDrv::Reset effect on TQEn: none.** It writes the per-queue config registers
`0x285c00800 + q·0x2c = 0x200 | (table 0xafdd0[q] & 0x3f)` → q0..7 = 0x201, 0x202, 0x203,
0x204, 0x205, 0x206, 0x21e, 0x21f, plus 0x4000000 / 6 to a TQ word pair (0x341d4–e4) and
0x285874008 = 3 — it never touches bit13 of 0x420. [INFERENCE: whether the per-queue 0x200 bit
or 0x285874008 gates fetching independently — the firmware's own readiness checks consult only
0x420 bit13.]

**Updated minimal sequence** (supersedes §6 step order):

1. `00 00 00 00 1f 00 00 00 00 00 00 00 a8 10 00 00 01 00 00 00` — CH_PROPERTY_WRITE, len
   0x14, property 0x10A8, value 1 (tdCount from tdprop.bin) — after 0x202, before 0x204.
2. `00 00 00 00 00 00 00 00 00 00 00 00` — START, len 0x0c.
3. `00 00 00 00 29 00 00 00 <u64 PA nonzero>` — len 0x10.
4. `00 00 00 00 27 00 00 00 00 00 00 00` (0x27, len 0x0c) — exactly once; expect n2s IRQ.
5. `00 00 00 00 28 00 00 00 00 00 00 00` (0x28, len 0x0c) — exactly once, only after 0x27
   completes the cycle; expect s2n IRQ → "ANE goes to RUN" → EnableTQs.
6. Re-run 0x204 (raw prio 2); expect T2H (2,0) with a fresh seqno and the doorbell word at
   0x285c008F4 = 0x80000000 | 1 | seq<<16.
