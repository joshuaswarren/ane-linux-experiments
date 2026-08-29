# Speed crossover results

## Linux: 2.50x CPU on the tied output head

The tied output head (248320x2048 fp16) runs faster than CPU numpy on the
same Linux host: `791 ms` on the ANE versus `1975 ms` on CPU, `2.50x`.
Quality holds against the fp32 reference: `max_err=0.0010`, argmax exact,
top-10 exact.

The earlier `0.33x` was never device speed. The old `run_gemm` allocated
and tore down four buffer objects on every tile call, about `2 ms` of churn
each time. The persistent path allocates its buffers once and keeps the
weights resident on device, which drops the floor to `0.187 ms` per submit
(300-call mean). The head is `485x8 = 3880` persistent `512x256` tiles, one
submit per tile, with fp32 CPU accumulation of the 8 partials per row tile.
One-time tile programming costs `6.3 s`. The result is dispatch-bound:
3880 submits at the `0.187 ms` floor account for `0.73 s` of the `791 ms`.

The end-to-end one-token path is not faster yet. One token still needs
`5,376` serialized GEMM submissions because the available Linux interface
exposes fixed `512x512` programs instead of a reusable whole-model graph.

The latest clean-boot Qwen check generated the same token on both paths. The
committed ANE path measured `steps=7.272`, `logits=7.672`; the CPU path
measured `steps=3.114`, `logits=2.568`. Vectorized weight packing and
sentinel-only polling reduced host work, but the ANE path still does not cross
CPU end to end.

- Receipts: `receipts/ane-static-graph-loop.log`
- Submit-floor benchmark: `ane-gemm-fast.py` (`--floor`)
- Full-head benchmark: `ane-head-bench.py`

## macOS: oMLX prefill crossover

The macOS control proves the hardware can cross the speed line. oMLX runs
Qwen3.8-27B prefill at `105.3 tok/s` with verified ANE procedures, versus
`95.8 tok/s` on the exact-weight GPU path and `5.546 tok/s` on a CPU-only
architecture control. The tuner observed ANE execution across 64 MLPs and
48 Gated DeltaNet layers. A no-cache output check matched byte for byte.

- Receipt: `receipts/qwen-ane-prefill-breakthrough.log`

## macOS full-ANE decode attempt: not a success

On macOS 26.5.2, a locally patched
[ANEForge](https://github.com/sbryngelson/ANEForge) checkout compiles the
full 24-layer Qwen model into reusable ANE programs with resident state. It
returns `[11, 353, 1144, 310]` for four greedy tokens and decodes them in
`0.496s` after warmup. The native llama.cpp CPU reference returns
`[11, 353, 2688, 4313]` in `0.096525s`. The ANE path is slower and diverges
after the second token, so it does not meet the success bar. Keep ANEForge's
Qwen residual scale at `1.0`; scale `32.0` changed the output sequence.

- Receipts: `receipts/aneforge-qwen-macos26.log`,
  `receipts/aneforge-qwen-precision-boundary.log`

## Vulkan control

The Vulkan result is a useful control, not an ANE result.

- Receipt: `receipts/qwen-vulkan-hellaswag.log`
