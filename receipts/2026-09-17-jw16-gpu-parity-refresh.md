# jw16 M1 Max GPU Q4 decode/prefill refresh — v0.6.1 release wheel vs native Metal

Date: 2026-09-17

## Verdict

Same-protocol Q4 decode/prefill on `jw16mbp1-linux` (Apple M1 Max, Honeykrisp, GPU not ANE) on the v0.6.1 release wheel completed with pinned generated-ID identity on both legs. Decode on the 30/32-token leg is 66.43% of native M1 Max Metal (190.6298 vs 286.96 tok/s), the 1053/32-token decode is 46.06% of native (130.7045 vs 283.79 tok/s), short-prompt prefill is 30.29% of native (459.7341 vs 1518 tok/s), and long-context prefill is 47.77% of native (3844.6236 vs 8048 tok/s).

Versus the 2026-09-14 rerun (`receipts/2026-09-14-jw16-gpu-parity-rerun.md`, on `mlx_omarchy==0.32.2.dev202609122106+b41e2b74`):

| Metric | 2026-09-17 v0.6.1 wheel | 2026-09-14 rerun (b41e2b74) | delta |
| --- | ---: | ---: | ---: |
| Q4 short decode, 30/32 | 190.6298 tok/s (66.43%) | 147.2815 tok/s (51.32%) | **+29.45%** |
| Q4 short prefill, 30 tokens | 459.7341 tok/s (30.29%) | 199.8427 tok/s (13.16%) | **+130.06%** |
| Q4 1K-context decode, 1053/32 | 130.7045 tok/s (46.06%) | 87.4478 tok/s (30.79%) | **+49.48%** |
| Q4 1K-context prefill, 1053 tokens | 3844.6236 tok/s (47.77%) | 2072.0272 tok/s (25.75%) | **+85.55%** |
| fp16 2048² matmul+add median | 8.622678 ms, 1.9928918232 TFLOPS | 8.680269 ms, 1.9796694651 TFLOPS | **−0.66% (faster), +0.668% TFLOPS** |

The 2048² fp16 `matmul(a,b)+bias` median sits inside the 09-14 same-protocol jw16 medians (8.680269 ms / 8.717198 ms / 8.712577 ms) at the fast end. The decode and prefill gaps to native are halved to two-thirds; prefill has now broken past 100% gain vs the 09-14 baseline.

This is one locked battery: short + ctx + matmul, fresh subprocess per Q4 leg, single `flock` hold on `/tmp/m1-gpu.lock` for the whole run. Not a thermally soaked multi-repeat median. AesPlaneStride holds jwm1 separate.

## Identity

- Receipt checkout (local mlx-omarchy HEAD): unchanged vs the 09-14 rerun.
- Measured source commit (installed wheel): `b8e5300` (release `0.32.2.dev202609170611+b8e5300`).
- Installed interpreter: `/var/tmp/jw16-v061-parity/v061-venv/bin/python` (Python 3.14.7).
- Installed wheel: `mlx-omarchy==0.32.2.dev202609170611+b8e5300` (release tag **v0.6.1**).
- Wheel file: `mlx_omarchy-0.32.2.dev202609170611+b8e5300-cp314-cp314-linux_aarch64.whl`, SHA-256 `70643b6161c126c4a661725b74653cd1be69eab14bfbf630a42620384406515c` (matches the assignment's pinned upstream release asset exactly).
- Source: GitHub release `joshuaswarren/mlx-omarchy` tag `v0.6.1`, asset `mlx_omarchy-0.32.2.dev202609170611%2Bb8e5300-cp314-cp314-linux_aarch64.whl`, created 2026-09-17T06:11Z, downloaded 2026-09-17 01:23Z local to `/var/tmp/v061-release/`.
- Provenance: `verified=match`; engine reports `core.cpython-314-aarch64-linux-gnu.so=sha256:4ad850da16c300ea` (same as 09-14 rerun/refresh) and `libmlx.so=sha256:9a72c3b84c74e7b3` (refresh of the 09-14 release's `f2d45e601f05dd22`).
- Harness tree: `/var/tmp/qmm-tilem` (vendored from upstream); HEAD unchanged from 09-14 (`3db3cb9a1d6d21f5ea1e002e93a8452b03e2b84f`).
- `scripts/bench_decode.py` SHA-256: `f5062d88f34b0845c1e59b0b35d2e33ae02180f636a0f65c543a4366ec2bef7f` — matches the 09-14 rerun exactly.
- `scripts/bench_matrix.json` SHA-256: `df8eb9f3ed84182604379b7cde070ade706bfe590fbf83a35b1877cfaf43f258` — matches the 09-14 rerun exactly.
- mlx-lm: `0.31.3`.
- Host: `jw16mbp1-linux`; architecture: `aarch64`; chip/GPU: Apple M1 Max T6001, `Apple M1 Max (G13C C0)`.
- Kernel: `7.1.6-1-1-ARCH` (PREEMPT_DYNAMIC, 2026-08-08).
- Mesa package: `mesa-honeykrisp-omarchy 26.3.0.devel.hk5deac1c-2` (Honeykrisp Vulkan stack).
- Vulkan ICD: the deployed `mesa-honeykrisp-omarchy-26.3.0.devel.hk5deac1c-2` wheel (last Term A deploy).
- Runtime device: `Device(gpu, 0)`; both Q4 legs reported `device=Apple M1 Max (G13C C0)`.
- Model: `mlx-community/Qwen2.5-0.5B-Instruct-4bit` at revision `a5339a4131f135d0fdc6a5c8b5bbed2753bbe0f3`.
- Model config SHA-256: `b045e57ea90b8f1b35f89f954b176a5c1faa02bd0af2c89bcec191239d66cef4`.
- Safetensors index SHA-256: `54001cb4c11197119c206dde28e7be08e5872aab6c6d271aed339ec77e84f870`.

Power before, after each Q4 leg, and after the matmul:

```text
/sys/class/power_supply/macsmc-ac/online=1
/sys/class/power_supply/macsmc-battery/online= status=Full
/sys/class/power_supply/tps6598x-source-psy-0-0038/online=0
/sys/class/power_supply/tps6598x-source-psy-0-003a/online=1
/sys/class/power_supply/tps6598x-source-psy-0-003b/online=0
/sys/class/power_supply/tps6598x-source-psy-0-003f/online=0
```

## Protocol

Identical to `receipts/2026-09-14-jw16-gpu-parity-rerun.md` and `receipts/2026-09-14-jw16-gpu-parity-refresh.md`:

- `MLX_DISABLE_COMPILE=1`, `HF_HUB_OFFLINE=1`.
- Greedy `temp=0.0`, `seed=0`, EOS suppressed, 32 requested tokens, 4 warmup tokens, decode over 31 inter-token gaps.
- `bench_matrix.prompt_text` for `short` (2 UTF-8 bytes → 30 chat-template tokens) and `ctx1024` (4759 UTF-8 bytes → 1053 chat-template tokens via the deterministic `numbered` template with 20 entries).
- Fresh subprocess per Q4 leg; outer battery process held `/tmp/m1-gpu.lock` inode 12 across all 3 legs; nested `flock -n` exit 1 during measurement.
- The 2048² fp16 `matmul(a,b)+bias` ran inside the same flock with seed 20260913, 3 warmups, 20 measured synchronized `matmul(a,b)+row-broadcast-bias` evaluations, median ms, TFLOPS from `(2*N^3+N^2)/elapsed`.

Native M1 Max divisors are the assignment roundings of the 2026-09-10 16m1mbp 12-rep Metal matrix: precise medians 286.96 / 283.79 decode and 1517.55 / 8048.42 prefill. jwm1 Linux numbers below come from `receipts/2026-09-13-jwm1-perf-parity.md` and were not remeasured here; AnePlaneStride owns that arm.

Battery driver: `/tmp/run-jw16-v061.sh` on the host; output captured at `/var/tmp/jw16-v061-parity/output/{short,ctx1053,matmul,identity-summary,lock,started,finished,host,kernel,lock-pre}.txt`.

## Results

JSON `decode_tps` / `prefill_tps` are the quoted rates.

| Metric | jw16 v0.6.1 wheel | native M1 Max Metal | jw16/native | jw16 09-14 rerun (b41e2b74) | delta vs rerun | jwm1 Linux M1 (09-13) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Q4 short decode, 30/32 | 190.6298 tok/s | 286.96 tok/s | 66.43% | 147.2815 tok/s | **+29.45%** | 107.3405 tok/s |
| Q4 short prefill, 30 tokens | 459.7341 tok/s | 1518 tok/s | 30.29% | 199.8427 tok/s | **+130.06%** | 322.9687 tok/s |
| Q4 1K-context decode, 1053/32 | 130.7045 tok/s | 283.79 tok/s | 46.06% | 87.4478 tok/s | **+49.48%** | 96.5263 tok/s |
| Q4 1K-context prefill, 1053 tokens | 3844.6236 tok/s | 8048 tok/s | 47.77% | 2072.0272 tok/s | **+85.55%** | 1112.2049 tok/s |
| fp16 2048² matmul+add median | 8.622678 ms, 1.9928918232 TFLOPS | — | — | 8.680269 ms, 1.9796694651 TFLOPS | **−0.66% (faster)** | 31.589904 ms, 0.5439732735 TFLOPS |

Both Q4 legs produced the pinned native generated-ID digests:

```text
short:   7fd25a869ff21678, n=32, first=9707,0,2585 last=646,387,7881
1053:    7da83f06ec9f001d, n=32, first=13060,498,369 last=3897,553,279
```

### Raw bench_decode stdout

Short:

```text
provenance: mlx-omarchy 0.32.2.dev202609170611+b8e5300 mx=0.32.2.dev202609170611+b8e5300 verified=match harness=23102851-dirty core.cpython-314-aarch64-linux-gnu.so=sha256:4ad850da16c300ea libmlx.so=sha256:9a72c3b84c74e7b3
decode 190.63 tok/s over 31 tokens (32 requested, EOS suppressed)
prefill 0.065s (reported separately, excluded from decode)
prompt_tokens 30
decode mean per-token 5.2 ms
generated_ids sha256:7fd25a869ff21678 n=32 first=9707,0,2585 last=646,387,7881
{"decode_tps": 190.6298, "device": "Apple M1 Max (G13C C0)", "engine": "bench_decode", "generated": 32, "ids_first": [9707, 0, 2585], "ids_last": [646, 387, 7881], "ids_sha256_16": "7fd25a869ff21678", "prefill_s": 0.065255, "prefill_tps": 459.7341, "prompt_tokens": 30}
```

1053:

```text
provenance: mlx-omarchy 0.32.2.dev202609170611+b8e5300 mx=0.32.2.dev202609170611+b8e5300 verified=match harness=23102851-dirty core.cpython-314-aarch64-linux-gnu.so=sha256:4ad850da16c300ea libmlx.so=sha256:9a72c3b84c74e7b3
decode 130.70 tok/s over 31 tokens (32 requested, EOS suppressed)
prefill 0.274s (reported separately, excluded from decode)
prompt_tokens 1053
decode mean per-token 7.7 ms
generated_ids sha256:7da83f06ec9f001d n=32 first=13060,498,369 last=3897,553,279
{"decode_tps": 130.7045, "device": "Apple M1 Max (G13C C0)", "engine": "bench_decode", "generated": 32, "ids_first": [13060, 498, 369], "ids_last": [3897, 553, 279], "ids_sha256_16": "7da83f06ec9f001d", "prefill_s": 0.273889, "prefill_tps": 3844.6236, "prompt_tokens": 1053}
```

### Matmul samples

Warmups, ms: `35.942133, 9.200743, 8.534949`

Measured, ms: `8.398823, 8.562532, 8.641490, 8.247864, 8.271322, 8.645740, 8.243281, 8.531907, 8.557323, 8.632615, 8.185531, 8.652199, 8.612740, 8.708532, 8.672157, 8.729574, 8.285947, 8.738408, 8.689407, 8.697324`

Median: `8.622678` ms. TFLOPS: `1.9928918232226`.

2x2 sanity matmul(A, A) result on the verification `[[20.0, 21.0], [43.5, 49.5]]` inputs produced a non-trivial bounded output `[[1314.0, 1460.0], [3024.0, 3364.0]]`, confirming fp16 weights landed on `mx.gpu` and `matmul` ran on the Honeykrisp Vulkan path.

## Lock and hardware safety

- Lock inode 12 before, during, and after the battery.
- Nested nonblocking flock rejected (`exit 1`) while the battery ran.
- After the battery: `flock -n /tmp/m1-gpu.lock` succeeded, inode 12 still present, lock file unlinked-free.
- `llm-inference.service`: stopped (sudo `systemctl stop`) before the battery — paused, not killed — and restarted (`sudo systemctl start`) immediately after; `systemctl is-active` reports `active` post-restart. The Llama server leg was never used for the measurement; the lock was acquired directly.
- No ANE access, module load/unload, device-tree change, llama enable/disable (aside from the systemd restart), SET 0xf, `1x896`, or reboot.
- No python, mlx, or bench process survived after the battery (only `jwm1-netconsole-receiver.py` and a transient bash subshell were observable).
- jwm1 untouched; AnePlaneStride holds that host for separate ANE work. No `63c1d3cf` write.

## Not claimed

- This is one locked battery; not a thermally soaked multi-rep median. Thermal soak separately, if desired, requires multiple fresh flocks with explicit cool-downs between — not in this receipt.
- The Q4 matmul TFLOPS gain (+0.668%) over the 09-14 rerun is within the same-protocol jitter band on jw16 (the three 09-14 medians span 8.680269 to 8.717198 ms); the headline decode/prefill deltas are the load-bearing result here.
- These rates hold the today's-ropepair-trio + SwiGLU-store-epilogue + QmmPrefillCoopmatF16 + tile-M occupancy floor + SPIR-V disk cache + `mesa-honeykrisp-omarchy-26.3.0.devel.hk5deac1c-2` stack. They are not portable to earlier wheels without re-running.
- Hardware/sensor-saturation check (peak GPU power, thermals during the run): not recorded in this receipt. The 09-14 protocol did not record them either; parity is what is being tracked here, not absolute peak.
