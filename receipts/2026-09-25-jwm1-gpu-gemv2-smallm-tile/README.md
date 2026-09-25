# 2026-09-25 — jwm1 (T8103) GPU levers: two-row Q4 GEMV landed (+4.3% decode), small-M coopmat tile (+9% TTFT), governor A/B, TTFT profile — Jwm1Parity7

Owner: Jwm1Parity7. Host: jwm1-linux (T8103, G13G), contract venv
`/var/tmp/jwm1-parity3-venv` (mlx-lm 0.31.3 + main patch set), user entry
point `~/.local/bin/mlx-omarchy-serve` -> `~/.local/share/mlx-omarchy/venv`,
`MLX_DISABLE_COMPILE=1`, bench `benchmarks/qwen38-mlx-bench.py` (10 prompts,
32 new tokens, prefill 512, 3 warmups). Prior state:
`receipts/2026-09-25-jwm1-parity5-gpu-parity-m64` (decode 37.47, ttft 50.26,
prefill 235.34 tok/s, e2e 1.0842 s; pins 486872c410629f1d (1-pass),
dbf704971617fdfc (10-pass)). macOS bars 47.05 / 99.12 / 343.73 / 0.7898.
Raw JSONs on jwm1: `/var/tmp/parity7/gpu/`, logs `/var/tmp/parity7/*.log`.

## 1. CPU governor A/B (normal priority, 2x interleaved, production wheel af73787)

| governor | decode tok/s | ttft tok/s | e2e s | prefill-512 tok/s | 1-pass digest |
| --- | ---: | ---: | ---: | ---: | --- |
| schedutil r1 / r2 | 37.52 / 37.53 | 50.16 / 50.59 | 1.0854 / 1.0859 | 226.4 / 236.6 | 486872c4… |
| performance r1 / r2 | 37.35 / 37.32 | 57.06 / 56.61 | 1.0572 / 1.0588 | 237.7 / 237.7 | 486872c4… |

On T8103 the GPU decode does not move with the cluster p-state (the ANE
lane's coupling, `receipts/2026-09-25-jwm1-ane-dvfs-boost`, is not a GPU
decode lever here; Jw16Levers2 reports +5% on T6001); TTFT does (+13%,
host-bound short prefill). Governor stays schedutil; nothing installed
depends on it.

## 2. Two-row Q4 GEMV (mlx-omarchy main `3232b1f5e`) — HOLDS and HELPS, installed

Wheel `mlx_omarchy-0.32.3.dev202609252032+3232b1f` (sha256 `63567e4d…`),
3x interleaved 1-pass contracts vs the production venv (af73787):

| leg | decode tok/s | ttft tok/s | e2e s | prefill-512 | digest |
| --- | ---: | ---: | ---: | ---: | --- |
| ctl r1 / r2 / r3 | 37.41 / 37.64 / 37.47 | 50.37 / 49.89 / 50.69 | 1.0876 / 1.0915 / 1.0782 | 236.9 / 236.3 / 236.3 | 486872c4… x3 |
| cand r1 / r2 / r3 | **39.14 / 39.03 / 39.13** | 50.85 / 50.65 / 52.39 | 1.0451 / 1.0481 / 1.0432 | 238.2 / 238.1 / 236.9 | 486872c4… x3 |

Decode +4.3% (37.51 -> 39.10 median of medians); 10-pass pin on cand:
**`dbf704971617fdfc` HOLDS** (decode 39.1, `raw/gemv-pin.log`).

Installed: the wheel is in both venvs (contract venv af73787 -> 3232b1f;
user venv 5738e29 -> 3232b1f, its mlx-lm reinstalled clean and main's
three patches applied — the 5738e29-era patched `gated_delta.py` could
neither take nor reverse the current patch set; `~/.local/share/mlx-omarchy/patches`
and `apply-mlx-lm-patches.sh` synced to main). 1-pass contract on each:
contract venv decode 39.14 / ttft 50.85 / prefill 236.9, user venv
39.19 / 50.64 / 225.5, digest 486872c4… on both (`raw/install-gemv.log`, JSON shas `raw/json-shas.txt`).
`mlx-omarchy-serve --help` runs. The published-release path
(`install.sh` downloads a release wheel) is the parent's: no release cut here.

## 3. TTFT fixed cost profile (diag wheel +diag.ecda0fa3, `/var/tmp/jwm1-parity5/out/prof-ttft.jsonl`)

Per first-token submission of a 10-17 token prompt (1161 dispatches, n=30,
profiler-inflated GPU times; kernel names from compute.h at ecda0fa33):

| kernel | dispatches | ms | us each |
| --- | ---: | ---: | ---: |
| QmmPrefillCoopmatBF16X32 (32-row tile) | 133 | 101.1 | 760 (n=6144: 930-950; n=2048: 400) |
| GatedDeltaPrefillBF16 (2 passes x 18 layers) | 36 | 53.4 | 1415 |
| QmmPrefillCoopmatM16BF16X32 | 48 | 12.2 | 254 |
| everything else (norms, casts, sdpa, conv, ...) | ~944 | ~33 | — |
| **total kernel** | 1161 | **199.3** | host record 12.6 ms |

Reading: the ~220 ms fixed cost is GPU-side. The 32-row coopmat prefill
GEMM at M=13 pads 19 dead rows into every mma and A load and runs at
7-18 GB/s of weight traffic (the decode GEMV streams the same weights at
28 GB/s); the GDN prefill scan costs ~108 us per token-step per layer
(same order as the decode kernel's 148 us: one thread per Dv row holding a
128-float state, 16 workgroups x 128 threads, memory-latency bound).

## 4. Small-M coopmat tile (mlx-omarchy `agent/jwm1-parity7-smallm-tile` @ `27aba5211`)

One hunk: `coopmat_tile_rows` returns 16 for `matrix_m <= 16` (one
16-row tile instead of a 32-row tile padded to 32; the 16-row twin already
ships for small grids, same k chain per output). Wheel
`mlx_omarchy-0.32.3.dev202609252046+27aba52` (sha256 `781f14f8…`), 2x
interleaved vs the installed 3232b1f venv:

| leg | decode | ttft tok/s | e2e s | prefill-512 | digest |
| --- | ---: | ---: | ---: | ---: | --- |
| ctl r1 / r2 (3232b1f) | 39.00 / 39.11 | 51.05 / 52.36 | 1.0473 / 1.0452 | 225.5 / 237.1 | 486872c4… |
| cand r1 / r2 (27aba52) | 39.08 / 39.14 | **56.23 / 56.00** | 1.0226 / 1.0166 | 237.5 / 225.2 | 486872c4… |

TTFT +8.6% (51.7 -> 56.1), e2e -2.5%, decode and prefill-512 unchanged
(M=512 keeps the 32-row tile). 10-pass pin on cand: **`dbf704971617fdfc` HOLDS** (decode 39.11, ttft 56.55, e2e 1.0174, `raw/smallm-pin.log`). Merged to mlx-omarchy main as `27aba5211` (fast-forward over 3232b1f5e) and installed in both jwm1 venvs (`raw/install-smallm.log`; patch state re-checked: raw refs 2, greedy refs 3 in both).

## 5. Verdict table after this lane (installed stack, normal priority)

| cell | before | after | macOS | ratio | verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| GPU decode tok/s | 37.47 | 39.1 | 47.05 | 0.83x | FAIL (was 0.80x) |
| GPU ttft tok/s | 50.26 | 56.55 | 99.12 | 0.571x (was 0.507x) | FAIL |
| GPU prefill-512 tok/s | 235.34 | ~237 | 343.73 | 0.69x | FAIL |
| GPU e2e s | 1.0842 | 1.0174 | 0.7898 | 1.288x latency (was 1.373x) | FAIL |
| pins 486872c4 / dbf70497 | — | hold on every candidate | — | — | PASS |

## 6. Next levers, named from the profile (not started)

- GDN prefill + decode kernels: 4 lanes per Dv row (32 Dk entries each,
  vec4 loads), the kv and o dot products handed lane to lane in ascending
  order (subgroup shuffle, no barrier) so the sequential f32 chain is
  bit-identical; 4x occupancy and memory-level parallelism. Targets the
  53 ms prefill share and 18 x ~148 us per decode token.
- Small-M qmm: a weight-streaming kernel that reads each Q4 word once for
  all M <= 16 x rows (the coopmat step structure is latency-bound at
  64 lanes per workgroup); exactness argument needs the ascending-k chain
  kept per output.
- Jw16GpuSubmit's Mesa barrier-batch fix (3.1 us x 1161 dispatches ≈ 3.6 ms
  of the fixed cost; rare-race battery required).
