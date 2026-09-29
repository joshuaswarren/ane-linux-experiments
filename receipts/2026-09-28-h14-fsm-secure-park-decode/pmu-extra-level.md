# PMU extra-level fault — M2 ANE fw 13.5 (a9c4b771), cmd 0x29

Measured on the M2, kernel 7.1.13-ARCH-polltx, DART 0x285800000 stream 0.
Firmware log is the legacy buffer at IOVA 0xfbfc0000. Host PS reads are
ioremap of 0x28e084000.

## What 0x29 does before it touches a register

Handler 0x27f60 logs `PMU base is 0x%llx` from the command payload, calls
SetPMUBaseAddress, then GetPowerStatus (0x62a9c). Get loads
`0x28e084008 + 8*domain`. If the domain flag is set and `(status & 0xFF)`
is not 0xFF, it assert-spins at CPowerControlServiceAneH14.cpp:243
(`0xFF == (powerstatus & 0xFF)`, site 0x62b08). An assert spin needs a
reboot. Do not rmmod.

## Fresh boot, no page-table edit

Software leaf for IOVA 0x28e084000 is `0xfff0028e08403` (PA 0x28e084000).
Host PS+0x00 through +0x30 read 0x3ff. Cmd 0x29 logs the PMU base, then:

```
apple-dart 285800000.iommu: translation fault: status:0x80040008 stream:0
code:0x8 (NO PTE FOR IOVA) at 0x28e084008
```

TCR0 is 0x9 (TRANSLATE_ENABLE | FOUR_LEVEL). PARAMS0 page size is 16 KiB.
Hardware walks one level past the software leaf and looks for a PTE inside
the MMIO page. The host-visible registers are not what the firmware reads.

## Extra-level table of the same leaf

Replacing the software leaf with a table of `0xfff0028e08403` removes the
NO PTE fault. 0x29 still assert-spins at line 243. Host PS registers stay
0x3ff. The translated read is not the host register. A table of leaves
pointing at a RAM page filled with 0xFF does the same: no store lands in
the page, and line 243 still fires.

## Not the cause

genpd holding the domains on does not explain this assert. The firmware
never observes the host 0x3ff value. A direct host store of 0x3F0 still
wedges the machine; that test is not a substitute for the firmware's load.

## Assert-site write is refused

The branch at VA 0x62b04 is `b.eq` (`0x54000900`) at PA
`0x100008aab04`. `ioremap` and `ioremap_np` both oopsed:
`Unable to handle kernel write to read-only memory`. The word is
unchanged. Do not map that page for write. The machine stayed up.
jwm1 was not on Linux, so there was no reboot after the oopses.
`0x29` was not sent on that boot.

## What completed, and what wedges

A software leaf with SP_END=0xfff aimed at a RAM page filled with 0xFF
is a terminal translation. Cmd 0x29 wrote 0x3F0 at page offset 0x30.
The offset is preserved. Clearing each 0x3F0 to 0, and no other word,
let the six polls finish. 0x29 returned result 0. CPU status stayed
0x2d. The procedure-call output was still the 0x7e sentinel. The host
PS registers stayed 0x3ff.

A terminal leaf aimed at PA 0x28e084000, subpage fields clear
(0x28e08403), still faults NO PTE at 0x28e084008. The DART does not
accept that MMIO page as a leaf target.

Writing TCR stream 0, and a pmgr-style off/on of 0x28e084030, each
wedged the machine. Do not repeat either write.


## Next measurement

0x29 can complete through a RAM mirror. That does not run the tiles.
The DART rejects a leaf aimed at the PMU page. A host write of TCR or
of the PMU power register wedges the machine. The missing piece is a
translation to PA 0x28e084030 that the DART accepts. Do not discover
it by writing DART or PMU registers.

## Doorbell landed, output did not

Property 0x10A8 value 1 set progMgr+0x9890. The first call after that,
with no earlier parked job, copied 1 into the shadow frame +0x328.
The doorbell at 0x285c208F4 read 0x80010001 (tdCount 1, seqno 1).
TQEn bit 13 at 0x285c20420 was set (register 0x803000). The TM event
FIFO count at 0x285c20428 was 0. The output buffer stayed all zeros.
Inputs were not zero (first fp16 values 0xc800 and 0xb800). y == a+b
is not met.



## The doorbell names an empty 2 MiB buffer

Queue config is 0x201 on all 8 queues, so Reset ran. Queue 5
doorbell is still 0x80010001. The per-seq record word 1 is
0xfbc00000. That IOVA is the boot malloc tagged 0x45585050,
2 MiB, and every 16 KiB page is zero. The compiled descriptor
is intact at 0xfbedc000 (+0x10 = 0x3d0000). The firmware never
copied it into the buffer the record names. y == a+b is not met.

The 2 MiB buffer is the CExpandablePool slab. Tag 0x45585050 is
built at 0x1530c (`mov w1, #0x5050; movk w1, #0x4558, lsl #16`)
in CExpandablePool.cpp:0x88. expandPool records the pointer and
does not copy a task descriptor into the slab.

A read of every word at 0x285c00000 and 0x285c20000 wedged the
host. The screen froze on an early-boot frame. Do not scan a
whole TM page. Recovery is a reboot through the jwm1 USB owner.


## Fresh boot, same empty page

On the next boot the ordered steps 0x1f, START, 0x29, 0x27, 0x28,
and 0x204 all returned status 0. The RAM mirror cleared 12. The
seqno-1 record was again `07a00001 fbc00000`. That page's first 8
words were zero. The output buffer was zero. The call does not
fill the page the doorbell names.


## Filling the named page did not run the doorbell

The queue-5 doorbell was still 0x80010001. Copying the loaded
descriptor (0xf4 bytes, 50 nonzero words) into that page left the
doorbell unchanged and the output zero. A pending doorbell does
not fetch the page when the page becomes non-zero.


## Fill before the doorbell also failed

The descriptor was copied into 0xfbc00000 before the firmware
wrote the doorbell. The call returned status 0. The doorbell
was 0x80010001. The event count was 0. The output was zero.
Host power registers 0x28e084000 through 0x28e084030 read 0x3ff.
The domains are on. The tiles did not fetch that page.

A host write of the doorbell register wedged the machine.
Do not repeat it.



## Trace omission clears the CREATE fault, record still empty

TQEn at +0x2420 reads 0 right after insmod. EnableTQs has one
caller (0x4bb18) and Reset does not touch bit13, so the 1 seen
on earlier boots came from the event pump after the switches
ran. Counters 0/0 on this boot too. Omitting TRACE_ENABLE
removed the "Can't post, Driver has trace shared buffer handle"
fault at CREATE, but the per-seq record is still the
constructor stub and the output is zero. The fault is not what
holds the record fill.

Do not send 0x23 shape A. The program vtable +0x70 is NULL and
shape A would call it and assert.


## Correction (2026-09-29): TQEn read used the wrong offset

The section above says TQEn reads 0 at +0x2420. That is wrong.
`dart_tq.ko` read 0x285c00000 + 0x2420 = 0x285c02420. The firmware
register is base + 0x20420 = 0x285c20420 (CSneTMDrvH14 0x33270,
`mov w9, #0x420; movk w9, #2, lsl #16`). `dart_tq4.ko` reads the
right address. On boot 553378f5 it returned en=0x803000 (bit13 set)
and queue-5 doorbell 0x80010001, with the switch counters at
engine+0x61c/0x620 still 0/0.

So TQEn is 1 while the doorbell stays pending. The earlier claim
that the 1 came only from the event pump after a Sec->NonSec
switch is not supported. Either bit13 is set by reset or a tunable,
or the counter offsets are not the ones the switch uses. Open.

The "empty task page" sections also rest on an unproven reading of
0xfbc00000. 0x42df0 (getL2SpillBufferIndex) and 0x159b0
(getPoolIdxAddr) store a pool address at 0x42644. That page may be
L2 spill scratch, not a task descriptor. Zero there proves nothing
about the task fetch until that is settled.

## Settled by static decode of fw 13.5 (2026-09-29, live dump of boot 553378f5)

These four results replace the earlier "parked in PAUSE" root cause.

1. Host cmds 0x27 and 0x28 only set the aneSecurePhase flag
   (ExeLoop+0x1a2) and call powerUpAne/powerDownAne. They never post
   an ELFSM event. Path: 0x27e88/0x27ef4 -> SendSecureModeRequest
   0x5197c -> CPipe::Post -> DataProcessor 0x4f74c type 4 (0x4fa44).
2. ELFSM events come only from hardware IRQ 10 (0x4a93c, key 2) and
   IRQ 11 (0x4a96c, key 3). The table at 0xc8020 is keyed by event,
   not target state. State 1 accepts key 1, 2 and 4. Key 3 has no
   edge from state 1.
3. Live ELFSM state is 1 (RUN). It never left state 1. A stray IRQ
   11 at boot dropped its key-3 post and still ran EnableTQs
   (0x4bb18), so TQEn=1 with counters 0/0. There is no PAUSE park.
4. Firmware 0xfbc00000 (record word1) is the firmware-MMU address of
   the per-seq record itself, not the L2 spill pool and not a task
   descriptor (only writer: 0x3457c inside 0x343f8). The zero page the
   host read at the DRAM address is an unrelated pool slab. The
   "empty task page" claims above do not stand.

The TQ gets its work from a 7-word FIFO push at 0x285c20400 (sites
0x345a8, 0x34630, 0x450a4) and then the doorbell. The loaded
descriptor at 0xfbedc000 still holds the 0x0000dead placeholders at
+0xd4 and +0xdc, so the buffer-address patch never touched that
copy. Open: does the TD-build routine (0x44c98) run at all.

Also: `tools/h14_seq_kext_init.py` builds the kext init commands,
and `tools/m2_collect/` holds a read-only collector.

## Push FIFO readback (boot 553378f5, seven single reads)

0x285c20400..0x285c20418 read w0=0xfd68be00 w1=0 w2=0xfbedc000 w3=0
w4=0x97 w5=0x3d w6=0x5. This is the pushToHWDirect push (fw 0x450a4):
first address is the per-seq record (heap VA 0x20fd68be00, device
address 0xfd68be00), second is the program descriptor (0xfbedc000),
size 0x3d words, queue 5. The record is zero except its 16-byte head,
so the patch table the TQ reads is empty and the 0x0000dead
placeholders in the descriptor stay unpatched. Queue 5 doorbell
0x80010001, TQEn 0x803000, event FIFO count 0, queue cfg 1,2,3,4,5,6,
0x1e,0x1f, power regs 0x3ff, DART TCR 9. All reads were single words.

## Bare call vs call with tdCount (boot f64ca14e)

Sequence: LOAD, CREATE, then (a) one PROCEDURE_CALL with progMgr+0x9890
still -1, then (b) property 0x10A8 = 1 and a second call. No 0x27,
0x28 or 0x29 on this boot. TQEn (0x285c20420) reads 0x803000 right
after CREATE, before any call, so TQEn=1 is the boot state.

- Call (a): the push FIFO holds the same shape as before
  (`0xfd68be00 0 0xfbedc000 0 0x97 0x3d 5`). No doorbell (all eight
  read 0). Output buffer keeps its sentinel (crc 0ce22471).
- Call (b): q5 doorbell reads 0x80020001, pending. Event FIFO count
  0. The output buffer is zero over all 32768 bytes (crc 758d6336)
  before the ack. Inputs are intact. The call-(a) output buffer is
  still the sentinel.

A compute of 512 fp16 would touch 1 KiB, not all 32 KiB. So the
firmware clears the output buffer when it submits a call with a valid
tdCount. The zero output is not a tile result. The tiles still do not
run: the doorbell stays pending and no event arrives.

## Queue enable register reads (boot f64ca14e)

Three single-word reads: 0x285c20510 = 0x0, 0x285c20800 = 0x201,
0x285c208dc = 0x201. Queue words hold Reset's 0x201. The command
register is idle. fw EnableTq (0x34318, TM vtable slot +0xb0)
writes 0x10|qid to 0x20510 and sets bit 9 of the queue word.
Neither queue 0 nor queue 5 shows bit 9, so EnableTq has not run
for either. Static decode: TM Reset never writes 0x20510, and the
only caller found so far sits in the ExeLoop event drain
(0x4ee00-0x4f280). The hardware never acknowledged the queue-5
doorbell (0x80020001, bit 30 clear).

## Correction: EnableTq is abort recovery, not a missing init step

The section "Queue enable register reads" above says the queue enable
never ran and calls it a missing step. That reading is wrong.

- 0x201 already has bit 9 (0x200) set, so the queue words cannot show
  whether EnableTq ran. Reset (0x340f4) writes 0x201 directly.
- The command register 0x285c20510 is written only by AbortTQE
  (0x34318) and base AbortTQ (0x332a4). Neither has a direct caller.
  The only route is the vtable+0xb0 call at 0x4f04c inside
  handleAbort_abortRaisePriority (0x4ed1c), which only a type-2
  abort command reaches (host cmd -> CANEController::CmdProcessor ->
  engine vtable+0xe0 SendAbortRequest -> ExeLoop pipe -> DataProcessor
  cmd type 2).
- So 0x285c20510 = 0 is the normal state. It is not evidence of a
  missing enable. A TD finish or a TqStop IRQ does not run EnableTq.

Queue 5 is stuck because its stop doorbell (0x80020001) has bit 30
clear, so TqStopIsr (0x4a680) cannot consume it. That still does not
explain why the hardware never ran the TD. Open.
