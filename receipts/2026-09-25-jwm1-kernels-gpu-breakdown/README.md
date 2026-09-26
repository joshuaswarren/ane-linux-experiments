# jwm1 (T8103) GPU kernel breakdown + mel-DFT landing (2026-09-25)

Owner: Jwm1Kernels. Host: jwm1 (m1-host, T8103, G13G B1), ICD honeykrisp
`7faf04c` (`/usr/local/lib/libvulkan_asahi.so.7faf04c`). Installed stack:
`/var/tmp/jwm1-parity3-venv`, wheel after landing
`0.32.3.dev202609252026+7c0bd851` (before: `dev202609252152+bfe2ddc`).

## 1. Per-kernel GPU time breakdown (Vulkan timestamps per dispatch)

Instrument: mlx-omarchy built-in GPU profiler
(`-DMLX_OMARCHY_GPU_PROFILING=ON`, `MLX_OMARCHY_GPU_PROFILE=<path>`), a
build-time-gated per-dispatch `vkCmdWriteTimestamp` pair. Raw NDJSON
profiles were run-ephemeral; the ranked results below are the receipt.
Rooflines (measured on this device, `fma-ceiling/verdict.json`): f32 FMA
2303 GFLOP/s sustained, fp16 packed 4736 GFLOP/s; LPDDR4X 68.25 GB/s
nominal. Chains/window kernels measured 52-54 GB/s effective = the
practical bandwidth ceiling (~79% of nominal).

### One mel chunk (3001x512 frames, 10 reps; 62 dispatches/rep so
profiling overhead is negligible; GPU busy = wall, both ~22 ms pre-change)

| kernel | WGs | per rep | avg | % of wall | achieved |
|---|---:|---:|---:|---:|---|
| DFT radix-4 DIF (`parakeet_vdsp_radix4_dif_f32`) | 3001 | 11.36 ms | 11.4 ms | 51% | 1.1 GB/s, ~2 GFLOP/s — latency-bound |
| mel projection pair (`parakeet_mel_dot_log_f32`) | 1501 x2 | 7.74 ms | 3.87 ms | 35% | ~3.9 GB/s |
| per-frame stats | 1 | 1.65 ms | | 7% | |
| frames (preemph+window) | 6002 | 0.89 ms | | 4% | |
| normalize | 3013 | 0.62 ms | | 3% | |

### One TDT slot (192 slots per fixture run; 6 dispatches/slot, 1 submit
per ~64-slot chunk; per-slot GPU busy 728 us ~= wall/slot)

| kernel | WGs | per slot | achieved |
|---|---:|---:|---|
| chains LSTM x2 (gx=100) | 100 | 247 us | 6.55 MB weights/layer -> ~54 GB/s = 79% of nominal BW |
| window joint (gx=33) | 33 | 199 us | 10.5 MB joint -> ~52.8 GB/s = 77% |
| fold (grid 1) | 1 | 93 us | trivial work; = dependent-dispatch turnaround |
| fold_proj (grid 1) | 1 | 94 us | trivial work; = turnaround |
| control (grid 1) | 1 | 94 us | argmax reduce + turnaround |

Isolation proof: dispatching fold/chains back-to-back with no data
dependency gives 1.5-1.8 us marginal (`raw` profiles, kexp2); the ~93 us
grid-1 in-chain cost is serial dependency turnaround, not kernel
execution. Kernel-fusion of the grid-1 trio is therefore the wrong lever
(single-workgroup fusion already falsified 4.7x slower,
`agent/jwm1-parity10-tdt`); the lever is per-CS turnaround (mesa) or
bandwidth on chains/window (52->65+ GB/s would save ~90 us/slot).

### One decode token (contract shape; 1 submit/token; 891 dispatches)

Top items by total profiled time; ground truth from unprofiled
microbenches (a 262144-element fused multiply costs 1.1-1.3 us; the
profiled 330-410 us per dispatch is profiler overhead, ~50 us/dispatch):

| family | per token | real cost | note |
|---|---:|---:|---|
| QMM GEMV/GEMM sweep (q/k/v/o, mlp, lm_head) | ~370 | dominates | ~1.15 GB weights/token -> ~45 GB/s effective (66% of nominal BW); macOS 21.25 ms/token implies ~54 GB/s (79%) |
| GDN step elementwise (`Compiled*Broadcast*Multiply`, n=262144 = state 16x128x128) | 90 | ~0.12 ms | state update runs the `gated_delta_ops` fallback because `mx.metal.is_available()` is False on the Vulkan build |
| Sum reductions (kv_mem, y) | 36 | ~2.3 ms profiled, ~0.05 ms real | same fallback |
| RMSNorm + small elementwise | ~395 | ~0.3 ms | |

Decode is bandwidth-bound in the qmm sweep; the elementwise flood is
dispatch-count noise, not compute. Cutting it (next item) does not move
the rate.

### One prefill-512 step

146,375 dispatches captured. The pure prefill leg is one large batched
QMM sweep (gx=7760, n=127139840, 427 ms profiled) plus the compiled
elementwise flood; ttft-leg segments repeat per chunk
(QMM gx=192/64 + ~1500 elementwise). No prefill lever landed; see
`raw/contract-*.json` for rates.

## 2. Levers measured (all bit-exact requirements enforced)

| lever | verdict | evidence |
|---|---|---|
| mel DFT: 2 frames per 128-lane WG | **LANDED** — bit-exact (3001/2999/2048 frames bitwise vs previous kernel), mel stage 22.06 -> 19.36 ms median; mlx-omarchy main `7c0bd851` | `raw/gates-summary.txt`, bitwise harness in kexp1 |
| mel DFT: 4/8 frames per WG | bit-exact but slower (9.17/9.07 vs 8.67 ms) | kexp1 |
| GDN fused kernel (`mx.metal.is_available()` gate) | bit-exact on decode digest (`c2ff5650379ab4d2` both arms, 384-token prompt x 32 tokens) but NO speed win (35.16 vs 34.26 tok/s) — not landed | `/tmp/gdn_ab.py` arms in session log |
| TDT grid-1 fusion | falsified before this lane (4.7x slower); breakdown shows why (cost is turnaround, not kernel) | Jwm1Submit2 receipt + this breakdown |
| mesa barrier set: 7faf04c + 41ccf96cc59/371cdd80c20/cc489fa17f9 (usc-barrier-study) on /tmp ICD | TDT chain 155.6 -> 148.8 ms median (-4.4%, high variance) — not landed; handed to the mesa lane | A/B arms in session log, `/tmp/mesa-ab.icd.json` |
| decode elementwise fold / GEMV concat fusion (T6001 class) | pointless on T8103: elementwise is 0.1-0.2 ms/token of real work; T6001 dispatch reductions already in installed bfe2ddc | this breakdown |

## 3. Gates on the installed result (post-landing, one GPU window)

Pins (10 prompts, greedy, 32 new tokens, prefill 512, warmup 3; digest =
ordered_records_sha256 prefix):

| pass | digest | expected | verdict |
|---|---|---|---|
| 1 | `486872c410629f1d` | identical | PASS |
| 3 | `bc519c03c4ef5fd1` | identical | PASS |
| 10 | `dbf704971617fdfc` | identical | PASS |

Contract vs macOS (this window; evening box, ANE lanes active — walls are
noisier than the morning receipt, digests are the hard gate):

| metric | this window | morning receipt | macOS | ratio (vs macOS) |
|---|---:|---:|---:|---:|
| decode tok/s | 37.38 | 39.17 | 47.05 | 0.79x FAIL |
| prefill-512 tok/s | 238.93 | 236.72 | 343.73 | 0.70x FAIL |
| ttft tok/s | 50.19 | 57.11 | 99.12 | 0.51x FAIL |

Parakeet (installed stack, stock ane module `5a22ee3`):

- mel stage wall: 19.36 ms median (was 22.06) — the landing.
- contract3 full pipeline: `all_gates: true` (transcript/hidden/cell
  bitwise vs golden), medians: encoder_ane 182.6, mel_frontend 20.5,
  tdt_decode 204.0, total 415.1 ms (in-process protocol).
- corpus gate 6/6 PASS rc=0, emissions 104/0/0/28/101/104 — identical
  pattern to the receipted battery, tok/frm/dur/hidden/cell all true.

Installed state verified: wheel
`mlx_omarchy-0.32.3.dev202609252026+7c0bd851-cp314-cp314-linux_aarch64`
force-reinstalled into `/var/tmp/jwm1-parity3-venv` immediately before
the gate window; ICD untouched at `7faf04c`; no reboot; M2 catcher
untouched.

## 4. Merge record

- mlx-omarchy: `7c0bd851` on `origin/main` (bfe2ddc..7c0bd85), direct
  merge per program rules, authored as Joshua Warren.
- ane-linux-experiments: this receipt via worktree branch
  `agent/jwm1-kernels-dft` -> `origin/main`.

## 5. Handoff notes for the next lane

1. TDT (largest remaining Parakeet item): attack per-CS turnaround
   (fold/fold_proj/control 93 us each of pure latency) and
   chains/window bandwidth (77-79% of nominal). The barrier-set A/B ICD
   remains at `/tmp/mesa-ab.icd.json` on jwm1 (base 7faf04c + the three
   usc-barrier-study commits) for repeat trials.
2. Decode: the qmm sweep at 66% of nominal bandwidth is the whole gap to
   macOS's ~79%; the T6001 Q4-GEMV tiling line (3232b1f5, 1faf7f00) is
   the reference work. The GDN fused kernel is bit-exact and free to
   adopt (`mx.metal.is_available()` gate) but bought nothing measured.
3. mel projection pair (7.7 ms, ~3.9 GB/s) is the next mel item.
4. `[rtmod]` fprintf-per-submit hygiene is env-set on jwm1
   (`MLX_OMARCHY_TRACE_DISPATCH` in the environment): ~0.1% of wall and
   noisy logs; consider unsetting at the shell level.
