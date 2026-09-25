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


`decode-t8103-ane-perfstate.txt`, from the same ioreg plist.

- `perf-regs` is 4 records of 16 bytes (`reg` index, offset, size, unk), the
  same struct as m1n1 `PMGRPerfRegs` (`m1n1/adt.py`).
- `perf-domains` record 8 (byte offset 112) is `ANE`: byte 1 = perf block 0,
  byte 3 = voltage group 8. Block 0 is `perf-regs[0]`: pmgr `reg[1]`
  (0x23d280000, size 0x74000) + 0x34000 = PA **0x23d2b4000**, size 0x100.
  That span is inside the range the ADT lists for pmgr. It is not the
  unmapped region that reset the M1 Max.
- m1n1 `dump_pmgr.py` places a clock at `perf_regs[block].reg + 0x100 +
  perf_idx * 0x10`. The ANE clock entry in the devices table is perf index 4
  of block 0, so the word is PA **0x23d2b4140**.
- Asahi `drivers/soc/apple/apple-pmgr-misc.c` drives the same register shape:
  desired state in bits 3:0, granted state read back in bits 7:4. The ANE
  ladder (`voltage-states8`) has 12 steps, so step 11 is 1464 MHz.

Probe: omarchy-ane `agent/ane-clock-m1` `ane/h13/ane_perfstate_probe.c`.
Default is one read. `request=11` writes the desired field once, waits for
the granted field, and restores the saved word on unload. Not run yet:
jwm1 is owned by Jwm1Parity5.
