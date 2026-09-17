# jwm1 GPU Q4 parity refresh — v0.6.3 release wheel vs native Metal

Date: 2026-09-17

## Verdict

Same-protocol Q4 decode/prefill on `jwm1-linux` (Apple M1 T8103, Honeykrisp, GPU not ANE) on the **v0.6.3 release wheel** completed with pinned generated-ID identity on both Q4 legs. Short-prompt decode is 77.93% of native base-M1 Metal (117.34 vs 150.57 tok/s), 1053/32 decode is 75.28% of native (105.68 vs 140.38 tok/s), short-prompt prefill is 132.89% of native (390.829 vs 294.10 tok/s, still faster than native), and 1053-token prefill is 60.09% of native (1106.151 vs 1840.90 tok/s).

Versus the 2026-09-14 rerun (`mlx-omarchy` `receipts/2026-09-14-jwm1-gpu-parity-rerun.md`, on `mlx_omarchy==0.32.2.dev202609122355+b41e2b74`):

| Metric | 2026-09-17 v0.6.3 wheel | 2026-09-14 rerun (b41e2b74) | delta |
| --- | ---: | ---: | ---: |
| Q4 short decode, 30/32 | 117.34 tok/s (77.93%) | 107.285 tok/s (71.25%) | **+9.37%** |
| Q4 short prefill, 30 tokens | 390.829 tok/s (132.89%) | 331.0513 tok/s (112.56%) | **+18.06%** |
| Q4 1K-context decode, 1053/32 | 105.68 tok/s (75.28%) | 95.0352 tok/s (67.70%) | **+11.20%** |
| Q4 1K-context prefill, 1053 tokens | 1106.151 tok/s (60.09%) | 1111.5836 tok/s (60.38%) | **−0.49%** |
| fp16 2048² matmul+add median | 31.378557 ms, 0.547637148770098 TFLOPS | (not run 09-14; 09-13 perf-parity 31.589904 ms, 0.5439732735 TFLOPS) | **−0.67% (faster) vs 09-13** |

The decode and short-prefill gains are consistent with the Honeykrisp CDM barrier trim (`mesa-honeykrisp-omarchy 26.3.0.devel.hkf96e090-2`, measured +6.32% ctx1053 / +2.90% short in its own A/B), the rope-pair trio + SwiGLU store epilogue (201 `vk_compute_dispatches`/token decode), and the ANE `map_mode=3` cached-mapping default (module `1fc2e02`). The 1053-token prefill is flat within jitter; its bottleneck (`QmmPrefillCoopmatF16`) is not what those changes targeted.

This is one locked battery: short + ctx runs (each run also covers the long 262-token leg; ctx4096 is explicit-selection and excluded), fresh subprocess per run, single `flock` hold on `/tmp/m1-gpu.lock` for the whole battery. Within-battery repeats: short decode 117.34 / 117.42 tok/s, ctx decode 105.68 / 107.17 tok/s. Not a thermally soaked multi-repeat median.

## Identity

- Measured wheel: **v0.6.3 release asset** `mlx_omarchy-0.32.2.dev202609171159+1ed1dab-cp314-cp314-linux_aarch64.whl`, SHA-256 `dcb84f7b196bf70c61c420d72f8fcf001bdbac92716b039f0cd6c8fcd08fe23d` — the GitHub release-URL bytes, already sha-asserted by the v0.6.3 gate (`ane-linux-experiments` `receipts/2026-09-17-v063-published.md`) and re-asserted before this battery.
- Installed wheel: `mlx-omarchy==0.32.2.dev202609171159+1ed1dab` (release tag **v0.6.3** = `1ed1dab6`).
- Interpreter: `/var/tmp/V063REL-venv/bin/python` (Python 3.14.7), mlx-lm `0.31.3`, wheel installed `--no-deps`.
- Host: `jwm1-linux`; `aarch64`; `nproc=8`; Apple M1 T8103, `Apple M1 (G13G B1)`.
- Kernel: `7.1.6-1-1-ARCH`.
- Mesa package: `mesa-honeykrisp-omarchy 26.3.0.devel.hkf96e090-2` (Honeykrisp Vulkan stack, CDM barrier trim).
- ANE module: `ane 1fc2e02` (srcversion `E1B035ACD965D9CB62F91AC`), loaded (`ane 65536 0 - Live`), `map_mode=3` (cached-mapping default).
- Harness tree: `/var/tmp/v062-wt` at `1ed1dab6` (dirty: untracked `build.log` only); provenance `harness=1ed1dab6-dirty`.
- `scripts/bench_decode.py` SHA-256: `f5062d88f34b0845c1e59b0b35d2e33ae02180f636a0f65c543a4366ec2bef7f` — matches the 09-14 rerun exactly.
- `scripts/bench_matrix.json` SHA-256: `df8eb9f3ed84182604379b7cde070ade706bfe590fbf83a35b1877cfaf43f258` — matches the 09-14 rerun exactly.
- Model: `mlx-community/Qwen2.5-0.5B-Instruct-4bit` snapshot `a5339a4131f135d0fdc6a5c8b5bbed2753bbe0f3` (HF cache), `HF_HUB_OFFLINE=1`, `MLX_DISABLE_COMPILE=1`.
- Runtime device: `Device(gpu, 0)`.
- Battery driver: `/var/tmp/run-jwm1-v063-parity.sh`; outputs under `/var/tmp/jwm1-v063-parity/` (`short.json`, `ctx.json`, `matmul.json`, `status`), stdout to files, not pipes.
- Battery window: started 2026-09-17T08:11:02-05:00, finished 08:11:56-05:00 (~54 s).
- Power: `macsmc-ac/online=1`, `macsmc-battery/status=Full` before and after.

## Protocol

Identical legs to the 09-14 rerun and the jw16 v0.6.1 refresh:

- `bench_matrix.py --mode run --select short-decode-32` and `--select longctx-1024-decode-32`, fresh subprocess each, one outer `flock -w 900 /tmp/m1-gpu.lock` hold for the whole battery (inode 35 before and after; nested `flock -n` returned 1 during the battery; lock-free after; never unlinked).
- Greedy `temp=0.0`, `seed=0`, EOS suppressed, 32 requested tokens, 4 warmup tokens, decode over 31 inter-token gaps; prefill quoted separately.
- `bench_matrix.prompt_text`: `short` = 2 UTF-8 bytes → 30 chat-template tokens; `ctx1024` = 4759 UTF-8 bytes → 1053 chat-template tokens.
- Provenance gate printed `verified=match` on every leg: `mlx-omarchy 0.32.2.dev202609171159+1ed1dab mx=0.32.2.dev202609171159+1ed1dab verified=match harness=1ed1dab6-dirty`.
- fp16 2048² `matmul(a,b)+bias` inside the same flock: GPU sanity 2x2 first, `mx.random.seed(20260913)`, 3 warmups discarded, 20 measured synchronized evaluations, median ms, TFLOPS from `(2*N^3+N^2)/elapsed`.
- Preflight honored: `/tmp/parakeet-gate.*` scratch cleaned, ≥3 GiB free on `/tmp` asserted (3 G) before starting.
- Native divisors (pinned, `native-2026-09-06-summary.json`): base-M1 **150.57** short decode / **140.38** ctx decode / **294.10** short prefill / **1840.90** ctx prefill tok/s.

## Results

| Metric | jwm1 Linux | Pinned native base-M1 | Linux/native | Delta vs 2026-09-14 rerun |
| --- | ---: | ---: | ---: | ---: |
| Q4 short decode, 30/32 | 117.34 tok/s | 150.57 tok/s | 77.9305% | +9.37% |
| Q4 short prefill, 30 tokens | 390.829 tok/s | 294.10 tok/s | 132.8898% | +18.06% |
| Q4 1K-context decode, 1053/32 | 105.68 tok/s | 140.38 tok/s | 75.2814% | +11.20% |
| Q4 1K-context prefill, 1053 tokens | 1106.151 tok/s | 1840.90 tok/s | 60.0875% | −0.49% |
| fp16 2048² matmul+add median | 31.378557 ms, 0.547637148770098 TFLOPS | — | — | −0.67% faster vs 2026-09-13 |

Pinned generated-ID digests matched on both Q4 legs:

```text
short:   7fd25a869ff21678, n=32, prompt_tokens=30
1053:    7da83f06ec9f001d, n=32, prompt_tokens=1053
```

(The 262-token `long` leg also ran inside each invocation; its digest `f873dc2bdd34c0fe` is recorded in the raw JSON but has no pinned divisor and is not a parity leg here.)

## Lock and hardware safety

- Lock inode 35 before, during (nested nonblocking flock rejected, rc=1), and after; battery ended `lock-free-after`; file never unlinked.
- No `deqp`/`cmshape2`/bench process was live at preflight; none survived after.
- `ane.ko` remained loaded; no ANE command, unload, reboot, 1x896, or SET write.
- jw16 untouched (its row was refreshed separately today from its own battery); no `63c1d3cf` write.

## Not claimed

- One locked battery, not a thermally soaked multi-repeat median. The within-battery repeats (short 117.34/117.42, ctx 105.68/107.17 tok/s) bound the jitter.
- The 1053-token prefill delta (−0.49%) is within the jitter band; the load-bearing deltas are decode and short prefill.
- Native base-M1 Metal divisors remain the pinned `native-2026-09-06-summary.json` values; macOS was not re-measured here.
- Hardware/sensor-saturation check (peak GPU power, thermals): not recorded, same as the prior protocol receipts.
