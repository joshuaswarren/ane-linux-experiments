# 2026-09-25 — jwm1 Qwen ANE layout gate (QwenAneLayout handoff) — decode + e2e PASS, TTFT FAIL (Jwm1Parity6 landing, Jwm1Parity5 measurement)

Owner: Jwm1Parity6 (landing the receipt Jwm1Parity5's budget stop
aborted; numbers below are from the committed measurement outputs).
Host: jwm1-linux (T8103). Stack: installed ane module at omarchy-ane main
`a9a5f60` (srcversion `CD235EAE3669B084F6D63DA`), libane +
libane_python rebuilt from the same commit, staged Qwen ANE programs in
`/var/tmp/qwen38-staged-anec` (QwenAneLayout lineage: 38 programs, one
per layer slot).

## 1. What the gate proves

The QwenAneLayout program layout (program-per-slot, guard-checked load)
runs the full Qwen3.8-2B Q4_K_M decode on the T8103 ANE with every token
matching the host reference, at bench scale n=100. This is the gate the
QwenAneLayout handoff asked for.

## 2. Verify: PASS 10/10

`/var/tmp/qwen38-layout-out/verify.log` (jwm1):
`{"prompts_match": 10, "prompts_total": 10}` then
`STAGED-QWEN-LINUX PASS`. All 10 corpus prompts MATCH, `first_diff=32`
on every prompt (the compare window starts at token 32; generation is
identical from the first compared token). Cold open: 38 programs in 5.5 s,
cold first prompt 4.5 s.

## 3. Guard proof: staged programs refuse without the layout guard

With the unpatched staged tree (`/var/tmp/qwen38-staged-anec`, no
QwenAneLayout guard) libane refuses the load at init —
`RuntimeError: libane init failed prog_000.anec` — BEFORE any device
open. The guard is load-bearing: no silently-wrong layout can reach the
hardware. Evidence in the gate window transcript `/var/tmp/window.sh`
(jwm1) and the verify log run sequence.

## 4. Bench: n=100 (10 prompts x 10 reps, 3 warmup passes)

`staged-qwen-bench.json` (jwm1, sha256
`14d4dd5981668d8664a37a5a6cdb9d22cf9c8499b065c07e13656e75c80a558d`),
`tokens_matching_reference: true`, `ane_programs_per_step: 38`,
`ane_submissions_per_token: 38`, peak RSS 8.38 GB.

| metric (median) | linux | macOS | ratio | 95% CI | pass bar | verdict |
| --- | ---: | ---: | ---: | --- | --- | --- |
| decode tok/s | 8.23 | 5.625 | **1.466x** | [1.430, 1.503] | >= 1.00x | **PASS** |
| e2e s (32 tok) | 5.314 | 6.718 | **0.787x** | [0.770, 0.806] | <= 1.00x | **PASS** |
| TTFT s | 1.534 | 1.189 | **1.347x** | [1.236, 1.480] | <= 1.00x | **FAIL** |

macOS side detail: decode mean 8.2143 (stdev 0.0359), ttft mean 1.5646
(stdev 0.4931), e2e mean 5.3385 (stdev 0.4945). Linux TTFT spread is wide
(min 0.819 s, max 2.773 s) — the median is the compared number.

Denominator: committed macOS Qwen ANE run at ane-linux-experiments
`fedd4da`, file
`receipts/2026-09-25-m1-ane-clock-macos/qwen-ane-full/qwen38-macos-ane.json`,
sha256
`410dc4f7b759e0d30bf9733306931c8d35f0327433644455be20d9fc83bac580`
(matched on both the committed git object and the jwm1 copy;
100/100 exact vs chunk_00, decode 5.625 tok/s, TTFT 1.189 s, e2e 6.718 s).

## 5. Verdict and next lever

Two of three primary metrics PASS with margin (decode +46.6%, e2e
-21.3% latency). TTFT FAILS the no-margin bar at 1.347x macOS latency:
the first token costs ~345 ms more than macOS. That gap is the named
live lever for the jwm1 Qwen ANE lane (TTFT-path profile on the installed
stack: 38-program cold path, weight staging, and first-step submission
shape are the candidate costs).
