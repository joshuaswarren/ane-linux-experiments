# Apple Neural Engine experiments on Linux

Scripts and receipts from getting real work out of the Apple Neural Engine on
an M1 MacBook Pro running Omarchy for Mac (Arch and Hyprland on the Asahi
kernel). Everything here was verified against numpy on real hardware. The
full story, including the mistakes, is written up at
[joshuawarren.com](https://joshuawarren.com/blog/m1-neural-engine-linux-gpu-llm/).

## Qwen ANE status: Linux full-model execution, macOS speed crossover

The unusual result in this repository is Linux. An M1 MacBook Pro running
Omarchy Linux now sends real Qwen3.8 GGUF weights through the Apple Neural
Engine without Core ML, AppleNeuralEngine.framework, or a macOS runtime.
All 24 main Qwen3.8-2B layers execute with persistent Gated DeltaNet and
full-attention state.

The Linux path is not faster yet. One token still needs `5,376` serialized
GEMM submissions because the available Linux interface exposes fixed
`512x512` programs instead of a reusable whole-model graph.

The macOS control proves the hardware can cross the speed line. oMLX runs
Qwen3.8-27B prefill at `105.3 tok/s` with verified ANE procedures, versus
`95.8 tok/s` on the exact-weight GPU path and `5.546 tok/s` on a CPU-only
architecture control. A no-cache output check matched byte for byte.

## What is proven

- **gemm and elementwise primitives** driven from Python with raw ioctls
  (`ane-network.py`): a 2-layer MLP, every matmul on the engine.
- **Softmax composed from add/mul/max/sq** (`ane-softmax.py`): range-reduced
  Taylor exp, Newton-Raphson reciprocal, pairwise-halving reductions. No exp,
  reciprocal, or divide instruction was ever found; none was needed.
- **Both attention matmuls on the engine** (`ane-attention.py`): `Q·K^T` and
  `attn·V` work by placing the activation in the weight DMA blob. The blob is
  built once per matrix, not per step.
- **A whole transformer block with no CPU arithmetic** (`ane-block.py`):
  projections, scores, scale, softmax, weighted sum, FFN. The CPU moves fp16
  buffers and computes nothing.
- **A resource-safe runtime** (`ane-runtime.py`): owns the DRM fd and its
  persistent BO workspace, submits real gemm work, waits for output DMA, frees
  every BO at close, and passes `runtime_gemm max_err=0.0000 output_ok=True` on
  real hardware.
- **Qwen3.8-27B ANE prefill crossover on macOS**: the tuner observed ANE
  execution across 64 MLPs and 48 Gated DeltaNet layers. It reached
  `105.3 tok/s`, `9.92%` above the exact-weight GPU path. The exact
  deterministic output matched. See
  `receipts/qwen-ane-prefill-breakthrough.log`.
- **Real Qwen model weights** (`ane-weights.py`, `ane-real-tile.py`):
  dequantizes `blk.0.attn_qkv.weight` from the selected Qwen3.8-2B Q4_K_M
  GGUF, converts its first 512x256 tile to the ANE fp16 layout, and matches
  numpy within `max_abs_err=0.000402`. This is one projection tile, not a
  quality result.
- **Arbitrary-size matmul by tiling** (`ane-tiled.py`): any `W @ x` in
  512x256 tiles, verified to (2048, 1024), with the cross-tile reduction
  optionally on the engine too. A verified 512x512 descriptor now handles
  wide projections and halves their input-column tile count. A 1024-input
  descriptor is not usable; its random-weight check returned `output_ok=False`.

Numbers for all of the above are in `receipts/`.

## Partially verified: batched submission

`ane-batch.py` chains task descriptors in one submission. The submit ioctl
carries `td_count` and the driver passes it to the task manager.

- Two, three, four, and eight identical descriptors per submission produce
  numerically correct output when each count is tested as the first submission
  after a clean reboot and bring-up ladder.
- Clean first-submission results are in
  `receipts/ane-batch-perboot-clean.log`: n=3 measured 1.64ms and 1.63ms,
  n=4 measured 0.12ms and 1.64ms, and n=8 measured 1.66ms and 0.48ms total.
- A clean two-TD test with different weight blobs produces the first output
  but leaves the second at the `+inf` sentinel. Per-TD weight batching is not
  verified.
- Timing is not stable. The same n=2 configuration measured 1.61ms, 0.75ms
  and 2.16ms total across three clean boots. No model-throughput headline is
  quoted.
- Earlier failures were contaminated. A first run tried n=1,2,4,8 in one
  process. n=4 hung. Every later submission inherited the queue wedge. That
  did not prove a hardware limit, so no descriptor ceiling is claimed.

## Standard model

This work uses `empero-ai/Qwen3.8-2B-Distill-GGUF`, specifically
`Qwen3.8-2B-Q4_K_M.gguf` at 1,312,164,224 bytes. It fits the 16 GB M1 and
uses the Qwen3.5-2B hybrid Gated DeltaNet/full-attention architecture.
`ane-weights.py` dequantizes its Q4_K tensors. `ane-real-tile.py` runs the
first tile of `blk.0.attn_qkv.weight` on the ANE and matches numpy within
`max_abs_err=0.000402`.

Qwen3.8-Flash-Next does not fit this machine. Its official repository is
360.0 GB. Its available `UD-Q4_K_XL` quant is 111.3 GB.

## Current Qwen status

`ane-qwen-model.py` runs all 24 main Qwen layers; GGUF `blk.24.nextn.*` is
the MTP head and stays outside the loop. It runs both Gated DeltaNet and
full-attention paths, persistent state, and tied output logits. CPU and ANE
agree on two generated prompts and return finite `(2048,)` hidden state and
`(248320,)` logits. `ane-tokenizer.py` provides real CPU token IDs, and
`ane-kv-cache.py` provides bounded full-attention state. The custom ANE path
still differs from llama.cpp after the first `Hi` token and remains slower
than the custom CPU path. This Linux raw-KMD decode path has not met the
success bar. The macOS oMLX path has now met it for fixed-shape prompt
prefill only. See `receipts/qwen-ane-prefill-breakthrough.log`.

The Vulkan result remains a useful control, not an ANE result. See
`receipts/qwen-vulkan-hellaswag.log`.

## macOS full-ANE decode attempt: not a success

On macOS 26.5.2, a locally patched [ANEForge](https://github.com/sbryngelson/ANEForge)
checkout compiles the full 24-layer Qwen model into reusable ANE programs with
resident state. It returns `[11, 353, 1144, 310]` for four greedy tokens and
decodes them in `0.496s` after warmup. The native llama.cpp CPU reference
returns `[11, 353, 2688, 4313]` in `0.096525s`. The ANE path is slower and
diverges after the second token, so it does not meet the success bar.
Keep ANEForge's Qwen residual scale at `1.0`; scale `32.0` changed the
output sequence. See `receipts/aneforge-qwen-macos26.log` and
`receipts/aneforge-qwen-precision-boundary.log`.

## Warning

The bring-up path can hard-reset the machine. A wrong register write reboots
it instantly, with no panic and no log. If you try this, use netconsole for
evidence: on btrfs, a reset rolls back unsynced writes and eats your log file.
Do not run any of this on a machine you care about keeping up.

## Standing on

- [omarchy-mac](https://github.com/omarchy-mac/omarchy-mac) - the platform
  this all ran on: the opinionated Arch and Hyprland setup for Apple silicon
  Macs. The userland, the tooling, and the reason the machine was usable as
  a workbench at all.
- [eiln/ane](https://github.com/eiln/ane) - Eileen Yoon's reverse-engineered
  kernel driver and userspace library, and the
  [t8103 device-tree patch](https://github.com/AsahiLinux/linux/commit/bf6651bb55212f2cfab573bd0d49bf5c601b4703)
  that carries the six ANE power domains and the real MMIO base.
- [allbilly/ane](https://github.com/allbilly/ane) - ops driven from Python
  with nothing but numpy, which these scripts build on and expect at
  `~/src/apple-ane`. The Asahi kernel underneath provides the DART and
  power-management plumbing these drivers sit on.


## Apple Core AI reference

Apple's [coreai-models](https://github.com/apple/coreai-models) repo is a
useful reference for the separate Apple Neural Engine stack on macOS and iOS
27. It provides export recipes, PyTorch primitives, and Swift runtime tools.
Its [Neural Engine authoring rules](https://github.com/apple/coreai-models/blob/main/skills/skills/model-authoring/references/neural_engine_rules.md)
confirm several patterns that matter here:

- use fp16 and static shapes for Neural Engine execution;
- use BC1S layout and 1x1 Conv2d for projections;
- split attention per head rather than expecting fused SDPA;
- pass KV cache as readonly functional input/output;
- use `-40000.0` instead of `-inf` for fp16 causal masks.

The [Qwen3 recipe](https://github.com/apple/coreai-models/tree/main/models/qwen3)
shows Apple's supported export path for Qwen3. It does not yet replace this
Linux KMD runtime or provide a Qwen3.8 export, but its layout and cache rules
are now part of the design reference for this project.

## Layout

| File | What it does |
|---|---|
| `ane-weights.py` | Dequantize GGUF tensors and emit ANE fp16 tiles |
| `ane-real-tile.py` | Execute one real model tile and compare with numpy |
| `ane-tokenizer.py` | Token IDs from a real GGUF through llama.cpp |
| `ane-kv-cache.py` | Bounded per-layer key/value state |
| `ane-bringup.sh` | The gated bring-up ladder; run this first, every boot |
| `ane-network.py` | 2-layer MLP, gemm + relu, vs numpy |
| `ane-softmax.py` | Softmax from composed primitives, vs numpy |
| `ane-attention.py` | Full attention, both matmuls on-engine, vs numpy |
| `ane-block.py` | Whole transformer block, no CPU arithmetic, vs numpy |
| `ane-runtime.py` | Resource-safe fd/BO ownership and gemm submission |
| `ane-qwen-layer.py` | Qwen full-attention layer with ANE projections |
| `ane-qwen-model.py` | 25-layer Qwen token step and tied logits |
| `ane-driver-qid.py` | Patch KMD to select qid through submit.pad |
| `ane-tiled.py` | Arbitrary-size tiled matmul, cost measurement, projection |
| `ane-transformer.py` | Earlier block variant (CPU softmax path kept for comparison) |
| `ane-driver-bostage.py` | Stage-gates the BO_INIT mapping path for bisection |
| `ane-bo-bisect.sh` | Per-stage runner for the above |
| `ane-ioctl-trace.py` | Wraps fcntl.ioctl, marks every call to /dev/kmsg |
| `ane-warmup-test.sh` | Minimal warm-up A/B test |
| `ane-fullchain-test.sh` | Power chain + module + first op, one command |
| `receipts/` | Run logs backing every number above |

## License

MIT
