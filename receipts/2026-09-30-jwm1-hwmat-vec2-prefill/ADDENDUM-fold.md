# Addendum 2026-10-01: constant-delta shared address fold on top of vec2 (prefill 0.89 -> 0.90-0.91x)

mesa-1 asahi/hwmat-vec2-on f04cf2e97d0 (installed on jwm1 as /usr/local/lib/libvulkan_asahi.so.7faf04c-vec2fold; rollback: copy asahi_icd.json.honeykrisp-7faf04c.active over asahi_icd.json).

Hardware facts measured with the qmm-prefill-bench --dump probes: lload/lstore index immediate = +4 elements of the access type per unit; base register is a byte address; index add does not wrap at 16 bits. The folding pass groups shared accesses per block by their underlying value, keeps the lowest constant in one shared base and encodes the deltas as immediates.

Correctness evidence: qmm harness output sums equal fold-off; Parakeet product path status match on 4 runs (the first, whole-constant version diverged the mel FFT shader - see notebook H81 for the diagnosis, the gate that caught it, and the shader-cache-key pitfall for env-gated compiler behavior).

Ledger on the installed driver (n=5 each, all digests pinned; macOS paired cells):
| Cell | Linux | macOS | Ratio |
|---|---:|---:|---:|
| decode 64 / 128 / 256 | 41.81 / 41.49 / 41.40 | 49.36 / 49.26 / 49.33 | 0.847 / 0.842 / 0.839 (LOSS) |
| prefill 512 / 1024 / 2048 | 313.36 / 314.15 / 307.21 | 345.31 / 345.76 / 341.80 | 0.907 / 0.909 / 0.899 (LOSS) |
