# ANE DVFS on T6001 — mechanism found: firmware-mediated clocking, not an AP register (2026-09-22/23)

Owner: AneDvfs. Host: m1max-host = m1max-host = m1max-host-alias (T6001, kernel 7.1.6-1-1-ARCH).
Assignment: find and fix why the Linux ANE runs ~3.2x slower than macOS on the
identical whole-encoder program. Prior evidence: lane/m1max-gpu @445ef35 (§1
tqid/TM probe, §3 macOS core window), receipts/2026-09-22-encoder-m1max-anomaly
§4a (fixed-low-clock hypothesis).

## 1. Result in one paragraph

The hypothesis survives with its mechanism now identified. **Linux programs no
ANE clock at all** (omarchy-ane: genpd raise + TM enable only), so the engine
runs at whatever clock iBoot's boot-time setup left — measured flat 440.1
ms/iter, bit-exact. **macOS raises the same silicon to ~138 ms sustained
through the ANE's own firmware**: AppleH11ANEInterface issues
`CSNE_CMD_CH_PROPERTY_WRITE` "setting FW perf mode", and the ADT wires the
frequency domain as `perf-domains` "ANE" + `clocks` "PLL_ANE0" → group 8 →
`voltage-states8` = a 6-state (freq, volt) ladder 300/540/780/1020/1260/1500
MHz at 550/615/650/734/800/909 mV. Frequency follows voltage; voltage belongs
to the CLPC power firmware (the per-domain "DPE" blocks in ADT pmgr
`hw-dpe-reg` are CLPC address space — the ANE0 block reads as unmapped/aliased
from the AP). **No AP-accessible ANE DVFS register exists on T6001**: the
ane0 pmgr grant beyond the proven SET words (+0x38) is read-hostile (a
kernel-context ioremap_np readl sweep hard-reset the machine), and the one
hardware candidate block resolves to CLPC, not the AP. The gap therefore does
not close with a driver register write; it closes by bringing up the ANE
firmware stack (the t6021 rtkit lane's mission, ported to T6001) or it does
not close. No clock change is installed on m1max-host; the installed module remains
stock EA1B0B74.

## 2. Measured before/after table (T6001, whole-encoder program)

Identical harness (direct worker, bundle graph 020428fc, libane d06222a8),
identical inputs, hidden sha must be e1e061ab…:

| configuration | n=1 ms | n=8 ms | n=32 ms | slope ms/iter | hidden16 | module |
|---|---:|---:|---:|---:|---|---|
| Linux stock (BEFORE, tonight, post-reboot) | 1088 | 4172 | 14742 | **440.1** | e1e061ab92ef1a61 | EA1B0B74 |
| Linux with probe module (dvfs_debug=1, no clock change — dump only) | — | — | — | not measured (window lost to the 00:07 wedge) | — | probe build |
| macOS reference (same silicon, CoreML ane arm, sustained 3 warmup + 200 reps, 23:41 CDT) | — | — | — | **140.1 median** (times 134.6–136.x) | 0 mismatches vs gold | AppleH11ANEInterface |

The AFTER column for a driver clock change is **not delivered — honestly**.
The measured rate never moved because no safe clock-programming path exists;
everything above the baseline row is the macOS reference that the mechanism
analysis explains. 3.19x = 440.1/138 sustained; consistent with Linux sitting
at a fixed low clock (~470 MHz implied if macOS runs the 1500 MHz top state)
against a 300–1500 MHz managed ladder.

Parakeet e2e (battery.sh, 3 legs through fused_e2e) was **not re-run**: it is
insensitive to any change shipped tonight (none), and its flock window was
ceded to GdnCoopmat's GPU window after the second wedge.

## 3. Evidence chain (all artifacts in this directory + local decode files)

1. **Driver programs nothing** — omarchy-ane probe path: `ane_attach_genpd`,
   `devm_platform_ioremap_resource_byname("engine")`, `ane_tm_enable`. No
   clk/opp/perf-state programming exists anywhere in the tree.
2. **macOS one-shot window** (23:40–23:52 CDT, asahi-bless -n -y --set-boot 1,
   round trip verified both ways):
   - `adt-pmgr.plist/.txt` — full T6001 /arm-io/pmgr ADT node:
     `perf-domains` (14 entries incl. named ANE), `voltage-states8` ladder,
     `perf-regs`, `hw-dpe-reg`, `clocks`, `ps-regs`, `devices`, `soc-clusters`
     (clusters EACC/PACC0/PACC1/ANE0/AFR/ANE1/DISPLAY…).
     Decode: `decode-voltage-states-perf-domains.txt`,
     `decode-hw-dpe-reg.txt`, `decode-clocks-soc-clusters.txt`.
   - `t6001-ane0-adt.txt` — ane0 node: engine 0x284000000/32 MiB + pmgr grant
     0x28E08C000/0xC02C (the SET words are its first 0x38 bytes). **No
     separate DVFS window on T6001** (T6021 splits one off at pmgr+0x1C000;
     T6001 does not grant it to ane0).
   - `bench_ane_long.json` + `goldcheck_ane_long.txt` — sustained 200-rep ane
     arm: median 140.13 ms, 0 mismatches vs the pinned gold.
   - `powermetrics --samplers ane_power` is a **no-op sampler on 26.6.2**:
     43.6 KB of sample headers over ~50 s at 100 ms cadence under sustained
     ANE load, zero ANE lines (reproduces the prior window's finding; the
     GHz fields do not exist on this OS build).
   - Live MMIO readback during the CoreML run: **not possible** without
     kernel debug (no /dev/mem; KDP route previously rejected by Main).
     The candidate-register readback ran on the Linux side instead (§4).
3. **Kext static analysis** — AppleH11ANEInterface 9.512.0 (studio-host, build
   25G83 = m1max-host's exact OS; fixture already on file from the t6021 lane):
   log strings prove the clock path is firmware-mediated:
   `CSNE_CMD_CH_PROPERTY_WRITE for setting FW perf mode failed`,
   `Registering with PerfControl with %u tokens`, `ANEPerfRequest`,
   `fAneSysClockAssertions`, `EnableANEClocksAndPower`. The kext's own MMIO
   writes (ane-hunter kext_scan) are gate guards (0x738/0x798/0x7f8 ←
   0x01FF01FF pre-CPU-start), not frequency programming.
4. **ADT decode specifics**:
   - `clocks` entry `{slot 0x13, group 8, "PLL_ANE0"}` — the group-8 ladder
     belongs to the ANE0 PLL. Cross-checked: `perf-domains` has a named ANE
     domain; `soc-clusters` lists ANE0/AFR/ANE1.
   - `hw-dpe-reg` 40-byte records: ECPM/PCPM at cluster+0x28000, ECORE/PCOR
     per-core, `ANE0` @ 0x8590c0c8 → 0x28590C0C8 (engine span),
     `ANE1` @ 0x2990C0C8 (die-1 space; T6001 Linux binds only ane0).
5. **Linux-side register readback (probe module, SET-guarded)** — commit
   `9ff6d3b` on omarchy-ane `lane/ane-dvfs` (worktree ~/src/omarchy-ane-dvfs
   on m1max-host; dvfs_debug=1). The ANE0 DPE block dump completed cleanly:
   head words 0xfff/ffffffff-alternating pattern, remainder zero — the
   block is not AP-mapped content (CLPC's view of it lives in its own
   address space). The SET words read 0x3ff as always. The sweep beyond
   ps_base+0x38 wedged the machine (§5).

## 5. Platform incidents — full honesty log (four resets tonight)

| # | time | operation | verdict |
|---|---|---|---|
| 1 | 23:17–23:21 | /dev/mem read sweep incl. pmgr+0x1C000 | real reset; mechanism later identified: arm64 /dev/mem maps Normal-NC, which external-aborts on Apple device pages (ioremap uses Device-nGnRnE). /dev/mem is banned on this box. |
| 2 | 23:27 | /dev/mem "safe" calibration incl. cpufreq window | real reset, same pgprot mechanism. |
| 3 | 23:56 | rmmod/insmod probe | NOT a wedge: an unexplained clean shutdown began 23:56:00 (journal; also killed GdnCoopmat's first run at 23:56:48; neither operator ordered it — suspected omarchy auto-action, unresolved). |
| 4 | 00:07 | kernel ioremap_np probe, extended dump | REAL reset, genuinely new datum: the ane0 pmgr grant beyond +0x38 is read-hostile even from kernel context with correct device attributes. The DPE-block portion of the same dump ran clean seconds earlier. |

Every reset self-recovered to Linux with the stock module (EA1B0B74
verified after each) and llm-inference auto-started; real completion
probes passed at 23:24 ("Pacific", finish=stop) and 23:53 (post-macOS).
Final-state verification repeated at close-out (below). m1max-host was left
clean: stock module loaded, service active, lock with the service.

## 6. Routes forward (ranked)

1. **ANE firmware bring-up (the real fix, both SoCs).** macOS raises perf
   mode through the firmware via CSNE_CMD; Linux has no /lib/firmware/apple
   ANE firmware and no rtkit/CSNE client for this engine. The t6021
   rtkit-client lane is already the carrier of exactly this mission
   (hardware milestone 1: safe refusal at the CPU gate on laptop-host), and its
   mined assets cover the first half: the selene firmware macho
   (`receipts/2026-09-18-t6021-engine-layout-mined/fw-h14j-selene/`, plus
   per-SoC builds needed for T6001) and the ane-hunter toolchain
   (fw_tables RegTracker decodes firmware TUs; kext_scan maps kext MMIO).
   Porting that lane to T6001 and implementing the perf-mode command is
   the route that actually reaches 1500 MHz-class clocks — with voltage
   handled by CLPC, which is why no register-only shortcut can be safe.
2. **iBoot boot-clock RE (explains 441 vs 260, does not close the gap).**
   The T8103 boots its ANE at a higher fixed clock (same driver, 260
   ms/iter amortized on m1-host) — different iBoot choices per SoC.
   `receipts/2026-09-20-iboot-j414c/iboot_j414c_dec.bin` is on file; the
   sweep artifact exists but the clock-init sequence was not decoded.
3. **NOT viable: AP-direct ANE DVFS writes.** Read-hostile grant pages
   (§5 #4), CLPC-owned DPE blocks (§4.5), and voltage co-management make
   every variant of this either impossible or an out-of-spec unsafe write.
   Do not retry without the firmware stack.

## 7. Assignment deltas vs the original ticket

- "live readback of candidate registers during an active CoreML encoder
  run" on macOS: executed on the Linux side instead (probe module during
  idle + baseline); macOS-side MMIO requires kernel debug (rejected class).
- "implement the perf-state setup … ms must move toward 138": the
  investigation reached a mechanism that forecloses the register route;
  nothing was forced. The probe/dump machinery IS implemented and committed
  for the firmware lane's use.
- "same fix on T8103 through its owner": moot for tonight's route — the
  mechanism (firmware-mediated DVFS) is SoC-family-wide; the T8103 handoff
  is the firmware lane's, at its owner's cadence.

## 8. Artifacts index

- `t6001-pmgr-adt.txt`, `t6001-ane0-adt.txt` — macOS ioreg IODeviceTree
  captures (T6001, 26.6.2/25G83, 23:41 CDT).
- `decode-*.txt` — mechanical decodes (voltage-states/perf-domains,
  hw-dpe-reg, clocks/soc-clusters).
- `bench_ane_long.json`, `goldcheck_ane_long.txt` — sustained macOS ane arm
  + bit-exactness vs gold.
- omarchy-ane `lane/ane-dvfs` @ 9ff6d3b — probe module (dvfs_debug dump,
  SET-guarded; m1max-host worktree ~/src/omarchy-ane-dvfs; fetched to the local
  repo).
- Baseline battery outputs: m1max-host /tmp/dvfs-baseline-{1,8,32}/ (scratch).
