# jwm1 Parakeet: GPU pre-warm + 1 GB buffer cache (2026-09-29)

mlx-omarchy origin/main 440889401 (CLI change), deployed on jwm1's live venv. Pins unchanged: transcript sha db501a8c0803..., status match in every run; Qwen decode64/128/256 and prefill digests identical (7fe6badf4d560e25, da5568eeb4b6a1c1, 828b55d6249d9679, ccb601895581d89f).

Why: the first GPU work after >= ~50 ms of GPU idle is ~+10 ms slower (a fixed cost, absorbed by any heavy burst issued just before it; macOS pays a comparable penalty on the same die, +105% on a 1 ms matmul). Parakeet's mel stage is the first real GPU work after the CPU-only decoder load. A background thread streams 1024x1024 f32 matmuls during that stage (results discarded) and is joined before mel. The warm-up outputs alone made the TDT chain ~10 ms slower (they evict the small buffers the chain reuses from the 32 MB buffer cache), so the Parakeet CLI also raises the cache limit to 1 GB (which is worth ~4 ms on TDT by itself).

| In-process warm, medians (ms), n=9 per arm | audio | decoder_load | mel | encoder_ane | tdt | detok | total |
|---|---:|---:|---:|---:|---:|---:|---:|
| old behaviour (PRE-WARM=off, CACHE_MB=0) | 4.1 | 42.6 | 29.6 | 140.2 | 144.3 | 22.8 | 383.8 |
| new default | 2.9 | 41.3 | 19.4 | 139.9 | 131.8 | 22.8 | 358.6 |
| live venv after deployment (n=6) | 2.9 | 41.7 | 19.5 | 139.7 | 133.2 | 23.6 | 360.6 |

Stage-matched vs the paired macOS stages (mel 14, encoder ~135-138, decode ~120 = 272 ms, receipts/2026-09-29-jwm1-parakeet-corpus): Linux mel + encoder + TDT = 292.4 ms, 0.930x (was 0.886x). Still a loss on every stage.

Also measured (kept off): warm during the ANE wait (no gain, +2.3 ms contention on encoder_ane); constant early submit; buffer-cache-only changes for Qwen (no decode/prefill/TTFT effect). Switches: `MLX_OMARCHY_PK_PREWARM=off`, `MLX_OMARCHY_PK_CACHE_MB=<n>` (0 keeps the MLX default). Not measured: GPU energy of the ~45 ms warm-up per transcription (no wattmeter).
