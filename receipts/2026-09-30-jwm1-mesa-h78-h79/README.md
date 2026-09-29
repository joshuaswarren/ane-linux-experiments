# jwm1 2026-09-30 (session 2, addendum): Mesa lane H78/H79 records

Lane: joshuaswarren/mesa-1, branch `asahi/local-offset-fold` (57100f495c1, two commits on base 160b7af8aeb; built and run on jwm1 in ~/src/mesa-fn + /var/tmp/mesa-fn-build, ICD /tmp/h1/fn.icd.json). Validation loop: tools/qmm-prefill-bench (mlx-omarchy) mismatch + FNV output sums + min-of-6-processes timing (the harness launch is bimodal 9.6/12.2 ms; see H76).

## H78 (local load/store index immediate): parked at the semantics
- Infrastructure now works: LOCAL_LOAD/STORE accept 16-bit immediates (agx_ir.c), the emitter emits index=K under AGX_LOCAL_PROBE, and an NIR pass (AGX_LOCAL_SHIFT/AGX_LOCAL_E) subtracts K*E from every 16-bit shared address mod 2^16 (cursor fix nir_before_instr; metadata none; 144 accesses shifted per kernel, no crash).
- Unit matrix (gate shape, K=8 x E in {1,2,4,8,16,32,64,128}, K=1/32/255 at E=4): no E reproduces the control output sum. The additive model effective = base + K*E is disproved at every plausible unit. agx_zero() (immediate 0) honors the base register, so the flag is not "ignore base". This matches the 2026-07-14 WIP experience.
- Next: determine the immediate semantics from the hardware directly (micro-shader with a known shared pattern, or hand-encoded test from the dougallj applegpu doc), or hoist/vectorize the fragment address arithmetic inside agx_nir_lower_simdmat.c instead (the WIP's other half).

## H79 (shared-memory vectorization): rejected for this kernel
- nir_opt_load_store_vectorize + nir_var_mem_shared, env AGX_VEC_SHARED: mismatch 0, sums equal control, but timing neutral-to-0.5%-slower (6v6 processes). The qmm coopmat fragment accesses are scattered per lane and the dequant stores stride TILE_N, so nothing vectorizes. Negative record committed.

## Where the prefill gap stands after today
- FULL_N shipped (+8.8% prefill, mlx-omarchy b612e4f63; live, digests pinned). Prefill 0.80x macOS.
- Kernel ISA (X_F32 coopmat): 473 AGX instructions per 64 simd_matrix_fmadd32; the uniform address arithmetic (one iadd per lload/lstore, index operand always 0) is the identified remaining codegen waste; scalar fp32 ALU is ~0.53x the fp16 rate on this die (H72).
