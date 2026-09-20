# Apple Neural Engine experiments on Linux

This repository tests the Apple Neural Engine on Linux.
The target is an M1 MacBook Pro with Omarchy and the Asahi kernel.
The scripts compare ANE output with numpy on real hardware.

The latest results are in the [Linux ANE article](https://joshuawarren.com/blog/ane-linux-crossover/).
Every headline number has a matching receipt in `receipts/`.

## Current status

**2026-09-20:** jwm1 (T8103) fresh Arch boot reported (user-observed at login); Omarchy provisioning and benchmark recertification pending. Historical T8103 numbers in this tree are dated evidence from prior Linux boots, not a current recert.

T8103 (M1) has a bound ANE (historical, prior Linux boots). Persistence is a systemd unit that binds the device at boot. Schema-4 add-mul, tiny select, 1x1 conv, and `(1,256,128)` and `(32,256,128)` linear are exact fp16. The exported add family is exact too: re-exported 1x512 and 1x896 both returned exact, status 0, on 2026-09-14 (`receipts/2026-09-14-1x896-export-fix.json`). The earlier 1x896 `-110` was a converter defect chain, fixed on main: hardcoded td_size over-fetching the task (`8e89936`), the task record left unmasked (`a29a395`), the coefficient stream read from byte 0 of the weight blob instead of its declared payload offset, and the nchw header stamped at the 64-byte-padded convention instead of the task's own tile-DMA geometry (`52a3211`). The exported family's task puts its source on channel 4 and its destination on channel 5, the reverse of libane's positional layout, so it needs the derived-channel libane from omarchy-ane `ane-parity` `20d24ad` (`receipts/2026-09-14-1x896-channel-polarity.json`); that commit is not on omarchy-ane `main`.

T6001 (M1 Max) has `/dev/accel/accel0` live. SET follows runtime PM: SET0 reads `ACTUAL=0` while suspended and `0xf` after `open(accel0)` via genpd, no userspace write. Do not write SET `0xf`. The same add-mul, tiny select, 1x1 conv, and both linear shapes are exact and match T8103. The re-exported 1x512 and 1x896 also returned exact, status 0 (`receipts/2026-09-14-t6001-export-family.json`). A live overlay is not the packaged DTB: the packaged T6001 DTS exists only on omarchy-linux `feature/t6001-ane-bind` `9247b41`, unmerged. The omarchy-ane `main` `8554583` T6001 driver is being rebuilt on the lifecycle-correct base (bring-up scaffolding and GEM/ref bugs); the T6001 bind on main is a proven bring-up, not the shipping driver.

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
# On the macOS reference machine, from the ANEForge checkout.
PYTHONPATH="<llama.cpp checkout>/gguf-py" \
  uv run --project . --with pyyaml python tools/aneforge-qwen-reference.py \
  --model /path/to/Qwen3.8-2B-Q4_K_M.gguf \
  --prompt-corpus qwen38-prompts-10.jsonl \
  --max-new-tokens 32 --warmup 1 --repetitions 1 \
  --logits-output qwen38-reference-10-logits.npz
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
