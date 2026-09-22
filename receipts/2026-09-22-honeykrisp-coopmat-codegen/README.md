# 2026-09-22 — Honeykrisp coopmat codegen audit + addressing levers (audited, two levers measured and REJECTED)

Lane: HoneykrispCoopmatCodegen. Hosts: m1-host (M1, G13G) for everything measured; m1max-host dark for the whole window (GpuTlbLatency TLB2MCTG one-shot reboot never returned; >45 min down at wrap-up — needs the promised power-cycle). Repo: `joshuaswarren/mesa-1`, branch `hkc-coopmat-codegen` @ `7faf04c065c` (honeykrisp-omarchy tip) on both hosts; m1max-host clone at `~/src/mesa-1`, m1-host clone fresh-cloned to the same commit. **No driver change landed** — nothing survived measurement. Identity held trivially and was re-proven.

## Task 1 — Codegen audit (complete)

Method: the wheel's dump path is bypassed, so the shipped `qmm_coopmat.comp` (256 lines, TILE_M=32/N=32/K-step 16, 8x8x8 f32 accumulate) was compiled to SPIR-V with glslangValidator and replayed through a standalone `vkCreateComputePipelines` harness (`coop_prefill_bench.c`, prior lane) against a source-built honeykrisp (`/var/tmp/mesa-7faf04c-m1-host/base.so`, ICD json) with `AGX_MESA_DEBUG=shaders` and `MESA_SHADER_CACHE_DISABLE=true`. Full dump: `artifacts/base-dump.txt` (5794 lines: NIR → AGX IR → RA → packed asm).

Baseline sanity: harness base timings m1max-host 3.07 TFLOP/s / m1-host 0.94-0.98 TFLOP/s on 512x2048x6144 — matches the wheel-level qmm_prefill numbers (3.3-3.5 / prior receipt).

### Instruction mix (m1-host build, 512x2048x6144)

Whole shader: 770 packed instructions, ~50 regs/thread, 120 uniforms.

Hot inner region (k-step loop, 352 instrs issuing 16 `simd_matrix_fmadd32`):

| class | count | note |
|---|---:|---|
| `iadd` + `imadd` | 155 | shared/weight address arithmetic, ~10 per MMA |
| `and`/`bfeil` | 47 | lane masking for shared addressing |
| `lload`/`lstore`/`store` | 56 | staging + coopMatLoad traffic |
| `wait` | 16 | one per load group |
| `barrier` | 7 | 2 per k-step + drain |
| control flow (`if`/`pop_exec`/jmp) | ~49 | divergence masks |
| `fadd`/`ffma` | 24 | dequant scale*bias |
| **MMA** | **16** | 16x 8x8x8x2 FLOP |

Roof arithmetic (G13, marcan ~10 TFLOP/s implied peak): 16 MMAs ≈ 26 core-cycles; the surrounding ~336 non-MMA instructions are the measured cost — at 3.07 TFLOP/s the kernel spends ~7 cycles per MMA, i.e. ~3.3x off the MMA roof, with the gap fully accounted for by address math + staging + barrier serialization. This is the driver-side explanation PrefillCoopmatTile predicted; tile-side levers are confirmed exhausted.

## Task 2 — Landed? No. Two levers implemented, measured, rejected

The audit's smoking gun was `agx_emit_local_load/store` hardcoding the lload/lstore index operand to zero (`/* TODO: optimize address arithmetic */`) — every shared access pays a full per-use `iadd`. Three variants were built and measured on m1-host (each verified with a standalone shared-memory kernel AND the bit-verifying qmm harness):

1. **Peel constant addends into the lload immediate index** (`agx_nir_lower_shared_bitsize` + emitters). Correct on a standalone kernel only for tiny offsets; any real immediate index (2048) silently produced wrong/zeroed reads — the packed-immediate index form does not behave as the packer assumes on hardware. qmm checksum drifted (1108324632231936 → 1105177727501824). REJECTED.
2. Same, with the 16-bit-index scaling guess (units/element). Same failure. REJECTED.
3. **Split the address `iadd(var, var)` into lload base+index registers** (NIR keeps a 16-bit `iadd`; backend uses its operands directly as base/index; correct on offtest3). On qmm: −19% (13.79 → 17.01 ms on 2048x6144) AND checksum drift. Hardware does not add base+index in bytes for these patterns. REJECTED.

Along the way one real trap was found and documented: adding `LOCAL_LOAD/STORE` to `agx_allows_16bit_immediate` lets the optimizer inline truncated immediates into the *value* slot of local stores — silent corruption. Do not do that.

All three variants are reverted; `hkc-coopmat-codegen` is clean at `7faf04c065c` on m1-host (m1max-host clone is at the same commit, clean, built `/var/tmp/mesa-7faf04c-m1max-host/build`). Negative artifacts: `artifacts/peel-dump.txt` (immediate-index build), `offtest.tgz` (shared-addressing test kernels + dump harness), `o-base.txt`/`o-peel.txt`.

Remaining candidate (not attempted, out of runway for this lane): the precise-math div/rcp cost (a99347c3fc5) — a cheaper correctly-rounded sequence is a self-contained compiler project and touches the m1max-host identity anchor; it needs its own lane with the owner's blessing to re-anchor if numerics move.

## Task 3 — Measurement + identity

Microbench (`coop_prefill_bench`, 7 reps, med, m1-host, base driver after revert):

| shape (m,n,k) | ms med | TFLOP/s | checksum | vs ref |
|---|---:|---:|---|---|
| 512,2048,6144 | 13.20 | 0.976 | 1108324632231936 | matches |
| 512,2048,2048 | 4.42 | 0.973 | 1108324632231936 | matches |
| 512,6144,2048 | 12.38 | 1.041 | 3324973896695808 | matches |

Model-level prefill-512 on m1-host (10 prompts x 3 passes, warmup 2, greedy, temp 0, fork driver env `VK_DRIVER_FILES=/var/tmp/mesa-7faf04c-m1-host/base.icd.json`, wheel diag.2cc3067 + GDN patch venv, under `flock /tmp/m1-gpu.lock`, kernel 7.1.13-3-2-ARCH):

| metric | this run | reference (pct lane) |
|---|---:|---:|
| pure prefill tok/s | **130.92** | 130.94 |
| decode tok/s median | 34.27 | 34.25 |
| ordered_records_sha256 | **`ac1b2695…48f1`** | `ac1b2695…48f1` IDENTICAL |

Identity held. m1max-host prefill legs could not run (host dark); nothing landed, so the 274.3 tok/s / `ac1b2695` ppa baseline stands.

## Follow-ups for Main

1. m1max-host needs a power-cycle (GpuTlbLatency's own rollback path: "if not back in 10, power-cycle restores stock"). It has been down the entire lane window.
2. The codegen plateau is now fully explained (address math + barrier/staging serialization at ~3.3x off MMA roof), and both address-decomposition levers are measured dead against real hardware. Any further gain needs either (a) hardware-documented immediate addressing (ask marcan/upstream — the packer's index-immediate encoding is a fiction), or (b) the precise-math div/rcp lane.
3. m1-host `/var/tmp/mesa-7faf04c-m1-host/` holds the fresh mesa-1 clone (branch `hkc-coopmat-codegen` @ 7faf04c065c), venv (meson/ninja), clean base driver + ICD, and audit harness — reusable by future lanes.
