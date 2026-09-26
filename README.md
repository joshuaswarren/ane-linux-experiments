# Apple Neural Engine experiments on Linux

This repository tests the Apple Neural Engine on Linux.
The target is an M1 MacBook Pro with Omarchy and the Asahi kernel.
The scripts compare ANE output with numpy on real hardware.

The latest results are in the [Linux ANE article](https://joshuawarren.com/blog/ane-linux-crossover/).
Every headline number has a matching receipt in `receipts/`.

## Current status

**2026-09-25 (evening fold):** m1-host (T8103) is recertified on the fresh
Arch boot. The Qwen ANE staged-decode cell passes (decode 1.49x macOS,
TTFT 0.84x, e2e 0.69x; prefill-512 1.223x — see the parity matrix), the
Parakeet golden contract is bit-exact on the installed ane module
(`receipts/2026-09-25-jwm1-parakeet-golden-rerun` on a9a5f60;
`receipts/2026-09-25-jwm1-kernels2-clean` verifies 5ecff86 installed and
loaded), and the GPU Qwen pins hold (dbf704971617fdfc / bc519c03c4ef5fd1).
The m1max-host ANE encoder runs 440.7 ms under the resident ANE worker and
the whole Parakeet pipeline dropped 1825 -> 892.9 ms
(`receipts/2026-09-25-jw16-levers6/artifacts/part2/RESULTS.md`). m2-host
(T6021) is still not live-inference-qualified; the 09-25 early-release dry
image fell to recoveryOS and both fallbacks held
(`receipts/2026-09-25-m2-early-release`).

T8103 (M1) has a bound ANE (historical, prior Linux boots). Persistence is a systemd unit that binds the device at boot. Schema-4 add-mul, tiny select, 1x1 conv, and `(1,256,128)` and `(32,256,128)` linear are exact fp16. The exported add family is exact too: re-exported 1x512 and 1x896 both returned exact, status 0, on 2026-09-14 (`receipts/2026-09-14-1x896-export-fix.json`). The earlier 1x896 `-110` was a converter defect chain, fixed on main: hardcoded td_size over-fetching the task (`8e89936`), the task record left unmasked (`a29a395`), the coefficient stream read from byte 0 of the weight blob instead of its declared payload offset, and the nchw header stamped at the 64-byte-padded convention instead of the task's own tile-DMA geometry (`52a3211`). The exported family's task puts its source on channel 4 and its destination on channel 5, the reverse of libane's positional layout, so it needs the derived-channel libane from omarchy-ane `ane-parity` `20d24ad` (`receipts/2026-09-14-1x896-channel-polarity.json`); that commit is not on omarchy-ane `main`.

T6001 (M1 Max) has `/dev/accel/accel0` live. SET follows runtime PM: SET0 reads `ACTUAL=0` while suspended and `0xf` after `open(accel0)` via genpd, no userspace write. Do not write SET `0xf`. The same add-mul, tiny select, 1x1 conv, and both linear shapes are exact and match T8103. The re-exported 1x512 and 1x896 also returned exact, status 0 (`receipts/2026-09-14-t6001-export-family.json`). A live overlay is not the packaged DTB: the packaged T6001 DTS exists only on omarchy-linux `feature/t6001-ane-bind` `9247b41`, unmerged. The omarchy-ane `main` `8554583` T6001 driver is being rebuilt on the lifecycle-correct base (bring-up scaffolding and GEM/ref bugs); the T6001 bind on main is a proven bring-up, not the shipping driver.

The out-of-box install plan is [docs/omarchy-ane-out-of-box-plan.md](docs/omarchy-ane-out-of-box-plan.md). The kmod is SoC-gated. Do not GRUB a whole-tree DTB.

Older Qwen speed and parity numbers are in `receipts/` and [crossover results](docs/crossover-results.md).

## Qwen3.8 MLX decode and prefill matrix (2026-09-21)

Measured Qwen3.8 decode and prefill rates on Apple M-series laptops with the
mlx runtime: Apple Metal on macOS and the omarchy Vulkan backend on Asahi
Linux. Same physical SoC is paired across both operating systems where a
switch was possible. Numbers are greedy (temperature 0) with a fixed
100-prompt corpus, 32 generated tokens, warmup runs, then measured repeats;
each receipt records the runtime distribution and version, the OS, the model
and tokenizer hashes, the selected backend and adapter evidence, thermal
readings, medians with dispersion, and an ordered per-record token hash.

The 2-bit-identical model file (Qwen3.8-2B, 4-bit mlx, 1,059,404,429 bytes)
is byte-identical on every host. Results are preliminary until each cell is
re-run with the corrected metadata harness; the run script is
`benchmarks/qwen38-mlx-bench.py` (native runtime) and
`benchmarks/qwen38-serve-bench.py` (OpenAI-compatible server clients).

| Hardware | OS | Model | Backend | Prefill (tok/s, median) | Decode (tok/s, median) |
|---|---|---|---|---|---|
| M1, 8 GB | Omarchy (Asahi) | Qwen3.8-2B 4-bit | mlx omarchy Vulkan | 17.8 (preliminary) | 18.4 (preliminary) |
| M1 Max, 64 GB | Omarchy (Asahi) | Qwen3.8-2B 4-bit | mlx omarchy Vulkan (adapter: Apple M1 Max G13C) | 36.6 (52.6 pure 512, single-run) | 34.2 |
| M2 Max | Omarchy (Asahi) | Qwen3.8-2B 4-bit | mlx omarchy Vulkan (adapter: Apple M2 Max G14C) | 47.2 (75.8 pure 512, single-run) | 45.0 |
| M1 Max, 64 GB | Omarchy (Asahi) | Qwen3.8-27B Q4_K_M | llama.cpp Vulkan (production server) | n/a (TTFT 2.3 s median) | 7.2 |

Notes and honesty rules for this table:

- The mlx omarchy backend refuses any non-Apple Vulkan physical device by
  default (admission check in the shipped runtime), and a loader trace during
  execution names the Apple adapter (M1 Max G13C / M2 Max G14C) as the
  enumerated device, so the measured cells ran on the Apple GPU, not llvmpipe.
- Prompt-through-first-token rates and pure prefill (512-token prompt, no
  generated token, recorded as `pure`; single run, prompt derived from the
  same corpus file by join-and-repeat to 512 tokens) are separate metrics; the prefill
  column is prompt-through-first-token unless marked pure. The 27B row is an
  API-client measurement of a thinking model whose 32 generated tokens are
  mostly reasoning tokens; TTFT is given in seconds instead, and the rate is
  an SSE chunk rate until a usage-verified rerun.
- Outputs are deterministic per host across passes. Token streams are NOT
  byte-identical across hosts, so no cross-operating-system or cross-SoC
  ratio is claimed as parity: with verified identical inputs, 8 of 10
  prompts matched byte-exactly and 2 diverged at token 19 or later.
- macOS cells are pending an owner-approved operating system window; they
  will be added with the same protocol when measured. (Superseded 2026-09-24:
  the macOS denominators were measured — see the parity matrix below.)
- Raw per-run receipts stay outside the repository.


## Three-laptop parity matrix (2026-09-25)

Measured parity state for the three surfaces (GPU Qwen3.8-2B, ANE whole
encoder, Parakeet) on m1-host (T8103), m1max-host (T6001), and m2-host
(T6021), against same-SoC macOS denominators. The bar is >=1.00x macOS
throughput and <=1.00x latency. The m1-host Qwen ANE staged cells meet the
bar; every GPU and Parakeet cell is still below macOS.
Every value is quoted from a committed receipt; a value that exists in no
receipt is marked `unreceipted` instead of dropped.

| Host | Cell | Linux | macOS | Ratio | Verdict | Receipt |
|---|---|---|---|---|---|---|
| m1-host | Qwen decode | 37.52 tok/s (p10 37.41), pin dbf704971617fdfc identical on omarchy-ane 9a0ec81 + wheel af737871e | 47.05 tok/s | 0.79x | FAIL | `receipts/2026-09-25-jwm1-parity3-main-battery` |
| m1-host | Qwen prefill-512 | 217.59 tok/s (1-pass digest 486872c4 identical) | 343.73 tok/s | 0.63x | FAIL | `receipts/2026-09-25-jwm1-parity3-main-battery` |
| m1-host | Qwen TTFT | 50.88 / 49.67 tok/s (r1 / p10) | 99.12 tok/s | 0.51x | FAIL | same |
| m1-host | Qwen e2e (32 new tokens) | 1.0883 s | 0.7898 s | 0.72x | FAIL | same |
| m1-host | ANE whole encoder | 138.03 ms median with the CPU-cluster boost held (171.04 ms when it lapses mid-submit); 137.95 ms on the installed 5ecff86 battery | 113.12 ms | 0.82x | FAIL | `receipts/2026-09-25-jwm1-ane-dvfs-boost` (5ecff86 install verified in `receipts/2026-09-25-jwm1-kernels2-clean`) |
| m1-host | ANE gate battery | runtime+primitive+bundle PASS on kmod 9a0ec81 + wheel af737871e (bundle C++ 34/34, 5904/5904; h13 python 15/15 after ce91f5b8e) | n/a | n/a | PASS (correctness) | `receipts/2026-09-25-jwm1-parity3-main-battery` |
| m1-host | Qwen ANE staged decode (max_len 50) | decode 8.23 tok/s (n=100); post-fix re-run: decode 1.4926x, TTFT 0.9677 s, e2e 0.6905x, 100/100 tokens exact, sweeps 3/3 | decode 5.625 tok/s, TTFT 1.189 s, e2e 6.718 s | decode 1.49x, TTFT 0.84x, e2e 0.69x | PASS (all three metrics) | `receipts/2026-09-25-jwm1-qwen-ane-layout-gate`; re-run `receipts/2026-09-25-jwm1-qwen-ane-ttft-rt`; TTFT root cause corrected to CPU-cluster DVFS coupling, durable fix omarchy-ane 5ecff86 (`receipts/2026-09-25-jwm1-ane-dvfs-boost`) |
| m1-host | Qwen ANE prefill-512 (max_len 513 export) | 14.36 tok/s (median of 3 walls, runner 95fe3fe boundary) | 11.74 tok/s (same staged-decode geometry, max_len 513) | 1.223x | PASS | `receipts/2026-09-25-qwen-ane-export-513` (replay 368/368 byte-identical to the macOS 513 goldens) |
| m1-host | Parakeet warm pipeline | current-stack whole-pipeline warm median 739.7 ms (TDT host loop on GPU, combined-parakeet lane); older certified boundary baseline 298.6 ms; parity4's 529 ms re-measure was the ~1.8x slow-engine state (ANE clock lever open). Today, bit-exact: mel 22.06 -> 19.36 ms (mel-DFT two-frames-per-workgroup landing), TDT chain 155.5 -> 151.1 ms (rtmod trace hygiene), encoder exec 140.3-141.1 ms (golden PASS on ane a9a5f60/5ecff86); TDT kernel-count fusion falsified 4.7x slower | 271 ms (rep10) | 0.37x current stack; 0.91x best-certified boundary | FAIL (falsified levers: parity4 fusion/mel variants, parity10 TDT fusion; landed levers: mel-DFT two frames per workgroup, rtmod trace gating; open lever: firmware-mediated ANE clock) | `receipts/2026-09-25-jwm1-parity4-falsifications-and-ane-regression`; `receipts/2026-09-25-jwm1-parakeet-golden-rerun`; `receipts/2026-09-25-jwm1-kernels-gpu-breakdown`; `receipts/2026-09-25-jwm1-parity10-parakeet-tdt-mel`; `receipts/2026-09-25-jwm1-kernels2-clean` |
| m1-host | Parakeet transcript | db501a8c, hidden 554a3d66 x3 on af737871e wheel + 9a0ec81 kmod | match | parity | PASS (correctness) | `receipts/2026-09-25-jwm1-parity3-main-battery` |
| m1max-host | Qwen decode | 77.33-77.48 tok/s; installed since the measurement: cpufreq-floor.service (+4.3% decode) and the dep-skip barrier trim (+0.8%, +0.65 tok/s) | 180.38 tok/s (earlier protocol: 179.47) | 0.43x | FAIL | `receipts/2026-09-24-launch-sink2/macos-t6001-denominators/qwen38-macos-metal.json`; levers `receipts/2026-09-25-jw16-levers3` |
| m1max-host | Qwen prefill-512 / TTFT / e2e | not run | 1326.05 tok/s / 359.98 tok/s / 0.2081 s | - | NOT RUN (Linux leg) | same |
| m1max-host | ANE whole encoder | 440.7 ms encoder stage under the resident ANE worker (whole-encoder pipeline 1825 -> 892.9 ms, -65% stage; earlier const-cache knob c59cc91 measured 1631.7 ms) | 140.9 ms (CoreML, bit-exact; 09-24 10-rep window 141.18) | 0.32x | FAIL | `receipts/2026-09-25-jw16-levers6/artifacts/part2/RESULTS.md`; macOS window `receipts/2026-09-25-jw16-levers5` |
| m1max-host | ANE firmware | release sequence runs, stalls before HELLO | n/a | n/a | NOT RUN (no inference path) | `docs/t6021-ane-bringup-findings.md` in omarchy-ane, sections 4-5 |
| m1max-host | Parakeet total | 892.9 ms total, RTF 0.0856 (was 2463.0/2480.4 ms; baseline 2572.3 ms) | 264 ms full pipeline (mel 15, encoder 140.9, tdt+decode 102) | 0.30x | FAIL | `receipts/2026-09-25-jw16-levers6/artifacts/part2/RESULTS.md` (both sides) |
| m1max-host | Parakeet transcript | 104/104 match, db501a8c pins | match | parity | PASS (correctness) | same |
| m2-host | Qwen GPU | not run on the main-tip battery; Sep-23 qualified stack measured decode 72.58 / prefill-512 906.84, stale vs mlx-omarchy main | 179.0 / 1109.82 tok/s | 0.40x / 0.82x (stale stack) | FAIL (stale stack); NOT RUN (current) | `receipts/2026-09-24-m2-gpu-parakeet-prep`; `receipts/2026-09-23-m2-gpu-qwen38`; `receipts/2026-09-23-m2-macos-denominator` |
| m2-host | ANE encoder | no inference path; firmware release sequence proven (status 0x28) on T6021 and T6001; with the VENC power leg up the firmware reaches its service loop; mailbox FIFO queued, never drained, no HELLO; the 09-25 early-release dry image fell to recoveryOS, both fallbacks intact | 90.71 ms, bit-exact vs Linux gold | n/a | NOT RUN | omarchy-ane `docs/t6021-ane-bringup-findings.md` sections 12-13; `receipts/2026-09-25-m2-mailbox-api`; `receipts/2026-09-25-m2-early-release`; `receipts/2026-09-23-m2-macos-denominator` |
| m2-host | Parakeet | never run (structurally blocked: T6021 ANE unavailable) | rep10 0.167 s, 107 tokens — MISMATCH vs golden 104 | n/a | NOT RUN (Linux); denominator flawed (macOS) | `receipts/2026-09-24-m2-gpu-parakeet-prep`; `receipts/2026-09-23-m2-macos-denominator/m2-macos-window/parakeet-20260923T145525` |

Notes:

- Ratios are fraction-of-macOS: Linux/macOS for rates, macOS/Linux for
  latencies. A FAIL is recorded as measured; no acceptance criterion was
  lowered.
- Receipt sets that previously lived only on side branches
  (`agent/jwm1-macos-baselines`, `agent/ane-static-start` lineage,
  `lane/jw16-parakeet-recover-clean`, `lane/m2-fwstart`, plus the M1 Max
  lane receipts merged at caabc0f) are integrated into main by
  `integration/receipt-branches-20260925`; every citation above now
  resolves on main. `.local/`, `.work/`, `receipts-work-*` scratch and
  files over 1 MiB were excluded.
- m1-host GPU values are the n=100 re-measurement on the landed main tip
  (mlx-omarchy tree `024d4fe60`; records pin `dbf704971617fdfc`,
  bit-identical to the T6001 pin). The earlier same-day leg measured
  decode 36.37 / prefill 219.2 / e2e 1.1145 — run noise, same FAIL.
- Value corrections against the earlier ticket wording: the m2-host macOS
  encoder median is 90.71 ms (90.73 is rep 7), the m2-host macOS Parakeet
  rep10 inference is 0.167 s, and the current m1max-host macOS decode
  denominator is 180.38 tok/s (179.47 was the earlier protocol). The
  m1max-host macOS ANE denominator (141.18 ms) lives inside the committed
  `t6001-macos-denominators.tgz` (gzip members are invisible to a text
  grep; verified by extraction, tar sha256 `968d5c5b…`).
- 2026-09-25 evening fold: the m1-host Qwen ANE staged cells (layout gate,
  TTFT re-run, 513 prefill export) are receipted PASS. The m1max-host
  encoder and Parakeet totals are re-based on the resident ANE worker
  (levers6 part 2) against that receipt's own 264 ms macOS denominator.
  Same-cell macOS denominators differ by measurement window (ANE encoder:
  140.27 levers3 / 140.9 levers6 / 141.18 launch-sink2 tgz); each ratio
  quotes the window paired with its Linux value. The 5ecff86 boost module
  is installed on m1-host (`receipts/2026-09-25-jwm1-kernels2-clean`).
- The m1-host Parakeet row is the combined-parakeet lane (warm reps
  1588.2/1597.8 ms after a cold rep). The same receipt also holds a faster
  current-stack whole-pipeline warm median of 739.7 ms with the TDT host
  loop moved to GPU — still 0.37x, still FAIL. Neither meets the bar.
- The m2-host GPU/Parakeet cells are staged behind `tools/m2-window`
  (kit re-measures mlx-omarchy main on the next window). The `90154f0d`
  wheel id quoted for that kit appears in no receipt.

Nothing in this table is done until every performance cell reads
>=1.00x macOS throughput and <=1.00x latency.

## Qwen reference workflow

The locked macOS reference uses the real
`Qwen3.8-2B-Q4_K_M.gguf` file and ANEForge.
The model must exist on the macOS reference system.
The tokenizer command `llama-tokenize` must be in `PATH`.
Pass `--contract benchmarks/qwen38-2b-contract.json` for the exact 100-prompt
corpus. The runner then validates the model, layer count, token count, and
corpus checksum before compilation.
Run the hardware-independent checks on Linux:

```sh
uv run --with numpy python -m unittest \
  tools.test_ane_contract \
  tools.test_aneforge_qwen_reference \
  tools.test_compare_qwen_reference
```

Run a bounded macOS reference capture:

```sh
# On the macOS reference machine, from the ANEForge checkout.
PYTHONPATH="<llama.cpp checkout>/gguf-py" \
  uv run --project . --with pyyaml python tools/aneforge-qwen-reference.py \
  --model /path/to/Qwen3.8-2B-Q4_K_M.gguf \
  --prompt-corpus qwen38-prompts-10.jsonl \
  --max-new-tokens 32 --warmup 1 --repetitions 1 \
  --logits-output qwen38-reference-10-logits.npz
```

The runner writes one JSON summary and one compressed logits archive.
The archive preserves prompt lengths and repeated-run boundaries.
The comparator maps prompt IDs before it compares candidate arrays.
The complete 100-prompt capture exceeded the 900-second bound in the current
reference run.
The 100-prompt attempt and ten-prompt checksums are in `receipts/`.

## Quick start

1. Read the warning below.
2. Run `./ane-bringup.sh` after every boot.
3. Try `python3 ane-network.py`.
4. Run the checks:

   ```sh
   uv run --with numpy python -m unittest \
     tools.test_hwxv2_to_anec \
     tools.test_production_anec_probe \
     tools.test_ane_contract \
     tools.test_aneforge_qwen_reference \
     tools.test_compare_qwen_reference
   ```

## Documentation

- [Fresh HWX usage](docs/fresh-hwx-usage.md): conversion and device parity.
- [Static graphs](docs/static-graphs.md): reusable graphs and submissions.
- [Crossover results](docs/crossover-results.md): speed and model results.
- [Out-of-box ANE install](docs/omarchy-ane-out-of-box-plan.md): SoC-gated kmod, no whole-tree DTB.
- [Apple Core AI reference](docs/apple-coreai-reference.md): export guidance.

## Main tools

| File | Purpose |
|---|---|
| `ane-bringup.sh` | Run the device recovery ladder. |
| `ane-network.py` | Run a two-layer MLP. |
| `ane-runtime.py` | Own persistent buffers and submit GEMM work. |
| `ane-qwen-model.py` | Run the 24-layer Qwen token step. |
| `tools/qwen-token-runtime.py` | Keep Qwen recurrent and attention state on the ANE. |
| `ane-head-bench.py` | Measure the tied output head. |
| `ane-static-loop.py` | Run a reusable static graph. |
| `tools/` | Convert HWX files and run fresh-format probes. |
| `tools/aneforge-qwen-graph.py` | Compile and run a Qwen-shaped SwiGLU graph through ANEForge. |
| `tools/production-anec-sequential.py` | Execute production tasks one at a time. |
| `patches/` | Hold the Linux libane patches. |
| `receipts/` | Hold command output and measured results. |

## Warning

The bring-up path can hard-reset the machine.
A wrong register write can reboot it without a panic or log.
Use netconsole when you need evidence.
A btrfs reset can lose unsynced writes.
Do not run this work on a machine that must stay available.

## Credits

- [omarchy-mac](https://github.com/omarchy-mac/omarchy-mac) provides the platform.
- [eiln/ane](https://github.com/eiln/ane) provides the reverse-engineered driver.
- [allbilly/ane](https://github.com/allbilly/ane) provides Python ANE operations.
- [Asahi Linux](https://github.com/AsahiLinux/linux) provides the kernel.

## License

MIT
