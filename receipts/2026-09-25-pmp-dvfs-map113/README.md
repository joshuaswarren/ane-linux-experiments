# RegMap 113 / PA 0x400004000 identified: the PMP-served device-DVFS command interface (2026-09-25)

Owner: PmpDvfsResearch. Off-device only (PVE static analysis; no laptop touched).
Question: which node/reg covers 0x400004A00 and 0x400006000 on T6001, what block it
is, who makes a DVFS command take effect, and whether the mechanism extends to
T8103/T6021.

Sources (all on PVE): live T6001 ADT
`~/.cache/ane-live-adt-jw16mbp1-20260913T1789287036951/adt.bin`
(J316cAP / MacBookPro18,2), T6021-family ADT `/tmp/j414c.adt.raw`
(J414cAP / Mac14,5, ADT pmgr compatible `pmgr1,t6021`), 22G74 T6001 stub KC
`/var/tmp/jw16-kc/kernelcache.release.mac13j.macho` (sha256 prefix 35695639 —
same blob AneClockM1's `t6001-pmgr.asm` was disassembled from), 22G74 T6021
stub KC `/var/tmp/t6021-kc/kernelcache.t6020.13.5-22G74.macho`, omarchy-linux
kernel tree (`drivers/soc/apple/pmp.rs`, `drivers/pmdomain/apple/`), m1n1
proxyclient (`~/src/m2-m1n1`), iBoot j414c
(`/tmp/m2kstart/omarchy-ane/receipts/2026-09-20-iboot-j414c/iboot_j414c_dec.bin`),
live capture `receipts/2026-09-25-t6001-perfstate-capture` (branch
agent/m1-ane-clock-macos) raw `/tmp/levers7-raw/ane-perfstate.out`.

## 1. Verdict

- **T6001: `/arm-io/pmgr` reg[113] = raw 0x200004000, size 0x4000** (device-tree
  reg is pre-bridge; the `/arm-io` bus range adds 0x2_00000000) → **absolute
  PA 0x400004000, 16 KiB**. Cross-checked against the macOS ioreg capture's
  IODeviceMemory[113] = 0x400004000/0x4000 (same entry list, 241 windows).
  DVFS_CMD = base+0xa00 = 0x400004A00; DVFS_ON = base+0x2000 = 0x400006000.
- The block is **not** a clock controller and not plain mailbox SRAM: it is the
  AP-side **command window of the PMP's (Power Management Processor) device-DVFS
  subsystem** — the interface behind ApplePMGR's "PTD-SOC-DEV-DVFS" state
  machines. A DVFS command takes effect because the **PMP coprocessor firmware
  is running** and consumes/acks these registers; it is not a bare hardware
  sequencer that fires on write.
- Under Asahi Linux the PMP is **not running** (DTS node `pmp@28e700000` is
  `disabled`; live probe showed report-SRAM `actual=0 status=0`, no ack), which
  is exactly why direct Linux writes of the same values read back 0 and change
  nothing (431–438 ms vs macOS 140.86 ms encoder).

## 2. T6001 ADT evidence

### 2a. The pmgr reg[113] window and its neighbors

`/arm-io/pmgr` (`pmgr1,t6001`), 241 reg entries. Entries cited below as
(raw → absolute, bridge +0x2_00000000), all size 0x4000:

| idx | raw | absolute |
|---|---|---|
| 0 | 0x8e080000 | 0x28e080000 (main PMGR island; map0) |
| 2 | 0x8e580000 | 0x28e580000 (east island; map2) |
| 4 | 0x8e000000 | 0x28e000000 (ANE0 ASC window) |
| 110 | 0x200000000 | 0x400000000 |
| 111 | 0x200018000 | 0x400018000 |
| 112 | 0x200014000 | 0x400014000 |
| **113** | **0x200004000** | **0x400004000** ← DVFS_CMD +0xa00, DVFS_ON +0x2000 |
| 114 | 0x200008000 | 0x400008000 |
| 115 | 0x20000c000 | 0x40000c000 |
| 116 | 0x200010000 | 0x400010000 |
| 117 | 0x201000000 | 0x401000000 |
| 118 | 0x201008000 | 0x401008000 |
| 119 | 0x201004000 | 0x401004000 |
| 134 | 0x82000000 | 0x282000000 |
| 135 | 0x104000000 | 0x304000000 |
| 136 | 0x183000000 | 0x383000000 |
| 137 | 0x202000000 | 0x402000000 |

The 0x400000000–0x401008000 cluster (110–119) is claimed by **no other ADT
node** — the walk of all 367 nodes found nothing else in the pre-bridge band
0x2_00000000–0x2_02000000 except `/arm-io/error-handler` (0x402000000, 0x4000)
and `/arm-io/pmp`. Entries 134–137 are the **first 16 KiB of each of the PMP's
four die-IO PIO ranges** (see 2b) — i.e. ApplePMGR maps windows inside
PMP-controlled areas as a matter of course.

### 2b. `/arm-io/pmp` — the coprocessor

`device_type = "pmp"`, `role = "PMP"`, compatible `iop,ascwrap-v4`
(iBoot/RTBuddy ASC wrapper), reg (raw → absolute):

1. 0x8ec00000 + 0x6c000 → **0x28ec00000** — ASC wrap (CPU control/RVBAR area)
2. 0x8e850000 + 0x5010 → 0x28e850000
3. 0x8e700000 + 0x100000 → **0x28e700000** — PMP SRAM/PMGR (1 MiB)
4. 0x8e3d0000 + 0xc00 → 0x28e3d0000 (fw-PMGR scratch)
5. `pio-reg-index = 4`: nine PIO ranges, each mapped into the PMP's own IOMMU
   at `pio-vm-base 0xc0000000`, granule 0x1000000 (`pio-vm-size 0x40000000`):
   abs 0x282000000, 0x304000000, 0x383000000, **0x402000000**, the three
   CPU-cluster PMGRs 0x210e70000/0x211e70000/0x212e70000, and (die-1 spares)
   0x482000000, 0x502000000.

Interrupts 1006–1009 = the ASC mailbox (Asahi DTS `pmp_mbox` at 0x28ec08000,
`apple,asc-mailbox-v4`). `iommu-parent` = pmp DART. **No `pre-loaded`
property** (contrast: `/arm-io/ane0` has `pre-loaded = 1` — the ANE firmware is
iBoot-loaded, the PMP's is not declared so).

### 2c. The PMP nub declares the DVFS domains — including ANE

`/arm-io/pmp/iop-pmp-nub` (compatible `iop-nub,rtbuddy-v2`) carries a
**`dvfs-domain`** table (16 × 28-byte entries: u32 idx, u32 count, u32 arg,
char[16] name):

```
dev  1 DCS          (4)     dev  9 SOC0_ANE_SYS (3)
dev  2 FAB          (3)     dev 10 SOC0_AVD     (3)
dev  3 FAB_PLL      (3)     dev 11 DISP0        (3)
dev  4 FAB_AFNC0    (3)     dev 12 AVEMSR0      (4)
dev  5 FAB_AFNC2    (3)     dev 13 AVEMSR0_AVE  (4)
dev  6 FAB_AFNCX    (3)     dev 14 AVEMSR0_MSR  (4)
dev  7 AFR          (3)     dev 15 FAB_AFNC4    (3)
dev  8 SOC0         (3)     dev 16 DISP1        (3)
```

**The PMP nub itself declares the DVFS state groups it manages: DCS, FAB(+PLL,
AFNC), AFR, SOC0, SOC0_ANE_SYS, SOC0_AVD, DISP, AVEMSR.** This matches:

- the pmgr `devices` table (77 power domains, 430 devices): **`ANE_SYS` has
  `notify_pmp = True`** (psreg=5, id2=55; so do GFX, VENC_SYS, AVD_SYS,
  ISP_SYS, MSR*, PRORES, DISPEXT*_FE, plus the per-rail `-VNOM/-VMAX/-VMID2`
  devices), while `ANE_SYS_CPU` does not;
- the pmgr `clocks` table: `id=1 PMP` (a PMP clock channel), `PLL_AFR`,
  `PLL_ANE0` (id=21, perf_block 8 = perf-regs[8] = reg[4]+0x70000 =
  0x28e070000, size 0x64 — the known ANE PLL block);
- the 22G74 ApplePMGR log string in the stub KC:
  `ApplePMGR: [Die %u] PTD-SOC-DEV-DVFS: Device=0x%x level=%d msg=0x%llx`
  (`msg` = the 0x80000000|… token), plus `ApplePMGRNub::DeviceDVFSState`,
  `_devDVFSStateList`, an ADT `dvfs-domain` property consumer, and IOReport
  channels `SOC-DEV-DVFS`, `DVFS-STATE`, `PMPTOOL`;
- `H11ANEIn::submitWorkToPerfController(H11ANERequestParams*,
  H11ANEProgramCreateArgsOutput*, bool)` in the same KC — the ANE driver is
  the upstream trigger of the PMGR DVFS ops.

### 2d. The ANE perf domain and its ladder

`pmgr` `perf-domains` (14 × 28-byte entries): ANE = bytes `08 10 00 08` —
**domain index 8** (SOC=1, ECPU=2, DCS=3, PCPU=5, ANE=8, DISP=0xb, AVEM=0xc,
PCPU1=0xd; PMP-delegated domains are 0x20–0x25: PMP-SOC, PMP-FAB0–3,
PMP-DCS), states-table index b0=0x08, flag b1=0x10 (set only for ANE).

`voltage-states8` = the 6-entry ANE op-point ladder (freq Hz, mV):

| state | freq | volt |
|---|---|---|
| 0 | 300.0 MHz | 550 mV |
| 1 | 540.0 MHz | 615 mV |
| 2 | 780.0 MHz | 650 mV |
| 3 | 1020.0 MHz | 734 mV |
| 4 | 1260.0 MHz | 800 mV |
| 5 | 1500.0 MHz | 909 mV |

Note what the token does: it changes frequency **and voltage** (909 mV at the
top). Voltage sequencing on this SoC is the PMP's job (its RTKit opcodes are
REGISTER_IOREG/SET_IOREG — named IO regulator channels). The captured ~4.6 ms
inter-command cadence is a sequencer step pace, not a host loop.

## 3. T6021 (j414c / Mac14,5, `pmgr1,t6021`) ADT evidence

- The T6021 pmgr reg[] (73 entries) has **no window at 0x400004000**. The
  die-IO band entries are: [42] 0x204ea8000 → 0x404ea8000, [44] 0x204e80000
  (0x28000) → **0x404e80000 = `pmgr_gfx`** (the GPU-area PMGR island Asahi's
  t602x DTS also carries), [48] 0x40a000000, [50] 0x40c000000, [72]
  0x408000000 (0x1ffc000). `perf-regs[9]` = reg 44 + 0x10000, size 0x6b — a
  perf block inside pmgr_gfx (T6001's perf-regs never leave the 0x28exxxxx
  islands).
- `/arm-io/pmp` is **structurally identical** to T6001: same ASC
  (0x28ec00000+0x6c000), same SRAM/PMGR (0x28e700000+0x100000, plus
  0x8e850000+0x5010 and fw-PMGR 0x28e3d0000+0x2000), `role=PMP`, same
  `iop,ascwrap-v4`, same mailbox IRQ pattern (1083–1086); PIO ranges shifted
  to abs 0x280000000, 0x300000000, 0x340000000, **0x400000000**, CPU clusters,
  0x480000000, 0x500000000.
- `/arm-io/pmp/iop-pmp-nub` again carries `dvfs-domain`: DCS (4), FAB (3),
  **AFR (6 levels, arg 0x21)**, SOC0 (3), DISP0 (4), AVEMSR0 (3), DISP1 (4), …
  — the same PMP-managed DVFS subsystem, with the AFR/ANE group grown to 6
  levels.
- `perf-domains` ANE entry bytes are identical (`08 10 00 08` → domain 8).
  `voltage-states8` on this capture is `{1,1,1,0,2,0}` (not a frequency
  ladder) — the T6021 ANE op-point table is NOT states8; the actual T6021 ANE
  ladder was not identified in this pass.
- `/arm-io/ane0` on T6021: fw window 0x84000000 (0x2000000), ASC at
  0x28e080000 (0x4034) + 0x28e08c000 (0x4000), **no `pre-loaded`** — matches
  the fleet record that the T6021 ANE firmware must be staged and started
  under Linux.

## 4. Who runs the PMP — macOS, iBoot, m1n1, Asahi

- **macOS (22G74, both stub KCs):** `ApplePMGR.kext` (+ per-SoC
  `AppleT6000PMGR` / `AppleT6020PMGR` / `AppleT6021PMGR`,
  IONameMatch `pmgr1,t60xx`; plus `AppleBringUpPMGR` for `pmgr1,bring-up`),
  `ApplePMP.kext` with personalities `ApplePMP`/`ApplePMPv2`
  (**PMPEndpoint1**) and `ApplePMPThermal` (**PMPEndpoint2**) on
  `RTBuddyEndpointService`, and **`ApplePMPFirmware.kext`**
  (`IOMatchCategory RTBuddyFirmwareService`, `IOPropertyMatch role=PMP`) —
  macOS owns the PMP's RTKit boot and firmware servicing.
- **iBoot (j414c decoded):** contains `iop-pmp-nub`,
  `arm-io/pmp/iop-pmp-nub`, `pmp-dart`, `dart-pmp`, `pmgr_disable_pmp_pmc`,
  `fpmp`, `pmpr`, `PMPx` — iBoot participates in PMP bring-up during its own
  boot, but the Linux handoff state (next point) shows it does not leave a
  serving PMP behind for us.
- **Linux handoff state (measured, m1max-ane-clock receipt §2):** PMP report
  SRAM (0x28e3c0000, `pmp-ane-sys`) reads `tgt_read=0x60003000 actual=0x0
  status=0x0`; setting the report bit produced no ack ("pmp not ready, no ack
  expected"). **The PMP firmware is not running under Asahi Linux.**
- **Asahi kernel (omarchy-linux):** `drivers/soc/apple/pmp.rs` — a complete
  RTKit PMP driver (module `apple_pmp`, compatible `apple,t6000-pmp-v2`):
  maps reg-names `pmp` (0x80000 window) and `asc` (0x4000); patches bootargs
  in PMP SRAM (pointer at `+0x22c`, size `+0x230`; keys `BDID`, `DVID`,
  `DCAP`); starts the ASC CPU (`CPU_CONTROL 0x44 |= CPU_RUN BIT4`); RTKit
  handshake on endpoint **0x20**; serves the PMP's syscalls —
  `GET_IOVA_TABLE 0x10` (maps `apple,pio-ranges` into an IOMMU domain at
  PIO_VM_BASE 0xc0000000, granule 0x1000000), `MALLOC 0x12`, `FREE 0x14`,
  `SET_BUF 0x30`, `REGISTER_IOREG 0x32` (reads a named channel: name[0x30],
  size@0x40; looks up DT property `apple,tunable-<name>` for the payload),
  `SET_IOREG 0x34`. **It loads no firmware file** — `apple_rtkit_init` has no
  firmware argument; the design assumes the PMP firmware image already sits in
  the PMP SRAM at handoff (iBoot-loaded, CPU parked) [INFERENCE from the
  driver's shape; not yet verified on hardware]. Gaps: the DT carries no
  `apple,tunable-*` IOREG payloads (the driver logs "unknown property" and
  registers a zero-length channel), and `pmp@28e700000` is `status =
  "disabled"` in the shipped DTS — so the driver has never bound on this
  fleet. `APPLE_PMP` Kconfig exists (`selects APPLE_PMP_REPORT +
  RUST_APPLE_RTKIT`); the tree-local .config has `CONFIG_APPLE_PMP_REPORT not
  set`, so the jw16 kernel build config must be checked before relying on it.
- **m1n1 (`~/src/m2-m1n1`):** zero PMP references in the proxyclient tree —
  m1n1 neither boots nor quiesces the PMP.

## 5. 22G74 AppleT6000PMGR disassembly (jw16 stub KC, sha 35695639)

Bases: `setPerfState` va 0xfffffe0009b52f1c (file 0x2b4ef1c); `writeReg32`
va 0xfffffe0009b54ee8 (file 0x2b50ee8); special branch va 0xfffffe0009b56368.

- **`setPerfState` (22G74) accepts domains 1–5 via a jump table at
  0x9b52f9c and domain 13 explicitly (0x9b52fb8); domain 8 is not accepted in
  22G74** — the ANE domain-8 apply path was added by the 25G83 kext (live
  capture: 36 `SET f=_ZN9ApplePMGR13_setPerfStateEjhj a2=8` hits). The
  register mechanics below are unchanged across both.
- **`writeReg32` general path:** a 10-iteration loop (`cmp x28, #0xa` at
  0x9b55210) over a static table at va 0xfffffe00074fa828 (16 B entries:
  map, reg, f2, f3), extracted from the KC at file 0x4f6828:

  ```
  [0] map=0 reg=0x208 f2=0x1f8   [5] map=2 reg=0x178 f2=0x170 f3=0x168
  [1] map=0 reg=0x228 f2=0x208   [6] map=3 reg=0x1a8 f2=0x1a0
  [2] map=0 reg=0x200 f2=0x1f0   [7] map=3 reg=0x1b0 f2=0x1a8 f3=0x1a0
  [3] map=2 reg=0x150 f2=0x148   [8] map=3 reg=0x1c0 f2=0x1b8
  [4] map=2 reg=0x170 f2=0x168   [9] map=3 reg=0x1c8 f2=0x1c0 f3=0x1b8
  ```

  For each entry it calls the read vtable slot (+0xd18) and the write slot
  (+0xd30), applying `orr w3, w0, #0x20000000` (0x9b55028, 0x9b5509c):

  ```
  fffffe0009b55024  blraa x8, x17        ; readReg32(map, reg, die)
  fffffe0009b55028  orr  w3, w0, #0x20000000
  fffffe0009b5504c  blraa x9, x17        ; writeReg32(map, reg, val|BIT29, die)
  ```

  **The BIT29 OR is value arithmetic on PS-register words, not address
  translation** — it sets an unnamed sticky flag (bit 29; Asahi's
  pmgr-pwrstate.c names bits 31/28/27-24/19-16/12/11/10/9-8/7-4/3-0 but not
  29–30) on the ten listed PS words before the requested write. **None of the
  ten is a map113 register**, so a plain map113 write takes the direct path —
  there is no lock dance, mailbox doorbell, or handshake on the DVFS_CMD/
  DVFS_ON window itself.
- Special cases inside writeReg32: `map0 +0x18014` (0x9b55230, the captured
  gate register — read, compare against 0xf, write value, then write 0xf/0x0
  with die XOR 1 via +0xd30, plus event records via +0xd38 with
  (0x10, 0, 0x2ee00, die)); `map0 +0x1e8` (0x9b55404 — masks the value with
  `#0xfffffbff`, i.e. clears bit 10 `DEV_DISABLE`, and does the same
  PS-target dance); `map2 +0xc00` with `die != 0` → 0x9b56368 (per-die GPU/AFR
  RMW). The die selector enters as `w4`/`x19` everywhere.
- The **address bridge** (+0x2_00000000) that turns raw ADT 0x200004000 into
  the mapped 0x400004000 comes from the `/arm-io` bus ranges, applied by
  iBoot when it builds IODeviceMemory — visible in the capture's ioreg
  (IODeviceMemory[113] = 0x400004000) and reproduced by m1n1/Asahi for every
  other window. It is not something Linux must emulate per-write.

## 6. The exact macOS sequence (live 25G83 capture, 42 map113 writes)

From `/tmp/levers7-raw/ane-perfstate.out` (t in µs, per-burst):

```
1. writeReg32(map113, 0x2000, 0x1, 0)              # DVFS_ON = 1
2. writeReg32(map113, 0x0a00, 0x80000000, 0)       # CMD: token, state 0→0
3. ... per transition, ~4.6–4.7 ms apart:
   writeReg32(map113, 0x0a00, 0x80000000|(prev<<4)|new, 0)
   tokens seen: 0x01,0x02,0x05 (0→n), 0x10,0x12,0x30 (n→0),
                0x23, 0x35,0x45, 0x43, 0x54,0x50   # states 0..5
4. writeReg32(map113, 0x0a00, 0x80000000, 0)       # idle token
5. writeReg32(map113, 0x2000, 0x0, 0)              # DVFS_ON = 0
```

The map0/map2 side of each burst (capture targets 0x1e8 = ps_afr ×430,
0x268/0x2c8 = ps_ane_sys/_cpu, 0x1800c/0x18014 gates, map2 0x1f8/0x3c0 =
ps_gfx, 0x64000 power gate) is the PMGR PS ladder that accompanies the
DVFS command stream; the clock/voltage transition itself is performed by the
PMP consuming the 0x400004000 window.

## 7. Linux-side plan (staged; each phase independently abortable)

**Phase 0 — recon (read-only, no PMP start):**
From a quiesce context on jw16 (llm-inference stopped, netconsole up, GPU lock
held), map 0x28e700000 (1 MiB) + 0x28ec00000 (0x4000, ASC wrap) with a tiny
scoped driver (the `pmp_ane_probe` pattern; never /dev/mem) and:
(a) dump PMP SRAM head — look for a firmware image (valid ARM64 code /
boot-args table at the `+0x22c` pointer); (b) read ASC `CPU_CONTROL` (0x44)
and the RVBAR lane. Discriminates "iBoot left the firmware parked in SRAM"
(Rust driver works as written) from "SRAM is empty" (we must extract the PMP
firmware from ApplePMPFirmware.kext on macOS/IPSW first — blob not present
anywhere on PVE today).

**Phase 1 — boot the PMP under Linux:**
Enable in the jw16 DTB (staged-boot machinery, `set -euo pipefail` + byte
verification + automatic Linux fallback): `pmp@28e700000` status=okay,
`pmp_mbox@28ec08000`, pmp DART, `ps_pmp` domain. Ensure `CONFIG_APPLE_PMP=y`
(jw16 kernel config must be checked; the driver is in-tree). Add the
`apple,tunable-*` IOREG payloads the PMP asks for during REGISTER_IOREG —
source: extract from macOS (ApplePMPFirmware/ApplePMP kext resources or a
live macOS boot log of the PMP's channel registration). Boot and gate the
result on observable proof: RTKit HELLO, syscall churn in dmesg, and the
report SRAM (`pmp-ane-sys`) `status` starting to ack. If the PMP faults or
rails misbehave: reboot clears everything (PMP state is not persistent).

**Phase 2 — replicate the DVFS command stream (only after Phase 1 proves out):**
Scoped driver maps 0x400004000 (0x4000) and, with the ANE idle, writes exactly
the captured sequence: `0x2000 ← 1`; `0xa00 ← 0x80000000`; step one rung at a
time `0xa00 ← 0x80000000|(prev<<4)|new` with ≥5 ms spacing (macOS uses
~4.6 ms); idle token; `0x2000 ← 0` at close. Verification per step:
read-back/ack behaviour changes (non-zero), `PLL_ANE0` block (0x28e070000,
perf-regs[8]) reflects the new rate, encoder slope moves (target: the
431–438 ms → macOS 140.86 ms gap closes at the matching state), outputs remain
bit-exact against the golden capture, and the PMP report SRAM stays healthy.
Never write a state jump larger than one rung per command; never write tokens
while the ANE is mid-submit until Phase 2 is proven idle-safe.

**Expected outcome:** state 5 (1500 MHz / 909 mV) is what macOS runs the
capture at; if Linux currently idles near state 0–2 (the 3.06× encoder gap is
consistent with a mid-ladder point), Phase 2 closes most of the T6001 ANE
clock gap. Exact per-state wins to be measured, not assumed.

## 8. Safety assessment

- **Writing map113 while the PMP is dead is a proven no-op** (A/B: 431–434 vs
  436–439 ms, both regs read 0 after write — f026da17). It does not wedge the
  ANE and is not in the engine-window-read class that hard-reset the M2. It is
  simply useless without the receiver.
- **Booting the PMP is SoC-wide power infrastructure**, not a bounded ANE
  experiment (the m1max-ane-clock receipt's standing verdict). The PMP
  sequences DCS/FAB/ANE/SOC/DISP/AVEMSR voltage rails; a missing IOREG table
  (the known Linux gap) means the firmware runs without the rail metadata
  macOS gives it. Bounded by: staged boot with automatic fallback, quiesce
  window, netconsole attached, no serving load, and full reversibility (a
  reboot restores the stock disabled-PMP state; nothing in the boot image is
  modified — the DTB overlay lives in the ESP like the existing ANE DT work).
- **Direct PLL_ANE0 writes without voltage sequencing remain forbidden** (the
  out-of-spec class rejected in ane-dvfs §5). The PMP route is the only
  voltage-correct path to 1500 MHz.
- The ANE engine window, its DARTs, and CoreSight are untouched by every phase.

## 9. T8103 and T6021 applicability

- **T8103 (jwm1): NO.** The t8103 DTS has no `pmp` node and no
  0x400000000-band window at all (grep: zero hits); M1 has no PMP-served DVFS
  command interface. The M1 ANE runs the same op-point under macOS and Linux
  (iBoot preload leaves it identical), and there is no M1 ANE clock gap to
  close. Domain 8 exists on T8103's PMGR, but its apply set is the local
  pmgr islands only.
- **T6021 (jw14m2): SAME SUBSYSTEM, DIFFERENT SURFACE.** The PMP node,
  nub, `dvfs-domain` table (AFR with 6 levels), and macOS kext stack are
  present; the PMP is likewise not started under Linux today. But the T6021
  pmgr reg[] has no 0x400004000 window — the equivalent device-DVFS command
  surface has not been located/captured on T6021 (candidates: pmgr_gfx
  0x404e80000, whose perf-regs[9] block at +0x10000 is T6021-only, or a
  window inside the PMP's 0x400000000 PIO range). For T6021 the certified
  perf lever remains the ANE-firmware route (staged fw + RTKit + CSNE_CMD
  perf-mode per the t6021 bring-up record); a PMP-enabled boot would
  additionally be required for any voltage-stepped ANE DVFS there. Note also
  the T6021 ANE op-point ladder was not found in the j414c ADT states tables
  checked (states8 is not a frequency table there).

## 10. Artifacts

- This receipt (ADT parses reproduced with `~/src/m2-m1n1/m1n1/adt.py`;
  scripts inline in the session log).
- Live ADT: `~/.cache/ane-live-adt-jw16mbp1-20260913T1789287036951/adt.bin`;
  T6021 ADT: `/tmp/j414c.adt.raw` (both /tmp-class storage — worth copying
  into a receipt if reused).
- Raw capture: `/tmp/levers7-raw/ane-perfstate.out` (also committed in
  receipts/2026-09-25-t6001-perfstate-capture on branch
  agent/m1-ane-clock-macos).
- 22G74 T6001 stub KC: `/var/tmp/jw16-kc/kernelcache.release.mac13j.macho`
  (sha256 prefix 35695639); prior disassembly:
  `/var/tmp/jw16-kc/t6001-pmgr.asm`.
