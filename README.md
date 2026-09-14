# Apple Neural Engine experiments on Linux

This repository tests the Apple Neural Engine on Linux.
The target is an M1 MacBook Pro with Omarchy and the Asahi kernel.
The scripts compare ANE output with numpy on real hardware.

The latest results are in the [Linux ANE article](https://joshuawarren.com/blog/ane-linux-crossover/).
Every headline number has a matching receipt in `receipts/`.

## Current status

T8103 on m1-test-host has a bound ANE. Persistence is `m1-test-host-ane.service`. Schema-4 add-mul is exact fp16 through the mlx-omarchy v2 adapter. 1x896 times out with -110 and is forbidden.

T6001 on t6001-test-host has `/dev/accel/accel0` live. SET0 at `0x28e08c000` was gated (`receipts/2026-09-13-t6001-test-host-set0-read.json`); T8103-shaped SET genpd raised ACTUAL=0xf without a userspace `0xf` write (`receipts/2026-09-13-t6001-set-domains.json`). The same 64-el schema-4 add-mul is then exact fp16 in 2 ms (`mlx-omarchy/receipts/2026-09-13-t6001-test-host-ane-set-exec.json`, y `bade941d` matching T8103). 1x896 remains forbidden. Do not write SET registers from userspace.

The out-of-box install plan is [docs/omarchy-ane-out-of-box-plan.md](docs/omarchy-ane-out-of-box-plan.md). The kmod is SoC-gated. Do not GRUB a whole-tree DTB.

Older Qwen speed and parity numbers are in `receipts/` and [crossover results](docs/crossover-results.md).

## Qwen reference workflow

The locked macOS reference uses the real
`Qwen3.8-2B-Q4_K_M.gguf` file and ANEForge.
The model must exist on the macOS reference system.
The tokenizer command `llama-tokenize` must be in `PATH`.
Pass `--contract benchmarks/qwen38-2b-contract.json` for the exact 100-prompt
corpus. The runner then validates the model, layer count, token count, and
corpus checksum before compilation.
Run the hardware-independent checks on Linux:

```sh
uv run --with numpy python -m unittest \
  tools.test_ane_contract \
  tools.test_aneforge_qwen_reference \
  tools.test_compare_qwen_reference
```

Run a bounded macOS reference capture:

```sh
cd ~/src/ANEForge
PYTHONPATH="$HOME/src/llama.cpp/gguf-py" \
  ~/.local/bin/uv run --project . --with pyyaml python /tmp/aneforge-qwen-reference.py \
  --model "$HOME/ane-models/Qwen3.8-2B-Q4_K_M.gguf" \
  --prompt-corpus /tmp/qwen38-prompts-10.jsonl \
  --max-new-tokens 32 --warmup 1 --repetitions 1 \
  --logits-output /tmp/qwen38-reference-10-logits.npz
```

The runner writes one JSON summary and one compressed logits archive.
The archive preserves prompt lengths and repeated-run boundaries.
The comparator maps prompt IDs before it compares candidate arrays.
The complete 100-prompt capture exceeded the 900-second bound in the current
reference run.
The 100-prompt attempt and ten-prompt checksums are in `receipts/`.

## Quick start

1. Read the warning below.
2. Run `./ane-bringup.sh` after every boot.
3. Try `python3 ane-network.py`.
4. Run the checks:

   ```sh
   uv run --with numpy python -m unittest \
     tools.test_hwxv2_to_anec \
     tools.test_production_anec_probe \
     tools.test_ane_contract \
     tools.test_aneforge_qwen_reference \
     tools.test_compare_qwen_reference
   ```

## Documentation

- [Fresh HWX usage](docs/fresh-hwx-usage.md): conversion and device parity.
- [Static graphs](docs/static-graphs.md): reusable graphs and submissions.
- [Crossover results](docs/crossover-results.md): speed and model results.
- [Out-of-box ANE install](docs/omarchy-ane-out-of-box-plan.md): SoC-gated kmod, no whole-tree DTB.
- [Apple Core AI reference](docs/apple-coreai-reference.md): export guidance.

## Main tools

| File | Purpose |
|---|---|
| `ane-bringup.sh` | Run the device recovery ladder. |
| `ane-network.py` | Run a two-layer MLP. |
| `ane-runtime.py` | Own persistent buffers and submit GEMM work. |
| `ane-qwen-model.py` | Run the 24-layer Qwen token step. |
| `tools/qwen-token-runtime.py` | Keep Qwen recurrent and attention state on the ANE. |
| `ane-head-bench.py` | Measure the tied output head. |
| `ane-static-loop.py` | Run a reusable static graph. |
| `tools/` | Convert HWX files and run fresh-format probes. |
| `tools/aneforge-qwen-graph.py` | Compile and run a Qwen-shaped SwiGLU graph through ANEForge. |
| `tools/production-anec-sequential.py` | Execute production tasks one at a time. |
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
