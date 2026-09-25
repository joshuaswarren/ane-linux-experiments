# 2026-09-23 — M2 Max (T6021) macOS denominator window (grouped capture)

Window owned by M2Gpu per Main. Single one-shot bless to macOS
(`sudo asahi-bless --next --set-boot 1`; default stays Omarchy; --get-boot
verified unchanged), plain `reboot` to return. Reboot gate: /boot is ext4
(nvme0n1p5), boot files off-btrfs — no grub-fstest required. ESP marker
verified before AND after the round trip: `/boot/efi/m1n1/boot.bin`
sha256 `ff4852219a4f88b720158f646472beeaa112b8922f7abbdd55fb1f1558fb4d0d`.

Host: Mac14,5, Apple M2 Max, 96 GiB, macOS 27.0 (26A428). Bundle
`mac-reference-bundle-full.tar.gz` sha256 `82c1a701…` verified on-box before
extraction. caffeinate -dimsu held the whole window; python3.13 (3.13.15)
already present. Window 14:52:05–14:58:38 CDT (legs) + capture pass.

## Legs

### (a)(b)(e) run-core.sh — whole-encoder CoreML bench (CORE-BUNDLE OK)

| arm | median ms | placement | compile ms | load ms | bit-exact vs Linux gold |
| --- | ---: | --- | ---: | ---: | --- |
| cpu | 187.16 | cpu 1374 | 222.1 | 2209.2 | report-only |
| **ane** | **90.71** | **ane 1346 / cpu 28** | 200.8 | 13382.1 | **YES (0/240000, max_delta 0)** |
| all | 92.15 | ane 1306 / cpu 23 / gpu 45 | 202.4 | 13764.2 | no (221455 mism, max_delta 0.037 — report-only) |

M2 Max ANE runs the same encoder at **0.80×** the M1 (T8103) macOS time
(90.71 vs 113.12 ms) with identical placement class. ANE power: none-recorded
(no ANE power counters exposed on this OS build — same class as the M1
denominator note).

### (d1) run-qwen-gpu.sh — Qwen3.8 GPU MLX, upstream Metal (GPU-BUNDLE OK)

- decode **179.0 tok/s** median (n=100), ttft 367.68 tok/s, pure prefill-512
  **1109.82 tok/s** (wall 0.4613 s), e2e median 0.2129 s, peak RSS
  1,668,186,112 bytes.
- ordered_records_sha256 `85b9bc6d…` — **byte-identical to the M1 macOS Metal
  run**: upstream Metal produces the same records digest across M1 and M2 Max.
- Comparators: M1 macOS 47.05 decode / 343.73 prefill; M1 Max macOS 179.47
  decode. M2 Max Metal ≈ M1 Max Metal (0.997×). Linux T6021 (same-day
  receipt): 72.58 decode / 906.84 prefill → **macOS/Linux on T6021 = 2.47×
  decode, 1.22× prefill** (M1: 1.33× decode; M1 Max: 2.82× decode).

### (c) run-parakeet.sh — GATE FAILED (mechanism identified, out dir shipped)

Per-arm transcripts are deterministic (ane rep1 == rep10). The English text is
IDENTICAL to the golden transcript through `…flour-fattened sauce………`; the
gate fails only on the decoder's trailing junk tokens: every arm ends
`… ЮНЕН` while the pinned golden ends `… Юн Ю` (cpu ends `… ЮНЕНТИ`, expected
to differ). So this is an M2 TDT decoder tail-token difference, not a text
error — Main/owner to decide whether a text-prefix criterion applies. All
per-arm out files + SHA256SUMS.outputs shipped.

### (d2) run-qwen-ane.sh — early exit (recorded honestly)

GGUF downloaded and verified (sha OK), model load started, then
`ModuleNotFoundError: No module named 'gguf'` from ANEForge's `_gguf.py`
under the window python. No compute; the err=11 decoder-compile blocker was
NOT reached. No packages installed (reads-only window discipline); a `pip
install gguf` into a venv would be the next step for a rerun.

## ANE evidence (M2FwStart-2 request)

Captured under `m2-macos-window/ane-evidence/`: `ane0.txt` + `ane0-full.txt`
(full property dump incl reg/segment-ranges/clock-ids/power-gates),
`ane0-devicetree.txt`, `dart-ane0.txt`, `dart-ane-nodes.txt` (all dart-ane
nodes found), `dart-t8110-all.txt` (AppleT8110DART sweep), `fud-ls.txt`
(/usr/standalone/firmware/FUD does not exist on this build), `iscpreboot-ls.txt`
+ `iscpreboot-root.txt`, `kext-ane-ls.txt` (AppleANELoadBalancer + H11/H16
ANE interfaces + T60xx/T81xx/T83xx ANE HALs), `firmware-dir-ls.txt`.
Copies at `.work/m2-macos-ane-ioreg/` and
`~/.local/state/omarchy-private-evidence/m2-macos-ane/`.

## Provenance

- Raw: `m2-macos-window/` (session.log, per-leg out dirs, ane-evidence) and
  `m2ref/` (bundle out/ with bench JSONs, goldchecks, ane_power, environment).
- Hostnames scrubbed to neutral labels; machine class Mac14,5 kept per repo
  convention; no serials.
