# jwm1 (M1, T8103) macOS paired legs, 2026-09-28

One macOS window on the same M1 that runs Linux (macOS 27.0 26A428, ANE fw 3600.25.2, mlx 0.32.2 / mlx_lm 0.31.3,
model mlx-4Bit 0867d98b sha b0d5de68…, corpus sha 9299a3b2…). Protocol: `benchmarks/qwen38-mlx-bench.py`
(temp 0 greedy, warmup 2, n=5 per cell); runner `mac-gpu-cells.sh`. Encoder: `run-core.sh` (fixed harness, cfg wired at 2bc91123,
placement from MLComputePlan). Raw outputs in `raw/`. Linux comparands: jwm1 Linux receipt 2026-09-28 (Mesa/Honeykrisp, mlx-omarchy 42fbbc5).

| Cell | Linux | macOS (median, range, n) | Linux/macOS | Result |
|---|---:|---|---:|---|
| prefill 512 tok/s | 242.14 | 345.31 (345.23-345.73) n=5 | 0.701 | LOSS |
| prefill 1024 tok/s | 240.40 | 345.76 (345.55-345.95) n=5 | 0.695 | LOSS |
| prefill 2048 tok/s | 235.57 | 341.80 (340.51-341.95) n=5 | 0.689 | LOSS |
| decode 64 tok/s | 39.22 | 49.36 (49.33-49.40) n=5 | 0.795 | LOSS |
| decode 128 tok/s | 38.26 | 49.26 (48.78-49.32) n=5 | 0.777 | LOSS |
| decode 256 tok/s | 37.63 | 49.33 (48.55-49.42) n=5 | 0.763 | LOSS |
| whole-encoder ANE ms (bit-exact both sides) | 138.86 (pass16, libane exec 138.04) | 113.24 ane arm, 112.85 all arm, n=10, placement ane 1345/cpu 29 | 0.815 (latency 1.23x) | LOSS |
| Parakeet fixture e2e (104 tok, transcript == golden both) | 0.92-1.6 s pipeline (fused_e2e / installed-wheel driver) | inference 0.272 s median n=10 (mel 14 ms, enc 138 ms, decode loop 120 ms), RTFx 38.45x | ~0.17-0.30 | LOSS (Linux TDT decode is host-driven) |

Notes: macOS Parakeet CLI encoder stage (138 ms) ~= Linux encoder_ane (138.86 ms); the 113 ms figure is the bare CoreML predict in the bench.
Prefill digest ccb601895581 is identical on both OSes (same prompt). Decode digests differ across backends by design (within-backend deterministic).
macOS loadavg at GPU start 2.44 (post-boot), thermal clean. Not done in this window: Qwen ANE reference (no llama-tokenize / GGUF on the Mac at capture time), Parakeet corpus beyond the fixture.
Private notebook entry with pre-registration: actor jwm1-parity, 20260928T222400Z (not in this repo).
