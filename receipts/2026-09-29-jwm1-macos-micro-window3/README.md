# jwm1 same-die op-level macOS vs Linux (third macOS window, 2026-09-29)

One macOS window (macOS 27.0 26A428, up 05:49Z, back on Linux 06:01Z) on the M1 that runs Linux. Same scripts (`scripts/`) on macOS (mlx 0.32.2 Metal, python 3.14.7, Qwen3.8-2B MLX 4-bit, prompts sha 9299a3b2...) and on Linux (mlx-omarchy wheel 1daa1ad5d, Honeykrisp). Linux numbers are from the same scripts run on the live venv earlier the same day (see notebook entries H31-H51; raw macOS outputs in `macos-raw/`). No parity claim comes from these micro numbers; they direct where to work.

| Op (same script, same shapes) | macOS | Linux | Linux/macOS time |
|---|---:|---:|---:|
| 1024^3 matmul f32, sustained (ms) | 1.004 | 4.617 | 4.6x |
| 1024^3 matmul bf16, sustained (ms) | 1.112 | 3.523 | 3.2x |
| matmul after >= 50 ms idle (f32, ms) | 2.05-2.14 | 6.99-7.49 | idle penalty +105% macOS, +52% Linux (shared M1 property) |
| add 2048 dependent chain (us/op) | 3.7 | 9.5 | 2.6x |
| rms_norm 2048 chain (us/op) | 6.0 | 14.5 | 2.4x |
| qmm M=1 2048x2048 chain (us/op) | 35.6 | 61.5 | 1.7x |
| host record (async_eval return, add / rms / qmm, us/op) | 1.5 / 1.4 / 3.1 | 4.3 / 4.7 / 9.7 | ~3x |
| up_proj qmm 6144x2048, M = 2 / 4 / 8 / 16 (us) | 181 / 347 / 673 / 688 | ~600 / ~570 / ~570 / ~570 | macOS faster at M<=4, Linux faster at M=8-16 |
| up_proj qmm at M = 32 / 64 / 512 (us) | 645 / 1162 / 9079 | 897 / 1613 / 10963 | 1.4x / 1.4x / 1.2x |
| in_proj_a qmm N=16, M = 2..8 (us) | 23-25 | 260-300 | 11x |
| single forward L = 1 / 11 / 128 / 512 (ms) | 23.4 / 109 / 376 / 1473 | 48 / 175 / 575 / 1974 | 2.0x / 1.6x / 1.5x / 1.3x |
| decode: fresh-cache L=1 / synchronous / pipelined per token (ms) | 22.5 / 24.8 / 20.0 | 33.4 / 44.8 / 23.1 | exposed sync cost +4.8 vs +21.7 ms |
| streaming bandwidth: add r+w / lm_head qmm M=1 (GB/s) | 59.6 / 59.7 | 57.5 / 61.4 | equal |
| mx.sum over 256/512 MB (GB/s) | 57.2 / 57.7 | 4.5 / 4.0 | 13x slower on Linux |

Per-token arithmetic: weights read per decode token = 1058 MB (772 MB QuantizedLinear + ~286 MB tied lm_head/embedding), 17.7 ms at 59.7 GB/s. macOS 20.0 ms pipelined (2.3 ms over the roof), Linux 23.2 ms (5.5 ms over).

## Follow-up probes on Linux (this session, all digest-checked where they touch the model)

- Synchronous-token cost decomposition (`phase_trace.py`): python build 3.6-4.3 ms, `async_eval` return (host record + submit) 14.3-17.0 ms, wait 25.6-26.0 ms. The GPU cannot start until recording ends because the node budget is 4096 (one submit). Wake-up latency (jw16 poll driver: -1 ms) and CPU frequency (busy spinners: -3 ms) are not the cause.
- Smaller submit batches (`MLX_OMARCHY_BATCH_NODES`, branch agent/batch-budget-env f026573c1): synchronous token 45.5 -> 34.7 ms (128), L=11 forward 158-174 -> 135 ms, but qwen38 TTFT only -2..-6% and pipelined decode -1..-4% at 64-256; digest 7fe6badf4d560e25 everywhere. Not a default candidate as a constant.
- Native stack sampling (gdb, 160 samples of synchronous tokens): 64% of samples in the GPU wait ioctl; of the non-wait samples 0 have libvulkan_asahi in the top frames; allocator create/map/unmap (mmap/munmap under `VulkanAllocator::malloc/destroy_buffer`) is the visible hot spot.
- Buffer-cache limit (mx.set_cache_limit 32 -> 256/1024/2048 MB): synchronous token 44.9 -> 38.5 ms; decode, prefill and TTFT unchanged (decode64 41.62 vs 41.53-41.57 tok/s, ttft 0.1844 vs 0.1830-0.1841, prefill512 255.8 vs 255.2-256.5, prefill2048 251.9 vs 250.1-252.5); Parakeet warm pipeline unchanged (380.8 vs 381.4 ms); digests identical.

## Levers this data supports (no parity yet: all three surfaces still below macOS)

1. Non-quantized matmul kernel: 3-5x slower than Metal (mel STFT/mel-filter matmuls, Parakeet joint/decoder matmuls).
2. Large-array reductions (mx.sum 4 GB/s; per-token LogSumExp over 248k logits).
3. qmm at M = 2..4 (macOS 2-3x faster) and M >= 32 (macOS 1.2-1.4x faster); the N=16 floor is a Linux coopmat property (H31-H40 negatives).
4. Per dependent tiny dispatch: GPU side 4.3 vs 1.7 us, kernel-internal latency (rms_norm 11 vs 4.4 us), host record 3x.
