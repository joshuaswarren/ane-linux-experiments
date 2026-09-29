# Addendum 2026-10-01: constant-delta shared address fold on top of vec2 (prefill 0.89 -> 0.90-0.91x)

mesa-1 asahi/hwmat-vec2-on f04cf2e97d0 (installed on jwm1 as /usr/local/lib/libvulkan_asahi.so.7faf04c-vec2fold; rollback: copy asahi_icd.json.honeykrisp-7faf04c.active over asahi_icd.json).

Hardware facts measured with the qmm-prefill-bench --dump probes: lload/lstore index immediate = +4 elements of the access type per unit; base register is a byte address; index add does not wrap at 16 bits. The folding pass groups shared accesses per block by their underlying value, keeps the lowest constant in one shared base and encodes the deltas as immediates.

Correctness evidence: qmm harness output sums equal fold-off; Parakeet product path status match on 4 runs (the first, whole-constant version diverged the mel FFT shader - see notebook H81 for the diagnosis, the gate that caught it, and the shader-cache-key pitfall for env-gated compiler behavior).

Ledger on the installed driver (n=5 each, all digests pinned; macOS paired cells):
| Cell | Linux | macOS | Ratio |
|---|---:|---:|---:|
| decode 64 / 128 / 256 | 41.81 / 41.49 / 41.40 | 49.36 / 49.26 / 49.33 | 0.847 / 0.842 / 0.839 (LOSS) |
| prefill 512 / 1024 / 2048 | 313.36 / 314.15 / 307.21 | 345.31 / 345.76 / 341.80 | 0.907 / 0.909 / 0.899 (LOSS) |

TTFT on the installed driver (n=5 passes x 5 prompts, medians per pass 0.1477-0.1575 s): 0.1547 s vs macOS 0.1248 s = 1.24x latency (LOSS; was 1.28x).

## H82 (negative): CDM barrier bits and workgroup barriers are not the dependent-dispatch floor
Variants built from the production lineage with only libagx_dgc.h changed: {4,5,6,8} and {5,6,8} hold every digest (decode64/256, prefill512) but are speed-neutral (d64 41.84 / 41.63 vs 41.53 tok/s base, d256 41.48 / 41.31 vs 41.42, within run noise); {6,8} diverges (decode digests changed) - at least one of the cache-maintenance bits is required for dependent chains. A 1-workgroup norm-like micro-kernel shows the same ~10-12 us per chained dispatch with 9 barriers, 3 barriers, or none, so cheaper kernel bodies cannot close the decode gap: 441 dependent dispatches per token x ~6 us above macOS's 3.7 us floor ~ 2.6 ms of the 3.8 ms/token gap. Remaining decode levers: fewer dispatches (fusion into existing kernels) or a lower launch/dependency floor (driver level; the dependency-tracked CDM barrier was tried on T6001 and failed its rare-race gate).

## Addendum 2 (2026-10-01): compute shaders skip the pre-RA pressure scheduler (H84), post-RA scheduler and norm batching closed (H85, H83)
mesa-1 asahi/hwmat-vec2-on 283bf35c055 installed on jwm1 (/usr/local/lib/libvulkan_asahi.so.7faf04c-vec2fold-nosched). `agx_pressure_schedule` moves each load next to its use, serializing the memory round trips of small compute kernels; compute shaders now skip it (AGX_SCHED_COMPUTE=1 restores). Paired A/B vs the previous driver: decode64/128/256 +1.36 / +1.78 / +1.67%, prefill -0.4..+1.0% (noise), every digest pinned, Parakeet 5 runs match.
Closed negatives: H85 post-RA latency scheduler port (exact; qmm harness 3.5-5.2% slower, decode +-0.1%); H83 RMSNorm load batching / 32-bit word view (no gain even with the scheduler off; the word-view variant was not exact at d64); H82 CDM barrier bits (neutral).
Also found: other lanes' commits on mlx-omarchy origin/main (GDN state tile through shared memory, logsumexp/argreduce prefetch) tuned on the M1 Max cost the M1 -3.8% decode with digests pinned (reported to the jw16 agent); always A/B against a control from the same base.

Ledger on the installed driver (n=5 each, digests pinned; macOS paired cells):
| Cell | Linux | macOS | Ratio |
|---|---:|---:|---:|
| decode 64 / 128 / 256 | 42.43 / 42.10 / 42.05 tok/s | 49.36 / 49.26 / 49.33 | 0.860 / 0.855 / 0.852 (LOSS) |
| prefill 512 / 1024 / 2048 | 309.67 / 311.69 / 306.06 | 345.31 / 345.76 / 341.80 | 0.897 / 0.901 / 0.895 (LOSS) |
| TTFT | 0.1495 s | 0.1248 s | 1.20x latency (LOSS) |
