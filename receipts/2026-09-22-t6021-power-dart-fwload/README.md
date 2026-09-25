# T6021 ANE power, DART/IOMMU, and ASC firmware-load path (2026-09-22)

Lane: T6021PowerDartFw. Consumer: T6021RtkitPort (RTKit client) and the driver lane.
Scope: everything that must be true BEFORE an RTKit handshake can succeed on the
M2 Max (T6021, J414c = t6021-test-host / t6021-test-host). Non-goals: RPC opcodes
(H14RpcProtocol), inference, other hosts.

Sources cited as: **[DTB]** stock modules DTB `t6021-j414c.dtb`
(sha256 ea6c9a8a…, decompiled to decompiled t6021-j414c.dts),
**[OVL]** `omarchy-ane ane/t6021-j414c-ane.dts` (board overlay actually
booted via fdtoverlay + update-m1n1), **[DRV]** omarchy-ane t6021 driver sources
(`.work/boot-w15/ane/t6021/ane_t6021.h`, `ane_t6021_fwload.c`,
`ane_t6021_boot.c`), **[PMGR]** `drivers/pmdomain/apple/pmgr-pwrstate.c`
(omarchy-linux tree, same file as mainline asahi-6.x),
**[DART]** `drivers/iommu/apple-dart.c` (same tree), **[NS]** receipts/
2026-09-21-t6021-host-tm/NIGHT-SUMMARY.md + per-arm receipts in that dir,
**[SID]** receipts/2026-09-20-h14-dart-stream-identification.md,
**[W7]** receipts/2026-09-19-h14-w7-write-grant-static-analysis.md.

Confidence labels: [FACT] = read from a binary/source named above; [MEASURED] =
observed live on t6021-test-host in a cited receipt; [OPEN] = not resolvable statically.

## HARD SAFETY RULE (twice proven today)

**Unpowered ANE-block MMIO reads hard-hang this fabric.** A read of an
unpowered window raises an async external abort that wedges the box; the
kernel-context variant cannot be recovered without the watchdog. Two events
today: (1) 2026-09-18 bisect — first engine read at 0x285c2400c external-
aborted with only the five-domain raise (bisect note in [OVL] fragment@3
comment); (2) posted-mapping class — every Apple-fabric window must be mapped
NON-POSTED (`ioremap_np` / `/dev/mem O_SYNC`); a posted `writel` to the same
word that userspace wrote safely froze the box (arm-A/A5, [NS] §1a).
**Corollary: no MMIO access of any kind (read or write, posted or not) until
every ANE genpd domain reads ACTUAL=0xf from pm_genpd.** [MEASURED, NS §1a/§2]

## 1. Power-up sequence

### 1.1 Domain topology [FACT, DTB lines + OVL fragments]

All islands are `apple,t6020-pmgr-pwrstate` (fallback t8103) under
`power-management@28e080000` (pmgr c000 window). Parent chain (child → … →
always-on root):

```
ane_set4@4030 → ane_set3@4028 → ane_set2@4020 → ane_set1@4018
              → ane_base@4010 → ane_td@4008 → ane_sys@260 → afnc0_lw0@218 (apple,always-on)
ane_sys_mpm@4000 → ane_sys@260                      (orphan in stock DTB, see below)
ane_cpu@2e0 → ane_sys@260
```

- Stock DTB ane_sys@260 `power-domains = <0x1a>` (itself), phandle 0x1a; the
  islands at 0x4008/0x4010/0x4018/0x4020/0x4028 carry phandles 0xb5/0xb6/
  0xb7/0xb8/0xb9; ane_cpu@2e0 parent = 0x1a; ane_sys_mpm@4000 parent = 0x1a.
  [FACT, decompiled t6021-j414c.dts:2569-2826]
- **Gap the overlay exists to fix:** ane_sys_mpm@4000 has NO phandle in the
  stock DTB, so genpd can never raise it, and the set1..4 cascade bottoms out
  at ane_td/ane_base — the six-island chain is only complete when the bound
  device explicitly consumes ane_sys_mpm. [FACT, OVL fragment@3 comment +
  2026-09-18 bisect]

### 1.2 What the bound device must declare [FACT, OVL fragment@2]

`ane@284000000` (reg 0x2 0x85c04000 size 0x24000, engine window) carries
six `power-domains`: ane_cpu@2e0 (0x1f0), ane_set1..4 (0xb7-0xb9, 0x1f1),
ane_sys_mpm (0x1f5). Its DARTs: ane_dart0 power-domains=<0x18> (= pmp,
always-on), ane_dart1/2 power-domains=<0x1f0> (= ane_cpu). [FACT, OVL]

### 1.3 What genpd actually does on power-on [FACT, PMGR]

`apple_pmgr_ps_power_on` → `apple_pmgr_ps_set(ACTIVE, auto_enable=true)`:
writes TARGET=0xf with AUTO_ENABLE, then polls `PS_ACTUAL == APPLE_PMGR_PS_ACTIVE
(0xf)` (field [7:4]) with a 100 µs timeout; `apple,always-on` islands are
skipped. genpd raises parents before children (framework ordering), so
attaching all six islands makes `pm_runtime_get` / probe of ane0 raise the
whole chain bottom-up. Genpd "active" = ACTUAL==0xf or (TARGET==0xf &&
auto-PM enabled). [FACT, PMGR lines 34-35, 92-113, 135-145]

### 1.4 The ACTIVE poll that must gate MMIO [MEASURED + FACT]

Before ANY engine/TM/DART-window MMIO: all eight ANE-related genpd domains
must show ACTUAL=0xf. Live healthy state: `ane_cpu 0x1f0003ff`,
set1-4 ACTUAL=0xf ([NS] box-final readback; s4 exclusion note "genpd set1-4
ACTUAL=0xf"). The W3-phase1 audit script (`h14_w14_prereq_audit.py` family)
already encodes this as "valid ONLY while all eight ANE genpd domains are on
(verified via pm_genpd before any MMIO)". Eight = ane_cpu + ane_sys + ane_sys_mpm
+ ane_td + ane_base + ane_set1..4. [FACT, repo script header]

### 1.5 What must ALSO be true but Linux does not provide [OPEN]

- **ANE-SYS-V clock gate (ADT gate 473)** has no Linux pmgr domain — pass13.
  ADT ane0 `clock-ids` = 318-321 are attached by the kext
  (`enableDeviceClock` then `enableDevicePower`, dev+0x8F0, KC 0x95d1d20) but
  the overlay carries no `clocks` property and no Linux driver consumes them.
  Whether 318-321 are real clock gates or a VENC artifact is [OPEN]
  ([NS] §5 item 3, arm-s13). The m1n1 path covers this via
  `pmgr_adt_power_enable("/arm-io/ane")` which walks the ADT clock-gates
  array with full parent recursion ([W7] §1) — the Linux DT overlay has no
  equivalent for gate 473.
- **Never power-cycle ane_cpu from Linux kernel context.** s24: writing the
  pmgr@2e0 register with TARGET←0 (even value-preserving 0x1f0 otherwise)
  from kernel context is FATAL — box froze, watchdog reboot. Any power cycle
  of the ASC island must happen in a quiesce context (m1n1/iBoot), never from
  a running Linux kernel. [MEASURED, arm-s24-ps-cycle-freeze.md]
- RESET pulse (ps@2e0 bit31) is state-dependent and does NOT clear the RVBAR
  latch; do not use it as a reset tool. [MEASURED, arm-s23]

## 2. DART / IOMMU wiring

### 2.1 Instances and windows [FACT, OVL + NS §1b]

Three bound DART instances (t8110-class) + a fourth unbound window:

| Instance | MMIO | Role | DT |
|---|---|---|---|
| dart-ane0 inst0 | 0x285800000 (+0x4000) | LLT (read+write, table walks) | `ane_dart0` [OVL] |
| dart-ane0 inst1 | 0x285810000 | BRD (burst-read) | `ane_dart1` [OVL] |
| dart-ane0 inst2 | 0x285820000 | BWR (burst-write) | `ane_dart2` [OVL] |
| DAPF window | 0x285804000 | access-protection filter (not a DART) | unbound [OVL comment] |

Compatible: `"apple,t6020-dart", "apple,t8110-dart"`. The mainline match
table has NO `apple,t6020-dart` entry — it binds via the t8110 fallback
(`apple_dart_hw_t8110`: APPLE_DART2 PTE format, 256 SIDs, 1 TTBR, 4-level
support). [FACT, DART of_device_id at drivers/iommu/apple-dart.c:1625-1631]

All three attach IRQ AIC2 raw 885, level-high (`<0 0 885 4>`), which is
dart-ane0's shared translation-fault line (error-reflector at ADT
0x29e09c000). [FACT, OVL; SID §7]

### 2.2 Stream IDs [MEASURED]

All three instances use **stream 0**. Live state (s18): all three windows
show TCR 0x9 (TRANSLATE_ENABLE | FOUR_LEVEL), identical TTBR 0x1000df99
(VALID), ENABLE 0xffff (all streams on) — apple-dart programs the same
pagetable on every instance in the device's iommus list. ADT `sid` property
0xf00000000 → stream 0 (calibration table across DART instances confirms
low-nibble encoding). [MEASURED, arm-s18-stream-state.md + arm-s12-sid-
calibration.md]. Caveat [OPEN]: stream 0 is the Linux-overlay + m1n1 claim;
whether the ASC's pre-MMU boot-ROM fetcher emits stream 0 is not statically
provable — a dart-ane0 translation-fault dmesg line names the offending
stream directly if wrong ([SID] verdict).

### 2.3 IOVA window and buffer mapping

- DART vm-base = **0x10000000000 (2^40)** [FACT, ADT dart-ane0 vm-base, SID
  §1.2]. The t8110 tunables program window base/end: reg 0x308 =
  vm-base>>12 = 0x10000000, 0x310 = window end (s17 programmed all three
  windows to cover the full 4 TiB window; inst1/2 were garbage before).
  [MEASURED, arm-s17-dart-window.md]
- Buffers: `dma_alloc_coherent` on the ANE platform device; the dma-iommu
  iovad allocates top-down from ~4 TiB downward. The driver maps with plain
  `iommu_map()`/`iommu_unmap()` on the device's attached domain — apple-dart
  implements `.map_pages` + `.iotlb_sync_map`, so TLB flush is driver-owned
  and automatic; no raw TTBR/TCR writes. [FACT, DRV fwload header + ane_drv.c
  ane_iommu_map_pages]
- The firmware staging surface is physically NON-CONTIGUOUS after
  dma_alloc_coherent under this setup (consecutive leaf PAs differ by
  -0x4000 — the coherent allocator returns one IOVA, not one PA range), so
  anything that must alias a physical entry point must copy page-by-page via
  `iommu_iova_to_phys`, never assume contiguity. [MEASURED, DRV fwload
  header, kcore table walk 2026-09-20]
- DAPF (0x285804000): instance-0 filter with 5 ADT entries guarding the pmgr
  ANE islands; NO entry covers DRAM, vm-base, or alias IOVA. m1n1's
  `dapf_init_all` never programs dart-ane0. DAPF is excluded as the missing
  fetch gate (s20/s21: programmed + publish + wake changed nothing).
  [FACT+MEASURED, arm-s17-dapf-analysis.md, arm-s20-s21]
- There is **no SART** in the ANE path on t6021 — the only SART node in the
  DTB is ANS2/NVMe's (sart@34bc50000, consumed by nvme@34bcc0000).
  [FACT, decompiled t6021-j414c.dts:5258-5272]

## 3. Firmware image: selection, load, verify, entry

### 3.1 Image selection [FACT]

`request_firmware("apple/ane/t602x_ane0_fw_selene_rc4x.macho")` — the
selene rc4x IMACHO extracted from macOS (fixture 0x1a0000 B). ADT ane0 has
`"pre-loaded" = <01000000>` (iBoot marked the fw surface pre-loaded).
[FACT, DRV fwload.c:88; [SID]-adjacent ADT extract in
receipts/2026-09-22-m2-proxyclient-prep/consts-validation.log]

### 3.2 Validation [FACT, DRV]

Shared `ane_fw_validate.h` (offline regression twin in tools/): sha256 pin,
strict exact-image assertions — 7 load commands, 3 pinned segments
(__TEXT fileoff 0x4000 → vm 0x0; __DATA → vm 0xe8000; zeroed vmsize tail),
entry point 0, bounded LC walk.

### 3.3 Load/entry — two paths, one live latch [FACT + MEASURED]

**macOS/iBoot state on this box (the norm after a normal boot):** iBoot
staged selene and latched RVBAR. Every live read: RVBAR = 0x10000000001 —
bit0 = released-latch (kext law: bit0 set ⇒ ANE_Init SKIPS the RVBAR write,
tbnz-skip; no clear path exists anywhere in the KC), entry bits = 0x10000000000
= DART vm-base, i.e. the ASC fetches at the START of the dart-ane0 IOVA
window. The kext target value would be 0x0081010000000001
(0x0081<<48 mode bits | entry | valid) — the live latch is MISSING bits 55
and 48 (mode bits), which points the core at physical 0x10000000000 with no
DART, hence silent park. RVBAR is WRITE-ONCE/STICKY while this latch
persists: live re-write and in-reset writes are both IGNORED. Repairing the
mode bits requires a power-cycle of ane_cpu in a quiesce context (m1n1/iBoot
or kext-quiesce), NOT Linux kernel context (s24 fatal).
[MEASURED, [NS] §3-§4, arm-s22/s23/s24]

**Fresh-boot path (what the driver must implement, in order)** — K14
ANE_Init + AppleASCWrapV4, all offsets [FACT, [NS] §3 byte anchors; [DRV]
boot.c constants]:

1. ps@2e0 (ane_cpu) ← TARGET 0xf, read-validate 0xff (genpd does this).
2. SCRATCH0..7 ← 0 (InitANEScratchRegisters; engine+0x1840048..0x1840064).
   Kext also writes SCRATCH7 ← 1 then 0 (cold marker) — SCRATCH7=1 vs =0 is
   receipt-conflicted; leave 0 [OPEN].
3. SCRATCH6 ← 1.
4. RVBAR (engine+0x1050000) writeq = `0x0081000000000001 | (fw_dva &
   0xFF7EFFFFFFFFF800)` — **skip iff bit0 of read64 is set** (our box: skip).
   [DRV ane_t6021_rvbar_compose; [NS] §3]
5. CPU_CONTROL (engine+0x1400044) write32 0, then 0x10 (RUN, bit4).
6. Poll SCRATCH7 == 0x08042006 (READY) — kext loop ≤1000 × 1 ms; timeout
   ⇒ power_off/power_on retry in kext (fatal from Linux — do not).
7. ONLY after READY: publish SCRATCH0/1 = u64 fw-side pool/dev address
   (dsb st before), then wake SCRATCH7 ← 0xF7FBDFF9, then Poll B on the same
   magic; SCRATCH1:SCRATCH0 then returns the fw device address
   (aneAddressToHostAddress domain: FWIM+IPC whitelist only).
   **RTKit HELLO/EPRollCall rides on top of this; the fw HELLO only comes
   after the wake.** ([NS] §3; RTBuddy
   _handleHello/_handleEPRollCall/_handlePowerAck in [W7] §2-G3)

**Pool/IPC content (P5) is [OPEN]**: pool_word0 must be the macOS
requested-size value, never a synthesized constant (selene 0x20908 silently
skips pool registration on word0==0; word0 never dereferenced). Suballoc
header map and IPC size gates in [NS] §5 item 2.

Entry alias (current Linux vehicle): when RVBAR is latched at
0x10000000000, the driver iommu_maps each staged fw page (PA taken via
`iommu_iova_to_phys` of the staging IOVA) at the latched entry offset on the
device domain, verifying each target page unmapped first; aperture headroom
check vs `dom->geometry.aperture_end`. [FACT, DRV fwload ane_t6021_fw_alias_map]
Alias round-trip verified AP-side (first word 0x14000081); ASC-side fetch
visibility remains [OPEN] (fetch discriminator arm27 not ported).

### 3.4 Who does what: iBoot vs kernel

- iBoot: extracts/stages selene into a carveout, latches RVBAR (with mode
  bits, when it owns the power domain), leaves `pre-loaded`=1 in ADT.
- macOS kext (ANEHWDevice::ANE_Init + RTBuddy): power raise, scratch init,
  RVBAR skip-or-write, CPU release, READY poll, pool/IPC publication, wake,
  then RTKit management protocol.
- Linux driver: genpd raise (probe), fw request/validate/stage (dma_alloc),
  entry alias if latched, scratch/release/poll/publish/wake (fenced,
  opt-in), then RTKit client. The kernel must NOT touch ps@2e0 target bits
  and must NOT rely on physically-contiguous staging.

## 4. Probe-time pre-flight checklist (assertable)

Ordered gates; any failure ⇒ abort before the next, no MMIO yet:

1. DT: `ane@284000000` present, `power-domains` count == 6, `iommus` ==
   three DARTs each with sid 0, `interrupts` = 884 (ane) [OVL].
2. DARTs bound: `apple,t8110-dart` driver bound to 285800000/810000/820000,
   ane0 in one iommu group with all three suppliers; IRQ 885 lines armed.
3. **genpd gate:** all eight islands (ane_cpu, ane_sys, ane_sys_mpm, ane_td,
   ane_base, ane_set1..4) report ACTUAL=0xf via pm_genpd before the FIRST
   MMIO access. Assert `PS_ACTUAL` (field [7:4] of each ps reg) == 0xf.
4. Mapping: every ANE window mapped non-posted (ioremap_np / O_SYNC). No
   plain `ioremap` writel/readl to 0x284000000-family or pmgr windows. Ever.
5. RVBAR read64 (engine+0x1050000, non-posted): if bit0==1 ⇒ latched path
   (read entry bits; check mode bits 55/48 — if missing, boot attempt is
   pointless until a quiesce-context power cycle; log and stop). If bit0==0
   ⇒ fresh-boot path, program composed RVBAR per §3.3 step 4.
6. Firmware: `apple/ane/t602x_ane0_fw_selene_rc4x.macho` loads, sha256 +
   exact-image assertions pass; staging via dma_alloc_coherent (IOVA-based,
   no contiguity assumption).
7. CPU release: CPU_CONTROL 0 → 0x10 only after 1-5 green; poll SCRATCH7
   0x08042006 ≤ 1 s (heuristic deadline, kext-parity 1000 ms); on timeout:
   NO power_off/power_on retry, NO further writes — report and stop.
8. Publish/wake: only after READY; SCRATCH0/1 = real pool address (P5
   content from a macOS-produced build; never a synthesized constant);
   wake 0xF7FBDFF9; Poll B; only then RTKit HELLO is expected.
9. During ANY of this: never write ps@2e0 target/reset bits from kernel
   context (s24 fatal); never touch engine+0x1844000 doorbell before READY
   ([NS] N4 host-write-fatal class).

## 5. Not resolvable statically (needs hardware/m1n1)

- Whether the ASC boot-ROM fetcher emits stream 0 (fault log discriminates).
- ADT clock-ids 318-321 / gate 473 (ANE-SYS-V): real gates or VENC artifact.
- RVBAR mode-bit repair from Linux: CLOSED as impossible in kernel context;
  must be done by m1n1/iBoot context (matches Main's morning recommendation).
- ASC-side visibility of the entry alias; P5 pool/IPC content producer.
- SCRATCH7 cold-boot value 1 vs 0 (receipt conflict).

## Live-host note

Read-only sysfs/DT confirmation on t6021-test-host was attempted (ssh laptop alias /
t6021-test-host / t6021-test-host-lan / t6021-test-host-linux): all unreachable this session (timeout /
no route — box likely held or down by the higher-priority RTKit lane). All
facts above are from on-disk binaries and prior live receipts; nothing in
this document depends on the missed reads.
