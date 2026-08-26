# Apple Neural Engine experiments on Linux

Scripts and receipts from getting real work out of the Apple Neural Engine on
an M1 MacBook Pro running Linux (Asahi kernel, Arch userland). Everything here
was verified against numpy on real hardware. The full story, including the
mistakes, is written up at
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
- **Arbitrary-size matmul by tiling** (`ane-tiled.py`): any `W @ x` in
  512x256 tiles, verified to (2048, 1024), with the cross-tile reduction
  optionally on the engine too. Measured cost: ~1.9 ms per tile, dominated by
  the ioctl round trip, which projects a 3B model at ~0.023 tok/s. The wall
  is submission granularity, not arithmetic.

Numbers for all of the above are in `receipts/`.

## What is not proven

No LLM runs on this. Every result uses random Gaussian weights: no tokenizer,
no KV cache, no model file. The single largest gap is batched submission -
many tiles per task-descriptor chain instead of one Python ioctl per tile.

## Warning

The bring-up path can hard-reset the machine. A wrong register write reboots
it instantly, with no panic and no log. If you try this, use netconsole for
evidence: on btrfs, a reset rolls back unsynced writes and eats your log file.
Do not run any of this on a machine you care about keeping up.

## Standing on

- [eiln/ane](https://github.com/eiln/ane) - Eileen Yoon's reverse-engineered
  kernel driver and userspace library, and the
  [t8103 device-tree patch](https://github.com/AsahiLinux/linux/commit/bf6651bb55212f2cfab573bd0d49bf5c601b4703)
  that carries the six ANE power domains and the real MMIO base.
- [allbilly/ane](https://github.com/allbilly/ane) - ops driven from Python
  with nothing but numpy, which these scripts build on and expect at
  `~/src/apple-ane`.
- [Asahi Linux](https://asahilinux.org/) - everything else about this
  machine working at all.

## Layout

| File | What it does |
|---|---|
| `ane-bringup.sh` | The gated bring-up ladder; run this first, every boot |
| `ane-network.py` | 2-layer MLP, gemm + relu, vs numpy |
| `ane-softmax.py` | Softmax from composed primitives, vs numpy |
| `ane-attention.py` | Full attention, both matmuls on-engine, vs numpy |
| `ane-block.py` | Whole transformer block, no CPU arithmetic, vs numpy |
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
