# macOS ANE working-state engine dump vs Linux (M2 Max, 2026-09-25)

With the ANE firmware running under macOS, the ANE RVBAR reads
0x0000010000000001. That is the same locked value Linux reads, without the
0x81 mode bits, so the missing mode bits are not what stops the Linux start.
CPU_STATUS reads 0x20 and 0x28 while the macOS firmware runs, so 0x28 is not
a park signature. SCRATCH7 reads 0 in the working state. macOS leaves every
VENC rail off while it uses the ANE, and it leaves ane_sys_mpm off. Linux
raises both. Those two power differences are the Linux test.

## Capture

- Box: JW14M2 (T6021), macOS 27.0 26A428, SIP off. Boot 12:55:14 CDT.
- Kext: `com.warren.ANERegDump` UUID 3FBA77CF, binary sha 932d3b9b
  (omarchy-ane 14620db runtime-request build), approved by Joshua.
- Request: `ranges.txt` in this directory. The gate is ane_sys@260,
  ane_cpu@2e0 and ane_td/base/set1-4@4008-4030, all ACTUAL 0xf. The gate
  leaves out ane_sys_mpm@4000 because macOS never raises it (receipt
  2026-09-25-macos-ane-pstable). The request also adds the VENC ps words.
  `adt 1` was requested, but no ADT range landed (see Gaps).
- Script: `capture3.sh`. It takes an idle dump, starts the Parakeet encoder
  loop, waits until powermetrics shows nonzero ANE power, makes gated
  attempts until two pass, and ends with an after dump. Log:
  `capture-run.log`.
- Workload proof: the same encoder run reported placement ane 1346 / cpu 28
  (`encoder-placement.txt`).
- The two passes (load3 13:02:55 and load4 13:02:59) caught every gate word
  at ACTUAL 0xf: ane_sys and ane_cpu 0x1f0003ff, the compute islands 0x3ff.
  They fell in the encoder's model-load phase. The 500 ms powermetrics
  sample taken just before each read showed 0 mW. The steady 4.8 W reps ran
  13:03:05-13:04:26, and no engine read landed in that phase.
- The box stayed up throughout. The raw dumps are in private evidence
  (`2026-09-25-macos-ane-engine-dump/`), with hashes in `dump-SHA256SUMS`.
  `decoded.txt` holds the `decode_cap3.py` output for idle, load3, load4 and
  after. The full wrapper word lists are `load3-wrapper-nonzero.txt` and
  `load4-wrapper-nonzero.txt`.

## macOS working state vs Linux

Engine offsets are from 0x284000000. The Linux column comes from the lane
receipts named on each row.

| register | macOS working (load3 / load4) | Linux | source for Linux |
|---|---|---|---|
| RVBAR +0x1050000 | 0x0000010000000001 | 0x0000010000000001 | 2026-09-25-m2-handshake |
| CPU_CONTROL +0x1400044 | 0x00000010 (RUN) | 0x10 after release | 2026-09-25-m2-handshake |
| CPU_STATUS +0x1400048 | 0x20 / 0x28 | 0x2a, then 0x28 after RUN | 2026-09-25-m2-handshake |
| SCRATCH0-7 +0x1840048 | 0 0 0 0 0 0 **1** 0 | SCRATCH6=1 written by S1, SCRATCH7 stays 0 | 2026-09-25-m2-handshake |
| +0x1840068 / +0x184006c | 0 / **4** | not logged (READY poll only) | 2026-09-25-m2-handshake |
| mailbox A2I_CTRL +0x1408110 | **0x000a0001** | 0x00020001 | 2026-09-25-m2-handshake |
| mailbox I2A_CTRL +0x1408114 | **0x000a0001** | empty (not logged as a word) | 2026-09-25-m2-handshake |
| wrapper +0x1400040 | 0x000a0000 | not read | - |
| wrapper +0x1400a00..a14 | 0 x6 | 0xffffffff x6 written (IRQ unmask test) | 2026-09-25-m2-handshake |
| wrapper +0x1400b80..b94, +0xbfc | 0xffffffff | not read | - |
| DART enable (+0xc00) | stream 0 only, all three instances | stream 0 translate | 2026-09-23-m2-fwstart s9 |
| DART sid0 TCR / TTBR | 0x9 / 0x1004102d, same table on all three | TTBR 0x1000e055 equalized on all three | 2026-09-25-m2-handshake |
| DART sid15 | not enabled | TCR 0x9 + valid TTBR (earlier runs) | 2026-09-23-m2-fwstart s9 |
| dart0 PROTECT +0x200 | 0x6 | not logged here | - |
| DART ERROR +0x100 | dart0 0x10a00000 / 0x00a00000, dart1 0x00f00000, dart2 0x00700000; bit 31 clear | dart1 0x00f00000, bit 31 clear | 2026-09-23-m2-fwstart s9 |
| pmgr ane_sys_mpm@4000 | **0x00000300** | **0x000003ff** | 2026-09-23-m2-fwstart s9 |
| pmgr ane_sys@260, ane_cpu@2e0 | 0x1f0003ff | 0x1f0003ff | 2026-09-23-m2-fwstart s9 |
| pmgr td/base/set1-4 | 0x3ff | 0x3ff | 2026-09-23-m2-fwstart s9 |
| VENC_SYS 0x2902803e0 | **0x0f000300 (off)** in idle, load and after | **0x1f0003ff** after the rtclient raise | fw-debug b6-b8 dmesg |
| VENC_DMA, PIPE4/5, ME0/1 0x290288000-020 | **0x300 (off)** | raised to 0x3ff | 2026-09-23-m2-fwstart s9 |

The DART rows at sid1-15 of dart1 and dart2 read values that change between
load3 and load4 (for example TTBR 0x3fbffd7c, then 0x3fbff57c). Those are
not a live TCR/TTBR layout. Only sid0 is enabled. The wrapper words at
+0x4150 and above also change between the two samples and look like
SRAM contents.

## What this changes for Linux

1. **RVBAR is not the blocker.** macOS runs the firmware with the same locked
   latch and no mode bits.
2. **Leave ane_sys_mpm off.** omarchy-ane agent/t6021-macos-ps-form 265bb63
   (fw_start_mpm_off, default on) does this.
3. **Leave the VENC rails off.** The rtclient raises them by default
   (fw_start_venc_gates=1). The macOS form is fw_start_venc_gates=0.
4. **The mailbox control words differ in bit 19** (0x000a0001 on macOS vs
   0x00020001 on Linux). Bits 16 and 17 are FULL and EMPTY. What bit 19
   means is open.
5. SCRATCH7 is 0 in the running state, so a READY poll on SCRATCH7 can only
   see a transient value. +0x184006c reads 4 in the working state.

## Gaps

- No fw-text, fw-data or boot-args range landed, although the request set
  `adt 1`. The kext looks up `IODeviceTree:/arm-io` and then
  `childFromPath("ane0")`, and the live node is `ane0@84000000`. The lookup
  probably misses on the unit address [INFERENCE].
- No engine read landed during the 4.8 W reps. The two passes are
  model-load-phase states with the firmware running and all islands on.
- VENC was not sampled at 4.8 W. It read off in the idle, load3, load4 and
  after samples.

## Wrapper map (engine+0x1400000..+0x1414000, load3 vs load4)

Linux's fw_start sequence writes none of the stable words below. They are
pre-RUN candidates pending kext evidence (asked of M2PreRunRE).

| offset (wrapper) | value | note |
|---|---|---|
| +0x0 | 0x00000001 | stable |
| +0x8 | 0x12345678 | stable test-pattern-shaped word |
| +0x40 | 0x000a0000 | stable |
| +0x44 / +0x48 | 0x10 / 0x20->0x28 | CPU_CONTROL RUN / CPU_STATUS |
| +0x444 | 0x00000010 | second CPU_CONTROL-shaped word, RUN bit 4 |
| +0xa00..+0xa14 | 0 | Linux's IRQ-unmask test wrote 0xffffffff here |
| +0xb80..+0xb94, +0xbfc | 0xffffffff | stable; candidate mask/enable bank |
| +0x1008 | 0x1 at load3, 0 at load4 | transient |
| +0x4110..+0x4140 | 0x00020001 / 0x00000001 | mailbox-shaped CTRL block, no bit 19 |
| +0x8110..+0x811c | 0x000a0001 x2, 0x1 x2 | the ANE mailbox A2I/I2A CTRL |
| +0xc110, +0x10110 | 0x000a0001 | two more mailbox-shaped blocks |
| +0x481c..+0x497c (stride 0x20), +0x881c, +0x883c, +0xc81c, +0x1081c | 0x000a0000 | per-channel status words carrying bit 19 |
| +0x4150.., +0x8150.., +0xc150.., +0x10150.. | changes between samples | FIFO SRAM contents |

Bit 19 (0x80000) is set in every mailbox CTRL and per-channel status word
that macOS's driver polls, and absent from the +0x4110 block it does not
poll. That fits M2PreRunRE's decode of bit 19 as UNDERFLOW (a read of an
empty FIFO), a symptom of host reads rather than a configuration value.
