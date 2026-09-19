# H14/T6021 W9 — EP0 HELLO re-fired behind the W8 grant: grant verified live (SCRATCH nonzero latch), MBI send class still SErrors — the aperture grant is PARTIAL (2026-09-19)

Verdict: **EVIDENCED WALL, narrowed.** The full W5/W6 runbook ran green,
the W8 write-grant sequence was applied from userspace immediately before
the armed load and was verified live in the same boot (nonzero-value
writes to SCRATCH latched and read back exact 17 s before the send), and
the EP0 MGMT HELLO still aborted: seam `MGMT TX HELLO(host):
msg=00100000000c000b -> a2i(half) + doorbell 0x1` then **SError on CPU0,
code 0xbe000000, 11 µs later** (2059.722654 → 2059.722665), watchdog
reset ~71 s after that. No retry. Box self-recovered healthy.

**The W8 grant is real but partial.** It unlocks the SCRATCH/GPIO write
class; the MBI send class — a2i_wr `+0x1850000/+0x1850004` and doorbell
`+0x1844000` — stays host-write-rejected with the grant applied. The
aperture is not one fabric gate, and W6's "rejects EVERY host write" is
refined accordingly.

## 1. Runbook execution (all green before the send)

| prereq | result |
| --- | --- |
| jw14m2 stability | up 32 min, load 0.18, zero SError/abort lines this boot; spaced ssh round-trips green |
| netconsole flowing | `ANE-W9-NETCONSOLE-PROBE-20260919T132200` via /dev/kmsg → collector in <1 s (13:21:08.701, sender 192.168.3.103:6668 → omp-studio-local /var/log/fleet-netconsole.log) |
| ramoops armed | 4 MiB @ 0x10010000000, "pstore: Registered ramoops" at boot — **empty after the SError** (hard wedge skips the panic dump; same as W4-fix/W5/W6) |
| stage 1 | `h14_bringup.py --stage 1`: all eight `ps.raise.ok` (words arrived `0x3ff` this boot, normalized to `0x…1ff/0x…2ff`); ane_cpu `0x1f0003ff → 0x0f0001ff` (AUTO_ENABLE clear, ACTUAL=0xf) |
| on-box build | sources rsynced from omarchy-ane `feat/t6021-ane-driver-w4` @ 460d00e (all four files byte-identical: git blob hashes matched on-box); built on-box vs running `7.1.13-3-1-ARCH`; vermagic match; ko sha256 `87d2288eda143c641c92d1def80be06503e32febf57dc04a2b7d78913acbd57a`; banner stamp `79e6054-dirty` |
| box exclusivity | a sibling lane (jwm1 initramfs recovery) ran a CPU-only `mkinitcpio` on the box, completed and handed off BEFORE the device window; no /dev/mem, module, or ANE contact from it |

## 2. Grant applied from userspace, then verified live

**Method: userspace grant, immediately prior to insmod.** The proven W8
sequence (`h14_write_grant_test.py`, verbatim, /tmp copy) ran under
`timeout -k 10 150` after stage-1; the armed `insmod
./ane_t6021.ko allow_unqualified=1 rtkit_transport=1 mbi_doorbell=1`
followed ~40 s later. The driver's only aperture writes are the MBI
sends inside the MGMT session (audited: every `writel` in the tree is in
`ane_mbi_send`/EP doorbell send), so a userspace grant fully covers the
ordering requirement — no grant code was added to the driver.

- All 12 tunable writes completed with the **same readback profile as
  W8** (`+0x0=0x10`, `+0x3c=0xa0030`, `+0x400=0x40010001`, `+0x410/20/30=0x1100`
  exact; `+0x38` partial; `+0x600/+0x7xx/+0x900` read 0 — W8's
  write-only-or-absent-on-t6021 finding repeats). `VERDICT:
  APERTURE_UNLOCKED`, no abort.
- **W8 confound (b) closed (nonzero probe):** after the grant, SCRATCH
  GPIO0 (`+0x1840048`) took `0xa5a5a5a5` and `0x5a5a5a5a`, both read
  back exact (`NONZERO_LATCH_OK`), then restored to `0x0` (W8-end
  state). Fabric acceptance is proven for real values, not just an
  identity write — and this ran 17 s before the HELLO, proving the
  grant state survived script exit and was live at the send.
- W8 confound (a) also closed by construction: this boot's arc was
  stage-1 raise → grant tunables → probe → HELLO in one continuous
  sequence, so the delta vs the W6 abort boot is the tunables alone.

## 3. The HELLO attempt and the crash seam (netconsole 13:22:39–13:22:42 CDT)

- Loaded banner: `loaded ane_t6021 79e6054-dirty (RTKit transport ON;
  8-domain power gate; CSNE TX ARMED (mbi_doorbell=1))`.
- Baseline watch (3 s): i2a `0000000bb53eb904` — **29 type-0 heartbeat
  ticks** (hi `0x0b` this boot, vs W6's `0x0a`), no [MGMT] discriminator
  fire. Ambient heartbeat only; fw never spoke first.
- The one-shot host opener, seam printed before the first store:

```
[2059.722654] ane_t6021 284000000.ane: MGMT TX HELLO(host): msg=00100000000c000b -> a2i(half) + doorbell 0x1
[2059.722665] SError Interrupt on CPU0, code 0x00000000be000000 -- SError
[13:23:53.830] Booting Linux on physical CPU 0x0000000000 [0x611f0380]   (watchdog reset, console died mid-decode)
```

The abort sits inside the send's three stores {`writel` lo →
`+0x1850000`, hi → `+0x1850004`, `0x1` → `+0x1844000`}, same set as W6.

## 4. How this differs from W6 — and what it proves

| | W6 | W9 |
| --- | --- | --- |
| grant | none | W8 tunables applied + SCRATCH nonzero latch verified 17 s prior |
| seam | `MGMT TX HELLO(host): msg=00100000…` | identical (msg=00100000000c000b) |
| SError | CPU0 0xbe000000, **25 µs** | CPU0 0xbe000000, **11 µs** |
| SCRATCH class that boot | fatal (W4-fix boot; untested W6 boot) | **accepted and latching** |
| outcome | watchdog reset, box healthy | watchdog reset, box healthy |

PROVEN:
1. The aperture is **not monolithic**. With the grant applied and live,
   the fabric accepts and latches host writes at SCRATCH (`+0x1840048`)
   but rejects the MBI send class (`+0x1850000/4`, `+0x1844000`) with
   the same async external abort. W6's "rejects EVERY host write" is
   dead; the wall is **class-scoped**, and the m1n1 12-tunable grant
   does not carry the MBI class's unlock.
2. The grant hypothesis (W7: `base+0x0 <- 0x10` releases the aperture)
   is **partially refuted**: it is sufficient for SCRATCH, insufficient
   for MBI sends. Either a second, MBI-specific grant exists that the
   t8103-derived tunables do not carry (consistent with the 09-18
   finding that the t8103 sub-map does not transfer wholesale to t6021
   — the zero-readback tunables `+0x600/+0x7xx/+0x900` point the same
   direction), or the running RTBuddy fw itself owns/locks its send
   surfaces and the Linux boot's fw state rejects a host-first HELLO at
   the transaction level.
3. No HELLO reply exists to capture: the fw stayed on the type-0
   heartbeat until the abort killed the host. The post-HELLO surface
   scan could not run (box reset); the pre-HELLO snapshot and its 7
   region reads completed clean.

NOT PROVEN [open]: which of the three stores aborts first (the seam
precedes the whole send; 11 µs allows all three to have issued — the
latency delta vs W6's 25 µs is recorded but n=1 each, no conclusion).

## 5. Parking state

- Watchdog reset 13:23:53; box healthy by ssh 13:25:37 (up 1 min, load
  0.16, zero SError lines in the new boot, module NOT loaded, nothing
  auto-loads it, ramoops registered-but-empty). jwm1, jw16 untouched.
- Evidence: `receipts/w9-netconsole.log` (383 lines, collector window
  13:21:30–13:24:00: grant klog, probe klog, scan klog, banner, watch
  ticks, TX seam, SError, reboot). The /var/tmp tee files did not
  survive the reboot (volatile on this box) — the collector log is the
  evidence channel, per lane discipline.
- Driver delta: **no logic change.** Module text updated to the W9
  truth (the old "rejects ANY host write" / "SCRATCH read-only" claims
  were falsified) — omarchy-ane `feat/t6021-ane-driver-w4` @ `27c3aff`,
  pushed.
- Next-lane order (replaces W6 §4): the wall is now class-scoped —
  candidates: (i) find the MBI-class grant in the t6021 boot chain
  (iBoot/fabric filter config for the +0x1844000/+0x1850000 pages; the
  t8103 tunable map is known-incomplete for t6021); (ii) treat the
  fw-owns-its-send-surfaces hypothesis seriously — map the fw→host
  message path first (it is still unmapped) and check whether a
  fw-initiated HELLO arrives on a surface Linux hasn't read, i.e. the
  host must never speak first on this transport; (iii) a macOS-side
  capture of the same registers at RTBuddy session time to compare
  granted-state. No retry of the send class without one of these.
