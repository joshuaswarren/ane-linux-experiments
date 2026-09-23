# jwm1 macOS denominators — one-window capture + Linux parity table (2026-09-23)

One macOS window on the M1 (T8103): reboot gate, core + parakeet + qwen-gpu +
qwen-ane legs, return to Linux, installed-wheel golden re-verify, same-protocol
Linux qwen bench. Device released back to Linux healthy. All raw outputs in
`macos/` and `linux-verify/` (neutral labels; environment.txt contains no
serial/hostname). Harness deviations: `harness-notes.md`. Reboot gate receipt:
`gate-reboot.md`.

Identity: macOS 27.0 (26A428), MacBook Pro Apple M1 16 GB, ANE fw 3600.25.2 /
Linux 7.1.13-3-2-ARCH aarch64, mlx-omarchy 0.32.3.dev202609230623+b4757ac.
Bundle sha 82c1a70198fd… (verified on-box pre-extract). Same pins both sides:
fixture 1089-134686-0000 (10.435 s), model b650695c, gold transcript db501a8c…,
Qwen3.8-2B-mlx-4Bit @0867d98b (safetensors b0d5de68… verified both sides).

## Parity table (Linux = installed wheel b4757ac unless noted)

| Metric | macOS (this window) | Linux (this window) | Ratio M:L |
|---|---|---|---|
| Whole-encoder ANE bench, median of 10 (bit-exact vs gold) | **113.12 ms** (112.41–113.47) | fresh-session ANE exec **142.1 ms**; warm-session-wake 266–276 ms | 0.80× (fresh) |
| MLComputePlan placement (whole encoder, 1374 ops) | ane **1345 / cpu 29** (ane=all arms); cpu arm 1374 cpu | n/a (island path, no CoreML plan) | — |
| Whole-encoder correctness | ane + all arms bit_exact TRUE (0/240000, max_delta 0); cpu 237818 mism max_delta 0.206 (expected, report-only) | goldens bit-exact every run (mel 5b54f4a9, hidden 38c73261, transcript db501a8c) | both exact |
| Parakeet transcript gate (ane/gpu/all) | MATCH golden, 104 tok, deterministic (identical stdout sha per arm) | MATCH, db501a8c, 104 emissions, 4/4 runs | parity |
| Parakeet cpu arm | DIFFERS 101 tok (pinned contract) | n/a | — |
| Parakeet warm encoder stage | **138.5 ms** median (n=10, ane arm) | encoder_ane 267.5–277.1 ms warm-wake / **142.1 ms** fresh | 0.52–0.98× |
| Parakeet mel frontend | 14 ms | 61.3–62.1 ms warm | 0.23× |
| Parakeet TDT decode loop | **120 ms** (CoreML decoder+joint, in-process) | **472–502 ms** (host-driven honeykrisp submits; 145 round trips ≈1.3–1.5 ms submit+wait+wake) | 0.25× — structural: macOS decode runs inside CoreML, Linux pays per-submit host round trips |
| Parakeet warm pipeline total | stage-sum ≈272 ms (ane arm; host overhead not reported) | **914.8 / 937.5 / 920.0 ms** (median 920.0, n=3) | — |
| Parakeet RTFx (ane arm) | 37.8–38.5× | 11.3× (10.435 s / 0.920 s) | 0.30× |
| Parakeet cold load (ANE program) | models ready 24.06 s (CoreML compile) | ANE session open 372.0 ms (fresh) | — |
| Qwen3.8-2B GPU decode tok/s (10×10 prompts, 32 tok, greedy) | **47.05 tok/s** median (n=100, σ1.53), records sha 85b9bc6d… | **35.40 tok/s** median (n=100, σ0.13), records sha dbf70497… | 1.33× |
| Qwen3.8-2B GPU pure prefill (512 tok) | **343.73 tok/s** (wall 1.4895 s) | **140.01 tok/s** (wall 3.6568 s) | 2.45× |
| Qwen3.8-2B GPU TTFT tok rate | (wrapper reports decode+prefill; ttft in json) | 50.72 tok/s median (σ7.1) | — |
| Qwen3.8-2B ANE | **BLOCKED** — leg exits "ANEForge not found" on this Mac; the ANEForge/e5rt decoder-compile blocker (`ane_e5rt_program_compile failed mask=0x4 err=11`, ANE fw 3600.25.2) is proven on m2-host and owned by the owner lane | blocked (no ANEForge export path for this contract) | — |
| Encoder bench, CPU arm | 272.80 ms median (placement all-cpu) | n/a | — |

Supersession: the old jwm1 macOS figures 122.12/119.56 ms were produced by an
`encoder_bench` that did not pass MLModelConfiguration at load (placement never
verified; harness defect fixed in 2bc9112) and stand unattributed. The 113.12 ms
+ placement proof above replaces them as the jwm1 macOS ANE denominator.

The Linux TDT floor confirms the ticket premise: TDT 472–502 ms is 145 decoder
round trips of submit+timeline-wait+host-wake; macOS hides the same work inside
CoreML at 120 ms. The remaining Linux pipeline gap is dominated by that loop,
not by encoder or mel (encoder parity within 0.8–2× depending on session state).

Qwen records hash: NOT an apples-to-apples cross-platform pin —
85b9bc6d… (Metal) vs dbf70497… (honeykrisp/Vulkan) differ because the two GPU
stacks round differently; each hash is the within-backend determinism pin (both
runs fully deterministic, n=100 each). Perf rows above are the parity cells.

## Provenance

- macOS raw: `macos/core-20260923T014214/` (bench JSONs, goldcheck, powermetrics,
  environment), `macos/parakeet-20260923T015004/` (114 files, per-arm stage
  walls + SHA256SUMS.outputs), `macos/qwen-gpu-20260923T015315/`.
- qwen-ane recorded exit: run 2026-09-23T01:54:24 CDT, RC=1
  "ANEForge not found at ~/src/ANEForge" — no compute, no
  err=11 claim fabricated for this box.
- Linux raw: `linux-verify/run-{1..4}/transcribe-report.json` (status match,
  emissions 104, transcript db501a8c…), driver `/var/tmp/pk-sess-driver.py`
  (canonical installed-wheel path per TdtFused; its receipt:
  mlx-omarchy branch agent/tdt-defer-commit
  receipts/2026-09-23-tdt-speculative-window.md, worktree
  ~/.config/superpowers/worktrees/mlx-omarchy/TdtFused, bundle
  /var/tmp/tdtfused-land/tdtfused-final.bundle — push hook-blocked upstream).
- Lock: all Linux GPU/ANE work under flock /tmp/m1-gpu.lock, never stolen.
