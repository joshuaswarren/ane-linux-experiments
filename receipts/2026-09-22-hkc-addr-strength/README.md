# 2026-09-22 — Coopmat hot-loop address-math: NIR attribution + both levers measured, both REJECTED on perf

Lane: HoneykrispAddrStrength. Host: m1-host (m1-host (M1/G13G, kernel 7.1.13-3-2-ARCH), GPU via `flock /tmp/m1-gpu.lock`, sharing windows with DecodeQmmDequant. m1max-host (m1max-host) never returned during this lane — dark all window, no legs run on it. Repo: `joshuaswarren/mesa-1` clone `~/src/mesa-1`, local branch **`hkc-addr-strength`** at `1c74488fe85` (parent `7faf04c065c` = honeykrisp-omarchy tip). Nothing landed; the base pipeline is untouched (knob defaults off, commit documents the rejected levers).

## Task 1 — Attribution of the 155 iadd/imadd (from base-dump.txt, NIR → AGX IR)

The dumped NIR is **post** `agx_nir_lower_cmat` — every `coopMatLoad` has already exploded into per-element `@load_shared` with per-use address chains, so NIR-level attribution reads directly:

Per k-step iteration (4-iter step loop, body = ~16 MMA plus staging):
- **~17 ops recomputing the mat_a lane base** (`load_subgroup_invocation` → ubfe×2, imadshl×4, iand×2, iadd) and **~4 ops for the mat_b lane base** — **fully loop-invariant** (lane and subgroup id never change), recomputed every iteration.
- **~12 per-element `iadd`** feeding the 12 per-element shared loads (4 for mat_a, 8 for mat_b) — one add per access, inherent while `agx_emit_local_load` hardcodes the lload index operand to 0 and both lload decomposition levers are hardware-rejected (prior lane).
- **Staging stores**: x_s addresses (`(i/8)*STEP_K + 2*(i%8)` + k-dependent term) and w_s dequant stores — mix of per-lane invariants recomputed per iteration plus the genuinely k-varying chunk terms.

Root cause found for why none of the invariant math is hoisted — **two stacked reasons**:
1. `agx_optimize_loop_nir` never runs `nir_opt_licm` at all.
2. Even with LICM added, plain LICM refuses to hoist from this loop: the `if (ks >= 4) break` at loop top means the body does not dominate the loop exit, and `nir_opt_licm` only visits dominating blocks.

## Task 2 — Lever B (compiler): speculative LICM — measured, REJECTED

Implementation (commit `1c74488fe85`): `nir_opt_licm` in `agx_optimize_loop_nir` with a filter allowing speculative hoisting of pure ops only (ALU with invariant sources, load_const/undef, `can_reorder` intrinsics; internal libagx shaders excluded — full speculation trips the unspillable-internal-shader RA assert). Plus `AGX_ADDR_MODE` knob: 1=LICM, 2=forbid unroll of barrier loops, 3=both, 0=off (default).

Mode 1/3 results — the hoisting works exactly as intended at the IR level, and is slower anyway:

- AGX IR hot-loop totals: `iadd` 699 → 411 (mode 3, whole shader), total iadd+imad 1022 → 762.
- The five in-loop `get_sr` (subgroup invocation) recomputes collapse to one hoisted copy; the ~21-op per-lane base chains leave the loop entirely (dump: `licm-dump.txt`, `m3-dump.txt`).
- Checksums bit-identical on every shape (1108324632231936 / 3324973896695808).
- **Wall-clock regresses 1.55–1.66x**:

| shape (m,n,k) | base ms (TFLOP/s) | LICM ms (TFLOP/s) | LICM+noUnroll ms |
|---|---|---|---|
| 512,2048,6144 | 13.18 (0.977) | 21.91 (0.588) | 21.58 (0.597) |
| 512,2048,2048 | 4.56 (0.941) | 7.01 (0.612) | 7.60 (0.565) |
| 512,6144,2048 | 13.37 (0.964) | 19.93 (0.646) | 19.96 (0.646) |

Mechanism (documented, not fully root-caused): shrinking the loop body flips `nir_opt_loop_unroll` — the 4-iteration step loop fully unrolls (static `simd_matrix_fmadd32` 48 → 128 in the mode-1 build), and even with unrolling forbidden (mode 2 neutral, mode 3 still slow) RA emits register-swap (`xor` triple) repair sequences for the hoisted live ranges crossing the barrier; the backend clearly has a pathology around long-lived address registers feeding `local_load` across `threadgroup_barrier`. That investigation is upstream-compiler work for another lane; this lane's levers are measured dead.

Mode 2 alone (unroll guard, no LICM): neutral, 13.29 ms — the unroll guard itself is not the regression.

## Task 3 — Lever A (shader): pointer-increment + hoisted bases — measured, REJECTED

`qmm_coopmat_a.comp` (in `artifacts/`): k_base as induction, per-lane x_s staging base `x_addr` advanced by `8*STEP_K` per j, `w_base` hoisted to `w_stage` (per chunk), coopMatLoad offsets as `a_off[rb] += MAT` / `b_off += MAT*TILE_N` accumulators. Compiles clean (`glslangValidator -V -DX_BF16 -DOUT_BF16`; base.spv reproduced byte-identically from the audited recipe, confirming flags). Bit-verified against base on identical inputs (`mismatch: 0`, checksums equal) and **5–9% slower**: 14.38 / 4.85 / 13.36 ms. GLSL cannot express the shared-memory pointer arithmetic the lowering emits, so the source rewrite only touches math the compiler already CSEs; the residue is noise plus slightly worse codegen from the accumulator arrays. Rejected.

## Task 4 — Model-level prefill-512 + identity (m1-host)

Recipe: wheel `mlx_omarchy-0.32.3.dev202609221253+diag.2cc3067` (fresh venv `/var/tmp/mesa-addr/venv-2cc` + `/var/tmp/patch-mlx-lm-gdn.py`), driver = stock 7faf04c `base.icd.json` (nothing landed), model snapshot `0867d98b…`, 10 prompts × 3 passes, warmup 2, greedy, temp 0:

- `ordered_records_sha256` = **`ac1b269553a220ee66d59011decad4740c90f7027ff42deca5b4c4484e2b48f1`** — IDENTICAL to the class digest. Identity held.
- pure prefill 120.4 tok/s this window (prior-lane reference 130.92; −8%, consistent with concurrent GPU-lane load on m1-host — DecodeQmmDequant active windows; decode median 34.3 tok/s vs reference 34.27 matches).
- artifact: `artifacts/identity-base.json`.

## Follow-ups for Main

1. m1max-host was dark the entire window — power-cycle still owed; second-host confirmation of these A/B numbers pending.
2. The next real coopmat lever is the backend pathology this lane exposed: long-lived address registers crossing `threadgroup_barrier` cost far more than the instructions they save (1.6x regression while *removing* ~290 static adds). Candidates: async-lload pipelining across the barrier, register-bank pressure in RA, or the xor-swap repair path. Needs its own lane with m1max-host up.
3. `AGX_ADDR_MODE` knob defaults to 0 (bit-identical base pipeline); the branch is local-only, not pushed.
