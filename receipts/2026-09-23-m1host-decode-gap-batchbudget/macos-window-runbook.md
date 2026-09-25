# m1-host macOS per-kernel window runbook (for Main's approval)

## Goal
Per-op-family Metal GPU timings for one decode token on m1-host's macOS,
same model + prompt as the Linux side, to build the
Linux-vs-Metal per-family cost table (the real lever list).

## Already done (off-device)
- `family_bench.py` (device-agnostic, pure mlx + mlx-lm 0.31.3):
  benches each op family with the real decode shapes via the model's
  own modules — QuantizedLinear families (six shapes), RMSNorm,
  conv+silu chain, gated_delta_update, SDPA, rope, lm_head full GEMV
  (QuantizedEmbedding.as_linear), plus a 3-trial whole-token decode.
  Amortized methodology: N launches between flushes (per-launch =
  max(host enqueue, kernel time)), median of 30, 3 warmups.
- Validated on the M1 Max Metal reference host (mlx latest): script runs
  end-to-end; sensible numbers (e.g. qmm[6144x2048] ≈ 259 µs = 12 MB at
  ~46 GB/s; small-kernel rows land on the ~0.8 µs/launch issue floor).
- Linux column captured on m1-host with the identical script
  (families-linux.json).

## Window needs (macOS side, ~15 min)
1. Boot m1-host to macOS.
2. Network on (model download) or the workstation can serve the
   snapshot (1.06 GB).
3. Python 3.10+ with pip (macOS-side; Xcode 3.9 is too old for mlx).
4. Commands:
   python3 -m pip install --user mlx mlx-lm==0.31.3
   python3 -c "from huggingface_hub import snapshot_download; \
     print(snapshot_download('SiddhJagani/Qwen3.8-2B-mlx-4Bit'))"
   python3 family_bench.py --model <snapshot-dir> \
     --out ~/families-metal-m1-host.json
   (then scp the JSON + script back to the workstation)

## Output
families-metal-m1-host.json (Metal per-family µs) — combined with
families-linux.json (Vulkan per-family µs, same script/methodology)
into the Linux-vs-Metal per-family table; biggest absolute deltas = the
real lever list.

## Notes
- The Linux side already ran: lm_head full composed = 5397 µs on Linux
  (m1-host, today's slow-state machine); expect ~900-1400 µs on macOS
  M1 — the lm_head row is expected to be the single biggest absolute
  delta (the pruned route is already installed on Linux, so the
  actionable reading is in the OTHER rows).
- gated_delta_update_raw is Linux-only (omarchy fast op); macOS uses
  the upstream gated_delta_update — benched separately on each host.

## Confirmed boot mechanics (offline verification on the Linux side)
- Boot tool: asahi-bless 0.4.2 (`/usr/bin/asahi-bless`).
- `--list-volumes`: 1) Macintosh HD (macOS), 2) Omarchy (Linux, current) — unambiguous.
- One-shot macOS boot: `sudo asahi-bless -n --set-boot-macos -y && sudo systemctl reboot`
  (-n sets the UEFI BootNext variable only; default order untouched, so the
  following reboot returns to Linux).
- Return: plain `sudo reboot` from macOS (BootNext consumed).
- macOS ssh: `ssh <m1-macos ssh alias>` (tailscale; daemon starts on macOS
  boot). Unreachable while Linux is booted (expected).

## macOS-side execution (single script, to run when the window opens)
1. ssh jw-m1-macos
2. Check python: `python3 --version` — need 3.10+. If the system python is
   3.9 (Xcode) and no homebrew python exists, install once:
   `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` is TOO heavy for the window; prefer an existing
   python3.10+/miniforge. If none exists, abort the window and report.
3. `python3 -m venv ~/venv-metal && ~/venv-metal/bin/pip install mlx mlx-lm==0.31.3`
4. `~/venv-metal/bin/python -c "from huggingface_hub import snapshot_download; print(snapshot_download('SiddhJagani/Qwen3.8-2B-mlx-4Bit'))"`
5. `~/venv-metal/bin/python family_bench.py --model <snapshot> --out ~/families-metal-m1-host.json`
6. `cat ~/families-metal-m1-host.json` → copy back to the workstation.
7. `sudo reboot` (returns to Linux; BootNext consumed).
