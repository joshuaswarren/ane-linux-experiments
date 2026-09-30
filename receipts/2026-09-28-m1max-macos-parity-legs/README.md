# 2026-09-28 — M1 Max (T6001) macOS legs paired with the Linux sweep

Host: m1max-host, MacBookPro18,2 (M1 Max 16"), macOS 26.6.2 (25G83), AC power,
`pmset powermode 0` (automatic), thermal pressure Nominal in every powermetrics
sample of the GPU cells. One grouped window, 2026-09-28 22:28Z–23:41Z
(one-shot `asahi-bless -n --set-boot-macos`, plain reboot back to Linux; ESP
marker `m1n1/boot.bin` sha256 `b1bb1eec…` unchanged before/after).

Comparison is jw16-macOS vs jw16-Linux only. Linux cells: 2026-09-28,
`mlx-omarchy 0.32.3.dev…+ccfb97fb1` on Honeykrisp. macOS cells: upstream `mlx 0.32.2`,
`mlx-lm 0.31.3` on Metal (runtime version differs, unavoidable). Same bench
script (max_tokens=new_tokens fix verified by grep and by every decode pass
producing exactly N tokens), same corpus (sha `9299a3b2…`), same model snapshot
`0867d98b` (safetensors sha `b0d5de68…`), prompt 1, n=5, warmup 1, greedy.

## Qwen3.8-2B GPU (paired)

| cell | macOS median (range) | Linux median | Linux/macOS |
|---|---:|---:|---:|
| decode 64 tok | 180.01 (179.34–180.23) tok/s | 80.54 | 0.447 |
| decode 128 tok | 179.28 (179.22–179.50) | 79.86 | 0.445 |
| decode 256 tok | 178.28 (178.15–178.47) | 78.31 | 0.439 |
| decode 512 tok | 177.12 (177.03–177.19) | 76.05 | 0.429 |
| prefill 512 tok | 1327.16 (1324.71–1340.73) | 748.69 | 0.564 |
| prefill 1024 tok | 1355.77 (1355.36–1359.66) | 833.54 | 0.615 |
| prefill 2048 tok | 1379.63 (1379.08–1379.89) | 862.17 | 0.625 |

All seven are losses against the pass rule (>=1.00x); run-to-run spread is <1%.

## Window 5 (2026-09-29) — prefill protocol parity, both arms, same window

One macOS boot, 2026-09-29 19:02:36Z–19:13Z, AC power, `powermode 0`, no thermal
warning in the pre/post `pmset -g therm` samples; cells ran 19:08:35–19:11:00Z.
macOS venv `mlx 0.32.2` / `mlx-lm 0.31.3` with the SAME vendored
`mlx-lm-last-logits.patch` as jw16 Linux (`sha256 6fb1685c…`, applied on-box,
backup `qwen3_5.py.pre-lastlogits` kept). `MLX_OMARCHY_FULL_LOGITS=1` is the
full-logits control arm in the same window; its three medians reproduce the
window-4 stock cells within 0.1% (1327.99/1355.94/1379.13 vs 1327.16/1355.77/
1379.63). Linux pairs are PrefillGap3 W2 (same-boot base/cand, n=5, vec2 ICD +
last-logits patch). Records gates: ordered_records_sha256 `100a61b62470` in ALL
30 pf runs of BOTH arms — token identity holds across Metal and Honeykrisp for
the prefill protocol.

### Prefill (n=5 per cell, prompt 1, warmup 1, greedy)

| cell | macOS last-logits (range) | Linux last-logits | L/M | macOS full-logits (range) | Linux full-logits | L/M |
|---|---:|---:|---:|---:|---:|---:|
| prefill 512 | 1742.68 (1739.05–1748.15) | 1089.55 | 0.625 | 1327.99 (1324.74–1336.45) | 894.42 | 0.674 |
| prefill 1024 | 1793.60 (1793.15–1804.40) | 1234.30 | 0.688 | 1355.94 (1355.63–1357.21) | 988.93 | 0.729 |
| prefill 2048 | 1826.74 (1826.47–1827.22) | 1307.31 | 0.716 | 1379.13 (1371.97–1380.02) | 1032.61 | 0.749 |

The last-logits lever is now measured on BOTH OSes: macOS gains +31.2/+32.3/+32.5%
over its own stock protocol (Main's 2026-09-29 unmeasured estimate ~1.7k at 2048
is confirmed at 1826.74). Like-for-like, Linux is at 0.625/0.688/0.716 of macOS —
the honest prefill gap under the current serving protocol; reporting only the
full-logits arms (0.674/0.729/0.749) would understate it.

### Decode baseline, fresh same window (macOS patched venv)

| cell | macOS median (range) | tok identity vs Linux | Linux median (2026-09-28 sweep) | L/M |
|---|---:|---|---:|---:|
| decode 64 | 179.72 (179.49–180.41) | MATCH `c84b3e7af640` | 80.54 | 0.448 |
| decode 128 | 179.08 (178.80–179.51) | DIFFERS macOS `a6199c8c2b21` vs Linux `07c515e0338b` | 79.86 | 0.446 |
| decode 256 | 178.72 (178.60–179.38) | DIFFERS `d1326cc0e4a4` vs `c6aabbf0a51d` | 78.31 | 0.438 |
| decode 512 | 177.02 (176.75–177.14) | DIFFERS `7c26830d3b35` vs `5c120987f0e5` | 76.05 | 0.430 |

Every pass generated exactly N tokens (no EOS truncation); at 128+ tokens the
greedy stream diverges between Metal and Honeykrisp numerics (expected-class,
kernel-flags contract; the 64-token and all prefill records still match).

### Item B in the same window (eos staged-firmware dump) — NOT captured

`ANERegDump` first-ever load on jw16's macOS was refused: "Extension with
identifiers com.apple.nke.rvi,com.warren.ANERegDump not approved to load.
Please approve using System Settings." (kmutil.err retained). No approval click
or extra reboot was performed, per the one-window ruling, so the live eos
DATA/patchbay dump has NO hashes from this window. Captured instead: csrutil
disabled; Xcode present; kext REBUILT on-box (`fef35e2c…`, differs from the
frozen T6021 binary `932d3b9b…`) and staged in `/Library/Extensions` +
`~/jw16-macos-window/w5/` with `ranges5-t6001.txt` (T6001 carveouts from the
launch-sink2 boot log: TEXT `0x10000a5c000`/0xf4000, DATA `0x10001684000`/
0x5f8000, PS `0x28e080000`/0xc02c), an `aneprobe` rank-3 CoreML burst harness
(11188 preds/3 s smoke-tested) and `aneregdump`. Next window needs only the
System Settings Allow (+its reboot) and `bash macos-window5.sh`.
ADT evidence captured read-only: `ane0` segment-ranges u64 stream
[0x10000a5c000, 0x0, 0x10000a5c000, 0x3000f4000, 0x10001684000, 0xf4000,
0x1f0000f4000, 0x5f8000] — confirms the launch-sink2 surfaces from the live ADT;
ANE device `h13g`, 16 cores, ANEVersion 96; `ane_power` sampler again empty.

## Parakeet whole encoder (paired)

CoreML, corrected harness (`MLModelConfiguration` applied at load, `MLComputePlan`
placement), 3 warmups + 10 reps: `ane` 138.18 ms median (134.10–141.72),
placement ane 1341 / cpu 33, bit-exact vs Linux gold (0/240000 mismatches);
`all` 145.61 ms (ane 1334 / cpu 28 / gpu 12, bit-exact); `cpu` 205.07 ms.
Linux whole-encoder hold9 median 441.19 ms (bit-exact) => **3.19x slower on
Linux**. Prior macOS reference on this machine: 138–140 ms (2026-09-22).

## Parakeet end to end (macOS only in this receipt)

Golden fixture (10.435 s): `ane`, `gpu`, `all` arms match the pinned golden
transcript (104 tokens); `cpu` differs (expected). ANE arm: encoder 0.146 s
median, RTFx 39.5 (inference ~0.26 s = mel 0.016 + encoder 0.142 + decode 0.103).
The paired Linux re-run is not part of this window.

## Qwen3.8-2B ANE reference (macOS ANEForge, contract `macos_ane`)

3 warmup passes + 10 reps x 10 prompts, 32 new tokens, greedy, host fp32 lm_head:
decode 6.76 tok/s median (6.17–7.47, n=100), TTFT 12.36 tok/s, e2e 5.67 s median,
peak RSS 13.19 GB, ordered_records_sha256 `89f3fd9d…`. The 512-token pure-prefill
leg of the bundle crashed (`KeyError: 'gated_deltanet'` in ANEForge prefill mixers,
no GatedDeltaNet prefill path) and was disabled; a first full run that hit this
crash before writing JSON was discarded and re-run (both logs retained privately).

## Not measured / limits

- ANE clock: `powermetrics --samplers ane_power` records no ANE power on this OS
  build, so the macOS ANE clock is not directly observed here (ladder analysis in
  `receipts/2026-09-22-ane-dvfs`).
- Linux Parakeet e2e and Linux Qwen ANE reference: see the paired sections below.

## Parakeet beyond the golden fixture (Linux vs macOS, same laptop)

11-clip corpus (1.6 s to 32.4 s, including one >30 s concatenation), macOS window 3
`bin/parakeet` CoreML ane arm vs Linux `e2e_free` (whole-encoder ANE + mel + host-loop TDT).
Functional: transcripts identical on 9/11 clips; the 2 mismatches differ only in the
junk tail after speech ends (macOS ane and gpu arms disagree with each other there on
8/11 clips); mean WER Linux vs macOS 0.76%. **Functional parity: PASS.**
Performance (median warm): macOS inference 0.185-0.407 s vs Linux 0.641-1.430 s,
per-clip 2.7x-4.5x slower. 10.4 s fixture split: encoder 441 vs 142 ms (ANE firmware
perf mode never sent on Linux), TDT ~250 vs 103 ms (per-emission submit round trips),
mel 40 vs 16 ms. **Performance parity: FAIL.**

## Window 6 (2026-09-30) — Parakeet chain TDT certified e2e (paired)

The device-chain TDT (mlx-omarchy `881c09813`: tree-reduce control kernel + chains1
fusion, 5 dispatches/slot) certified against the host loop in ONE gpuwin window on
jw16: 11-clip corpus + 10.4 s golden fixture, 3 interleaved reps per arm, both arms.
Transcripts: fixture 104 tokens both arms, identical to the pinned text; 11/11 clips
chain == host token-identical; 11/11 == the certified 09-29 corpus transcripts;
9/11 exact vs macOS window 3 ane with exactly the same two junk-tail mismatches
(clip04, clip07), mean WER 0.76%. `--tdt-mode chain` is now the e2e contract default
(`e2e_free.py`), host kept as `--tdt-mode host`.

Paired per-clip, median warm, ms (Linux = chain arm; macOS = window 3 ane arm,
median of 3 reps; `tdt` vs macOS `decode`, `total` vs macOS `inference`):

| clip | sec | mel L/M | encoder L/M | tdt L/M | total L/M | L/M total |
|---|---|---:|---:|---:|---:|---:|
| clip00 | 1.64 | 31.8/15.0 | 441/147 | 39/24 | 513/186 | 2.76x |
| clip01 | 2.60 | 5.9/15.0 | 442/147 | 152/194 | 600/357 | 1.68x |
| clip02 | 4.06 | 6.0/15.0 | 442/148 | 151/162 | 601/325 | 1.85x |
| clip03 | 4.65 | 6.6/15.0 | 443/144 | 97/97 | 551/258 | 2.13x |
| clip04 | 5.09 | 6.5/14.0 | 443/148 | 119/131 | 572/293 | 1.95x |
| clip05 | 5.81 | 6.5/15.0 | 443/146 | 79/82 | 532/243 | 2.19x |
| clip06 | 7.10 | 6.5/15.0 | 443/144 | 80/76 | 533/235 | 2.27x |
| clip07 | 8.62 | 6.5/15.0 | 443/144 | 84/82 | 537/240 | 2.24x |
| clip08 | 10.89 | 6.6/14.0 | 443/143 | 113/106 | 566/263 | 2.15x |
| clip09 | 29.40 | 7.0/14.0 | 443/141 | 113/115 | 567/271 | 2.09x |
| clip10 | 32.42 | 13.4/28.0 | 885/290 | 215/214 | 1122/406 | 2.76x |

Chain TDT beats the host loop on every clip (fixture 100 vs 236 ms; corpus tdt
39-215 vs 77-496 ms) and sits at/near macOS decode parity (fixture 100 vs ~103 ms;
clips within ~±10% except sub-2 s). clip00 (first clip of every invocation) and
clip10 (2 x 30 s windows) mel/encoder rows carry warm-up/chunking artifacts on both
sides. The remaining e2e gap is the whole-encoder cell (441 vs ~145 ms), unchanged.
Raw artifacts + hashes: private notebook `artifacts/ParakeetCert/`.

## Qwen3.8-2B ANE reference, Linux leg

Linux ANE-only runner (native fixture), first 10 corpus prompts x 32 greedy tokens.
The path is bit-deterministic: p001 and p008 rerun gave identical ids and all
32x248,320 logits bit-equal, layer-step time jitter <1%; a single-process runner
reproduced both bit-exactly again. The contract's 10 reps were therefore not run to
completion (they re-measure <1% jitter on a deterministic path); the deterministic
sample is the Linux reference.
Latency: ~23.7 s per decode step (24 layers) + ~1.7 s logits, ~0.04 tok/s vs macOS
ANEForge 6.76 tok/s (~160x); e2e per prompt ~19 min vs 5.67 s. **Performance parity: FAIL**
(same root cause as the encoder: ANE clock/perf mode, plus per-step host overhead).
Functional: generated ids match macOS ANEForge over 32 tokens on 0/10 prompts, but
against an fp32 CPU reference of the same model both ANE paths diverge at similar
token indices (first divergence 6-21 on Linux, 5-27 on macOS; ties on 7/10), so the
mismatch is shared fp16 near-tie sensitivity, not a Linux defect. **Functional gate
vs macOS: FAIL as specified**; neither ANE path is fp32-class.
- Raw artifacts and the pre-registered notebook entries live in the private notebook.
