# jw16-levers8 addendum 4 — corpus gate 6/6 on jw16; Qwen ANE loader validated (2026-09-26)

Per Main's corrected directives. Host jw16, research-exclusive.

## 1. Corpus gate: 6/6 PASS on jw16 (existing harness, existing files)

Assets transferred read-only from jwm1 and hash-verified on both sides
(exact hashes supplied by Jwm1Kernels3, all matched):

| file | sha256 (first 16) |
|---|---|
| fixture.flac | 30885601173f96b0 |
| fixture_v03.flac | 8a94d738993a841c |
| fixture_v1.flac | b9541731e778128e |
| fixture_v5.flac | ddc49b6596aa8d87 |
| fixture_v10.flac | 872e0e6a989f6789 |
| 1089-134686-0000.wav | a7a1b5c9815084cc |
| corpus_gate.py (harness) | 540bf7aeca5703b0 |

Harness run UNCHANGED on jw16 except path constants (documented config
diff: jwm1 infra paths → jw16 equivalents: overlay tools PKG, T6001
worker + libane-strict from /var/tmp/encoder-whole, recovery inproc shim
/var/tmp/parakeet-recover, venv share whole bundle; every check intact).

Result — **6/6 PASS, rc=0** (gpu-chain path, bitwise hidden/cell, tokens/
frames/durations identical host-vs-chain):

| clip | frames | emissions | tok/frm/dur |
|---|---:|---:|---|
| fixture.flac | 375 | 104 | true |
| fixture_v03.flac | 375 | 0 | true |
| fixture_v1.flac | 375 | 0 | true |
| fixture_v5.flac | 375 | 28 | true |
| fixture_v10.flac | 375 | 101 | true |
| 1089-134686-0000.wav | 375 | 104 | true |

Emission profile 104/0/0/28/101/104 EXACTLY matches the jwm1 record —
the corpus exercises skip, blank-hop, partial and full slot schedules
identically on T6001. jwm1 was not touched beyond read-only file reads
(no GPU/ANE execution, no reboot).

## 2. Qwen ANE — loader blockers FIXED and validated on jw16; inference state

- Staged branch recovered: aneforge-deltanet-split.bundle
  (sha256 08fa1fb0…) fetched into a fresh sbryngelson/ANEForge clone at
  /var/tmp/levers8/qwen/aneforge-check; tip `2ea941c` verified.
- Contract GGUF staged: Qwen3.8-2B-Q4_K_M.gguf sha256
  4aa0fb13c4315142… (contract pin match); reference chunk_00.json
  staged alongside.
- **Loader validation on jw16**: at `2ea941c`,
  `qwen35.load_gguf(<contract gguf>)` loads CLEAN — no
  `output.weight` KeyError (tied lm_head fallback), no
  block_count KeyError (nextn exclusion) → LlamaPrefill. The two
  loader blockers from the 2026-09-25 receipt are fixed and proven on
  this host.
- **Compiler blocker (err=11)**: fixed by the split-series upstream of
  2ea941c (three staged ANE programs replacing the fused
  gated_deltanet decode), already proven by ACTUAL ANE inference on
  macstudio: 10/10 prompts × 32 greedy tokens equal to the frozen
  reference through 38 ANE programs per decode step (STAGED-QWEN-REF
  PASS) — actual decode, not encoder-only.
- **Remaining jw16 blocker (decision point for Main)**: the staged
  programs execute through ANEForge's e5rt runner, which is macOS-only.
  Laptop inference on jw16 requires either (a) the macOS slice —
  blocked by the no-OS-switch constraint — or (b) a Linux ANE-program
  runner for the staged 38-program chain (does not exist; new
  implementation lane). Nothing more was executed; no PMP work.

## 3. Standing parity numbers (unchanged from addendum-3)

validate_chain ALL PASS (tokens/frames/durations/hidden/cell);
inference-only boundary 579.4 ms vs macOS 264 (2.19x) — the unpassed
acceptance, encoder-exec-dominated; GPU-loop TDT probe 144.6 ms stage
(-30, needs interleaved A/B); warm mel 7.7-7.8 ms beats macOS 15.
