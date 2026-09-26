# jwm1 (T8103) acg_hack — baseline logged, RMW write hard-resets the box, feature stays default-off (2026-09-25)

Owner: AneAcgT8103 (Main), continuing parked AneClockM1's lead. Host: jwm1
(T8103, Omarchy 7.1.13-3-2-ARCH). Driver: omarchy-ane `agent/t8103-acg`
(eb4cf4c, pushed) — clean rewrite of the agent/m1-acg-hack chain; built on
jwm1 against the running kernel, zero warnings, params `acg_hack` plus the
certified set with identical defaults (`map_mode=3`, `dart_contain=Y`,
`boost_idle_ms=100`).

## 0. What the feature is

macOS `AppleT8103PMGR::writeReg32` (macOS 13.5 kernelcache; ADT flag
`ane-acg-hack=1`, confirmed in the T8103 pmgr ADT decode,
receipts/2026-09-25-m1-ane-clock-macos section 4) read-modify-writes the
word at PA 0x26b868a04 — inside the macOS ANE window (0x26a000000 +
0x2000000), far outside the Linux driver's engine reg (0x26bc04000 +
0x24000) — to `(old & ~BIT(12)) | 0x80001000` once ANE_SYS reaches state
0xf, and clears bit 12 on the power-down to 0. The rewrite:

- one constant: SoC descriptor `ane_soc_t8103.acg_word = 0x26b868a04`;
  `MAP_PA = word & ~(PAGE_SIZE-1)`, offset 0xa04 (jwm1 PAGE_SIZE=16384),
  compile-time `static_assert` that the word fits its page;
- one dedicated `devm_ioremap` page at probe, T8103 only (descriptor
  field, every other SoC carries 0); a failed map disables the feature
  loudly — the oops class of the first chain (engine+0x1868a04 read
  through the 0x24000 engine window) is structurally gone;
- access only while the islands are on: apply/log at the end of
  `ane_tm_enable` (probe resume or verified-on recovery), clear in
  `ane_pd_cycle`, `runtime_suspend` and `platform_remove` while the
  partitions are still up;
- `acg_hack` param default 0: one log line per power-up (PA, VA, value);
  `acg_hack=1`: the macOS RMW after the log, bit 12 cleared at every
  power-down.

## 1. Baseline value (acg_hack=0)

Slot obtained through Jwm1Submit2 and M2FwStart-2 (jwm1 rebooted at
18:57 to clear the kernel-internal ane module pin — refcnt 1 with no
holders and no fd anywhere in /proc; the pin was gone after reboot,
refcnt 0).

Clean load, no oops (`raw/stepA-baseline-dmesg.txt`):

```
[   57.959923] ane 26bc04000.ane: ANE-ACG pa=0x26b868a04 va=ffff80008b728a04 val=0x80000000
```

**Linux reads 0x80000000: bit 12 (the macOS ACG enable) is CLEAR on
Linux, bit 31 set.** macOS's RMW would make it 0x80001000. The lever
hypothesis is therefore real: the two systems genuinely disagree on this
word — Linux never applies the ane-acg-hack (consistent with AneClockM1's
finding that Linux writes no ANE perf/clock state).

## 2. acg_hack=1: machine hard reset — the RMW crashes jwm1

Step B: `modprobe -r ane; insmod ane-acg-eb4cf4c.ko acg_hack=1`. The ssh
session died 58 s in with no command output: the box hard-reset during
probe. Evidence (`raw/stepB-crash-facts.txt`):

- the following boot logs `macsmc-reboot: PMU logged 1 boot error(s) and
  0 panic(s)` — exactly one unclean reset total, and the 18:57 reboot was
  a clean systemctl reboot, so the boot error is this crash;
- auto-recovery to the stock module; no Oops/abort line survives (the
  reset is machine-level, not a kernel oops);
- the RMW write 0x80000000 → 0x80001000 is the ONLY access the
  acg_hack=1 path adds beyond the twice-proven clean baseline read path
  (read at probe in Step A, and again in the earlier parity8 era);
- zero filesystem damage: no btrfs/ext4/IO error lines post-crash.

Mechanism: bit 12 enables the ANE auto-clock-gate. Under macOS it rides
on CLPC/pmgr state Linux never configures; gating the idle engine's
clocks with no re-enable path aborts the next engine access (probe reads
TM_STATUS immediately after `ane_tm_enable`) and the abort is a machine
reset, consistent with every external-abort signature in this program.

No retry was attempted: the causal chain is exact-timing correlated and
mechanistically consistent, each attempt costs jwm1 an unclean reset on a
btrfs root, and the outcome cannot change without first porting the
macOS-side ANE clock management this hack depends on.

## 3. Decision

**The hack does not close or narrow the 140 ms → 112.99 ms gap — it hard
resets the box.** Per the assignment: recorded here, feature stays
default-off, omarchy-ane main untouched. `agent/t8103-acg` (eb4cf4c)
remains pushed as the durable record of both the safe read-only
instrumentation (baseline log, proven twice) and the falsified write
path. Any future attempt must first bring up Linux-side ANE clock
management (the missing input AneClockM1's lane identified), not flip
this bit alone.

## 4. Installed state (box clean)

- `/lib/modules/7.1.13-3-2-ARCH/updates/ane.ko` = stock
  5a22ee3 build, sha256 `57ceaddd…` (= `ane-stock-preacg.ko`),
  srcversion `32DC3F35CA4F4A20CEA9012` (`raw/module-shas.txt`);
- reloaded via `modprobe -r ane && modprobe ane` post-crash, refcnt 0,
  certified params `map_mode=3 dart_contain=Y boost_idle_ms=100`;
- zero ACG lines in the live dmesg (stock module carries no ACG code);
- my test build kept at `/var/tmp/ane-acg-eb4cf4c.ko`
  (sha256 `c16a2a8c…`).
