# jwm1 macOS denominators (2026-09-24) — branch `agent/jwm1-macos-baselines`

Owner: Jwm1MacBaseline (worker). Parent: Main. Lane: jwm1 macOS baselines.

Branch: `agent/jwm1-macos-baselines`
Base: `agent/jw16-launch-sink @ eb1e711` (HEAD at receipt time)

This receipt captures the harness-fix lineage, the relabel of the broken
prior numbers, and the M1 macOS denominator table for the three cells
requested by the assignment:

1. Parakeet whole-encoder CoreML bench (cpuAndNeuralEngine / all / cpuOnly)
   with placement proof from `MLComputePlan`.
2. Parakeet audio-to-transcript full pipeline baseline on the golden
   fixture (`1089-134686-0000`, 10.435 s) — end-to-end, RTF, stage
   timings, cold vs warm.
3. Qwen3.8-2B MLX GPU baseline (decode, prefill, TTFT, e2e).

## Blocker (read first)

This work could not be executed on jwm1 fresh on 2026-09-24 because the
laptop is **currently booted to Linux, not macOS**, contradicting the
assignment premise ("currently booted to macOS"). Evidence:

- `ssh jwm1` returns `Linux jwm1-linux 7.1.13-3-2-ARCH` (last boot
  `Sep 24 06:57`, uptime 3h52 at receipt time).
- Tailscale node `jw-m1-macos` (the Tailscale 100/8 address pinned in
  `~/.ssh/config`) reports `offline, last seen 3h ago` (the macOS side
  last had a connection about four hours before this assignment
  landed).
- ARP for the macOS-side LAN IP is `incomplete` from macstudio (same
  /23 subnet as jwm1) and from `16m1mbp` (Linux side, same /23).
- Direct `nc -z` to both the Tailscale address and the LAN address
  fails with timeout / no route.
- Wake-on-LAN magic packet sent from macstudio to MAC `CE:0F:2D:6E:A4:10`
  (jwm1 macOS MAC, obtained from the MikroTik DHCP lease `360 D
  <lan-ip-redacted> CE:0F:2D:6E:A4:10`) was not honored. Apple Silicon
  Wake-on-Wi-Fi only works when the laptop is plugged into AC power; on
  battery the NIC stays in the lowest-power state and ignores magic
  packets. The physical state (plugged in or battery) is not known to me.
- Rebooting jwm1 from Linux back to macOS would resolve the host state
  but violates the explicit assignment constraint "do not reboot it"
  (a separate agent needs the Linux webcam for M2 observation; the
  webcam devices `/dev/video0`, `/dev/video1` on `jwm1-linux` are
  crw-rw---- root:video and currently in active use).

The contradiction between the assignment premise (macOS) and the
assignment constraint (don't reboot into macOS) plus the host state
(Linux, webcam in use) is a **lane-level blocker**, not a worker-level
fix. Re-resolution requires Joshua or the lane owner.

## What this branch delivers anyway

1. **Harness-fix lineage** (cell 1): the harness defect at
   `receipts/2026-09-22-t8103-divisor/encoder_bench.swift` lines 32-34
   is fixed by commit `2bc9112` (already present in the parent of this
   branch). The fix passes `MLModelConfiguration` into `MLModel.load`
   and additionally records `load_ms` plus `MLComputePlan`-derived
   per-op placement. This branch carries the fix forward by inheritance
   (no fresh diff in this commit; see
   `receipts/2026-09-22-t8103-divisor/RELABEL-INCORRECTLY-ATTRIBUTED.md`).
2. **Relabel of old results** (cell 1): the 122.12 / 119.56 ms medians
   from the broken harness are preserved on disk but explicitly
   relabeled as **INCORRECTLY ATTRIBUTED, NOT ANE TIMINGS** in
   `receipts/2026-09-22-t8103-divisor/RELABEL-INCORRECTLY-ATTRIBUTED.md`.
   The same file documents the corrected re-measurement
   (`raw/core/bench_{ane,all,cpu}.json`) and the placement proof.
3. **M1 macOS denominators table** (cells 1, 2, 3): the actual
   corrected macOS numbers were captured **yesterday (2026-09-23)** by
   the sibling `agent/m1-mac-denominator` worker (commit `1df33f6`,
   receipt `receipts/2026-09-23-m1-mac-denominator/README.md`) on the
   same jwm1 macOS. The relevant raw outputs from that window are
   copied into this branch under `raw/{core,parakeet,qwen-gpu}/` with
   SHA256SUMS.provenance so the numbers can be re-verified from this
   branch without re-running the macOS bench.

The table below is the denominator set requested by the assignment,
sourced from the sibling receipt's captured raw outputs (every cell
checks out against an independently verifiable artifact: bench JSONs,
per-arm stdout transcripts, qwen-gpu JSON). Sourcing is documented
per-row.

## M1 macOS denominator table (Parakeet + Qwen3.8, 2026-09-23 capture)

All numbers come from the sibling `agent/m1-mac-denominator` receipt
(worktree `.work/m1-mac-denominator`, commit `1df33f6`), re-verified by
SHA256 against copies in this branch under `raw/`. Provenance file:
`raw/SHA256SUMS.raw` (23 files, all OK).

### Cell 1 — Parakeet whole-encoder CoreML bench (corrected harness)

3 warmups + 10 timed reps, `MLModelConfiguration.computeUnits` set and
passed into load, placement from `MLComputePlan` for the SAME compiled
model under the SAME `cfg`. Model
`~/.cache/mlx-omarchy/parakeet-reference/)mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c.../encoder.mlpackage`,
inputs `feat_f32.bin` and `mask_i32.bin` (Linux gold parity tensors).

| arm | median ms | min ms | max ms | mean ms | placement (preferred) | reps | raw source |
|---|---:|---:|---:|---:|---|---:|---|
| cpuAndNeuralEngine (".ane") | **113.12** | 112.41 | 113.47 | 112.92 | ane **1345** / cpu **29** | 10 | `raw/core/bench_ane.json` (`9980f20b…`) |
| all (".all")              | **113.23** | 112.48 | 113.30 | 112.97 | ane **1345** / cpu **29** | 10 | `raw/core/bench_all.json` (`c5d14d33…`) |
| cpuOnly (".cpu")          | **272.80** | 271.01 | 273.33 | 272.27 | cpu **1374**          | 10 | `raw/core/bench_cpu.json` (`01897557…`) |

`.ane` and `.all` are bit-exact vs Linux gold (`hidden` fp32→fp16, 0/240000
mismatches, max_delta 0). `.cpu` has max_delta 0.206 (expected for fp32
host path; report-only, not a regression).

Per-rep arrays (verbatim from the bench JSONs):

- ane: `112.41, 112.49, 112.52, 112.58, 113.00, 113.12, 113.19, 113.23, 113.24, 113.47`
- all: `112.48, 112.48, 112.54, 112.89, 112.97, 113.23, 113.25, 113.25, 113.28, 113.30`
- cpu: `271.01, 271.07, 271.29, 271.41, 272.79, 272.80, 272.82, 272.95, 273.26, 273.33`

### Cell 2 — Parakeet full audio-to-transcript (10.435 s fixture, all four arms)

Fixture `1089-134686-0000` (10.435 s audio, deterministic transcript
sha256 `db501a8c…`). Per-arm cold + warm1 + rep1 + rep10 stage timings
from the parakeet runner's stderr (`----- timing -----` block); bit-exact
transcript check on every run (`SHA256SUMS.outputs` lists identical
hashes for the ane/all/gpu stdout, with the cpu arm's stdout differing
by exactly the cpu-arm pinned contract).

| arm | cold inference | warm1 inference | rep1 inference | rep10 inference | cold encoder | rep10 encoder | rep10 decode | transcript |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| ane  | 0.295 s | 0.276 s | 0.276 s | 0.271 s | 0.150 s | 0.136 s | 0.120 s | match gold (104/104 emissions) |
| all  | 0.289 s | 0.279 s | 0.273 s | 0.272 s | 0.150 s | 0.138 s | 0.120 s | match gold (104/104 emissions) |
| cpu  | 0.494 s | 0.477 s | 0.477 s | 0.476 s | 0.357 s | 0.345 s | 0.117 s | differs (101/104, pinned cpu contract) |
| gpu  | 4.289 s | 1.007 s | 0.997 s | 1.000 s | 4.145 s | 0.833 s | 0.151 s | match gold (104/104 emissions) |

Models-ready cold-load latency: **24.06 s** (CoreML compile on first
hit, ms per arm). Warm path drops to ~0.12 s "Models ready".

End-to-end RTF on the warm ane arm: 0.272 / 10.435 = **38.4×** (sibling
parity table rounds to 37.8-38.5×). GPU arm RTF ~10.4×.

Per-arm transcript stdout copies are under `raw/parakeet/stdout_{ane,all,cpu,gpu}-{cold,warm1,rep1,rep10}.txt`. SHA256 on those
copies confirms content was not modified during the copy.

### Cell 3 — Qwen3.8-2B MLX GPU baseline (macos-metal)

Contract: `benchmarks/qwen38-2b-contract.json` (frozen_at 2026-08-29,
new_tokens 32, greedy temperature 0.0, prompts corpus sha256
`9299a3b2…`, prefill_leg_tokens 512). Run with `~/venv-metal312`,
`mlx_lm_version 0.31.3`, `mlx` dist `0.32.2`, model
`SiddhJagani/Qwen3.8-2B-mlx-4Bit` (model_sha256
`b0d5de68…`, tokenizer `87a7830d…`, config `6834d47a…`). 3 warmups, 10
passes × 10 prompts = 100 measured runs. Raw source:
`raw/qwen-gpu/qwen38-macos-metal.json` (sha256 `df40a6a8…`,
`ordered_records_sha256 85b9bc6d…`).

| metric | median | mean | stdev | min | max | n |
|---|---:|---:|---:|---:|---:|---:|
| decode_tok_rate (tok/s)           | **47.05** | 47.32 | 1.53 | 43.43 | 49.77 | 100 |
| pure_prefill_tok_rate (tok/s, 512 tok leg, wall 1.4895 s) | **343.73** | — | — | — | — | — |
| ttft_tok_rate (tok/s)             | **99.12** | 104.09 | 17.23 | 80.66 | 140.78 | 100 |
| end_to_end_s (per prompt, s)      | **0.7898** | — | — | 0.7395 | 0.8458 | 100 |

Records pin (Metal determinism): `85b9bc6da83b35bc6222b62648091d7d07d091810d7a0f392278b93d2c5ac4e4`. This is the within-Metal
determinism pin (n=100, all runs exact); it is **not** an apples-to-apples
pin across GPU stacks (the sibling receipt notes that Metal and
honeykrisp/Vulkan round differently and produce different determinism
hashes — that's by design).

Qwen3.8 ANE leg: **blocked**. The leg exits at the script's first gate
with "ANEForge not found at ~/src/ANEForge". The err=11 ANEForge/e5rt
decoder-compile blocker is proven on the m2-host reference Mac (ANE fw
3600.25.2, `ane_e5rt_program_compile failed mask=0x4 err=11`) and owned
by the owner lane; not fabricated for this M1.

## Provenance

- Branch: `agent/jwm1-macos-baselines`
- Base: `eb1e711` on `agent/jw16-launch-sink`
- Harness fix commit (predecessor): `2bc9112 t8103-divisor: pass
  MLModelConfiguration to MLModel load`
- Re-measurement source: sibling `agent/m1-mac-denominator @ 1df33f6`,
  receipt `receipts/2026-09-23-m1-mac-denominator/README.md`
- Re-measurement date: 2026-09-23 01:50-01:53 CDT
- All `raw/` files in this receipt are byte-identical copies of the
  sibling's `macos/{core,parakeet,qwen-gpu}/` outputs; SHA256 verified
  per `raw/SHA256SUMS.raw`.

## Artifacts

- `receipts/2026-09-22-t8103-divisor/RELABEL-INCORRECTLY-ATTRIBUTED.md` (this branch)
- `receipts/2026-09-22-t8103-divisor/encoder_bench.swift` (carries the
  post-`2bc9112` fix by inheritance; not modified on this branch)
- `receipts/2026-09-22-t8103-divisor/README.md` (UNCHANGED — original
  broken-harness numbers; superseded by RELABEL note)
- `receipts/2026-09-22-t8103-divisor/SHA256SUMS` (UNCHANGED — pins
  pre-fix harness `938dc559…`)
- `raw/SHA256SUMS.raw` (23 files, all OK)
- `raw/core/bench_{ane,all,cpu}.json` + `raw/core/environment.txt`
- `raw/parakeet/{stdout,stderr}_{ane,all,cpu,gpu}-{cold,warm1,rep1,rep10}.txt` + `SHA256SUMS.outputs` + `fetch-parakeet.log`
- `raw/qwen-gpu/qwen38-macos-metal.json`
