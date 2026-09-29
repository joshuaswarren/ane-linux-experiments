# isHWReady gate re-verification — fw135 static decode (2026-09-28)

Firmware: `/tmp/fw135.macho` (selene rc4x 13.5, sha a9c4b771). VA = file off − 0x4000.
Companion receipts: `findings.md` (H14SchedParkDecode, same day), kext135-command-sequence
(notebook thread `M2StaticDecode/20260928T2350Z`, kext-side 0x27/0x28 pairing).
Method: capstone disassembly of every cited VA; whole-image scans for offset/immediate
encodings (word-wise, not linear) for the writers questions. Every claim below cites
instructions. Items that could not be proven from the image are marked [INFERENCE].

## 1. isHWReady (0x50e64) — verified check order

`isHWReady(engine=x0, req=x1)`, returns w0. Guarded sub-checks print only if
`[engine+8]` bit30 set AND `[0x4f87a8]` (trace object) non-null — see §3.

```
0x50e78  ldrb w8,[x0,#0x1a0]; cbz w8,0x50e98   CHECK 1  override byte != 0 -> return 1 (0x50e80 mov w0,#1)
0x50e98  cbz x1 -> assert 'pReq' (0x50f08)
0x50ea4  w1=[req+0x3d8] prio; w8=[engine+0x18c] maxClientNbr; w9=[req+0x3d0] userId
0x50eb0  w21 = maxClientNbr*prio + userId
0x50eb8  assert w21 < priorityQCount (0xbdbdb); 0x50ec0 assert userId < maxClientNbr (0xb7b50)
0x50ec8  assert prio < maxPriorityNbr (0xbdbbf)
0x50ed4  x10=[engine+0x688][w21<<3] -> [x10+0x30]        CHECK 2  priority queue count
         0x50ee4 cbz -> CHECK 3; else 0x50ee8/0x51058 print '[isHWReady] priority queue is full!' (0xbbfcc) -> ret 0
0x5100c  w10=[req+0x3d4] jobId; assert < maxJobNbr (0xbbb52); x11=[engine+0x690]
0x51024  idx = maxClientNbr*jobId+userId -> [x11][idx<<3] -> [+0x30]   CHECK 3 job queue count
         0x51030 cbz -> subchecks; else print '[isHWReady] job queue is full!' (0xbbff0) -> ret 0
0x510f4  assert prio < 8 (0xbd9d4)                       SUB-A
0x510fc  w8=[engine+0x6c4+prio*4]                        SUB-B freeSlot[prio]
         0x51104 cmp #3; b.hs -> print '[isHWReady] no free slot!' (0xbc00f) -> ret 0
0x5110c  bl 0x51ccc (x0=engine, x1=prio)                 SUB-C dummy-network flags
         0x51114 cbz w0 -> continue; else print '...waiting for dummy network to complete' (0xbc029) -> ret 0
0x51194  bl 0x4dd44 (engine, req)                        SUB-D checkScheduleInfo
         0x511a0 tbz w0,#0 -> print '...schedule info is not available!' (0xbc067) -> ret 0
0x511a4  x0=[engine+0x6b0]; bl 0x167a0                   SUB-E ELFSM state
         cmp w0,#2 / (re-read 0x511b4, cmp #3); either -> '...switching to the secure mode: state=%d' (0xbc093) -> ret 0
         (state read twice: 0x511a4-0x511c0)
0x51220  x0=[engine+0x660] (SneTMDrv); w1=prio
         0x5122c x8=[vtbl+0xa8]; blr x8  -> x2           SUB-F1 per-priority TQ limit
0x51240  bl 0x4e170(engine, req, limit)                  SUB-F2 TQ space
         0x51248 tbz w0,#0 -> '...TQ%d TD count is full!' (0xbc0c6) -> ret 0
0x5124c  -> '[isHWReady] ready!' (0xbc0e9) -> return 1
```

Order confirmed identical to findings.md. Correction to findings.md: SUB-F1 is
`[SneTMDrv vtbl+0xa8]`, i.e. the object created at 0x49fbc (`adr x0,#0xbb5d9 'SneTMDrv'`,
`bl 0x33e38`, stored `[engine+0x660]`); its derived vtable is 0xc75c8 (set at 0x33e70),
so slot +0xa8 = **0x346a0** — `mov w0,#0; ret` (constant 0). The base-class vtable 0xc7198
holds the CXXPureVirt stub at +0xa8 (`'CXXPureVirt'` string 0xc0475 via 0x73a2c) — using the
base table would abort; the derived one is what runs. findings.md's vtable+0xa8(prio)
reference resolves to this constant-0 getter.

### SUB-C decode: 0x51ccc dummy-network flags

```
0x51cd8  cmp w1,#7; b.hi assert 'index < 8' (line 0x149)
0x51ce0  x8 = engine + prio*2
0x51ce8  ldrb w8,[x8+0x4968]   ; flag A = engine[0x4968 + 2*prio]
0x51cec  cbz -> 0x51d34
0x51cf0  return 1
0x51d3c  ldrb w8,[x8+0x4969]   ; flag B = engine[0x4969 + 2*prio]
0x51d48  return (flag B != 0)
```
- **Writers (whole-image scan, word-wise: strb imm-offset, strb reg-offset via
  `mov w?,#0x4968/0x4969`, `add #0x4968/0x4969`):**
  - SET A=1: 0x4c628 `strb w10(1),[engine + prio*2 + 0x4968]` inside the ExeLoop work-item
    processor (0x4bebc, called 0x4ba34 from the request thread 0x4b92c). Gated at 0x4c560 by
    `tbnz w25,#1` — the work item's `queue_dummy_network` bit (format string 0xbb89a
    '[EventInfo] event %d nid %d tid %d irq %d aborted %d queue_dummy_network %d').
  - CLEAR A: 0x4c60c `strb wzr` (same function, completion side, 0x4c224 reader).
  - No store anywhere targets 0x4969 (only readers: 0x4ed1c loop via `ldurb [x12,#-1]`
    with x10=0x4969, and 0x51ccc itself).
- **Who creates items with the bit set:** the only producer writing bit1 items is the
  cache-request/slot-free processor **0x4ed1c** (0x4f4b4 ring push at [engine+0x5f0], bit
  set at 0x4f6b4 `bfi w14,w9,#0x10,#8` with w9=1). 0x4ed1c has exactly one caller:
  **0x4fb28, inside the completion-path retry processor 0x4f74c** (findings.md's retryproc).
- **Boot value:** the engine object is `bl 0x64abc` (malloc, 0x35800 bytes, 0x3a288) — not
  calloc; no init store touches 0x4968/0x4969 (scan). [INFERENCE] boot-time heap pages are
  zero-filled (freshly mapped fw memory), so both flags start 0.
- **Verdict:** "waiting for dummy network" cannot fire on a fresh boot — the only setter is
  downstream of the first job completion (retry path). It CAN fire on a re-run after a prior
  completion queued a dummy-network re-emission that hasn't drained.

### SUB-D decode: checkScheduleInfo 0x4dd44

```
0x4dd64  idx = maxClientNbr*jobId + userId (asserts idx < jobQCount 0xbdcb7, jobId, userId)
0x4ddcc  w9 = [engine+0x6b8 + idx*8]           scheduleInfo[idx].priority
0x4ddd0  cmn w9,#1; b.eq 0x4de60               priority == -1:
0x4de60    w8 = [engine+0x6b8 + idx*8 + 4]     scheduleInfo[idx].count
0x4de68    cbz w8 -> 0x4dea0
0x4dea0    mov w0,#1; ret                      <- PASS (unused slot, consistent state)
           (count != 0 with priority -1 = assert 'scheduleInfo[queueId].count == 0' 0xbdb30)
0x4ddd8  return (scheduleInfo[idx].priority == req.priorityId)
```
- **Boot value:** `[engine+0x6b8]` array filled `{priority=-1, count=0}` at init
  0x4a210-0x4a24c (0x4a0b8 alloc of priorityQCount*8) -> SUB-D **returns 1 (pass)** on a
  fresh boot. findings.md eliminated it "by elimination"; here is the exact `mov w0,#1`
  that makes the elimination correct.
- **Fail mode:** a slot whose priority was recorded by an earlier launch and differs from
  the incoming request's priorityId. Writers of scheduleInfo entries are on the launch path
  (slot alloc 0x4e2e0 / launch 0x4e604 family) — so this fires on **re-submissions in a
  warm firmware**, not on the first CALL of a boot.

### SUB-E decode: ELFSM state (see §2). Passes on fresh boot (state 1).

### SUB-F decode: TQ space 0x4e170

```
0x4e184  x19 = limit (x2, = 0 from 0x346a0)
0x4e188  cmp limit,#0x10000 -> fail; w8=[req+0x30] (totTdNbr); cmp #0x10000 -> fail
0x4e1a0  idx asserts (jobQCount etc.)
0x4e1f4  w8 = totTdNbr + limit
0x4e1f8  cmp #0x10000; cset w0,lo             -> return (totTdNbr + 0 < 0x10000) = 1
```
Passes on fresh boot for any real program. Cannot be the failing check unless a prior
leak pushed totTdNbr toward 0xffff.

### Boot initial values summary (fresh boot, before any host traffic)

| check | state at boot | host command can change it? |
|---|---|---|
| 1 override `[engine+0x1a0]` | **1** (0x49754 `strb w8(1)`, after `[engine+0x658]` created OK at 0x49740; null -> init-fail assert 0x49b3c) | yes — §4 |
| 2 prio queue count | 0 (ctor 0x15aa0-family zeroes +0x30; 0x15dcc push) | indirectly (fills on park) |
| 3 job queue count | 0 | indirectly |
| SUB-A prio < 8 | n/a (priorityId mapped from raw by 0xc07c0) | no |
| SUB-B freeSlot | 0 (`memset [engine+0x6c4],0,0x20` at 0x4a08c) | grows with slot allocs (0x4e2e0) |
| SUB-C dummy flags | 0 [INFERENCE: zeroed heap] | only via completion/retry path, no direct command |
| SUB-D scheduleInfo | `{-1,0}` (0x4a210) -> returns 1 | set by first launch of a slot |
| SUB-E ELFSM state | **1** | only via 0x27/0x28 secure commands (§2) |
| SUB-F TQ limit/space | 0 / 0 < 0x10000 | no direct command found |

## 2. ELFSM initial state — proof it boots in 1, not 2/3

Creation (engine init, function containing 0x490e8..0x4a260):

```
0x49f38  x0 = [0x4f8538]                    FSM manager singleton (set by its ctor 0x16110)
0x49f44  x1 = 0xc8020                       descriptor table
0x49f4c  x2 = 0xbb5b9 "ELFSM"
0x49f54  x3 = engine
0x49f58  w4 = 1     <- INITIAL STATE ID
0x49f5c  w5 = 8     (event count)
0x49f60  w6 = 0x20; w7 = 0xa
0x49f68  bl 0x161a8 ; 0x49f6c str x0,[engine+0x6b0]
```

Constructor 0x161a8 (`0x164fc mov x0,x27` — returns the 0xa8-byte core object):

```
0x163fc  table entry kind 3 -> alloc 0xa8 (core)
0x1641c  [core+0x20]=0x12483579 magic; [core+0x24]=w7(0xa)
0x16424  [core+0x28]=table; [core+0x30]=state-ptr array
0x16428  str w23,[core+0x40]                ; w23 = x4 = 1  <- init state id
0x1642c  [core+0x48]=engine
0x1645c  bl 0x1651c                         core init
```

```
0x1651c  x10=[core+0x30] (state ptr array); x8=[x10]  (first state entry)
0x16528  w9=[core+0x40]                    ; = 1
0x16530  walk: w11=[x8+8] (entry id); stop when w11==w9
0x16544  str x8,[core+0x38]                ; CURRENT STATE = entry with id 1
```

State getter 0x167a0: `ldr x8,[x0,#0x38]; ldr w0,[x8,#8]; ret` — so GetState() == 1 at boot.

Table 0xc8020 raw (0x30-byte entries, word0=kind, word1=id, word6@+0x18=event, word10@+0x28=action):

```
0xc8020 k=0  zeros;            0xc8050 k=1 id=0 (state 0)
0xc8080 k=2 id=0 ev=1;         0xc80b0 k=1 id=1 (state 1)
0xc80e0 k=2 id=1 ev=2;         0xc8110 k=2 id=2 ev=3 act=0x578b4
0xc8140 k=2 id=4 ev=0;         0xc8170 k=1 id=2 (state 2)
0xc81a0 k=2 id=2 ev=3 act=0x578b4; 0xc81d0 k=1 id=3 (state 3)
0xc8200 k=2 id=3 ev=1 act=0x579a4; 0xc8230 k=2 id=2 ev=3
```

Live edge set (states 0,1,2,3 declared): `1 --ev2--> 2 --ev3--> 3 --ev1--> 1` (plus
`0 --ev1--> 1`, dead `4 --ev0-->`). Actions: **0x578b4** = FSMSwitchSecure (asserts
`!GetTQEn()` 0x3328c, reg write, `++[engine+0x61c]`, "switched from NonSec -> Sec, ANE goes
to PAUSE" 0xbddc1); **0x579a4** = FSMSwitchNonSecure (`++[engine+0x620]`, 0x30ee8 reload
tunables on `[engine+0x680]`, "switched from Sec -> NonSec, ANE goes to RUN" 0xbde17,
resets priority slots to -1 from 0x57a88).

**Who can post events:** only the ExeLoop request thread (0x4b92c, running on the work
semaphore). Strict callgraph for 0x167ac: engine-init 0x4ba4c signals the semaphore;
the request thread posts:
- 0x4babc `mov w1,#2; bl 0x167ac` — after printing "request nonSec -> Sec received"
  (0xbb806), selected when the received group == `[engine+0x640]` (group id 6, stored by
  init 0x49f74+ / registry 0x1b994).
- 0x4bb10 `mov w1,#3; bl 0x167ac` — "request Sec -> NonSec received" (0xbb834), group
  `[engine+0x648]`, then `bl 0x33270` (SneTMDrv).

Dispatch-level origin (host reachability): coarse fw commands
- **0x27 = SECURE_MODE_START** -> 0x27e88: `[server+0x130]` vtbl+0xd8 with w1=**1**
- **0x28 = SECURE_MODE_STOP** -> 0x27ef4: same, w1=**2**

(the kext135 notebook entry's pairing verified from the fw side; the findings.md "0x28 =
STATS" warning dissolves — that compare `x22,#0x28` at 0x27cb4 is the fine id inside the
coarse-0x23 case, i.e. (0x23,0x28) = STATS_BUFFER_SIZE_GET, a different command pair).

**No init path posts ev2/ev3 to ELFSM.** Conclusion: state 2/3 ("switching to the secure
mode") is unreachable on the h14 command sequence (PRINT_ENABLE, TRACE_ENABLE, LOAD_PROGRAM,
CREATE_PROCESS, PROCEDURE_CALL) — it requires a prior 0x27 (or 0x28 completing the window).
findings.md's root cause ("FSM received nonSec->Sec and never Sec->NonSec") is only viable
if the run that parked had previously sent a 0x27 — or if the firmware was warm from an
earlier macOS session on the same boot. On a literally fresh boot the SUB-E check passes.

## 3. Making the isHWReady prints appear — no recipe exists

The gate on every `[isHWReady] ...` print (also the park prints "Cached the Server Request
to ..." at 0x527e4/0x52ae8, the dispatch CMD logs at 0x27174-style preambles, and the
ExeLoop counters print 0x4b9bc):

```
ldr w1,[engine+8]; tbz w1,#0x1e, skip        <- bit30 of [engine+8] must be SET
ldr x0,[0x4f87a8]; cbz x0, skip              <- trace object must be non-null
bl 0x3210c                                    (assert prints via 0x1a724 additionally need byte [0x4f8570]!=0)
```

- **`[0x4f87a8]` writers:** CTraceBuffer ctor 0x31cd8 (`./sne/common/Debug/CTraceBuffer.cpp`,
  asserts `__null == instance` 0xb62af) stores itself at 0x31d5c; cleared 0x31f44/0x31fa0.
  Creation chain: fw startup 0x4344 (vtable 0x4ac898) -> controller start 0x2abd4 ->
  controller init 0x2ac30 -> `bl 0x26874` (0x26114 init block) -> 0x2688c `bl 0x31ef8`
  (operator-new thunk) -> 0x31cd8. **Non-null at boot — satisfied.**
- **bit30 of `[engine+8]`: NO writer exists in fw135.** Exhaustive scans:
  - 22 address computations of 0x4f87a8 (adrp+add) — every one consumed by `ldr x0`;
    zero `str`.
  - every `orr w?,w?,#0x40000000` (15 sites) and `mov w?,#0x40000000` (9 sites) inspected —
    none targets [engine+8]; no read-modify-write of `[x,#8]` matches (scan of ldr→str pairs).
  - engine ctor chain (0x3a144 -> 0x16014 -> 0x17540) never stores +8; base ctor zeroes
    from +0xb0 up only.
  - [INFERENCE] bit30 would have to arrive from unwritten memory; on zero-filled boot heap
    it reads 0 forever.
- **Loglevel bytes 0x4f8570-77:** written by PropertyWrite (0x26e2c) case 3 (sets
  0x4f8570=1, 0x4f8573=1, 0x4f8571=0x4f8572=1, and 0x4f8574-77 = (arg!=0)); also by the
  static print-manager ctor 0x1a300 (already 1 at boot). Host-reachable via coarse 0x1f
  (kext CH_PROPERTY_WRITE) -> generic handler 0x27174 -> stage-2 `[(payload+0xc)&0xff00]==0`
  -> `bl 0x26e2c(server, prop=[payload+0xc], value=[payload+0x10])`; also coarse (0x21,0xc)
  -> 0x27bb4 `0x304b0([server+0x120], 0x1602, [payload+8])` (tunable-object route).
  **Relevant only to the assert-print path 0x1a724 — irrelevant to the bit30 gate.**
- fw coarse table 0x2a598 (id field = u16 at payload+4): 0x1d/0x1f -> generic/property path,
  0x21 -> 0x27b4c (fine 0xc = TRACE_ENABLE), 0x24 -> 0x27ce0 (fine 8 = PRINT_ENABLE),
  0x27/0x28 -> secure start/stop, 0x0d/0x0e -> trigger/tunable writes — none touches
  [engine+8]. The task list (0x04/0x0a/0x1f/0x2e) contains no bit30 writer either.
- **Conclusion (proof, not judgment):** no host command in fw135 can make the
  "[isHWReady] ..." or park prints appear; bit30 of [engine+8] is dead. Observable
  alternatives: ring events (2,0) / (2,0x1a)/(2,0x1b) (not print-gated), the STATS pair
  (coarse 0x23, fine 0x28 -> 0x297bc -> 0x380dc stats buffer), and controller object state
  via DMA-visible structures.

## 4. Override (check 1) and re-running the parked request

Writers of `[engine+0x1a0]` (byte):
- init 0x49754: = 1 (see §1).
- **dispatcher coarse 0x04, fine 0x0c** (case 0x274f0: `cmp x22,#0xc`; len check `[x19] > 0xb`):
  `ldr w8,[payload+8]; cmp w8,#0; cset w9,ne; strb w9,[engine+0x1a0]` —
  **payload+8 u32 != 0 forces the override ON; == 0 forces it OFF.** Replies with the old
  value (`str w24,[x21+8]` -> exit 0x2a25c). Payload shape: +4 u16 coarse id (0x04),
  +8 u32 value; name idx for the log comes from the same +4 field.
- power-up 0x51b80 (engine vtable 0xc7f10 slot +0x28; prints "ANE powering up for job
  submission, isAllIdle: %d"): when arg1 (isAllIdle) == 0 -> `strb wzr,[engine+0x1a0]` —
  **the first job submission clears the boot override**, which is why real checks apply by
  the time the first PROCEDURE_CALL is evaluated.
- power-down 0x51c7c (slot +0x30): = 1.
- 0xe96c (`base-ctor` region, vtable 0xc4508) writes the arg — not on the h14 boot path.

Re-run paths for a parked request (findings.md said "waits forever"; refinement):
- **0x4f74c** retry processor — only from the completion path (0x4fb28 -> 0x4ed1c).
- **0x54ab8** cache-request processor (engine vtable 0xc7f10 slot +0xa8 = 0xc7fb8 -> 0x54ab8):
  pops cached requests, re-runs isHWReady at 0x54dd0 and 0x55dd0, and arms a delayed retry —
  string 0xbcf10 **"prepare timer for delayed trigger command for cache request idx (%d)"**.
  So a parked request is re-offered on job completion AND on this timer path, not strictly
  never.
- **PROCEDURE_CALL_TRIGGER_CACHE_REQUEST 0x209: no-op in fw135** — coarse table 0x2a658
  idx 9 (id 0x209) maps straight to the exit stub 0x2a25c (as do 0x20a/0x20d). No host
  command drains the queues directly.

Practical recipe implied by §4 (for the next hardware session, proposed in the notebook
thread): send coarse-0x04/fine-0x0c with +8=1 (override on) and then re-send the
PROCEDURE_CALL — isHWReady check 1 short-circuits to 1 and the launch proceeds. Caveat:
the previously parked copy is still queued and will re-emit via 0x4f74c/0x54ab8 on the next
completion/timer tick — expect a duplicate first-add unless the slot is cleared first.
Alternatively fire SECURE_MODE_STOP 0x28 (mode 2) then 0x27-0x28 pair per the kext
sequence to walk ELFSM 1->2->3->1 if the warm-state theory is the live one.

## 5. Ranking: which check fails on the h14 sequence

**On a literally fresh boot: none.** Every check is proven to pass from boot state:
override=1 until first power-up clears it; queues 0; freeSlot 0; dummy flags 0;
scheduleInfo {-1,0} -> `mov w0,#1`; ELFSM state 1; TQ space passes. isHWReady returns 1
and there is no park.

For the **observed** park (warm firmware — the h14 session had already run LOAD_PROGRAM to
completion per the (2,0x1a)/(2,0x1b) events in findings.md), ranked:

1. **SUB-D checkScheduleInfo == 0** — scheduleInfo[queueIdx].priority recorded by the
   earlier launch differs from the request's priorityId (or the slot was reused at a
   different priority). Evidence: the park decision tree (0x526c8 -> 0x5279c -> 0x527a8);
   the observed cache message distinguishes it — "Cached the Server Request to **Job**
   queue" (0xbbdc4) fires iff checkScheduleInfo==0 **or** the job queue is full; on the
   first park of a boot the job queue is empty, so a Job-queue cache message implies
   SUB-D (or a warm job queue). findings.md recorded the Job-queue message.
2. **ELFSM state 2/3** — only if a 0x27/0x28 was sent earlier in that firmware session
   (macOS kext sends 0x27 in ANE_PowerOn_gated; our Linux sequence did not). Demoted from
   root cause: the FSM provably boots in state 1 and nothing internal posts ev2.
3. **SUB-B freeSlot >= 3 / queues full** — three-plus outstanding submissions at the same
   priority without a drain (retry storm), same warm-state family as (1).
4. **SUB-C dummy-network** — only after a completion queued a dummy re-emission; cannot
   explain a first-ever park.
5. **SUB-F TQ space** — needs totTdNbr+limit >= 0x10000; impossible fresh.

Decision probe for the live machine (no prints needed): read the STATS pair
(coarse 0x23, fine 0x28) buffer via 0x380dc, and/or re-send the parked PROCEDURE_CALL once
after (a) nothing, (b) 0x28 then 0x27+0x28, (c) override 0x04/0x0c=+8=1 — which of (a)/(b)
unparks discriminates SUB-D-stale vs ELFSM-warm directly.

## Corrections vs findings.md

1. ELFSM initial state is 1, not "2/3 as boot state"; secure park requires an explicit
   host 0x27/0x28 (or a warm fw). §2.
2. checkScheduleInfo passes on fresh state — exact `mov w0,#1` at 0x4dea0. §1.
3. vtable [engine+0x660]+0xa8 = SneTMDrv derived slot = `mov w0,#0; ret` (0x346a0), base
   slot is CXXPureVirt. §1.
4. All isHWReady/park/CMD prints are dead code (bit30 of [engine+8] has no writer);
   findings.md's step 4 ("enabling the 0x4f87a8 writer makes prints visible") is wrong —
   the object is already registered; the gate that can't be satisfied is bit30. §3.
5. Parked requests are not strictly "never retried": 0x54ab8 arms a delayed-trigger timer
   ("prepare timer for delayed trigger..."). §4.
6. "0x28 = STATS_BUFFER_SIZE_GET" vs kext "0x28 = SECURE_MODE_STOP": both true at
   different dispatch levels — coarse 0x28 = SECURE_MODE_STOP; (coarse 0x23, fine 0x28) =
   STATS. §2.
