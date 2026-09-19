# AGX_SIMDMAT default restored to on — `hk/restore-simdmat-default` pushed to mesa-1 (not merged)

Date: 2026-09-19. Lane: RestoreSimdmatDefault. Repo:
`github.com/joshuaswarren/mesa-1`. Fix branch `hk/restore-simdmat-default`
at `3a37b4fb042`, cut from `honeykrisp-omarchy` `d8d4e1c500` and pushed.
Trunk `honeykrisp-omarchy` is intentionally untouched; merge is a separate
decision.

## Change

Reverts the safety gate in `f4859fb6991` (asahi: keep cooperative matrices
opt-in and key compiler switches): `agx_simdmat_enabled()` in
`src/asahi/compiler/agx_compile.h` is back to
`debug_get_bool_option("AGX_SIMDMAT", true)`. Safe now because `a2909940cbf`
(agx: lower cooperative matrices in software outside full subgroups) landed
the fallback that routes every non-full-subgroup dispatch through
`agx_nir_lower_cmat.c` — a valid shader is never rejected. Advertisement
(`cooperativeMatrix` feature) and the shader-cache key both derive from
`agx_simdmat_enabled()`, so flipping the default propagates with no other
wiring changes; `AGX_SIMDMAT=0` still disables, and the cache key still
tracks the option.

Stale opt-in comments updated in `agx_compile.c` and
`agx_nir_lower_simdmat.c`. `src/asahi/vulkan/tests/cache_options.py` re-pinned
to the default-on contract (unset advertises; `AGX_SIMDMAT=0` does not and
changes identity; `AGX_SIMDMAT=1` must equal the unset identity; other
options still perturb the key). py_compile clean; this lane runs no GPU
screening — the perf evidence is complete from MesaPortAndWork.

## Evidence: receipts/2026-09-19-agx-wait-batching-jw16.md (57bbb51)

MesaPortAndWork's NO-LAND screen on jw16 root-caused the trunk-tip decode
deficit (141 tok/s vs 190 installed) to this default flip and verified the
restore by env alone: `AGX_SIMDMAT=1` took decode 141 → 174.5 tok/s with the
same-source `5deac1c8` control rebuilding at 191 (toolchain innocent). This
branch makes that verified state the default instead of a per-run env var;
the residual −8.6% noted there is unattributed and remains open in that
receipt.
