# Apple Neural Engine experiments on Linux

Scripts and receipts from getting real work out of the Apple Neural Engine on
an M1 MacBook Pro running Omarchy for Mac (Arch and Hyprland on the Asahi
kernel). Everything here was verified against numpy on real hardware. The
full story, including the mistakes, is written up at
[joshuawarren.com](https://joshuawarren.com/blog/m1-neural-engine-linux-gpu-llm/).

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
- **A resource-safe runtime** (`ane-runtime.py`): owns the DRM fd and every
  BO, submits a real gemm, waits for output DMA, frees each BO, and passes
  `runtime_gemm max_err=0.0000 output_ok=True` on real hardware.
- **A real model-weight tile** (`ane-weights.py`, `ane-real-tile.py`):
  dequantizes `blk.0.attn_q.weight` from a Llama-3.2-3B Q4_K GGUF, converts
  its first 512x256 tile to the ANE fp16 layout, and matches numpy with
  `max_abs_err=0.000740`. This is one projection tile, not a full forward
  pass.
- **Arbitrary-size matmul by tiling** (`ane-tiled.py`): any `W @ x` in
  512x256 tiles, verified to (2048, 1024), with the cross-tile reduction
  optionally on the engine too. A single tile costs about 1.7ms in the
  current Python path. The submission path is the current performance
  question.

Numbers for all of the above are in `receipts/`.

## Partially verified: batched submission

`ane-batch.py` chains task descriptors in one submission. The submit ioctl
carries `td_count` and the driver passes it to the task manager.

- Two, three, four, and eight descriptors per submission produce numerically
  correct output when each count is tested as the first submission after a
  clean reboot and bring-up ladder.
- Clean first-submission results are in
  `receipts/ane-batch-perboot-clean.log`: n=3 measured 1.64ms and 1.63ms,
  n=4 measured 0.12ms and 1.64ms, and n=8 measured 1.66ms and 0.48ms total.
- Timing is not stable. The same n=2 configuration measured 1.61ms, 0.75ms
  and 2.16ms total across three clean boots. Something boot-dependent
  dominates, so no speedup or model-throughput headline is quoted.
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

## What is not proven

No full LLM runs on this. The remaining model path needs all real tensors
converted and scheduled, a complete Qwen hybrid layer, output logits, and a
KV cache across token steps. `ane-tokenizer.py` provides a real CPU token-ID
path through llama.cpp. `ane-kv-cache.py` provides bounded per-layer key/value
state and passes its self-test. Tokenization can stay on the CPU first.
Vulkan is the GPU path, not an ANE API; a GPU tokenizer is possible later but
does not replace this runtime.

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
