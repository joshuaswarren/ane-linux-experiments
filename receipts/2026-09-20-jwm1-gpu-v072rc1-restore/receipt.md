# jwm1 GPU restored on published v0.7.2-rc.1: SDPA + bounded compile-enabled Qwen3.8-2B decode (2026-09-20)

Lane: Jwm1GpuRestore. Host: jwm1-linux (Apple M1, T8103, serial `C02DP17UQ05P`
verified from `/proc/device-tree/serial-number` over pinned SSH). Fresh Asahi
Alarm btrfs image of 2026-09-20
([clean-install receipt](2026-09-20-jwm1-clean-install.json)); this lane is the
first GPU acceptance on that image. No reboot, no firmware/DT/kernel/network/
firewall/password/audio edits. SSH: ProxyJump macstudio, key `id_rsa_2025`,
`StrictHostKeyChecking=yes` against the pinned known-hosts entry (ed25519
`…SUvjRFWVxi`). PID1 is systemd (stale `init=/bin/bash` cmdline token left
alone; owner-exec path). NetworkManager/sshd/sddm active throughout.

## Verdict

**Real GPU inference works on the fresh jwm1 image.** On the published
v0.7.2-rc.1 aarch64 wheel (sha `fe51534b…`, three-way verified), Vulkan device
`Apple M1 (G13G B1)` / Honeykrisp / Vulkan 1.4.354:

- CPU matmul and the three-case SDPA numerical smoke: **PASS** (max abs errors
  2.20e-07 / 5.75e-07 / 0.0 against host float64, threshold 1e-4).
- Bounded compile-enabled decode (`bench_decode_vlm.py --prompt-id long
  --tokens 32 --warmup-tokens 4 --stop-policy ignore-eos`), model
  `SiddhJagani/Qwen3.8-2B-mlx-4Bit` @ `0867d98b…` (weights sha256
  `b0d5de68…` verified after download): **15.5882 tok/s over 32 tokens**,
  prefill 5.603949 s (245 prompt tokens), generated-ID digest
  `24a65754f4a0d99a`, first `[2, 9988, 314]` last `[383, 829, 7320]`.
  Provenance `verified=match`; `libmlx.so` sha256-16 `c28a485f98b55aad`.
- Post-run `sha256sum -c` of harness + weights: all OK. sddm active before and
  after — GUI undisturbed.

One bounded run per leg. **No performance-parity claim of any kind** — the
release's jw16 record (26.4057 tok/s, 233 prompt tokens) is that host's own
observation; jwm1 observed 15.5882 tok/s and 245 prompt tokens on the same
1208-char prompt, an unreconciled cross-host delta recorded as-is.

## Runtime construction (exact artifacts)

| item | value |
|---|---|
| wheel | `mlx_omarchy-0.32.3.dev202609201440+5b18306-cp314-cp314-linux_aarch64.whl`, sha256 `fe51534b1ed658f64f2e16f5ce4709c27cbb1c683388b50a2d04eacf6b362a01` |
| wheel verification | GitHub release v0.7.2-rc.1 API digest == local `/tmp/mlx-v072-rc1-assets/SHA256SUMS` == remote sha256 after scp |
| venv | `/var/tmp/jwm1-v072rc1/venv`, python 3.14.7, user-owned; image ships no pip/uv → venv pip bootstrapped by `ensurepip` (26.2.1) |
| install | `pip install --no-deps <wheel> -r requirements.txt`; requirements sha `1c3c69b8…` (the text-install receipt pin); upstream `mlx` **not** co-installed |
| prerequisite added | `openblas 0.3.34-1` (`pacman -S --needed`, no refresh) — genuinely absent; wheel links `libopenblas.so.0` (release body: built against `/usr/include/openblas`) |
| model | snapshot `0867d98bfb174b042d88461c0e7c97b86b34b381` downloaded at pinned revision; `model.safetensors` sha256 `b0d5de688567bf4acd5e421027acd410dabcdc255a5bd46fdbf06c75dc2e6863` matches the release qualification pin and [today's smoke receipt](2026-09-20-qwen38-distill2b-smoke.json); `HF_HUB_OFFLINE=1` in-window |
| GPU stack | mesa 26.2.3, vulkan-asahi 26.2.3, vulkan-icd-loader 1.4.357.0 (all preinstalled on the image) |

## Window protocol

Single exclusive `flock` on `/tmp/m1-gpu.lock` (created root-owned 0666 before
the window; inode 1384) held across both legs. **No inference service exists on
this image** — zero `llm`/`mlx` unit files, `llm-inference.service` inactive —
so the jw16 stop/restart protocol had nothing to act on; the GUI session
(sddm) was never touched. Compile enabled (`MLX_DISABLE_COMPILE` unset),
`HF_HUB_OFFLINE=1`, `PYTHONPATH`/profiling vars unset.

Harness files are byte-identical to the release acceptance tree
(`bench_decode_vlm.py` `8a821aba…`, `v072rc1-sdpa-check.py` `2982622b…`,
`bench_matrix.json` `df8eb9f3…`, `caps_sim_guard.py` `9ddb9abd…`,
`mlx_provenance.py` `21337ddd…`); `mlx_provenance` refused nothing and
reported `verified=match` against the installed wheel.

## Limits

- One bounded smoke per leg — not a statistical benchmark, not native-Metal
  parity, not a cross-host comparison.
- Prompt-token count differs from the jw16 acceptance (245 vs 233 on the same
  1208-char prompt); recorded, not reconciled.
- No ANE device action in this lane; no Linux ANE inference claimed.
- Fresh image with live GUI; numbers are not comparable to prior jwm1 boots.

## Artifacts

- Remote: `/var/tmp/jwm1-v072rc1/{wheel,venv,harness/,out/}`.
- Raw logs (this directory): `sdpa.log`, `decode.log`, `sha256.pre`.
- Machine record: [receipt.json](receipt.json).
- ANE follow-up is planned separately:
  [2026-09-20-jwm1-ane-restoration-plan.md](../2026-09-20-jwm1-ane-restoration-plan.md).
