# jwm1 (T8103) macOS window — ANE clock evidence + Qwen ANE denominator (2026-09-25)

Owner: AneClockM1. Host: jwm1 macOS 27.0 (26A428), MacBookPro17,1, reached on
its wired 2.5 GbE port (en12). Window ordered by Main while the M2 sat in macOS
(no hv run needed jwm1); M2FwStart-2 and Jwm1Parity5 notified before and after.

## 1. Reboot gate (jwm1 boot files live on btrfs)

- `grub.cfg` loads `/@/boot/vmlinuz-linux-asahi` from btrfs, so the full gate ran.
- `grub-fstest /dev/nvme0n1p5 cmp /@/boot/vmlinuz-linux-asahi /boot/vmlinuz-linux-asahi`
  rc=0 (35,834,368 B, byte-exact); negative control against the initramfs:
  `compare fail at offset 0.`
- ESP rescue pair `/boot/efi/grub-ane/` (kernel sha256 c9764582…, initramfs
  e388d633…, both equal to /boot) + `rescue-esp` entry in `/boot/grub/custom.cfg`
  (sourced by 41_custom).
- `asahi-bless -n --set-boot-macos -y`; `--get-boot` stayed `Omarchy`,
  `--next --get-boot` = `Macintosh HD`. m1n1 boot.bin sha256 41a39ac7….
- At commit time jwm1 is still in macOS and owned by Jwm1Parity5 (Main's
  order). The return to Omarchy is theirs; BootNext is consumed, so a plain
  reboot lands in Omarchy.

## 2. macOS encoder divisor (the 113 ms target)

`bin/encoder_bench` (mac-reference-bundle), pinned Parakeet encoder.mlpackage
(rev b650695c), `inputs/feat_f32.bin` + `mask_i32.bin`, units `ane`
(`.cpuAndNeuralEngine`):

| run | reps | median ms | min | max | placement |
|---|---:|---:|---:|---:|---|
| r1 (`encoder-bench-ane-r1.txt`) | 6 | **112.99** | 112.75 | 113.23 | ane 1345, cpu 29 |
| r2 (`encoder-bench-ane-r2.txt`, under powermetrics) | 4 | 116.00 | 113.00 | 121.29 | ane 1345, cpu 29 |

hidden_count 240000, mask_sum 375 both runs. Linux certified whole-submit on
the same laptop: 141.4 ms (receipts/2026-09-22-encoder-whole-program), i.e.
Linux/macOS = 1.25.

## 3. ANE clock observability on macOS

- `powermetrics -s ane_power --show-extra-power-info -i 200` during r2:
  1405 lines, sample headers only, zero ANE power/frequency lines
  (`powermetrics-ane_power-during-encoder.txt`). The sampler is listed
  ("dedicated rail ane power and frequency info") but emits nothing on 26A428.
  `-s ane` is rejected (`unrecognized sampler`).
- ioreg has no live ANE frequency property (`ANEFreq|ane-freq|PLL_ANE|active-freq|perf-level`
  matched nothing outside the pmgr ADT tables).
- `H11ANEIn` (AppleH11ANEInterface): `IOPowerManagement` CurrentPowerState 0,
  MaxPowerState 1 when idle; `ANEDevicePropertyTypeANEArchitectureTypeStr` h13g,
  16 cores (`t8103-ane-node-ioreg.txt`).

## 4. T8103 pmgr ADT: ANE clock tables (`decode-t8103-ane-clock.txt`)

- `perf-domains` idx 8 = `ANE` (a=0, b=0, y=0), unlike SOC/DCS/DISP (a=4, y=300).
- `clocks`: `PLL_ANE` record prefix `48 01 03 13` (slot 0x13, same slot as
  T6001 `PLL_ANE0`).
- `voltage-states8`: 12 frequencies 432–1464 MHz, every second word 0xffffffff
  (no voltage in the table; T6001's group-8 ladder carried mV).
- `ane-acg-hack` = 1, `ane-dpe` = 1.
- ANE node: `clock-gates` 0x12e, `power-gates` 0x12e, `clock-ids`
  0x140/0x141/0x142, `pre-loaded` 1, `ane-type` 0x40.

None of this says which ladder step macOS or Linux runs at.

## 5. Kext PMU bit (closed)

AppleH11ANEInterface 9.512.0 `ANEHWDevice::start` maps PA 0x23b110000 size
0x4000 for chip classes 0x40/0x70 (`0xfffffe000933600c`). Its only write into
that window (`0xfffffe0009349d78`): if device+0x3a98 == 0, clear mask 0x8 at
+0x100 (const pool `__TEXT,__const` file 0x44188: offset 0x100, mask 0x8). The
T8103 path never stores +0x3a98, so the clear runs. On jwm1 Linux in the
141.5 ms state, 0x23b110100 read 0x0 (one logged readl, Main-authorized; also
+0x0/+0x20/+0x50/+0xc0/+0xc8 = 0, SET+0 = 0x3ff). Bit 0x8 is already clear on
Linux: not the clock difference. No write was made.

## 6. Reload datapoint (AneKillCleanup)

Clean rmmod/insmod of omarchy-ane 686ccd6 (DART PTE lifetime fix, no clock
writes) restored the Parakeet engine to exec_ms 141.548 (golden match,
submissions 1). The 200–267 ms state followed one reload, not every genpd
power-on.

## 7. Qwen3.8-2B macOS ANE denominator

Run `qwen-ane-20260925T114615-full` (raw output in `qwen-ane-full/`). Contract
`backends.macos_ane`: 3 warmup corpus passes, 10 reps x 10 prompts, 32 new
tokens, greedy, 512-token pure prefill. ANEForge worktree `~/src/ane-af-split-wt`
at 2ea941c (QwenAneRef-2's fix tip; 0a9ead5 is its merge on the fork main).
GGUF sha256 4aa0fb13… and corpus 9299a3b2… verified by the harness.

Harness `qwen-ane-full/run_qwen_ane_ref.full.py` (sha256 bbb790ba…) =
QwenAneRef-2's `run_qwen_ane_ref.maxlen50.py` (ane-linux-experiments bc7aa74:
decode at max_len 50; prefill leg through the staged decode path,
`batched_prefill=False`, max_len 513, because 2ea941c has no batched
`gated_deltanet` prefill mixer) plus two changes: the brew llama-tokenize
regex parse (that copy's `split()` fails on `[a, b]` output), and a per-rep
`<out>.partial` checkpoint so a late-leg crash keeps the reps.
Tokenizer: homebrew llama.cpp `llama-tokenize` (macstudio binary + dylibs in
`/var/tmp/llama-bin`, PATH wrapper). It reproduces chunk_00 prompt ids 10/10.
Python: uv cpython 3.12.14 venv, numpy 2.5.3, gguf 0.19.0.

Correctness: all 100 rep records and the cold start equal the frozen
reference `chunk_00.json` (sha256 8269c36b…) token for token, 32/32
(`qwen-ane-full/tokencheck-vs-chunk_00.txt`).

`ordered_records_sha256` **89f3fd9d3b3f94901538488853caa90b45f3546373498c158036b4a56a5ce2ba**;
json sha256 410dc4f7…; peak RSS 7,935,852,544 B; wall 1162.6 s.

| metric | median | 95% CI of median (bootstrap, 10k, n=100) | mean | stdev | min | max |
|---|---:|---|---:|---:|---:|---:|
| decode tok/s | **5.625** | 5.505–5.720 | 5.609 | 0.423 | 4.37 | 6.84 |
| TTFT s | **1.189** | 1.042–1.290 | 1.221 | 0.366 | 0.742 | 2.830 |
| TTFT prompt tok/s | 12.48 | 10.41–13.30 | 11.72 | 2.44 | 3.89 | 15.28 |
| decode s (31 tokens) | 5.512 | 5.413–5.626 | 5.559 | 0.430 | 4.530 | 7.090 |
| e2e s | **6.718** | 6.651–6.870 | 6.780 | 0.561 | 5.736 | 8.428 |

Pure prefill, 512 tokens, 3 walls (39.41 / 43.62 / 44.88 s): median
**11.74 tok/s** (per-wall 12.99 / 11.74 / 11.41). n=3, so no CI is given.
Cold start (first generate, compile included): wall 47.69 s, TTFT 43.09 s.
Model load 9.94 s.

Per-pass median decode tok/s drifts down across the run: 5.83, 5.88, 5.82,
5.77, 5.71, 5.42, 5.38, 5.58, 5.25, 5.41. This is disclosed, not explained.
Joshua was logged in to the GUI session during this window.

Failed attempts in this window (no json, kept on PVE at
`/var/tmp/qwen-ane-out-backup/qwen-ane-out/`): 105302 died on a broken SSH
stdout pipe; 110308 died in pure_prefill because the cellar llama-tokenize was
a chunk_00 lookup shim; 112040 died in pure_prefill with
`KeyError: 'gated_deltanet'` (unpatched harness `m.prefill`); 114433-noprefill
was stopped by Main's order to keep prefill.

## 8. ANE perf-state register: decode and the macOS perf-state path

Correction: the first version of this section (87f86ab) named PA 0x23d2b4140
as the ANE perf word. That address was inferred, not decoded, and is wrong.
The probe built on it (omarchy-ane 581561f) was removed in 38beae6 before
any run.

`decode-t8103-ane-perfstate.txt` decodes the jwm1 macOS ioreg pmgr node with
m1n1's structs (`m1n1/adt.py`: `PMGRPerfRegs`, `PMGRDevices`, `PMGRClocks`,
`PMGRPSRegs`):

- `perf-regs` has 4 entries. `perf-regs[1]` = pmgr `reg[0]` (0x23b700000) +
  0x34000 = **0x23b734000**, size 0x100.
- `devices[99]` (byte 4752) `ANE_SYS`: flags 0xa2 (perf bit set),
  perf block 1, perf idx 0x31.
- `clocks` (byte 432) `PLL_ANE`: perf block 1, perf idx 0x48.
- `perf-domains` byte 1 is not a perf-regs index. It takes 4/1/4/1/0/4, and
  perf-regs only has 0–3.

So the ANE's perf entries point into `perf-regs[1]`. That block is the
T8103 twin of T6001 `perf-regs[1]` (reg[0]+0x2d000 = 0x28e0ad000), which the
2026-09-23 m1max-ane-clock receipt classed as the forbidden region next to
the read that hard-reset the M1 Max. The T6001 reset address was also inside
the ADT's pmgr range, so being inside that range does not make an address
safe. m1n1 `m1n1/hw/pmgr.py` models no register at reg[0]+0x34000, and no
Asahi driver touches it. The meaning of perf idx 0x31/0x48 inside that block
has no public source.

What macOS does (`t6020-setPerfState-dispatch.asm.txt`, full body in
`t6020-setPerfState-full.asm.txt`): in the macOS 13.5 kernelcache
(`kernelcache.release.mac14j`, T6021, sha256 9615a486…),
`AppleT6020PMGR::setPerfState(PerfDomainID, PerfState, bool, UInt32)` is
0xfffffe0009b7ef14–0xfffffe0009b7f684. It dispatches on the domain ID:

- IDs 2, 5 and 13 reach the write path. It writes the cluster command word at
  block + 0xe20020 as `(old & ~0x1f) | BIT(25) | (state & 0x1f)`. That is
  Asahi's CPU-cluster DVFS command (`drivers/cpufreq/apple-soc-cpufreq.c:25-31`:
  CMD 0x20, SET bit 25, PS1 bits 4:0).
- IDs 1, 3 and 4, and every ID other than 2, 5 or 13, branch to assert panic
  stubs (0x…83780, 0x…837c4, 0x…83808).

The ANE's perf-domain index (8) is not accepted, and neither is 9. On M2 the
host's only perf-state entry point therefore has no ANE path, and the host
never sets the ANE clock through pmgr. That fits the ANE firmware setting
its own operating point after `CH_PROPERTY_WRITE` "FW PERF MODE". The T8103
kernelcache, which is on jwm1's ESP (`asahi/kernelcache.release.mac13g`), not
on PVE.

## 9. ANE perf group PA resolved from the ADT (no device access)

The `PLL_ANE` clocks row is bytes `48 01 03 13`: slot 0x48, block byte 0x03,
id 0x13. Block 0x03 is `perf-regs[3]`: pmgr `reg[0]` + 0x78000, size 0xa.
The pmgr node's own `IODeviceMemory[0]` is PA 0x23b700000 (length 0x8c000),
so the ANE perf group is PA **0x23b778000**, 10 bytes
(0x23b778000–0x23b778009), inside a range the ADT lists for pmgr.

This is a third object, distinct from the retracted 0x23d2b4140 (inference,
removed in 38beae6 before any run) and from the ANE_SYS device row's
perf block 1 (0x23b734000, unsourced layout, no probe).

Kernelcache side (mac13g, sha256 861adca1…): `ApplePMGRNub::requestPerfState`
(0xfffffe000987b38c) maps enum 2 to internal domain 8 (ANE) and tail-calls
`ApplePMGR::_handlePerfStateRequest` (0xfffffe000986fb08), which accepts
domains 8 and 14 only. The apply routine (0xfffffe000986e7bc) writes an
8-bit state `(old & ~0xf) | (new & 0xf)` through the device register
accessor. No kext statically imports `requestPerfState`; H11ANEIn reaches
perf control through its token path (`notifyPerfController`
0xfffffe0009485234, `submitWorkToPerfController` 0xfffffe0009494190, via
`IOPerfControlClient` workBegin/workSubmit), and AppleT8103CLPCv3 owns the
PMGR perf imports (`aneWorkBegin` 0xfffffe0009af2af0, `aneWorkSubmit`
0xfffffe0009af2138 compute the state from submitted work). The accessor
base is built at ApplePMGR start from `perf-regs`, so the static PA is not
independently confirmed.

Next, Main's order: (b) dtrace/fbt first. `ane-perfstate.d` probes
`_handlePerfStateRequest` and the apply routine entry/return, logging
domain, state and x1 during an encoder run. It runs in the next jwm1 macOS
window (after the M2 is up in Linux and the catcher stands down;
coordinate with Jwm1Parity6 and M2FwStart-2). If dtrace shows macOS writing
0x23b778000, (a) follows as a read-then-write probe with that exact value.
No Linux read of pmgr reg[0] until then: jwm1 hosts the armed M2 catcher,
and a hang would cost the M2 recovery.
