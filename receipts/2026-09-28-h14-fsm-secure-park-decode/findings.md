# H14 ExeLoop secure-mode park decode (2026-09-28)

Firmware: /tmp/fw135.macho (firmware image) (selene rc4x 13.5, sha a9c4b771). VA = file off - 0x4000.
Kext: receipts/2026-09-18-t6021-engine-layout-mined/kext-h14j/AppleH11ANEInterface-10.19.2-mac14j-26A428
Decode session H14SchedParkDecode. All addresses verified by disassembly unless [INFERENCE].

## Root cause of the parked first-add PROCEDURE_CALL

The ExeLoop FSM ("ELFSM", object at [engine+0x6b0], created 0x49f38-0x49f70 via
0x161a8(table 0xc8020, name 0xbb5b9, ctx=engine, 1, 8, 0x20, 0xa)) received the
**nonSec -> Sec secure-mode request** and never received Sec -> NonSec. ANE is in
PAUSE. isHWReady (0x50e64) returns 0 whenever the FSM state is 2 or 3
("switching to the secure mode: state=%d", string 0xbc093, checked 0x511a4-0x511f8),
so every PROCEDURE_CALL parks in the job/priority queues. Tiles never ran.

- FSM state getter 0x167a0: `ldr x8,[x0,#0x38]; ldr w0,[x8,#8]; ret`
- Table 0xc8020 (0x30-byte descriptors): states declared 0,1,2; transitions
  0->1, 1->2, 2->3 (action 0x578b4), 4->0.
- 0x578b4 = FSMSwitchSecure() (CAneEngineExeLoopH14FSMDef.cpp): asserts
  `!pExeLoop->pSneDrv->GetTQEn()` (0x3328c), vtable+0x108(engine,0,0),
  writes reg 0x285874000+0x20000 = 2, ++[engine+0x61c] (nonSec2SecCnt).
- FSMSwitchNonSecure() 0x579a4: same TQEn assert, ++[engine+0x620]
  (sec2NonSecCnt), signals [engine+0x680] (0x30ee8), prints
  "switched from Sec -> NonSec, ANE goes to RUN" (0xbde17), resets every
  priority slot [prioCtx + slot*0x428 + 0xad0] = -1 (0x57a88+).
- FSM request handler loop 0x4ba78-0x4bb54:
  - group [engine+0x648] -> "request nonSec -> Sec received" (0xbb806)
  - group [engine+0x630] -> "request Sec -> NonSec received" (0xbb834) -> 0x33270(pSneDrv)
  - group [engine+0x650] -> "Debug Queue Interrupt trigger"
- Status strings: "switched from NonSec -> Sec, ANE goes to PAUSE" (0xbddc1),
  "secureMode Phase START/STOP" (0xbbe0f/0xbbe3d),
  "nonSec2SecCnt=%d, sec2NonSecCnt=%d" (0xbb7e2, print site 0x4b9e0).

## isHWReady (0x50e64) — full order of checks

req fields (pinned by assert strings): +0x3d0 userId, +0x3d4 jobId, +0x3d8 priorityId.
Engine geometry (ctor 0x3a144, called from init 0x490e8): +0x184 maxPriorityNbr(<9),
+0x188 maxJobNbr(<0x201), +0x18c maxClientNbr(<3), +0x198 priorityQCount=maxClientNbr*maxPriorityNbr,
+0x19c jobQCount=maxClientNbr*maxJobNbr.

1. override [engine+0x1a0] != 0 -> return 1
2. priority-queue [engine+0x688][maxClientNbr*prio+userId] -> [+0x30] != 0 -> "priority queue is full"
3. job-queue [engine+0x690][maxClientNbr*jobId+userId] -> [+0x30] != 0 -> "job queue is full"
   (0x510f4 reached when empty, w1 = priorityId):
   - priorityId < 8 assert (0x5113c)
   - freeSlot [engine+0x6c4 + prio*4] >= 3 -> "no free slot!" (0xbc00f)
   - 0x51ccc dummy-network flags engine+0x4968/0x4969 (stride 2/prio) -> "waiting for dummy network"
   - 0x4dd44 checkScheduleInfo
   - [engine+0x6b0] ELFSM state 2/3 -> "switching to the secure mode"  <- OUR FAILURE
   - vtable [engine+0x660]+0xa8(prio), 0x4e170 TQ space (totTdNbr [req+0x30] + count < 0x10000)
     -> else "TQ%d TD count is full!" (0xbc0c6)
4. pass -> "[isHWReady] ready!" (0xbc0e9)

Fresh-boot state proves checks 2-3 and the sub-checks cannot be the blocker:
queue ctor 0x15dcc zeroes +0x30 (0x15e64); freeSlot memset 0 (0x4a08c);
scheduleInfo [engine+0x6b8] filled {priority=-1, count=0} (0x4a210-0x4a24c).

## Park semantics (definitive)

- Dispatch: CALL handler 0x52504 (vtable) -> 0x37190 -> loop 0x52624 -> isHWReady 0x526c4.
- isHWReady==0 -> 0x5279c: checkScheduleInfo==0 -> 0x527e4 "Cached the Server Request
  to Job queue" (0xbbdc4) -> push 0x15f14 into pJobQueue[idx], park 0x52b64;
  else if job slot +0x30 non-null -> same park; if empty -> 0x52ae8 "Cached the Server
  Request to Priority queue" (0xbbd8c) -> priority-queue insert.
- Retry processor 0x4f748 (no BL callers; completion-path pointer): pops [x20+8],
  recomputes idx 0x4f824, re-emits (2,0), re-runs isHWReady 0x4f8b8; on ready
  allocates slot 0x4e2e0 ("Priority %d Slot %d" 0xbbd6c) -> launch 0x4e604.
- **The parked request waits forever; it is neither dropped nor timed out.** Retry
  happens only when another job completes. No timer posts any park-related event.
- The "final program event (prog 0, proc 0, args 0)" is the program-LOAD completion
  notify family: (2,0x1a) 0x37648 / (2,0x1b) 0x376c4 with args (prog, proc, u64),
  (2,0x1b) followed by host notify bl 0x3e010(x0,5). Not a park timeout.

## Event (2,0) arg identity correction

Ring entry (packed by 0x30244): +0x0c = (code<<8|type), +0x10..+0x30 = args x3..x7,
+0x30 = timestamp if arg5==0 (0x303ac-0x303d8). Emitters: 0x526ac and 0x4f8a0, args
(w3=[req+0x3d8] priorityId, x21 = maxClientNbr*priorityId+userId, 0, 0, 0); companion
log "%s [userId %d jobId %d priority %d] queueId %d" (0xbbcdd, prefix "ExeLoop Request
Received" 0xbbd0c). priorityId = 0xc07c0[raw] = [7,6,5,4,3,2,1,0]; raw priority 2 -> 5.
Recorded tuple (5, 0, 0xa, 0): 5 = priorityId, second 0 = prio-queue index; the old
labels userId/jobId/prio/queueId are wrong and "prio=0xa" is impossible (priorityId < 8).

## Command-id WARNING: kext-26 table does not match the 13.5 fw

w2/fw_cmd_table.json ids come from the macOS 26 kext. The 13.5 fw dispatch differs:
verified fw 0x08=PRINT_ENABLE (0x27ce0), 0x10=BOOT size>0xf (0x27cbc),
**0x28 = STATS_BUFFER_SIZE_GET** (0x27cb4 -> 0x297bc, size > 0x27, flag byte
payload+0x20 bit0, handler 0x2a214/0x2a218 -> 0x380dc, print 0xb3b76) — the kext table
calls 0x28 SECURE_MODE_STOP. Do not reuse kext ids. Dispatch prints
"[%s] CMD = %#04x [%s] at %lld" (0x27ca4) — map secure-mode ids from our own dispatch
log or the cmp chain in 0x27c00-0x2a300. Kext names for reference:
CSNE_CMD_SECURE_MODE_START/STOP/RESUME_TRANSITION, CSNE_CMD_SECURE_MODE_EVENT.

## Next steps

1. Zero-risk probe: send the fw command whose handler prints
   "nonSec2SecCnt=%d, sec2NonSecCnt=%d" (site 0x4b9e0) to read the FSM counters/state.
2. Map the fw SECURE_MODE ids from the dispatch log; send Sec -> NonSec request.
3. Watch fw console (PRINT_ENABLE already live) for "request Sec -> NonSec received"
   + "switched from Sec -> NonSec, ANE goes to RUN", then re-send the queued
   PROCEDURE_CALL and read the next isHWReady verdict ("ready!" 0xbc0e9 or one of
   0xbbfcc/0xbbff0/0xbc00f/0xbc029/0xbc067/0xbc093/0xbc0c6).
4. All "[isHWReady] ..." prints additionally gate on global flag [0x4f87a8] != 0 and
   bit30 of [engine+8] clear — enabling the 0x4f87a8 writer makes the exact failing
   check visible on every attempt.

## Kext part C (open)

w2/disx.py Macho recipe (symtab n_value>>16 & 0xFFFFFF + section base;
n_sect 4 -> __TEXT_EXEC.__text, 2 -> __TEXT.__os_log; __TEXT_EXEC base
0xfffffe0009500070): performSecondStageLoading 0xfffffe00095c540c,
initStatsBufferSection 0xfffffe00095c512c, populateProcedureBasicInfo
0xfffffe00095c5478. Wire-format decode pending; second-order for first-add.
