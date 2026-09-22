# 2026-09-22: QmmVecQ4 decode GEMV occupancy/latency on M1 Max — candidates measured, all rejected on the GB/s gate, nothing landed (production kernel already at ceiling)

Lane: DecodeM1MaxOccupancy. Base: `integration/qwen38-2026-09-22` @
`dc7ca4a0`. Local branch `agent/decode-m1max-occupancy`: m1max-host worktree
`/var/tmp/occ-wt` commit `92d71186`, m1-host worktree `/var/tmp/occ-wt` commit
`5b7beef3` (bench instrument only; **`git diff dc7ca4a0 -- overlay/` is
empty — no production change**).

## 1. Occupancy and latency measurements (new `--occ` mode)

Instrument: `tools/q4-bw-bench --occ` — pattern probe (exact decode byte
layout, q4_pattern.comp) swept over grid size with per-submit batching
(GPU-timestamp path on this driver is mis-scaled ~32x and was dropped;
wall + batching only), plus `q4_lat.comp`, a dependent-chain weight-word
pointer-chase probe. Artifacts: `artifacts/occ3-m1-host.ndjson`,
`occ4-m1max-host.ndjson`, `emul-*.ndjson`.

### Latency per weight word (dependent load, 64 MB buffer, 256 lanes)

| host | chain 16384 | chain 2048 |
| --- | ---: | ---: |
| m1-host (M1) | 199.7 ns | 207.6 ns |
| m1max-host (M1 Max) | 428.7 ns | 435.6 ns |

### Concurrency sweep, production pattern (2 scalar weight words/lane, 8 subgroups/workgroup)

| subgroups | m1-host GB/s | m1max-host GB/s |
| ---: | ---: | ---: |
| 1024 | 19.2 | 45.5 |
| 2048 | 33.8 | 86.8 |
| 4096 | 50.8 | 129.7 |
| 8192 | 50.8 | 161.8 |
| 32768 | 44 | 209.5 |
| 131072 | ~50 (flat) | 310.6 |

- **m1-host saturates at ~2048–4096 subgroups** (floor ≈ 10 ns/subgroup,
  ceiling ≈ 50 of 59 GB/s) — the M1 is bandwidth-saturated at decode
  shapes; there is almost nothing left for any shader change to take.
- **m1max-host is still climbing at 131072 subgroups** (310 GB/s pattern roof);
  decode dispatches (2B chain: qkv 3072, down 2048, gate_up 6144,
  qkvz 8192 columns = subgroups) sit at 100–162 GB/s on this curve —
  **latency-bound, exactly the 156-vs-300 gap in the decode profile**.
  Little's law: 300 GB/s × 430 ns ≈ 129 KB in flight; at 8 B/lane that is
  ≫ any lane-map trick at 2–12k subgroups can hide.
- Per-dispatch reality check: the honest in-model instrument (gap,
  widedep 24-set chain) gives production **160.0 GB/s m1max-host /
  48.5 GB/s m1-host** — i.e. the shipped kernel already runs AT the pattern
  ceiling for its dispatch geometry.

## 2. Candidates — per-candidate GB/s, all REJECTED

Kernel-level screens (`--2b --bf16eq`, bit-exactness vs base) and the
gap widedep chain (the GB/s gate; artifacts `eq2b*`, `gap2b-*`):

| candidate | bit-identical | m1max-host widedep GB/s | m1-host widedep GB/s | verdict |
| --- | --- | ---: | ---: | --- |
| production (xpack) | — | **160.0** | **48.5** | baseline (xpack arm = base to 0.03%, instrument honest) |
| w2 — uvec2 128-bit weight loads | yes (0 mismatches, 28 eq rows ×2 hosts) | n/a (isolated flat) | flat (−1%) | REJECT — pattern probe: wide loads are *slower* (v2 148.6 / v4 139.8 vs w2 161.8 at 8192 subgroups, m1max-host) |
| quad4 — 4 words/lane + uvec4 load | NO (1/8192 element flip, qkvz — reorder) | isolated −3..7% on qkv | flat | REJECT — no gain + breaks bit-identity |
| unroll — 2 iterations, 4 words/lane in flight | yes (0 mismatches) | **128.3 (−20%)** | **35.0 (−28%)** | REJECT |
| wg128 — 4 columns/workgroup | yes | 127.3 (−20%) | 36–40 (−17..25%) | REJECT |
| split-K ×2/×4 (geometry emulation, same bytes, S× subgroups, words/S each) | n/a (would reorder) | split2 +2%, split4 −7% | split2 −6%, split4 **−40%** | REJECT — more subgroups only adds contention + partial-buffer traffic; the pattern curve's latency term does not pay for it |
| subgroup-shuffle reduction | — | — | — | nothing to do: USE_SUBGROUP subgroupAdd is already shipped (shuffle emulation is slower on Honeykrisp per shader header) |
| larger MULTI groups | — | — | — | nothing to do: MULTI=3 + SwiGLU fold already merge every dependency-free pair; `down` consumes gate_up's output |

## 3. Model-level decode tok/s (cadence protocol, integrated dc7ca4a0 wheel)

`benchmarks/qwen38-mlx-bench.py` (sha `cca1a51f…` verified on both hosts),
10 prompts, greedy, 32 new tokens, warmup 2, prefill-512,
`MLX_COMMIT_TAG=integ-dc7ca4a0`:

| host | venv / wheel | decode tok/s (median) | receipt reference | artifacts |
| --- | --- | ---: | ---: | --- |
| m1max-host (M1 Max) | `/var/tmp/occ-venv` = `0.32.3.dev202609221028+dc7ca4a0` | **57.67** | 57.59 (integration receipt) | `cadence-m1max-host-integ.json` |
| m1-host (M1) | `/var/tmp/integ-venv` = same dc7ca4a0 wheel | **34.14** | 34.30 | `cadence-m1-host-integ.json` |

**Before/after: identical, by construction.** Every candidate failed the
GB/s gate, so no production change landed and there is no "after" arm to
A/B — the before/after row is the integrated wheel reproducing the
integration receipt's decode numbers on both hosts within 0.5%.

## 4. Identity

Zero production diff vs `dc7ca4a0` (`git diff dc7ca4a0 -- overlay/` empty
on `agent/decode-m1max-occupancy`), so teacher-forced logits vs the
integrated wheel are the same computation — zero argmax flips by
construction. The correctness receipt's gates
(2026-09-22-qwen38-correctness: 0 argmax flips, max |Δ logit| ≤ 1 bf16
step) therefore remain the standing identity evidence for this exact
tree. Cadence runs above also decoded coherent streams on both hosts
(sha recorded in each JSON).

## 5. Housekeeping

- m1max-host llama-server stopped for the bench window (pid 217612) and
  restored with the recorded cmdline (new pid 248451; needed
  `LD_LIBRARY_PATH=~/opt/llama-vulkan`, which the
  recorded cmdline alone lacked — worth noting in the restore file);
  `GET /health` = 200 after. m1-host: no llama running (as before); all
  m1-host runs under `flock /tmp/m1-gpu.lock`. m2-host untouched. No pushes.
- Instrument limitation recorded for the next lane: m1max-host wall-anchored
  submits carry a ~180–200 µs floor and GPU timestamps are mis-scaled
  (~32x) — `--occ` batches 8–128 dispatches per submit and divides.
  Isolated single-dispatch kernel timings on m1max-host are also floor- and
  SLC-dominated (14 MB gate_up fits the 48 MB SLC on reps); only the
  gap widedep chain is decision-grade.
- Raw artifacts: `artifacts/` (this directory). Host copies under
  `/var/tmp/occ/out/` on both hosts.

## Conclusion

The QmmVecQ4 decode GEMV is **not leaving bandwidth on the table at its
dispatch sizes** — it is latency-bound at 2–12k subgroups, and every
listed lever (wider loads, deeper per-lane pipelining, occupancy
redistribution via split-K or workgroup shape) either fails to raise the
pattern ceiling or actively loses on the in-model chain. The decode-side
levers that remain are above the kernel layer: dispatch count/queue
depth (out of scope here) and prefill/ANE (non-goals).
