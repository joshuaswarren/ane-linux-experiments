# jwm1 2026-09-30: paired fragment loads (AGX_HWMAT_VEC2) default-on -> prefill +9.4%, bit-exact

Source: mesa-1 `asahi/hwmat-vec2-on` (5b8df41ec94, one line on the production lineage commit 7faf04c065c: `getenv("AGX_HWMAT_VEC2_OFF") == NULL` replaces the opt-in gate in agx_nir_lower_simdmat.c). The vec2 path already existed as an env-gated experiment from the earlier llama.cpp work ("perf-neutral alone on f16 mul_mm"); on our f32-fragment qwen qmm coopmat kernel it is not neutral.

Installed on jwm1: /usr/local/lib/libvulkan_asahi.so.7faf04c-vec2, /usr/share/vulkan/icd.d/asahi_icd.json repointed. Rollback: `sudo cp /usr/share/vulkan/icd.d/asahi_icd.json.honeykrisp-7faf04c.active /usr/share/vulkan/icd.d/asahi_icd.json` (the original library remains). One-time cost: the first Parakeet run after the swap took 14 s in mel (shader cache regenerates for the new driver build id); subsequent runs are normal.

## Evidence
- qmm-prefill-bench (mismatch 0, FNV output sums equal control, gate + down, min of 6 processes): gate 9.60 -> 8.70 ms (-9.4%), down 13.26 -> 10.37 ms (-21.8%).
- In-model paired A/B, driver-only difference, fresh processes, interleaved: prefill512 279.9 -> 307.1 tok/s (+9.46%, n=3), prefill2048 275.9 -> 301.8 (+9.39%, n=2), decode256 41.31 -> 41.39 (+0.19%); digests identical.
- Full n=5 ledger battery on the installed default path (one lock hold): all six digests equal the pins (decode64 7fe6badf4d560e25, decode128 da5568eeb4b6a1c1, decode256 828b55d6249d9679, prefill ccb601895581d89f at 512/1024/2048).
- Parakeet product path (pk-sess-driver, 4 runs): status match, transcript sha db501a8c0803..., runs 2-4 mel 11.8 ms / encoder 139.5-140.3 ms / TDT 110.4-120.0 ms / total 325.6-343.9 ms (unchanged).
- Measurement pitfalls found: the Vulkan loader scans EVERY *.json in /usr/share/vulkan/icd.d (an extra ICD file silently made the "control" arm run the candidate) and ignores non-.json names; candidate ICDs must live outside that directory.

## Ledger vs jwm1 macOS (paired same-die cells, n=5 each, all LOSSES)
| Cell | Linux (median, range) | macOS | Ratio |
|---|---|---:|---:|
| decode 64 | 41.80 (41.77-41.91) tok/s | 49.36 | 0.847 |
| decode 128 | 41.44 (41.39-41.49) | 49.26 | 0.841 |
| decode 256 | 41.38 (41.34-41.39) | 49.33 | 0.839 |
| prefill 512 | 307.23 (307.00-307.42) | 345.31 | 0.890 |
| prefill 1024 | 306.51 (300.98-308.12) | 345.76 | 0.886 |
| prefill 2048 | 302.14 (298.72-302.37) | 341.80 | 0.884 |
| TTFT | 0.160 s (last measured) | 0.1248 | 1.28x |
| encoder ANE | 138.0-140 ms | 113.27 | 0.81 |
Prefill went 0.74 -> 0.80 (FULL_N, mlx-omarchy b612e4f63) -> 0.89 (this change) in one day. Remaining prefill gap: the address-arithmetic iadds around every fragment access and half-rate scalar fp32 dequant; next: extend the vec2 idea to the B fragments (col-major, strided pairs), hoist the row-address computation out of the K loop, and the dequant split (H72).
