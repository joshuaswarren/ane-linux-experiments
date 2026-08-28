# Apple Neural Engine experiments on Linux

This repository tests the Apple Neural Engine on Linux.
The target is an M1 MacBook Pro with Omarchy and the Asahi kernel.
The scripts compare ANE output with numpy on real hardware.

The latest results are in the [Linux ANE article](https://joshuawarren.com/blog/ane-linux-crossover/).
Every headline number has a matching receipt in `receipts/`.

## Current status

The tied Qwen3.8-2B output head beats CPU numpy on Linux.
It takes `791 ms` on the ANE and `1975 ms` on the CPU.
The speedup is `2.50x`.
The maximum error is `0.0010`.
The argmax and top-10 results match.

A sanitized macOS 26 HWX fixture reaches the Linux device.
A real 64-channel fixture graph passes exact channel-level parity.
The graph writes source channel 1 to output channel 3.
Signed stress values also pass.
See [fresh HWX usage](docs/fresh-hwx-usage.md).

Static ANEC graphs run and re-bind on Linux.
The state loop uses `ane_exec_loop`.
Runtime kernel swaps use `ane_bind_kernel`.
See [static graphs](docs/static-graphs.md).

The full Linux token path is not faster than CPU.
One token still needs `5,376` serialized GEMM submissions.
Fresh-format parity for the full Qwen production model is unproven.
See [crossover results](docs/crossover-results.md).

## Quick start

1. Read the warning below.
2. Run `./ane-bringup.sh` after every boot.
3. Try `python3 ane-network.py`.
4. Run `uv run --with numpy python tools/test_hwxv2_to_anec.py`.

## Documentation

- [Fresh HWX usage](docs/fresh-hwx-usage.md): conversion and device parity.
- [Static graphs](docs/static-graphs.md): reusable graphs and submissions.
- [Crossover results](docs/crossover-results.md): speed and model results.
- [Apple Core AI reference](docs/apple-coreai-reference.md): export guidance.

## Main tools

| File | Purpose |
|---|---|
| `ane-bringup.sh` | Run the device recovery ladder. |
| `ane-network.py` | Run a two-layer MLP. |
| `ane-runtime.py` | Own persistent buffers and submit GEMM work. |
| `ane-qwen-model.py` | Run the 24-layer Qwen token step. |
| `ane-head-bench.py` | Measure the tied output head. |
| `ane-static-loop.py` | Run a reusable static graph. |
| `tools/` | Convert HWX files and run fresh-format probes. |
| `patches/` | Hold the Linux libane patches. |
| `receipts/` | Hold command output and measured results. |

## Warning

The bring-up path can hard-reset the machine.
A wrong register write can reboot it without a panic or log.
Use netconsole when you need evidence.
A btrfs reset can lose unsynced writes.
Do not run this work on a machine that must stay available.

## Credits

- [omarchy-mac](https://github.com/omarchy-mac/omarchy-mac) provides the platform.
- [eiln/ane](https://github.com/eiln/ane) provides the reverse-engineered driver.
- [allbilly/ane](https://github.com/allbilly/ane) provides Python ANE operations.
- [Asahi Linux](https://github.com/AsahiLinux/linux) provides the kernel.

## License

MIT
