# 2026-09-22 — hkc-direct-coopmat: shared-memory x staging removed from the qmm coopmat prefill; identity held, +6.2% prefill-512 tok/s on m1max-host

Lane: HoneykrispDirectCoopmat. Host: **m1max-host** (m1max-host, M1 Max G13C, stock kernel 7.1.6-1-1-ARCH) for everything measured. **m1-host (m1-host) never returned to Linux during this lane** (macOS serial window; booted to macOS per FleetMacOSUnattendedAccess) — no m1-host legs were run; second-host confirmation is still owed. Nothing was rebooted; all GPU work under `flock /tmp/m1-gpu.lock` with `llm-inference` stopped for the measurement windows and **restarted + `/health` = `{"status":"ok"}` confirmed at wrap-up**.

## Code (landed on a local branch, not pushed)

Repo `joshuaswarren/mlx-omarchy`, clone `/var/tmp/ppa-wt` on m1max-host, branch **`hkc-direct-coopmat`**:

- `42c10a68` — qmm_coopmat: direct global-load A tiles (f16-x route), delete x_s staging, drain reuses w_s.
- `77b91403` — bf16-hybrid route: host widens bf16 x to f32 once (new `CastBF16F32` dispatch), shader gains `-DX_F32` build (`QmmPrefillCoopmatBF16X32` / `QmmPrefillCoopmatM16BF16X32`, CMake `qmm_coopmat_x32` / `qmm_coopmat_m16_x32`) that coopMatLoads f32 A straight from the f32 buffer; X_BF16 staged path preserved verbatim.
- `734ab782` — fix: the X32 build must read **scales/biases as bf16 (uint16 + exact widen)** like the route it serves; the f16 scale layout was wrong for the bf16-hybrid model and shifted every output.

Mesa (`joshuaswarren/mesa-1`) is **unchanged**: `agx_nir_lower_simdmat` lowers coopMatLoad deref-generically, so a global SSBO pointer just works; mixed-precision A (f16 or f32) with f32 accumulator was already the supported hardware form. Wheel: `mlx_omarchy-0.32.3.dev202609221835+diag.734ab78` (venv `/var/tmp/hkc-direct/venv-cand`, GDN patch applied).

## What the change deletes (hot loop, per k-step)

The bf16-hybrid route (the Qwen3.8-2B-mlx-4Bit snapshot) keeps the weight-nibble staging and its two per-step barriers — nibble data cannot feed coopMatLoad. What is gone: the **x_s shared tile**, its per-lane staging stores/unpack and address arithmetic; A tiles are coopMatLoad'ed straight from global (f32 for the bf16 route after one exact host-side widening pass, f16 directly on the f16-x route — f16·f16 products are exact in f32, so the f32-accumulator k chain is unchanged). Shared memory 4096 → 2048 B/workgroup. The output drain reuses the staging scratch.

## Validation (corrected harness)

The inherited `coop_prefill_bench` fills random-bit inputs — random f16/bf16/f32 NaNs saturate every accumulation, so **any** comparison reports `mismatch: 0` trivially (verified: flipping every input bit left the checksum unchanged at the all-NaN constant; enabled `shaderStorageBuffer16BitAccess` in the harness copy as well). All bit-exactness below is from the corrected harness (`x32check.c`: finite inputs 1+k/16, feature-enabled, per-arm input views) on m1max-host, base = staged `basebf16.spv`/`base.spv` from the 60c4903f wheel source:

| arm | shapes | mismatch |
|---|---|---|
| x32 vs base bf16 (m32) | 512×2048×2048, 512×2048×6144, m=17 odd | 0 |
| x32 m16 vs base bf16 m16 | 12×2048×2048, 17×2048×6144 | 0 |
| f16-direct vs base f16 | 512×2048×2048, 12×2048×2048 | 0 |

Microbench (7 reps, med, same-window A/B, real inputs): 512×2048×6144 **4.261 → 3.083 ms (3.024 → 4.180 TFLOP/s)**; 512×2048×2048 1.571 → 1.483 ms (2.734 → 2.897); 512×6144×2048 3.681 → 3.095 ms (3.500 → 4.163). Static packed instruction counts (whole shader, unroll differs between arms): base 695 packed / 16 `simd_matrix_fmadd32` / 10 `barrier` / 40+48 shared ld/st; final dump of the shipped x32 kernel is `artifacts/x32-dump.txt` (NaN-era `base-dump.txt`/`direct-dump.txt` retained only for the static-count baseline; static counts are input-independent).

## Model-level prefill-512 + identity (Qwen3.8-2B-mlx-4Bit snapshot 0867d98b, 10 prompts × 3 passes, greedy temp 0)

Alternating A/B ×3 (base = `PrefillProfileAttack-venv` wheel diag.60c4903, cand = diag.734ab78):

| leg | base tok/s | cand tok/s | digests equal |
|---|---|---|---|
| 1 | 276.7 | 291.0 | ✓ |
| 2 | 274.7 | 292.2 | ✓ |
| 3 | 274.6 | 291.6 | ✓ |

**`ordered_records_sha256` = `ac1b269553a220ee66d59011decad4740c90f7027ff42deca5b4c4484e2b48f1` — the class digest, IDENTICAL on every leg.** Decode ~52 tok/s unchanged. Pure prefill **274.7 → 291.6 tok/s median, +6.2%** on m1max-host (Metal reference 1020 tok/s; gap now ~3.5×, from ~3.7×).

## Attribution of the earlier digest drifts (documented so nobody re-chases them)

1. First variant dropped the `-DX_BF16 -DOUT_BF16` build entirely; the model is bf16-hybrid and dispatches that build, so bf16 data was read as f16 → digest `2245229b`. Fixed by `77b91403`.
2. Second drift (`24826fdb`): the X32 build read bf16 scales as f16 — invisible to the NaN-saturated harness, caught only after the finite-input fix. Fixed by `734ab782`.
3. `MLX_OMARCHY_NO_COOPMAT=1` makes both wheels agree (tile route), isolating all drift to the coopmat arms.

## Follow-ups for Main

1. m1-host (m1-host) legs owed when the box is back on Omarchy (same recipe; scripts in `/var/tmp/hkc-direct/` on m1max-host).
2. B-side remains: nibble weights cannot feed coopMatLoad; the two per-step barriers and the w staging are the remaining structure. Next lever if wanted: persistent-k/register-blocked B or a hardware-documented nibble path.
3. Branch is local-only (no pushes), wheel is a local diagnostic build.
