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
- Linux Parakeet e2e and Linux Qwen ANE reference are not yet re-run in this window;
  no parity claim for those cells.
- Raw artifacts and the pre-registered notebook entries live in the private notebook.
