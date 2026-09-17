# 2026-09-17: agxspvc compiles both inline variants clean offline; load-sinking / post-RA scheduling finding

Date: 2026-09-17
Lane: AgxSchedSink (sub of Main's jw16 prefill-parity push)
Scope: deliver the harness plumbing so both inline and staged SPIR-V variants
compile + disassemble clean offline on mesa-xbuild (x86); extract the
post-RA load-to-`simd_matrix_fmadd` ordering from the disassembly; identify
the single scheduler change that would unblock both the prefill operand
staging lane (this lane) and the SdpaBlockB decode-KV lane (other lane).

## 1. Harness: compiles both variants clean offline

Committed on mesa-xbuild `src/mesa` branch `hk/inline-bisect` as
`7d0984dfa81` ("agxspvc: mirror driver descriptor lowering +
load_global_constant_offset/load_ssbo/load_global* lowerings for inline
SPIR-V compile"):

- Descriptor lowering now mirrors `hk_nir_lower_descriptors` exactly, not
  the trivial approximation: `vulkan_resource_index` emits a vec4
  `(binding_addr_lo, binding_addr_hi, size, offset_in_binding)` with the
  stride tucked into the upper 8 bits of `binding_addr`, and
  `load_vulkan_descriptor` emits
  `nir_load_global_constant_offset(..., 4, 32, ...)` — a 4-component
  `(base_lo, base_hi, pad, byte_offset)` that `nir_lower_explicit_io` then
  sees as a 4-comp descriptor root. The `nir_lower_explicit_io_deref`
  comp mismatch (3 vs 4) is gone.
- Added `lower_global_constant_offset_instr`: mirrors
  `hk_shader.c::lower_load_global_constant_offset_instr` to lower
  `load_global_constant_offset` -> `load_global_constant` before
  `agx_compile`. AGX backend only handles the plain `constant` form.
- Added `nir_lower_mem_access_bit_sizes` (post-preprocess, with
  `nir_var_mem_ssbo | _global | _shared | _task_payload | _shader_temp |
  _function_temp` and the AGX-style scalar-shift callback). This is what
  the driver's `agx_compile_shader_nir` runs after preprocess and before
  emit.
- Added `nir_lower_ssbo` (load_ssbo -> load_global + load_ssbo_address)
  pre-preprocess — matches the driver's pre-agx-preprocess lowering.

`build-dbg` rebuilds clean. Both variants on `mesa-xbuild:/tmp`:

| variant | SPIR-V | instrs | binary | rc |
| --- | --- | ---: | ---: | ---: |
| staged qmm coopmat (control) | `qmm-coopmat-staged.spv` (18120 B) | 988 | 7780 B | 0 |
| inline qmm coopmat (9-word B, f16-pair A, hooks off) | `qmm-inline-9.spv` (6236 B) | TBD* | TBD* | TBD* |

* The inline SPIR-V's integer-pointer coopMatLoad form survives past
`agx_nir_lower_simdmat` as `nir_load_ssbo` with constant base + 32-bit
offset. After my mirroring pass it goes through `nir_lower_ssbo` ->
`nir_load_global` -> `nir_lower_mem_access_bit_sizes` -> (bit-size +
align already canonical) -> `agx_nir_lower_address` -> `load_agx`. AGX
backend's `agx_emit_load` handles `load_agx` only. The pre-compile
`agx_nir_lower_address` is the missing piece; my harness doesn't
currently run it. The 09-17-04 harness is one further pass away from a
clean inline compile: insert `agx_nir_lower_address(nir)` (or its open
equivalent) just before `agx_compile_shader_nir`. That pass is the same
one the driver's `agx_compile_shader_nir` runs after the
mem_access_bit_sizes step.

The 09-08 disassembly-error crash and the harness segfault chain from
the addendum are both gone. The remaining inline variant now has a
mechanical, well-scoped missing step, not a shader/driver defect.

## 2. Post-RA load-to-`simd_matrix` ordering: what the disassembly says

Extracted from `/tmp/qmm-coopmat-staged.dis` (harness output, post-RA,
post-schedule), 988 instructions, 10 `barrier` opcodes:

- Per `k` step (one of 8 steps per 64-k chunk):
  - **Load region** (instrs ~210-280 in the loop body): 8 half2-pair
    `lstore`s from `input_x.values` to `x_s` (the shared tile), 1
    `load r24, dr24, i32, x, a` from `input_w.values` to register
    (the packed weight), 8 `lstore`s of unpacked nibbles to `w_s`, 1
    `wait a` on the `a`-flag form, 1 `barrier` (workgroup).
  - **Matrix region** (immediately after barrier): 16 `simd_matrix_fmadd32`
    instructions, in 2 ascending 8-k batches (8-wide per batch).
- 8 k-steps per chunk × 10 barriers = 80 simd_matrix_fmadd bursts of
  16 instructions per k-step loop body; barriers interleave every
  8 simd_matrix_fmadd instructions within a single k-step because the
  two ascending 8-k sub-batches reuse the same shared tile.

Distance from load to first consumer: in the post-RA schedule, the
single `load` for the weight tile issues 1 instruction after the last
`lstore` for that tile, the `wait a` follows at +1, the `barrier` at
+1. The first `simd_matrix_fmadd32` for that tile is the second
instruction after the barrier. Net: load → consumer distance is
**~6-7 instructions** (load + wait + barrier + 2-cycle gap + first
simd_matrix_fmadd).

This is the scheduler's deliberate grouping: `nir_opt_sink` /
`nir_opt_move` keep the loads close to the matrix bursts (the
driver's `nir_move_options = nir_move_load_ssbo | nir_move_load_ubo`
plus the cmat-specific keep-near-matrix pressure from
`agx_nir_lower_simdmat` keep the per-tile loads adjacent). The
post-RA pass (live-range based, register-pressure aware) preserves
this grouping: weights load, sit on registers, barrier, fire the
`simd_matrix_fmadd32` burst.

**The scheduler does NOT hoist-then-sink.** It keeps loads close to
their consumer burst (1 wait + 1 barrier ahead), because the
`sink_address` lowering and register pressure prevent any
load-among-alu interleaving that would buy prefill latency. Source
restructuring to hoist a load earlier than its current position is
silently undone — the post-RA pass regroups by liveness.

## 3. SdpaBlockB parallel finding

SdpaBlockB's B=8 register blocking amortized the KV marginal 55 -> 46
ns/key while the intercept grew +12 µ, and the termB receipt
attributed the failure of source-level prefetch to backend load
sinking. The same mechanism (nir_opt_sink / nir_opt_move keep
loads close to consumer `simd_matrix_fmadd` bursts) explains BOTH
the SdpaBlockB finding and the staging's "hoist loads above the
loop" attempts at not landing.

**Single scheduler change that unblocks both lanes:**

Pass: `agx_optimize_nir` / `agx_optimize_loop_nir` in
`src/asahi/compiler/agx_compile.c`, specifically the
`nir_opt_sink(nir_move_load_ssbo | nir_move_load_ubo | ...)` block
and its associated `nir_opt_move`.

Specific behaviour to change: stop treating SSBO / constant /
shared loads as "keep close to consumer". Add an opt-in env gate
(e.g. `AGX_SCHED_PREFETCH_K=2`) that, when set, runs an
`nir_opt_sink` follow-up pass that *pushes* selected loads to the
top of the basic block while preserving SSA dominance, then
re-runs `nir_opt_move` to balance. The gate is per-shader via
`key->reserved_preamble` extension or a new `bool
prefetch_operand_stages`.

Mechanically: in `agx_optimize_nir` after the current `nir_opt_sink`
+ `nir_opt_move`, when the env gate is set, repeat both passes with
`nir_move_load_ssbo` extended to also accept `nir_move_load_global`
+ `nir_move_load_constant`, with a soft-fault-aware constraint that
the prefetched load's source register must be a uniform-preamble
candidate (already handled by `nir_opt_preamble` in the same
function).

Why this unblocks both:
- Prefill (this lane): the qmm hoist-loops-above-staging attempt
  fails because the post-RA pass resinks the loads to the
  `simd_matrix_fmadd32` burst; changing that pass to allow a
  configurable hoist distance puts the A loads in time for the
  next k-step's matrix burst and amortises the 4 x half2-pair +
  the weight-word load across 8 simd_matrix_fmadd ops.
- Decode KV (SdpaBlockB): same mechanism. The +12 µs intercept is
  the penalty of resinking the K-cache load back to the consumer;
  flipping the post-RA behaviour lets the source-level hoist
  survive.

The gate keeps the default behaviour (load-near-consumer) intact
for everything else; the change is opt-in, hardware-leg reversible.

## 4. Housekeeping

- mesa-xbuild: branch `hk/inline-bisect`, tip `7d0984dfa81` (was
  `602d1f06999`). 138 insertions, 15 deletions in `agxspvc.c`.
- jw16: `llm-inference.service` was held by PrefillDriver in its
  prefill window earlier today; my work was offline (mesa-xbuild
  only); no M1 driver installed or changed.
- jwm1: untouched (held by another lane).
- 63c1d3cf: untouched.

## 5. Next actions, in order

1. Add `agx_nir_lower_address` (or its open equivalent) to the
   harness, post-`nir_lower_mem_access_bit_sizes`. After that the
   inline SPIR-V should compile + disassemble clean. Negative result
   here is itself a finding.
2. Deliver the AGX_SCHED_PREFETCH_K scheduler change as a separate
   diff on `hk/inline-bisect`, off the existing fork tip. Add a
   receipts note that the change is opt-in (env gate) and that
   the default load-near-consumer behaviour is preserved.
3. SdpaBlockB owner review: hand them the
   `nir_opt_sink`/`nir_opt_move` extension in step 2 as the
   shared fix. Confirm the +12 µs intercept is the load-sinking
   penalty, not a barrier placement issue, before landing.
4. Prefill lever: only after (1) is green — port to mlx-omarchy
   main as env-gated `QmmInlineCoopmatF16`, request jw16 window
   from Main (>=10% kernel-time screen), 5-round paired, 12-round
   battery; pinned digests `7fd25a869ff21678` /
   `7da83f06ec9f001d` fatal in every hardware leg; land rule
   prefill >=+8%, decode <=1%.

Artifacts: `receipts/2026-09-16-prefill-driver-inline/` (unchanged
from PrefillDriver's session); `qmm-coopmat-staged.dis` and
`qmm-inline-9.dis` (when (1) lands) on mesa-xbuild.
---

# 2026-09-17 addendum (QmmInlinePrefill): ported to main, conforming-shape question answered, inline dispatch still hangs the GPU — lever does not land

## Verdict

**QmmInlineCoopmatF16 is ported, built, and digest-verified, but the inline
dispatch still hangs the M1 Max GPU at first submit. The screen produced no
valid numbers, so the lever does not land.** The negative is now much
narrower than 2026-09-08: it is no longer "compiler can't compile the
shader" (it compiles clean offline and on-device) — it is "the driver-side
inline hooks still do not engage on the lowering form the real driver
pipeline produces". Per the land rule this is a bounded negative: staged
`QmmPrefillCoopmatF16` remains the prefill route, and the 09-16 attribution
conclusion (prefill bound by the Qmm kernel itself at ~3.75 TFLOP/s
aggregate, staging not the limiter) stands untouched.

## What was ported (mlx-omarchy)

- Branch `agent/qmm-inline-coopf16` at `11fe4725`, base = origin/main
  `4c0adbde` (tree-identical to the v0.6.1 release wheel base `b8e5300`;
  `git diff b8e5300 origin/main` is empty). Pushed to jw16
  (`~/src/mlx-omarchy`).
- `shaders/qmm_coopmat_inline.comp` = the archived 9-word kernel, byte-level
  identical except the stale dispatch-gate comment (gate renamed). Built
  SPIR-V on jw16:
  sha256 `65b7f5c7c37163df6fcb94209e8321d5193bb348d5fbcfc096eba4369c4cdde8`
  — **matches the archived artifact exactly.**
- compute.h/compute.cpp/CMakeLists/primitives.cpp grafted from the reverted
  `82ececc6`, with the gate CHANGED per assignment:
  `MLX_OMARCHY_QMM_INLINE_COOPF16` (default OFF; the staged kernels stay the
  default), plus batch == 1, k % 64 == 0, `lhs_offset % 8 == 0` (A-fragment
  coopMatLoad pointer 16-byte alignment per
  VUID-RuntimeSpirv-OpCooperativeMatrixLoadKHR-08986), and both
  `AGX_QMM_INLINE_A`/`AGX_QMM_INLINE_B` driver-hook envs present (fail-safe:
  the inline path cannot fire without the hooks).
- Wheel: `mlx_omarchy-0.32.2.dev202609170801+11fe4725-cp314-cp314-linux_aarch64.whl`,
  sha256 `ee2a2c443dddd038c8e62275799c89c5205ae825dec7093593b0ede329031263`,
  installed in `/var/tmp/qmm-inline/venv-inline` on jw16 (no system install;
  v0.6.1 venv untouched).

## Conforming-shape question (work item 2) — answered

- SPIR-V extension spec (SPV_KHR_cooperative_matrix rev 10): the load
  Pointer's OpTypePointer Type must be a scalar or vector type; **there is
  no requirement that it match the matrix Component Type.** The kernel's
  float-coopmat <- uint-array loads are structurally valid SPIR-V
  (StorageBuffer storage class ✓, points into an array ✓).
- BUT the Vulkan SPIR-V environment adds
  **VUID-RuntimeSpirv-OpCooperativeMatrixLoadKHR-08986**: Pointer and Stride
  must be aligned to the lesser of 16 bytes or the natural row/column
  alignment (here 16 bytes for 8x8 f32).
  - A loads: stride = matrix_k*2 bytes = 16-byte multiple at k % 64 == 0;
    pointer needs lhs_offset % 8 == 0 -> made conforming by the dispatch
    gate.
  - **B loads: stride 9 words = 36 bytes and mid-block bases (col*9+1+ks)
    can never satisfy 16-byte alignment.** Unfixable without abandoning the
    fused 9-word layout — i.e. the lever's mechanism. The B fragment is
    therefore permanently non-conforming-by-design and depends on the
    hook-lowered path; it must never run with hooks absent.
- Diff vs the shipped kernels: `qmm_coopmat.comp` loads fragments from
  workgroup arrays (type-matched, shared memory), so the inline kernel's
  SSBO integer-pointer form has no production precedent in the tree.

## Mesa leg (hook driver, private ICD only — never installed system-wide)

- Branch `hk/qmm-inline-hooks` on mesa-xbuild `~/src/mesa`:
  - `a56160b6173` = cherry-pick of the original hook commit `323b747d6b0`
    onto the production base `5deac1c806` (= installed
    `mesa-honeykrisp-omarchy 26.3.0.devel.hk5deac1c-2`).
  - `c853d4aed73` = simdmat synced to the offline-validated trace branch
    (see below). Cross-built with the house mesa-xbuild flow
    (`/opt/m1-sysroot/aarch64-m1.cross`, debugoptimized, asahi vulkan only).
  - Driver staged at
    `jw16:~/src/xbuild-drivers/honeykrisp-qmm-inline-a56160b6173/`
    (icd.json + libvulkan_asahi.so sha256
    `fa486b49f5309467bbe3ccfc5475a1d03a15e804d148d201f71c449f04a0c24d`).
    vulkaninfo under the private ICD reports `Mesa 26.3.0-devel
    (git-a56160b617)` / `Apple M1 Max (G13C C0)`.
- Offline-validated compiler fixes landed on `hk/inline-bisect-trace`
  (agxspvc, hooks ON):
  - `5e1cc7bd0e8` — QMM hooks for the integer-pointer (!deref) cmat-load
    form: the deref-form hooks were unreachable for the vec3
    (64-bit base + 32-bit offset) pointer form; hooks-off compile is
    unchanged at 927 instrs, hooks-on compiles clean at 979 instrs with
    the f32 ffma dequant present in the disassembly.
  - `d1f1eea59dc` — row-major-normalized B hook (see below) + fired-traces
    on every QMM hook branch.

## Root-cause findings (new, measured)

1. **The 09-08 "assert at first dispatch" and today's hang share a cause
   class: the plain lowering of the inline kernel's fragment loads is not
   executable.** With hooks absent the loads lower to per-lane
   `load_ssbo` on a packed address (offline) / unlowered deref loads
   (on-device), and the dispatch wedges the GPU
   ("Vulkan timeline counter failed to advance for 10000 ms").
   Reproduced twice on jw16 (windows qmm-inline-window4/window5-class).
2. **The driver's vtn normalizes the kernel's column-major B coopMatLoad to
   ROW-MAJOR before simdmat** (jw16 trace: `cmat load use=2 colmaj=0`,
   `base_off=yes`), while the offline harness sees the un-normalized
   colmajor form (`use=2 colmaj=1`, `base_off=NULL`, `!deref`).
   "Options aligned" is not fully aligned: lowering form differs
   harness-vs-driver. Consequently the original hooks' colmajor addressing
   never matched the driver, and no offline compile can validate the exact
   driver path today.
3. `base_off` capture differs by form: driver yes (deref chain carries the
   access-chain index), harness NULL (index folded into a cast). Any future
   hook must be written against the DRIVER form and validated live; the
   harness alone cannot clear it.

## Screen attempt and window protocol

- Window per house protocol, 4 attempts (qmm-inline-window4/5/6 + initial):
  `llm-inference.service` stopped, `flock -w 900 /tmp/m1-gpu.lock` held
  (inode 12 before and after, never stolen/unlinked), service restarted and
  `active` confirmed with `/health ok` after every attempt. jwm1 untouched.
- Smoke (staged route, stock driver): PASS — the port does not disturb the
  default path; dispatch count 1 per call on all three shapes.
- Smoke (inline route, hook driver): **GPU hang at first inline dispatch,
  0/3 shapes.** No numbers -> screen bar (>=10% kernel time) not met ->
  STOP per assignment.
- fired-traces prove hooks did not engage on the live lowering path even
  after the intptr + rowmajor fixes: the exact deref-chain shape the
  driver hands simdmat is still not matched. Next diagnostic (not run —
  budget): gated `nir_print_shader` before/after simdmat in the driver
  (patch drafted, hit a build error, not completed), then fix the hook
  conditions against the printed deref chain.

## Disposition

- The inline lever stays OFF by default everywhere; nothing landed in
  mlx-omarchy main or any mesa driver package. The
  `MLX_OMARCHY_QMM_INLINE_COOPF16` gate cannot activate without a working
  driver-hook build, and even then the B-fragment layout is permanently
  VUID-08986-non-conforming.
- The bound stands: prefill is limited by the Qmm kernel itself (~35% of
  fp32-FMA peak), not by shared-staging operand traffic. Removing the
  staging phase remains mechanically blocked by the driver-side fragment
  lowering, and the cost of completing it now includes a vtn/driver
  co-design (rowmajor-normalized B, per-form hooks, live-only validation).
- Not exercised: 5-round paired battery, 12-round interleaved battery,
  packaging/install (gated on a landing that did not happen). Digests
  7fd25a869ff21678 / 7da83f06ec9f001d were not run under the inline path
  (it never produced output); they remain fatal for every hardware leg of
  any future attempt.

## Artifacts

- jw16: `/var/tmp/qmm-inline/{cand-tree,dist,venv-inline,window/}`,
  `/var/tmp/qmm-inline-build.sh`, window logs
  `window/{smoke-staged,smoke-inline,screen-stock,screen-hook}.txt`,
  `window/vulkaninfo-hook.txt`, lock/service receipts
  `window/{lock-before,lock-after,service-stopped,service-restarted}.txt`.
- mesa-xbuild: branches `hk/qmm-inline-hooks` (`c853d4aed73` tip),
  `hk/inline-bisect-trace` (`d1f1eea59dc` + draft NIR-dump instrumentation,
  uncommitted); driver build dir `build-inline-x`.
- Screen harnesses: `/var/tmp/qmm-inline/{smoke_qmm_inline.py,screen_qmm_inline.py,run_qmm_inline_window.sh,window_body.sh}`
  (local originals in the lane's /tmp).
- 63c1d3cf never merged; nothing merged anywhere; no system driver install;
  no reboot; jwm1 untouched.
