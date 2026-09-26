# jwm1 decode QMM bandwidth: shape set extracted, ranked against roofline, tiling screened — no tiling win exists; residual is dispatch turnover (mesa lane)

Owner: Jwm1Kernels3, 2026-09-26. Task: "extend q4-bw-bench to the extracted
Qwen3.8-2B decode shape set, rank per-shape GB/s against the T8103 roofline,
and tile the worst shapes toward 79%+ of nominal bandwidth, bit-exact. Merge
winners, install, rerun the full GPU contract."

**Verdict: the tile space around the production shader is exhausted — every
candidate screens at or below base (+0.1% best, bit-exact everywhere), so
there is no winner to merge or install. The mix runs 49.8 GB/s (73% of
nominal 68.25); the pattern ceiling on this memory system is 60-65 GB/s
wall-measured; the 15 GB/s residual is in-CS dependent-dispatch turnover
(~27 us x 9 dispatches/layer), which is mesa-owned, not shader tiling.**
Instrument + findings landed on mlx-omarchy main `aef33d8fa`
(`tools/q4-bw-bench/RESULTS-jwm1-20260926.md`).

## Shape set (--2b extended)

Derived from the checkpoint tensors (qwen3_5 hybrid: 18 GDN + 6 full-attn
layers, hidden 2048, inter 6144, head_dim 256, vocab 248320) and
cross-checked against the decode profile families:

- attn qkv MULTI (4096,512,512) k=2048 — q fixed to 4096 rows: the
  checkpoint's q_proj carries the attn_output_gate half (the old table's
  2048 was wrong)
- gate_up (6144,6144); down (2048,)k6144; qkvz (8192,)k2048
- gate6144 (6144,)k2048 — in-model in_proj_qkv/gate/up dispatch solo
  (profile: n=6144 gx=768, 756 records)
- zout (2048,)k2048; q4096; kv512; ab (16,16); **lm_head (248320,)k2048**
  (26% of token bytes — was missing from the table)

Instrument changes: `per_token` shapes skip gap-mode cycling (24 sets x
286 MB cannot fit an 8 GB box; lm_head's streaming rate is honest without
cycling because the weight never fits cache); descriptor pool scales with
the shape count; loops bounded by the active table size.

## Ranking (bytes-weighted per token; wall-clock medians)

| class | MB/token (share) | solo GB/s |
|---|---:|---:|
| 6144x2048 (qkv/gate/up) | 467 (44%) | 49.3 |
| lm_head | 286 (27%) | **56-61 (>=79% target)** |
| down | 170 (16%) | 52.0 |
| zout (2048x2048) | 99 (9%) | 38.2 (small-grid latency-bound) |
| q4096 / kv512 / ab | 35 (3%) | 46 / 17 / 1.5 |

Layer MIX (--gap widedep, 9 cycling shapes, 51.48 MB/layer): **49.8 GB/s =
73% of nominal**, flat from sets=1 to 24 (no residency crossover).

## Tiling screens (all bit-exact, raw/eq16.jsonl + iso runs: 0 mismatches)

| candidate | mix widedep | vs base |
|---|---:|---:|
| base (cols 8 = production) | 1.0335 ms | — |
| xpack | 1.0327 ms | +0.08% (noise) |
| unroll | 1.3973 ms | -35% |
| wg128 (cols 4) | 1.4172 ms | -37% |
| base retiled cols 16 (-DROWS_PER_SLOT=2) | 1.0334 ms | +0.01% (noise) |

## Accounting: where the remaining gap lives

Layer time 1.0337 ms vs 787 us of pure stream at the 65.4 GB/s pattern
ceiling = +247 us over 9 dispatches = ~27 us per in-CS dependent-dispatch
turnover (matches the chain-dep-bench floor; same mesa-1 honeykrisp lever).
Non-QMM decode overhead (~6 ms/token, GDN step runs the gated_delta_ops
fallback because mx.metal.is_available() is False on the Vulkan build) is a
separate lane. lm_head and the 6144x2048 class are at/near the memory
ceiling; macOS's implied 54 GB/s is the same wall, not shader headroom.

## Contract state (installed stack)

No runtime change was merged, so the installed stack is unchanged by this
step; pins hold by construction (no wheel, shader, module, or runtime edit
landed from this lane). Standing verified contract on jwm1: the release
lane's installed-from-release gates PASS on mlx-omarchy main `546dbb896`
(digest bit-exact `486872c4...`, decode 39.21/39.22 tok/s vs macOS 47.05,
ANE+GPU smokes green). A fresh `dft_gates_clean.sh` battery (same pinned
7c0bd851 wheel, pins 1/3/10, corpus, chain/mel walls, contract3) was
launched detached on jwm1 at the end of this window (pid 66809, log
`/tmp/gates-run-20260926.log`, results dir `/tmp/dft-gates-clean/`) and had
not flushed results at wrap-up; it is idempotent and any follow-up lane can
read its output there.
