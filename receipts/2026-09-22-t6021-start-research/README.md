# T6021 ANE start — apple-isp comparison, wedge attribution, RTKit/CSNE protocol (2026-09-22)

Lane: M2Research. Source-and-binary analysis only; no hardware touched.
Consumers: T6021FwStart (M2FwStart), the rtclient driver lane. All three
findings were delivered to M2FwStart over hub and acked in-session (§5).

Sources read in full this lane:
- **[ISP]** AsahiLinux/linux branch `isp/t602x-v2` (tree dd1bbfed), `drivers/media/platform/apple/isp/{isp-drv,isp-fw,isp-iommu,isp-ipc,isp-regs}.c/h` + `arch/arm64/boot/dts/apple/{t8112,t600x-die0,t600x-common}.dtsi` — fetched via gh api, read line-by-line.
- **[KEXT]** `receipts/2026-09-18-t6021-engine-layout-mined/kext-h14j/AppleH11ANEInterface-10.19.2-mac14j-26A428` — full llvm-objdump-19 disassembly cached this lane; every claim below cites a disassembly address.
- **[FW]** `fw-h14j-selene/t602x_ane0_fw_selene_rc4x.macho` — Mach-O segments re-parsed; channel names NOT present fw-side (kext-side only).
- **[RTKIT]** `drivers/soc/apple/{rtkit.c,mailbox.c,rtkit-internal.h,tunable.c}` + `include/linux/soc/apple/rtkit.h` + `lib/devres.c` + `arch/arm64/include/asm/{io.h,pgtable-prot.h}` in the local omarchy-linux tree (078f865d1 family).
- **[M1N1]** `.work/m1n1/proxyclient/m1n1/hw/asc.py` (ASC register map).
- Repo receipts: t6021-fw-start, t6021-power-dart-fwload, t6021-rtkit-port, h14-rpc-protocol (+notes), h14-w7-write-grant, h14-boot-prereqs, arm-A*/arm-b (t6021-host-tm), m2-ane-hook-run, m2-m1n1-hook.
- **[ADT]** live ADT capture `dtree-j414c.txt` (raw ane0 + dart-ane0 nodes re-read this lane) and the IORegistry export `tools/ane-hunter/fixtures/ane0-dt.txt`.

Confidence labels: [FACT] = read directly from the cited source this lane;
[MEASURED] = prior live receipt cited; [INFERRED] = stated inference.

---

## 1. Why a kernel-context CPU_CONTROL RUN wedges the fabric on T6021

### 1.1 Candidate disposition

| Candidate | Verdict | Evidence |
|---|---|---|
| DART not configured / bypass vs translate | NOT the wedge — produces logged faults + poll-A timeout, not a hard wedge | [MEASURED] s18: all three dart-ane0 instances TCR=0x9 (TRANSLATE\|FOUR_LEVEL), TTBR valid, ENABLE 0xffff; [MEASURED] 2026-09-20 netconsole dart fault (no PGD for IOVA 0x100000dca10) — box survived. Mainline `apple-dart.c` has no `apple,t6020-dart` entry and binds via t8110 fallback; per-stream bypass (t8110 TCR BYPASS_DART bit1 / BYPASS_DAPF bit2) is only set by the driver for ADT "bypass-N" — dart-ane0 ADT carries `bypass-15` only, and the enabled translate range 0xffff covers the device streams. |
| Firmware region not mapped at the RVBAR IOVA | Same as above — fault-class, not wedge-class; entry-alias already implements the mapping | [FACT] fwload `ane_t6021_fw_alias_map` maps staged pages at the latched entry; alias round-trip verified AP-side. |
| SART not programmed | N/A — there is no SART in the ANE path on T6021 | [FACT] only SART node in the DTB is ANS2/NVMe (sart@34bc50000). |
| DAPF not programmed | Excluded | [MEASURED] s20/s21: DAPF programmed 5/5 + publish + wake — silent. m1n1 `dapf_init_all` never programs dart-ane0 either. |
| Power-domain order | Not the differentiator (genpd parents-first, all 8 ACTUAL=0xf verified in both fatal runs); kernel-context ps@2e0 writes remain forbidden | [MEASURED] arm-A §4 readbacks, s24 freeze. |
| Posted writes | PROVEN wedge class on this fabric — but eliminated in the rtclient path (ioremap_np) and present in the legacy driver | [MEASURED] arm-A vs arm-A4/A5 + userspace diff, see §1.2. |
| **Cold-boot aperture/clock state (tunables + clock gates)** | **THE LIKELY REASON** — see §1.3 | §1.3. |

### 1.2 Posted vs non-posted (the proven mechanism, keep forever)

Attribute mapping on arm64 in this tree [FACT]:
- `ioremap` → `PROT_DEVICE_nGnRE` (posted) — `arch/arm64/include/asm/io.h:283`.
- `ioremap_np` → `PROT_DEVICE_nGnRnE` (non-posted) — same file, line 288.
- `devm_ioremap_resource` auto-upgrades to NP when the resource carries
  `IORESOURCE_MEM_NONPOSTED` — `lib/devres.c:139`; of_platform sets that flag
  under a `nonposted-mmio` parent — `drivers/of/address.c:1031-1069`.
- userspace `/dev/mem` of MMIO → `pgprot_noncached` = nGnRnE (non-posted).

Consequence [MEASURED]: the SAME word+value `eng+0x0 ← 0x10` (phys
0x284000000) freezes the box from a kernel `devm_ioremap` writel (arm-A) and
passes from `/dev/mem` O_SYNC userspace (W8, 12/12 tunables + SCRATCH) and
from the np-mapped driver (arm-A5, all 12 readbacks with values). The legacy
`ane_t6021.ko` maps with `devm_ioremap` — it must never touch the engine
window. The rtclient maps `ioremap_np` — correct.

### 1.3 The cold-stock-boot delta (likely cause of the fwstart#2 hard crash)

The ISP comparison isolates what "cold" means. On the ISP, Linux RUNs the ASC
CPU from scratch on every boot, and before `COPROC_CONTROL 0→0x10` it ALWAYS:

1. raises every power domain (probe-attached; `apple_isp_power_up_domains`,
   isp-fw.c:70), and
2. enables the block's clock gate: `isp_gpio_write32(isp, ISP_GPIO_CLOCK_EN,
   0x1)` (isp-fw.c:278, ISP_GPIO_CLOCK_EN = gpio+0x20, isp-regs.h:55), and
3. (only after a driver shutdown, marker 0xfeedbabe) performs a full coproc
   reset: `EDPRCR ← 2`, FABRIC_0..3 (0x738/0x798/0x7f8/0x858) `← 0xff00ff`,
   IRQ_MASK_0..5 `← 0xffffffff`, drain 0x818/0x81c, wait `STATUS & IN_WFI(0x3)`
   (isp-fw.c:225-258, isp-regs.h:11-25).

ANE T6021 equivalents and their Linux status:

- **Pre-CPU engine table**: the T6021 kext path applies
  `eng+0xB38/0xB98/0xBF8 ← 0x01FF01FF` (3 records) on EVERY
  EnableANEClocksAndPower, unconditionally (dev+0x784 gate has no writer) —
  pass4/pass5-closed, [FACT] boot.c comment + arm-b §2. **fwstart#2 ran mode 2
  = table SKIPPED**, while instead writing the t8103-derived m1n1 13-write set
  whose fabric words sit at **0x738/0x798/0x7f8** — the T8103 offsets, NOT the
  T6021 pre-CPU offsets. The ISP cold-boot path proves these FABRIC registers
  are the generic ASC coproc block brought up before RUN; writing the wrong
  generation's offsets and skipping the real table is exactly a
  "cold/wrongly-configured fabric face at CPU release" state.
- **Provider clock-gate group**: ADT ane0 `clock-ids [318 319 320 321]` +
  `clock-gates/power-gates [473]` (ANE-SYS-V) are enabled by the kext via the
  clock provider (enableDeviceClock/enableDevicePower at 0x95d1d48/0x95d1d90,
  arm-b §1) and by m1n1 via the `pmgr_adt_power_enable("/arm-io/ane")` gate
  walk. Linux has NO equivalent (overlay carries no clocks property; no pmgr
  domain for gate 473; `devm_apple_tunable_parse` in this tree is consumed
  only by the ATC PHY). The ISP analog is exactly GPIO_CLOCK_EN ← 1 before
  RUN. [FACT, ADT raw node; W7 G1]
- **Warm vs cold**: W8's 12/12 success ran on a box that had been through
  macOS earlier that boot; fwstart#2 ran on a stock boot where nothing had
  warmed the aperture. This is the W8-passed / fwstart#2-wedged delta without
  inventing a new latch. [INFERRED, but each half is receipt-sourced]

**Verdict** [INFERRED → testable]: kernel-context RUN wedges on T6021 because
the CPU is released against a fabric face that iBoot/macOS would have
configured and Linux does not: the T6021 pre-CPU table (skipped in mode 2) and
the ANE-SYS-V/clock-id gate group (unavailable), with the posted-write class
explaining why legacy-driver kernel attempts were disproportionately fatal
versus the userspace np path. Discriminating rerun (bounded): same fwstart
core on a warm boot (post-macOS) vs stock boot, table mode 1 (the 3 sourced
T6021 records), with the seam logs — if warm passes and stock wedges, the
clock-gate group is the missing piece; if table-mode-1 passes on stock, the
pre-CPU table is the missing piece.

### 1.4 What the ISP comparison also settles

- **RUN is the whole start**: m1n1 `hw/asc.py` CPU_CONTROL RUN=bit4, and the
  ISP writes CONTROL 0→0x10 and polls — no RVBAR write exists in the ISP
  driver (RVBAR 0x1050000 is defined in isp-regs.h:14 and never stored; every
  .c grepped). iBoot/bootloader latches it; mainline rtkit.c never starts
  CPUs (fw-start receipt §1 stands).
- **The ANE boot contract is the Apple-generic one**: ISP first-magic
  `0x08042006` = ANE SCRATCH7 READY; ISP wake `0xf7fbdff9` = ANE wake; ISP
  CONTROL/STATUS offsets = ANE CPU_CONTROL/CPU_STATUS. The H14 P0..P7
  contract's shape is confirmed against a shipped Linux driver.

---

## 2. Ordered Linux-context start sequence (mirrors apple-isp, T6021 addresses)

ISP step (file:line) → T6021 ANE adaptation. Every ANE address engine-relative
to the 0x284000000 aperture; power values per the pinned receipts.

| # | apple-isp (branch isp/t602x-v2) | T6021 ANE adaptation | ANE cite |
|---|---|---|---|
| 1 | genpd attach all domains, primary via device_link RPM_ACTIVE, secondaries `pm_runtime_get_sync` ascending (isp-drv.c:44-77; isp-fw.c:70) | genpd raise all 8 islands (ane_cpu, ane_sys, ane_sys_mpm, ane_td, ane_base, ane_set1..4); gate: every ps ACTUAL=0xf BEFORE any MMIO | power-dart-fwload §1.3/§1.4 |
| 2 | 4 windows via `devm_platform_ioremap_resource_byname` → non-posted (lib/devres.c:139 + of/address nonposted-mmio) | `ioremap_np` the 32 MiB engine window (mailbox child region inside — no exclusive request) | rtkit-port §2.2 |
| 3 | iommu domain over 3 ISP DARTs, stream 0 (t8112.dtsi:606); static heap carveout + drm_mm iovad from heap_top (isp-drv.c:80-131); surfaces `iommu_map_sgtable` (isp-iommu.c:120) | attach dart-ane0 inst0/1/2 stream 0; stage selene via dma_alloc_coherent + iommu_map; entry-alias at the latched RVBAR entry (0x10000000000), page-by-page via iommu_iova_to_phys | fwload; power-dart-fwload §2.3/§3.3 |
| 4 | bootloader staged the fw image; `isp_heap` "Filled in by bootloader" (t600x-common.dtsi), iommu-addresses static IOVA | iBoot/m1n1 stages selene (`pre-loaded=<1>`) — on a Linux-staged boot the fwload staging+alias REPLACES this step | ADT ane0 `pre-loaded`; fwload |
| 5 | `pm_runtime_resume_and_get` — "Needs to be power cycled for IOMMU to behave correctly" (isp-fw.c:744) | genpd resume_get before the sequence; never ps@2e0 from kernel (s24) | boot.c gates |
| 6 | `ISP_GPIO_CLOCK_EN ← 1` (isp-fw.c:278) | **GAP — no Linux provider**: ADT clock-ids 318-321 + gate 473 (ANE-SYS-V). Only m1n1 `pmgr_adt_power_enable("/arm-io/ane")` covers it today. | arm-b §1; W7 G1 |
| 7 | if shutdown marker: `EDPRCR←2; FABRIC 0x738/0x798/0x7f8/0x858 ← 0xff00ff; IRQ_MASK_0..5←0xffffffff; drain 0x818/0x81c; wait STATUS IN_WFI` (isp-fw.c:225-258) | T6021 pre-CPU table: `eng+0xB38 ← 0x01FF01FF`, `eng+0xB98 ← 0x01FF01FF`, `eng+0xBF8 ← 0x01FF01FF` (3 records, always-run, kext-sourced) — NOT the t8103 offsets | boot.c pass4/5; arm-b §2 |
| 8 | `GPIO_0..7 ← 0` (isp-fw.c:285-293) | `InitANEScratchRegisters`: SCRATCH0..7 (eng+0x1840048..0x1840064) ← 0, then SCRATCH7 pulse 1→0 | K14 0x960f2a8; boot-prereqs §1.5 |
| 9 | `mbox IRQ_ENABLE ← 0` until boot complete (isp-fw.c:295) | leave ASC mailbox quiescent until RTKit phase; IRQ 884 armed after handshake | rtkit-port §2.6 |
| 10 | `COPROC_CONTROL ← 0` then `← 0x10` (isp-fw.c:296-297) | `CPU_CONTROL (eng+0x1400044) write32 0`, then `0x10` (RUN) | rvbar-width local order; kext 0x95e954c boot |
| 11 | poll `GPIO_7 == 0x08042006`, ≤1000 × 1 ms (isp-fw.c:299-318) | poll `SCRATCH7 (eng+0x1840064) == 0x08042006`, ≤1000 × 1 ms; timeout ⇒ STOP, no retry | K14 poll; s22 |
| 12 | read fw requests (GPIO_0/1/3); write bootargs into IPC surface; publish args_iova GPIO_0/1; `dma_wmb()`; `GPIO_7 ← 0xf7fbdff9`; poll `0x08042006` (isp-fw.c:355-425) | publish SCRATCH0/1 = u64 pool/IPC DVA (dsb st before); wake `SCRATCH7 ← 0xF7FBDFF9`; poll B DONE (same magic); RTKit HELLO rides after the wake | NS §3; boot.c ack model |
| 13 | read fw-published channel table from the IPC surface (isp-fw.c:455-520) | RTKit: HELLO/EPRollCall/EPMAP on MGMT EP0 via the ASC mailbox (eng+0x1408000: A2I send0/1 = +0x1408800/+0x1408808, I2A recv0/1 = +0x1408830/+0x1408838, ctrl +0x1408110/114); endpoint bitmap capture names the CSNE channels | [M1N1] asc.py; [RTKIT] mailbox.c:38-48 |
| 14 | enable mbox IRQ (0xf) then IPC command processor start cmds (print/pmu/dsid/pmp/start) (isp-fw.c:630-730) | `apple_rtkit_start_ep` per announced EP; SetupEndpoints ring announces; CSNE_CMD PING 0x11 / BUILDINFO 0x06 on INIT; then REG_FILE_LOAD 0x05 ships the 1456 B `_rtk_tunables` (fw-side; per-chip T6021 selector content — macOS builds it at runtime, H14TunableManager) | rtkit-port §3/§6; arm-b §1.5 |

ISP evidence lines are [FACT] against the fetched branch; ANE adaptation lines
carry their own citations. Steps 6-7 are the two the fwstart#2 core did not
do — see §1.3.

---

## 3. RTKit endpoints and CSNE command framing (kext disassembly)

### 3.1 Transport (mailboxes)

- ASC block = engine+0x1400000. `ASCRegs` [M1N1 asc.py:34-43]:
  CPU_CONTROL +0x44, CPU_STATUS +0x48, INBOX_CTRL/OUTBOX_CTRL +0x110/0x114,
  INBOX0/1 +0x800/0x808, OUTBOX0/1 +0x830/0x838. So on T6021: A2I send
  words at eng+0x1408800 (payload u64) / +0x1408808 (endpoint u64 — the
  doorbell write), I2A recv at eng+0x1408830/+0x1408838, controls
  eng+0x1408110/0x1408114. Matches [RTKIT] mailbox.c APPLE_ASC_MBOX_* and the
  live W10 reads of 0x285408110/114.
- RTKit message = (endpoint, u64 msg); system endpoints MGMT=0, CRASHLOG=1,
  SYSLOG=2, DEBUG=3, IOREPORT=4, OSLOG=8; app endpoints ≥ 0x20
  (`APPLE_RTKIT_APP_ENDPOINT_START` = 0x20, rtkit-internal.h:22).
- `apple_rtkit_send_message` does `dma_wmb()` then mailbox send (rtkit.c:604-
  634) — buffer visibility before doorbell is upstream-mandated.

### 3.2 Endpoint numbers — what is pinned and how to get the rest

- Kext channel slots are **0..6** (`SetupEndpoints` bounds `cmp w1, #0x7` at
  0xfffffe00095fe690); descriptors at `dev+0x5c0`, stride 0x40
  (`ubfiz x9, x19, #6, #32` at 0xfffffe00095fe6d0); `HandleRTBuddyMessage`
  accepts indexes 1..6 (`cmp x19,#7 b.ge` reject at 0xfffffe00095ff038).
- Per-channel cfg table `__DATA_CONST.__const+0x814e520`, 40 B/entry; ring
  sizes 64K/256K/256K/64K/128K/64K for INIT/T2F_CMD/T2F_HIPRI/T2HS/T2HC/T2HT
  stand from the rtkit-port receipt.
- Channel NAMES (`FW_INIT T2F_CMD T2F_HIPRI T2H_SHMEM T2H_CMD T2H_TERM`,
  cstring 0xfffffe00074c5170) are kext-side only — selene contains no channel
  strings (grepped this lane; only `rtbuddy` at fw 0xa08b4) and selene.syms
  is empty. The concrete rtkit EP ids are owned by RTBuddyService and are
  announced by the firmware's EPMAP at handshake — capture them there (the
  rtclient's endpoint-bitmap log is the right mechanism). Convention check:
  app EPs start at 0x20, and m1n1's RTBuddy-v2-style SIO service uses
  `epmap[0x20]` — expect the six channels mapped at/above 0x20, small ids,
  announced order stable. [FACT for the mechanisms; EP ids = runtime datum]

### 3.3 Ring word framing — conflict RESOLVED (two different words)

Direct disassembly, both sides of the same kext build:

**(a) Ring ANNOUNCE / drain word** — `SetupEndpoints`
0xfffffe00095fe8b0-0x95fe8e8 [FACT]:

```
mov  w9, #0x14 ; mov w10, #0xc
cmp  x23, #0x100, lsl #12          ; ring size vs 1 MiB
csel x9, x10, x9, lo               ; shift = size<1MiB ? 12 : 20
mov  x10, #0x20000000000000        ; class 2<<52
mov  x11, #0x10000000000000        ; class 1<<52
csel x10, x11, x10, lo             ; class = size<1MiB ? 1 : 2
lsl  w11, w11, w9 ; mvn            ; granule mask
lsr  x9, x23, x9 ; tst; cinc       ; code = ceil(size >> shift)
bfi  x10, x9, #44, #8              ; word[51:44] = size_code
bfxil x10, x8, #0, #44             ; word[43:0]  = ring DVA low 44 bits
```

So the announce word = `{ring_dva[43:0] | size_code[51:44] | size_class[53:52]}`
with size = code << shift. The fw→host drain decode in
`HandleRTBuddyMessage` 0xfffffe00095ff0d4-0x95ff100 uses the SAME fields:
`sbfx x10, x9, #0, #44` (offset44), `ubfx x11, x9, #44, #8` (code),
`ubfx x12, x9, #52, #2` (class), size = class==0 ? 0 : class==1 ? code<<12 :
class==2 ? code<<20 : code<<21 (csel chain at 0x95ff0e0-0x95ff100); "queue
drained" when `offset44 == [ringobj+0x18]` (the ring's own base DVA) AND
`size == [desc+0x8]` (ring size) — compare/`ccmp` at 0x95ff10c-0x95ff114,
branch to the drain path at 0x95ff218.

Class table (definitive): **0 ⇒ 0 (doorbell-only), 1 ⇒ code<<12 (4 KiB
granule), 2 ⇒ code<<20 (1 MiB), 3 ⇒ code<<21 (2 MiB)**. W2's old
"class 1 ⇒ code<<13" was a misread (the <<21 line belongs to class 3).

**(b) Ring DATA word — both directions**: `{offset[23:0] | length[47:24]}`, len ≤ 0xFFFFFF.
- Send: `rtbuddyEndpointSendMessage` 0xfffffe00095f3bf4-8:
  `and w8, w25, #0xffffff` ; `bfi x8, x21, #24, #24`.
- Receive: 0xfffffe00095ff118-11c: `and x26, x9, #0xffffff` ;
  `ubfx x27, x9, #24, #24` → `processCommandResponse(dev, ring_base+offset,
  len, 0)` at 0xfffffe00095ff160. Bounds check offset+len ≤ ring size at
  0x95ff120-130 rejects malformed/drain words on the data path.

**Resolution**: the two prior receipts each decoded a different word of the
SAME protocol and were compared against each other. H14RpcProtocol's
{offset[0:28)|sizeCode[28:36)|class[36:38)} matches nothing in the binary.
The rtclient's `csne_ping` data-word packing (cursor[23:0]|len[47:24]) is
correct as implemented. For a 64 KiB INIT ring the announce word is:
`class=1, code=0x10 (64Ki>>12), dva=ring IOVA` →
`w = (iova & 0xFFFFFFFFFFF) | (0x10 << 44) | (1 << 52)`.

### 3.4 Command header and opcodes (stand, with one upgrade)

- Header `sCSneControllerCmdHdr` per h14-rpc-protocol notes §2 stands: cmd id
  u16 @+0x04, flags u8 @+0x06 (bits[0:5] preserved, [5:7]=1), +0x07=0,
  param0 u32 @+0x1c, param1 u32 @+0x20; message sizes 0x20/0x24; commands
  carved from ring memory (`ANEFirmwareCommandBuffer` alloc 0x95e45d4 → ring
  take 0x95e1918).
- EndpointSendMessage plumbing re-verified this lane: send method =
  queue vtable +0x1e8 via `blraa` at 0xfffffe00095f3c30; send retry/logging
  wrappers at 0x95f3990 family; `rtbuddyEndpointSendInPlace(u8 ep, u64, u64,
  u64, bool)` mangled name confirms ep travels as a u8 slot.
- Opcodes: 0x400-0x404 + 0xff00 HIGH (kext immediates), remainder MEDIUM per
  the h14-rpc-protocol receipt — unchanged. PING 0x11 / BUILDINFO 0x06 remain
  the first-boot control probes.

---

## 4. DART / SART requirements (assignment item, consolidated)

1. Three dart-ane0 instances (0x285800000 LLT / 0x285810000 BRD / 0x285820000
   BWR), all stream 0, t8110 fallback binding; TCR must read
   TRANSLATE_ENABLE|FOUR_LEVEL with a valid TTBR and ENABLE covering the
   device stream at RUN time — s18-measured state is the requirement.
   DAPF window 0x285804000 is NOT a gate (s20/s21).
2. No SART anywhere in the ANE path — requirement is DART-only.
3. The entry region: whatever IOVA the RVBAR latch encodes
   (0x10000000000 = dart-ane0 vm-base on this box) MUST be mapped before
   RUN — the entry-alias does this; a missing mapping yields a logged dart
   fault, never silence.
4. The DART windows reg 0x308/0x310 (vm-base/window end) must be programmed
   on all three instances (s17); the ADT `dart-tunables-instance-0/1/2`
   values were verified 18/18 to match what Linux programs (IORegistry
   capture re-read this lane; the ane0 node itself carries NO
   tunables/reg-tunables property — the tunables story is DART-side and
   fw-side `_rtk_tunables` only).
5. Non-posted mapping is a DART-adjacent survival requirement: every ANE
   window touched from Linux must be nGnRnE (§1.2).

## 5. What M2FwStart did with each finding

| Finding | Delivered (hub) | Ack | Outcome |
|---|---|---|---|
| Ring word framing + doorbell resolution (§3.3) | yes | yes | Adopted for the handshake phase: announce {dva[43:0]\|code[51:44]\|class[53:52]}, class-1 shift 12; matches their encoder |
| Wedge attribution + ISP comparison (§1) | yes | yes | Adopted, PLUS live addendum from the box (see below): the dangling-phandle dtb defect is a second, same-class mechanism |
| Start sequence + DART/SART consolidated (§2, §4) | yes | yes | Adopting table mode 1 (T6021 pre-CPU table) + the warm-vs-stock discriminator; their next runs are state-report / tunables / scratch / RVBAR bisect on the repaired dtb BEFORE any RUN write |

M2FwStart live addenda acked back into this receipt (2026-09-22):
1. The composed overlay dtb carries DANGLING phandles: 0x1f5 (ane_sys_mpm),
   0x1f1, 0x1f0 (ane_cpu) are referenced by ane0 and dart1/2 but defined
   nowhere in the live tree (OF errors at 0.012 s, phandle-walk verified).
   ane0 attaches only 5/6 domains; ane_cpu + ane_sys_mpm are never
   genpd-raised on a stock boot. This folds into §1.3: a released CPU whose
   island was never raised is the unpowered-window wedge class — the cold
   boot had TWO gaps (clock-gate group + unraised islands), not one.
   dtb repair (re-resolve the overlay phandles against the base) is the
   first fix ahead of any start attempt.
2. apple-mailbox fails probe every boot (-ENXIO, missing send-empty IRQ), so
   fw_devlink defers ane0 indefinitely — insmod cannot probe at all on the
   current tree; same dtb repair covers it (supplies the mailbox child/IRQ).

## 6. Method notes / provenance

- ISP sources fetched from AsahiLinux/linux branch `isp/t602x-v2` via gh api
  (tree dd1bbfed) to a scratch dir; nothing in-repo modified except this
  receipt. Kext + selene disassemblies cached (llvm-objdump-19, --macho);
  all cited kext addresses are symbol-anchored (syms file shipped with the
  fixture).
- ADT facts re-verified against BOTH the raw dtree dump (ane0/dart-ane0
  nodes) and the IORegistry export; where they differ (runtime-added
  `dart-tunables-instance-*` appear only in the IORegistry — XNU
  driver-supplied), the raw ADT is authoritative for what iBoot passes.
- selene channel-name absence + empty selene.syms recorded so nobody retries
  that route for EP ids; EPMAP capture at handshake is the path.
- No device contact, no ssh to any host; all evidence on-disk binaries,
  fetched upstream sources, and prior live receipts.

---

## 7. Addendum — B4 result and the B5 clock-gate decode (same day, later)

M2FwStart live result B4 (repaired dtb): pre-CPU table 0xB38/0xB98/0xBF8 ←
0x01FF01FF fired clean from kernel context; CPU_CONTROL RUN clean
(CPU_STATUS 0x2a → 0x28, STOPPED cleared); poll A timed out with zero
SCRATCH7 activity and zero dart faults; box alive. Table eliminated as the
wedge; RUN itself is no longer the wedge either. The remaining suspect is
§2 step #6 — the clock-gate group.

### 7.1 The pmgr id → register decode rule (this lane)

Device records in the ADT pmgr `devices` table decode as:
`ps_addr = ps-regs[map].window + ps-regs[map].off + index*8`
(dumper fields: map = ps-regs index, index = addr_offset×8).

Validated on seven known anchors:
| device | map/index | ps-regs entry | computed | authority |
|---|---|---|---|---|
| ANE_SYS | 6/12 | [6]=reg0+0x200 | 0x28e080260 | overlay ane_sys@260 |
| ANE_CPU | 6/28 | [6] | 0x28e0802e0 | overlay ane_cpu@2e0 |
| ANE_SYS_MPM | 8/0 | [8]=reg0+0x4000 | 0x28e084000 | overlay @4000 |
| ANE_TD | 8/1 | [8] | 0x28e084008 | overlay @4008 |
| ANE_BASE | 8/2 | [8] | 0x28e084010 | overlay @4010 |
| ANE_SET1 | 8/3 | [8] | 0x28e084018 | overlay @4018 |
| ANE_SET4 | 8/6 | [8] | 0x28e084030 | overlay @4030 |

pmgr reg windows (dump order): [0]=0x28e080000, [1]=0x29e280000,
[2]=0x290280000, [3]=0x28e680000, [4]=0x28e000000 …

### 7.2 The kext clock/power path is provider calls, not MMIO

`0xfffffe00095d1d20-0x95d1d90`: `ldr w2,[x20,#0x8f0]` (id from ADT
clock-ids) → vtable +0x8a8 (enableDeviceClock) → provider object dev+0x810,
vtable +0x8b0 (enableDevicePower), same id. No kext-side MMIO; the write is
the standard pmgr ps op (TARGET[3:0]=0xf | AUTO_ENABLE bit28, poll
ACTUAL[7:4]==0xf) — same shape as pmgr-pwrstate.c.

### 7.3 The ane0 clock-ids are VENC gates — the B5 addresses

ADT devices table decode of ane0 `clock-ids [318 319 320 321]`:
**318=VENC_PIPE4, 319=VENC_PIPE5, 320=VENC_ME0, 321=VENC_ME1** — all map 15
(ps-regs[15] = window2 + 0x8000 = 0x290288000), index 1..4. Apple wires
ane0's clock-ids to the VENC power gates on T6021 (ANE in the VENC complex
on this die). Kernel-writable B5 addresses (ps TARGET RMW 0xf|AUTO_ENABLE,
poll ACTUAL, 100 µs, never TARGET=0):

| id | device | ps addr |
|---|---|---|
| 318 | VENC_PIPE4 | 0x290288008 |
| 319 | VENC_PIPE5 | 0x290288010 |
| 320 | VENC_ME0 | 0x290288018 |
| 321 | VENC_ME1 | 0x290288020 |

Plain pmgr ps words (kernel-genpd op class), not the ane_cpu island —
outside the s24 fatal class.

### 7.4 Gate 473 (ANE-SYS-V) — CLOSED as "no register exists"

flag 0x10 = VIRTUAL → no ps word anywhere; enable = parent-walk only
(m1n1 pmgr.c PMGR_FLAG_VIRTUAL skip; XNU same). Parents already raised by
genpd. [FACT for the no-write semantics; parent-chain decode MEDIUM]

### 7.5 B5 discriminator and fallback

Enable 318-321 BEFORE CPU_CONTROL 0→0x10, rerun the identical contract core.
If poll A stays silent: the next item is not a register — it is G6/Item3
(FW_INIT boot-args surface identity; SetupFWInitBootArgs template dev+0x998,
0x100 bytes, surface+0x84=0x40) and the P5 pool word. Note: a working alias
predicts NO dart fault, so B4's clean fault log is consistent with "fetch
succeeded, firmware stuck early" — the shape a missing rail produces.
