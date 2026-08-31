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
A captured production HWX converts to ANEC, and the complete `3,072`-descriptor
graph executes in one Linux submit with finite output.
The production probe copies the full content payload into the command BO.
The production graph matches its int8 weight reference with
`max_err=0.0004772`, `mean_err=0.00004533`, and matching argmax.

ANEForge also compiles and runs a Qwen-shaped SwiGLU block as one ANE program.
The graph has eight operations and matches a deterministic CPU reference.
It reports `max_err=0.018799` and matching argmax.
See [crossover results](docs/crossover-results.md) and [fresh HWX usage](docs/fresh-hwx-usage.md).
The probe is [tools/aneforge-qwen-graph.py](tools/aneforge-qwen-graph.py).
The run receipt is `receipts/aneforge-qwen-graph.log`.

The Linux Qwen path now uses only the ANE for tensor work.
Pass `--recurrent-anec <ANEC>` to start the ANE tensor runtime.
The command stops if that runtime is missing.

All model math runs on the ANE.
This includes norms, gates, convolution, state, attention, RoPE, residuals,
and projections. The ANE also adds partial projection tiles.
The host loads weights and looks up embeddings.
It builds constants, packs buffers, and picks output tokens.

A complete hardware run produced 248,320 finite logits and selected token `220`.
Decoder layers took `86.342` seconds. Logits took `11.893` seconds.
The ANE control passed before and after the run.
See `receipts/qwen-linux-ane-only-validation.json` for commands and hashes.

The explicit `--backend cpu` path remains a reference.
There is no GPU or automatic tensor fallback.
Numeric parity across the fixed corpus is the next milestone.

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
