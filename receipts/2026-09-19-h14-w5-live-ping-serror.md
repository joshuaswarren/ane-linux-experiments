# H14/T6021 W5-live — first live RTBuddy-mode doorbell ring: CSNE_CMD_PING on EP1 SError'd the machine (0xbe000000) — the kext TX sequence is necessary but not sufficient without the RTBuddy session in front of it (2026-09-19)

Verdict: **EVIDENCED WALL.** `ane_t6021.ko` 0c35846 loaded with
`allow_unqualified=1 mbi_doorbell=1`, passed the eight-island gate + ASC
whitelist, and fired the full decoded TX sequence on EP1/INIT — ring copy
(cursor 0, len 8, msg48 `0x000008000000`) → a2i word (+0x1850000) →
doorbell `writel(0x2, ANE+0x1844000)`. **5 µs later CPU0 took SError
0xbe000000**, surfacing at the first MMIO read after the write pair;
console died mid-decode; watchdog reset ~2 min later; box back healthy.
The write pair was rejected by the fw/interconnect in the current
(fw-running, no-RTBuddy-session) state — same abort class as the SCRATCH
writes (2026-09-19, W4-fix) and the +0x1608xxx reads (W3-fix).

## 1. Runbook execution (all green before the ring)

| prereq | result |
| --- | --- |
| jw14m2 stability | up 1 h 09, two ssh round-trips 12:05:46 / 12:15:56 CDT (10 m 10 s apart), load ~0 |
| netconsole flowing | `ANE-W5-NETCONSOLE-PROBE-20260919T1211` via /dev/kmsg → collector in 9 s (sender 192.168.3.103:6668 → omp-studio-local /var/log/fleet-netconsole.log) |
| ramoops armed | 4 MiB @ 0x10010000000, "pstore: Registered ramoops" (0x400000, ecc 0) — **stayed EMPTY after the SError**: the hard wedge skipped the panic dump, same as the 09:50 class; netconsole is the evidence channel for this crash family |
| stage 1 | `h14_bringup.py --stage 1`: all eight `ps.raise.ok`, no TIMEOUT; ane_cpu already `0x0f0001ff` (AUTO_ENABLE clear persisted across the earlier rmmod), other islands same-value writes |
| safe load | `insmod ane_t6021.ko allow_unqualified=1` (commit 0c35846, built on-box against running 7.1.13-3-1-ARCH, BTF, sha256 `0a4e4622…`): ANEGATE pass, whitelist = the known-good alive set (RVBAR=1, VERS=0xe3044, RTB=1, RTB+7c=0x30, EDPRCR=0, SCRATCH0-7=0), banner "CSNE TX fenced"; rmmod clean |

## 2. The crash seam (kernel timestamps, netconsole 12:16:20.917 CDT)

```
[4200.077876] MBI msgregs pre-ping: i2a=00000017_af70ba9e a2i_rd=00000000 a2i_wr=00000000
[4200.077878] CSNE TX ep1: ring iova=0x00000000ffae0000 cursor=0 len=8 msg48=000008000000 -> a2i + doorbell 0x2
[4200.077883] SError Interrupt on CPU0, code 0x00000000be000000 -- SError
[4200.077886] CPU: 0 UID: 0 PID: 1962 Comm: insmod ... 7.1.13-3-1-ARCH
[4200.077893] pc : readl+0x14/0x20 [ane_t6021]
[4200.077898] lr : ane_t6021_csne_ping_attempt+0xe0/0x2a0 [ane_t6021]
[4200.077900] x27: ffff80009e000000 ... x24: ffff80009f170004   (x24 = x27 + 0x1170004 = eng+I2A_HI)
[4200.077910] x12: "...i + doorb ell 0x2" ... (console dies here)
```

Attribution: the ring-copy, the ring-slot reads, and the pre-ping msgreg
reads were all clean. The SError surfaced at the next readl after the
**{writeq msg48 → +0x1850000, writel 0x2 → +0x1844000} pair**; with no
read between them, the abort cannot be pinned to one write of the pair.
Candidates for the next lane: (a) the writeq's 64-bit MMIO width — the
AKF mailbox is word-shaped and the kext sites are 32-bit writes, the
driver's `writeq` was [INFERENCE-flagged]; (b) the doorbell bit/session
state (below); (c) both registers being RTBuddy-session-gated.

## 3. Why this is a session-precondition wall, not a decode error

macOS never sends an EP1 command without the full RTBuddy attach in
front of it: EP0 management HELLO / EPRollCall / PowerAck, the
SetupEndpoints surface-announce words (the 54-bit doorbell codec
mapping host buffers into fw-visible endpoints), then STARTEP. This
lane deliberately skipped all of it (the W5-live question was "does
selene answer the doorbell at all") — answer: **no, and the surface
rejects the attempt with a machine-fatal async abort.** The fw-side
endpoint state the kext creates first is the missing precondition; the
static decode (W5 static receipt) stands, the silicon simply refuses
unsolicited EP1 rings. Doorbell-bit-numbering [INFERENCE] remains
unvalidated — the session gate fires before any bit discrimination.

Side datum: pre-ping i2a hi read `0x17` vs `0x2` in every earlier
capture — the fw→host notify word drifts on its own across the hour
(other-channel/fw traffic); it is ambient, not ping-cause (it moved
before any host write).

## 4. Driver delta (omarchy-ane `feat/t6021-ane-driver-w4` @ 0c35846)

- `ane_t6021_csne_ping_attempt()` (rtkit.c): probe-time one-shot PING
  behind `mbi_doorbell=1` only; runs after first_resume (probe unwinds
  on gate failure, so the ping cannot fire un-powered); forces
  `ep[INIT].started` (the explicit opt-in), submits the 8-byte header,
  then watches the response surfaces 3 s, changes-only (ring slot +6/+8
  completion bytes, i2a hi, a2i_rd; i2a lo sampled for summaries only —
  ambient heartbeat). Never reached its watch loop live (fault at loop
  entry).
- Armed path now prints the pre-write seam line (ring iova, cursor,
  len, msg48, doorbell bit) — this line is what pins the crash cause in
  netconsole.
- Cross-build clean arm64 (0 warnings); on-box build clean vs
  7.1.13-3-1-ARCH.

## 5. Parking state

- Watchdog reset at ~12:17; box up and healthy 12:19 (uptime, 0 SError
  lines, ramoops registered-but-empty, module NOT loaded, nothing
  auto-loads it). rmmod impossible/unnecessary post-reset. SCRATCH
  registers untouched all lane (stage 1 writes pmgr only; driver writes
  only a2i + doorbell). jwm1, jw16 untouched.
- Netconsole evidence window: /var/log/fleet-netconsole.log lines
  2026-09-19T12:16:06–12:16:21 sender 192.168.3.103:6668 (safe load at
  4185.6, armed load at 4200.07, SError decode tail).

## 6. Next lane (in order)

1. 32-bit write halves for the a2i msg word (kill candidate (a)
   cheaply) — still expect the session wall.
2. EP0 MGMT exchange (HELLO/HANDSHAKE/ACK at +0x184c000/+0x1850000
   family behind the EP0 doorbell bit 0x1) before ANY EP1 send — the
   kext order is HELLO → EPRollCall → PowerAck → SetupEndpoints →
   STARTEP → app traffic; the driver has the MGMT decode (rtkit
   semantics) but no sender.
3. Only after a HELLO ACK: SetupEndpoints announce words, then EP1
   PING with the write-half fix.
