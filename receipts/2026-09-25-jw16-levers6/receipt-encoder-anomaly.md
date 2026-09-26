# jw16-levers6 part 1 — encoder anomaly: mechanism identified, fix blocked on one captured input (2026-09-25)

Owner: Jw16Levers6. Host: jw16 (T6001, 7.1.6-1-1-ARCH, ane srcversion
`32DC3F35CA4F4A20CEA9012` = v0.1.0-605-g5a22ee3, cached-BO lineage afb23dd).
Denominators: macOS T6001 whole-encoder 140.86 ms (levers5 step 2), T8103
Linux good-state 141.5 ms vs its macOS 113 ms (M1-clock receipt §6).
Reads-first: receipts/2026-09-22-encoder-m1max-anomaly,
2026-09-23-m1max-ane-clock, 2026-09-25-m1-ane-clock-macos,
2026-09-22-ane-dvfs, omarchy-ane docs/t6021-ane-bringup-findings.md.
No rejected hypothesis was re-run.

## 1. Engine-side timing (the task's core measurement)

kprobe (zero rebuild, stock module, disabled after) on `ane_tm_enqueue` /
`ane_tm_execute` around whole-encoder submits (13701 TDs, bundle graph
020428fc, libane d06222a8):

| session | enqueue | ane_tm_execute (push → completion) |
|---|---:|---:|
| first window (2 submits) | 13 µs, 139 µs | 438.78 ms, 438.78 ms |
| fresh-boot window, 4 submits | 13–15 µs | 431.5 ms ×3 (one submit outside capture) |

Worker slope re-verified twice: (14747-style) first window n1=1097/n8=4150 →
436.1 ms/iter; post-reboot n1=1081/n2=1523/n8=4084 → 429.0 ms/iter.

**Conclusion: the 440 ms is 99.97 % engine window.** Per-submit host work is
the ~30 TQ register writes (13–139 µs) plus the poll loop (prior poll_us
A/B: 436.7–441.9, noise). Host dispatch/sync/binding is exonerated on
T6001, matching the M1-side ftrace result for the GPU path
(Jwm1Submit2: run→done 21.9 ms flat vs host turnaround ≤0.83 ms).

**Golden:** hidden sha256 `fca96f1355485ec3…` (the certified CoreML gold
fp16 pin) on n1, n2 and n8 post-reboot; outputs bit-exact every run.

## 2. What is NOT the difference (measured or proven this session)

1. **DART topology is symmetric-class, not T6001-specific.** T8103 ANE has
   THREE darts too (m1n1 t8103_ane_tunables program 0x26b800000/810000/820000;
   live jwm1 dmesg: pagesize 4000, 16 streams, AS 32→36, DMA range 0..dfffffff).
   T6001 ANE: `apple,t6000-dart` ×3 at 0x285800000/810000/820000 (ane iommus
   phandles 0x10b/0x10c/0x10d), reg windows 0x400000 each, oas 42, ttbr_count
   4, max_sid 16 (apple-dart.c apple_dart_hw_t6000); pagesize comes from the
   DART's own PARAMS1 at probe — the same hardware macOS drives. Same-shape
   config cannot explain a Linux-vs-macOS gap. TLB/page-size parity:
   16 K pages both chips.
2. **pmgr ps words / genpd.** Live genpd summary: `ane_sys_cpu`, `ane_base`,
   `ane_set0..4` all `on`/`active` (SW), `ane_set5` `off-0` unattached —
   the symmetric 5-SET topology of the 09-22 receipt; raw words were 0x3ff
   (max) in both prior receipts. No headroom above DESIRED=ACTUAL=0xf.
3. **Driver bytes, libane, bundle, inputs**: identical lineage on both hosts
   (32DC3F35), bit-exact outputs.
4. **llm-inference contention / first-load / poll cadence / PMP report bit**:
   falsified by prior receipts; not re-run.

## 3. The T6001-specific difference: missing boot-time ANE platform tuning

m1n1 `tunables_apply_static()` (AsahiLinux/m1n1, commit 2abf3af3, eiln,
"tunables_static: add t8103 ane tunables"; verified in the 4184923 checkout)
applies ANE boot tunables **only for T8103**:

- engine-window entries incl. PMGR1/2/3 (offsets 0x738/0x798/0x7f8,
  values 0x200020/0x100030/0x100000a),
- the 3 ANE darts + DAPF, `dpe_sys` 0x26b8f0000, `dpe_soc` 0x26b8f4000,
- a **46-entry op-point/voltage table at 0x26b908000** (perf block), and

T6000/T6001/T6002 get **GPU tunables only**. All t8103 table blocks sit
inside the macOS ANE window (AneClockM1: window 0x26a000000/32 MiB; the
Linux DT engine window differs by a fixed offset — do not carry macOS
offsets into Linux MMIO directly).

That explains the cross-chip shape: T8103 Linux (tunables seeded at boot,
firmware self-managing on them) sits at 141.5 ms = 1.25× macOS; T6001
Linux (nothing seeded) sits at ~430–440 ms = 3.1× macOS. The iBoot-preloaded
ANE firmware is running on both chips under Linux (certified TM path);
without its op-point/DPE tables it self-manages at a low default.
Consistency check: T6001 ADT `voltage-states8` ladder = 300/540/780/1020/
1260/1500 MHz @ 550–909 mV; 1500/540 = 2.78, and with the T8103-class 1.25×
residual the observed 3.1× is what ladder-state 1 predicts
(`[INFERENCE]` — the active state is not readable from Linux).

Corroborating facts pulled this session: the live jw16 macOS
EmbeddedDeviceTrees (decoded from
`/System/Volumes/Preboot/.../usr/standalone/firmware/devicetree.img4`,
LZFSE, in artifacts/jw16-adt-embedded.bin) show the T6001 `ane0` ADT node
carries `compatible "ane,t8020"`, `dart-options`
(FPADDARTLLT/TRADDARTBRD/TRADDARTBWR), `filter-data-instance-0`,
`ane0-bw-threshold`, `vm-size`, clock/power-gates — **no tunables
properties**; ioreg pmgr node confirms perf-domain idx 8 = ANE and
`ane-dpe = 1` (artifacts/jw16-ioreg.txt.gz has the full tables).

## 4. Why the fix is not landed, and what unblocks it

The driver-side fix shape is proven by the T8103 precedent: write the
op-point/DPE tables into the driver-owned engine window at probe (module
param, `ane_boost.c` pattern; no pmgr writes, no firmware boot, in-window
access = the driver's normal class). What is missing is the **T6001 table
values**, and they exist in no reachable artifact:

- not in m1n1 (T8103-only; upstream has no T600x ANE entries),
- not in the ADT (this session, §3),
- not found in the 25.6.0/25G83 T6000 kernelcache
  (`/var/tmp/jw16-kc/kernelcache.release.mac13j.macho`): 617 monotonic-run
  const candidates scanned near AppleT6000PMGR / H11ANEIn / CLPC anchors,
  zero matches — CLPC likely synthesizes them at runtime from ADT + SROM
  calibration,
- not synthetically reproducible: the t8103 values are DPE register units,
  not MHz/mV (AneClockM1, negative result), so the T6001 ladder cannot be
  re-encoded without a packing rule,
- not capturable today: dtrace on jw16 macOS is SIP-blocked (levers5 step 3,
  Main holds the recoveryOS gate); no USB serial path exists to jw16 for an
  m1n1 boot trace; the firmware CSNE_CMD route is blocked fleet-side
  (physical-timer FIQ enable not host-writable; firmware + TM cannot
  coexist on T6001 per the bring-up doc §6).

**Unblock = one captured write set.** Either (a) a recoveryOS SIP window on
jw16 macOS running AneClockM1's name-based ane-perfstate.d (sha e1edfffb,
already written) during an encoder run — it logs `_handlePerfStateRequest`/
apply/accessor address+value pairs — or (b) a physical USB-C serial link to
jw16 for an m1n1 iBoot/hv trace. The moment either lands, the driver fix is
a bounded module param; expected staging ~176 ms class (T8103's 1.25×
residual), with the ≤140.86 ms pass bar additionally requiring the full
CLPC/firmware perf state (`[PREDICTION]`, labeled).

## 5. Artifacts and host state

`artifacts/`: kprobe-trace.txt (fresh-boot capture), run-n{1,2,8}.log,
jw16-adt-embedded.bin (LZFSE-decoded EmbeddedDeviceTrees), jw16-devicetree.img4.
jw16-ioreg.txt.gz (460 KB, full macOS ioreg) on PVE /tmp/levers6-raw/ —
excluded from git as an uncompressed-source dump; hashes below.
Worker outputs h1/h2/h8.bin = hidden gold `fca96f1355485ec3…` ×3.

sha256 (PVE /tmp/levers6-raw/): jw16-ioreg.txt.gz `be280c8906a5ceac…`,
jw16-adt-embedded.bin `8f8929608982f111…`, jw16-devicetree.img4
`380d88c1ebf5370d…`, kprobe-trace.txt `d1ffc3870888cb73…`, h1.bin
`fca96f1355485ec3…` (= the gold pin). Raw logs also on jw16 /tmp/levers6/
(scratch).

Host state: jw16 was rebooted Linux→macOS→Linux via the documented
`asahi-bless -n --set-boot-macos` switch (boot gate PASS: /boot ext4, ESP
vfat — off-btrfs); BootNext consumed; llm-inference active after return
with `/health` ok and a real completion probe. No driver, module, devicetree,
or boot-asset changes on any host. Tracing kprobe events are disabled but
still defined in tracefs (cleared at next reboot).
