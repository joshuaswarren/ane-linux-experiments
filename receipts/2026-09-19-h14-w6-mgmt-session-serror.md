# H14/T6021 W6 — EP0 MGMT session implemented and fired: the host HELLO opener (32-bit a2i halves + doorbell 0x1) SError'd CPU0 (0xbe000000) — the ANE control aperture rejects EVERY host write class; wall is upstream of protocol (2026-09-19)

Verdict: **EVIDENCED WALL, advanced.** The EP0 RTBuddy management session
(the W5-live missing precondition) is now implemented in the driver
(omarchy-ane `feat/t6021-ane-driver-w4` @ 243c0c1) and was fired live on
jw14m2 behind the full W5 runbook. The runbook ran green end to end; the
watch phase observed the fw→host pair for 3 s (ambient heartbeat only);
the single host opener `HELLO(host)` — **two 32-bit stores** to
+0x1850000/+0x1850004 then `writel(0x1, +0x1844000)` — was followed by
**SError on CPU0, code 0xbe000000, 25 µs later** (kernel
1803.094282 → 1803.094307). Watchdog reset ~72 s later; box healthy
12:48:29 (netconsole boot line), re-verified by read-only ssh 12:50:42.
This kills receipt-follow-up item 1 (the 64-bit `writeq` width was NOT
the cause): the surface rejects **any** host write into the ANE control
aperture — SCRATCH (W4-fix), EP1 ring (W5-live), EP0 MGMT (W6) —
regardless of width, doorbell bit, or protocol position.

## 1. Runbook execution (all green before the send)

| prereq | result |
| --- | --- |
| jw14m2 stability | three ssh round-trips 12:37:59 / 12:46:46 / 12:47:14 CDT (8 m 47 s + 28 s spans), uptime 20→29 min, load 0.00, zero SError/abort lines in the boot's dmesg |
| netconsole flowing | `ANE-W6-NETCONSOLE-PROBE-20260919T1742` via /dev/kmsg → collector in <1 s (sender 192.168.3.103:6668 → omp-studio-local /var/log/fleet-netconsole.log) |
| ramoops armed | 4 MiB @ 0x10010000000, "pstore: Registered ramoops" at boot — **stayed EMPTY after the SError** (hard wedge skips the panic dump, same class as W5/W4-fix) |
| stage 1 | `h14_bringup.py --stage 1`: all eight `ps.raise.ok`; ane_cpu `0x1f0003ff → 0x0f0001ff` (AUTO_ENABLE clear, ACTUAL=0xf) |
| armed load | `insmod ane_t6021.ko allow_unqualified=1 rtkit_transport=1 mbi_doorbell=1` (built on-box vs 7.1.13-3-1-ARCH, commit 243c0c1 tree, BTF, sha256 `ed8968e08133de0d77f18e97bc0cb61d52f6dfbb60f5ff952b0cf28596178a43`, vermagic match): eight-island gate + ASC whitelist pass (rvbar=1, vers=0xe3044, rtb_status=1, scratch0-7=0), banner, MGMT session began |

## 2. The session before the send (netconsole 12:47:14–12:47:17 CDT)

- MGMT watch HELLO baseline: `i2a=0000000a45e…` — then **~30 changes in
  3 s, every one type 0** (`[MGMT]` discriminator never fired; no
  early-exit). The pair is a **fast heartbeat**, not message storage:
  hi constant `0x0a`, lo counter advancing ~`0x2500000` per 100 ms
  tick. (W4-fix's `hi=0x2` / W5-live's `hi=0x17` are the same surface
  drifting state words.) The RTKit type decode of this pair is
  meaningless — the fw publishes no MGMT word on any surface we have
  mapped.
- After the silent window the session sent its one-shot host opener
  (the assignment-sanctioned "RTKit HELLO exchange on EP0"):
  `MGMT TX HELLO(host): msg=00100000…` (minver 11, maxver 12 in
  bits[31:16]/[15:0], type 1 in [59:52]).

## 3. The crash seam (netconsole, 12:47:17.790 CDT)

```
[1803.094282] ane_t6021 284000000.ane: MGMT TX HELLO(host): msg=00100000… -> a2i(half) + doorbell 0x1
[1803.094307] SError Interrupt on CPU0, code 0x00000000be000000 -- SError
[1803.09+] (console dies mid-decode)
[12:48:29.735] Booting Linux on physical CPU 0x0000000000 [0x611f0380]
```

The seam line printed **before** the first MMIO write of the send, so
the abort sits inside {writel lo → +0x1850000, writel hi → +0x1850004,
writel 0x1 → +0x1844000}. With W5-live's writeq variant already fatal
and this 32-bit-halves variant fatal, **write width is eliminated**;
with SCRATCH writes fatal (W4-fix) and reads stub-clean everywhere,
the rejector is state, not address-decode detail: the ANE control
aperture is host-write-rejected in the Linux boot's fw state, per
async external abort 0xbe000000, before any protocol semantics can
apply.

## 4. What this does and does not prove

- PROVEN: EP0 doorbell bit 0x1 with a well-formed RTKit HELLO (the
  "standard init should be safe" hypothesis, W5-live §6 item 2) is
  rejected exactly like the EP1 ring. No MGMT-first ordering can
  succeed while ANY aperture write aborts — the protocol ladder
  (HELLO → EPMAP → SetupEndpoints → STARTEP → PING) is walled BELOW
  its first host write, not at EP1.
- PROVEN: i2a (+0x1170000/4) is a heartbeat/status surface, not the
  fw→host message register. The real fw→host message path (and the
  fw→host doorbell/IRQ that the AKF dump names AKF_KIC_*) is still
  unmapped.
- NOT PROVEN [open]: whether macOS's XNU writes the same registers at
  runtime (the echo pair 0x…9606e38→0x…9606f0c evidence says yes) via
  a grant Linux lacks — candidates for the next lane: (i) an
  iBoot/fabric write-grant applied to the ANE aperture that the Linux
  boot must reproduce or request (compare with a macOS-adjacent
  capture or m1n1 on the same box); (ii) the running-boot transport
  being an entirely different surface (the W4-fix "RTBuddy host
  attach" framing may be the sideload-mode transport after all);
  (iii) a DART/IOMMU-shaped grant mistaken for MMIO (unlikely — CPU
  MMIO does not traverse DART).

## 5. Driver delta (omarchy-ane `feat/t6021-ane-driver-w4` @ 243c0c1)

- `ane_t6021_mgmt_session()` (rtkit.c): the EP0 session — watch i2a
  for MGMT words (type bits [59:52] nonzero discriminator), reply
  HELLO with versions clamped to 11..12, echo EPMAP (base + MORE/LAST),
  ACK IOP power state, log unknown words (EPRollCall/PowerAck decode
  on sight), then — only after the fw spoke — EP1 surface announce
  (54-bit doorbell word) + STARTEP EP1. 16-round cap.
- `ane_mbi_send()`: all host sends are two 32-bit a2i stores + the
  doorbell word, seam line printed before the first write.
- `ane_t6021_csne_submit()`: writeq replaced by 32-bit halves (W5-live
  receipt follow-up item 1 — executed; result: not the cause).
- `ane_t6021_csne_ping_attempt()`: gated on the session — fw-silent
  session fences the PING (soft wall) instead of replaying 0xbe000000.
  The PING itself never fired (session opener aborted first).
- Cross-check: on-box build clean, zero warnings (BTF pahole 131-vs-132
  note pre-existing).

## 6. Parking state

- Watchdog reset 12:48:29; box healthy (up, 0 SError lines, module NOT
  loaded, nothing auto-loads it, ramoops registered-but-empty). SCRATCH
  registers untouched all lane. jwm1, jw16 untouched.
- Netconsole evidence window: /var/log/fleet-netconsole.log lines
  2026-09-19T12:47:14–12:47:17 sender 192.168.3.103:6668 (safe-load
  banner 1800.076, watch ticks, TX seam 1803.094282, SError
  1803.094307, reboot 12:48:29).
- Next-lane order (replaces W5-live §6): the protocol items are all
  walled behind the write class; the lane that follows must first
  establish why the aperture rejects host writes (candidates §4) —
  e.g. an m1n1-side comparison on this box or a register-grant audit —
  before any further protocol replay. No retry without that.
