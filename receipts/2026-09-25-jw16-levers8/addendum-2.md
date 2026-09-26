# jw16-levers8 addendum 2 — translator cache proven and landed on mlx-omarchy main (2026-09-26)

Owner: Jw16Levers8. Follows addendum.md. Implements Main's directive:
remove the measured per-process translation cost, reuse the existing
content-addressed SPIR-V cache, no new abstraction.

## 1. What landed (mlx-omarchy origin/main 79ded5ac4)

Cherry-picked onto main as 14d3a7fad + 79ded5ac4 (single file,
overlay/mlx/backend/omarchy/custom_kernel.cpp, +170 lines):

- `translation_cache_path(identity)`: same `spirv_cache_root()` as the
  GLSL→SPIR-V layer (MLX_OMARCHY_SPIRV_CACHE opt-out/relocation
  honored), material = translator revision constant ("1") + the full
  `cached_translation` identity (source, grid, threadgroup,
  output_count, compile_mode), SHA-256-named `.tr` entries.
- `serialize/parse_translation`: full Translation struct on disk (glsl
  string + every Parameter: type, name, binding, scalar, atomic) —
  eval_gpu's consumer contract (parameters for bindings, glsl for the
  pipeline key) restored byte-identical on hit; strict bounds +
  total-consumption validation.
- Atomic tmp+rename store (pid-suffixed), identical to the SPIR-V
  layer's discipline.

The pipeline-cache commits (f97afca13/9efb728a2) remain UNMERGED —
still performance-neutral; they ride only on the agent branches.

## 2. Process bugs caught before/during hardware proof

- Compile gate on PVE caught the missing DeviceTable registration
  (9efb728a2) before any device window.
- The first hardware A/B of the translation cache showed NO hit; an
  mtime + filename-set experiment (identity deterministic across
  processes, files rewritten every run) isolated the fault to load, and
  a byte-level walk of a real on-disk entry reproduced it: get_string/
  get_u64 did not charge the 8-byte length fields to the remaining
  counter, so the strict total-consumption check rejected every valid
  entry. Fixed in ccfb97fb1; verified against all 12 real entries
  (old parse 0/12, fixed 12/12). On-disk format unchanged.

## 3. Hardware A/B on jw16 (T6001, fresh process each, all pins green)

Wheel 0.32.3.dev202609261344+ccfb97fb1
(sha256 f2a0caec70347d5849f96284d2710a868bbe7fc835e53d14814d105674707353):

| measurement | before (f26192bbf) | after (ccfb97fb1) |
|---|---:|---:|
| fresh-process mel call 1 (melprof2 A/B) | 110.8 / 112.0 / 146.4 ms | **31.2 / 28.6 ms** |
| warm transcribe mel_frontend (3 passes) | 110.6-117.1 ms | **29.0-30.4 ms** |
| full warm transcribe total | 1207-1240 ms | **1125.9-1126.4 ms** |
| resident r1 startup | 1242.8 ms | **1113.5 ms** |
| resident r2-r4 warm | 633-636 ms | 634.4-636.2 ms (unchanged, memo already warm) |
| cold (all caches cleared) first eval | 10.15-10.23 s | 18.5 s incl. the previously-warm 9.8 s glslc -O leg (cold-cost class preserved and now fully visible) |
| GPU digest 3-pass | bc519c03… | **bc519c03… exact** |
| Parakeet golden pins | all pass | **all pass** (warm0/pin-1/2/3/corrupt/resident r1-r4, 104/104) |
| truncated .tr corruption probe | — | tolerated: strict parse rejects, one kernel re-translates, all pins green (mel 49.6 ms that pass) |

Attribution: the removed ~81 ms/process is exactly the translate_msl
regex pass that perf attributed (~40% of first-call samples), now
reused from disk. Remaining warm per-process budget is dominated by
ANE encoder exec (440 ms) and TDT (131 ms) as before.

## 4. Merge discipline

- main received ONLY the proven win: `git diff 1faf7f00 origin/main --
  custom_kernel.cpp` is empty, so the cherry-picked content is
  byte-identical to the A/B-tested code; the neutral pipeline-cache
  commits stay on agent/pipeline-cache + agent/pipeline-cache-ab for
  the jwm1 A/B (Jwm1Kernels2 notified twice).
- File-ownership split with Jwm1Kernels3 honored: he owns
  primitives.cpp + gated_delta_prefill.shaders (agent/
  jwm1-kernels3-gdn-prefill); zero overlap with custom_kernel.cpp.

## 5. PMP extraction progress (off-device, no hardware action)

- SystemKernelExtensions.kc.levers7 is a PLAIN Mach-O (no compression);
  parsed its 172 LC_FILESET_ENTRY (0x80000035) entries: identifiers only
  cover on-demand kexts (AMD* et al.) — no ApplePMP* and no firmware
  payloads there either.
- Net position: the PMP firmware blob is in NEITHER kext collection.
  Remaining candidate sources for identity-verified firmware: the boot
  KC's ApplePMP.kext full content (its sections reference regions
  outside the committed boot macho — a SystemKC-side parse of that
  driver may still hold it), the macOS volume, or iBoot/NOR
  provisioning. Until one of those yields a verified blob, PMP stays
  unbootable-by-us, per Main's no-rail-writes directive. Phase-0
  (power-gated read-only PMP SRAM + ASC CPU_CONTROL dump) remains the
  smallest discriminating hardware step and stays behind the reviewed
  plan gate.

## 6. Host state

jw16: ccfb97fb1 wheel installed and pinned-green; caches warm
(spirv/pipelines/tr + Mesa); llm-inference active, real completion
verified after the last window ('OK', finish=stop); GPU lock with
llama-server only; ANE untouched at 5ecff86. Rollback: prior wheel
snapshot in /var/tmp/levers8-rollback (pre-lane state) and the
f26192bbf wheel rebuildable from agent/pipeline-cache-ab.
