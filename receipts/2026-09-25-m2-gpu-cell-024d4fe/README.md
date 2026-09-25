# M2 Max (T6021) Linux GPU cell, main wheel 90154f0d (2026-09-25)

## Result
Qwen3.8-2B GPU contract on m2-host (Linux 7.1.13-ARCH-m2mbox), mlx-omarchy
wheel 90154f0d (024d4fe lineage, SHA verified on-box before install), no ANE
module loaded, --skip-parakeet. Window rc=0, elapsed 81 s.

| metric | Linux (this cell) | macOS (d3dc1ae) | ratio |
|---|---|---|---|
| decode tok/s median | 78.59 (CI95 78.56-78.62) | 179.0 | 0.44x |
| pure prefill-512 tok/s | 737.85 (wall 0.6939 s) | 1109.82 | 0.66x |
| TTFT tok/s | 82.64 | 367.68 | 0.22x |
| e2e s median | 0.5557 | 0.2129 | 2.61x slower |

- Records digest dbf70497, gate MATCH (pinned). 100 records.
- Peak RSS: null (RSS wrapper bypassed; venv --copies fix for the
  ARM symlink-alias hang plus wrapper bypass for the -c/argv threading bug).
- Two kit-script defects found and worked around on-box (not committed):
  plain `python -m venv` produces a symlink-alias binary the kernel runs
  as a script (--copies required); the run_with_rss wrapper threads the
  outer `python -c` argv through and the inner interpreter reads the venv
  binary as source. Both belong to the kit owner lane.

## Provenance
- Raw: /var/tmp/m2-window-20260925T120840Z/ on m2-host (contract, derived,
  env, SHA256SUMS, window). Derived copied here.
- env: wheel 90154f0d verified, model pin b0d5de68, Vulkan asahi_icd,
  ANE loaded=0, parakeet non-viable.
