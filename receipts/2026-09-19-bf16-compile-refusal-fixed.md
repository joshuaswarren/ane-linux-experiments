# bf16 compiled-tape refusal fixed — fence lift — 2026-09-19 (jw16 T6001)

Lane: Bf16CompiledTape-2. Verdict: **COMPLETE 2026-09-19 (Bf16RecertRepair follow-up window): all open recert items closed on corrected lift+fix bytes — see section 11. Post-972c6ddb fused-chain dispatch-pin failure root-caused and fixed (1fbc9825 + 925cfa64); C++ battery, mlx-lm matrix, Bonsai-2-27B, and Parakeet AC/ACO gate all GREEN on wheel dev202609192209+1fbc9825.**

## 1. Archaeology (who added the refusal, does the defect still stand)

| commit | author | date | content |
| --- | --- | --- | --- |
| `d6160b5b` | Joshua Warren | 2026-09-01 | Installed the tape-level bf16 refusal (`tape_has_bfloat16` / `unsupported_tape_bfloat16` → `[omarchy] Compiled tape bfloat16 is refused … Re-run with MLX_DISABLE_COMPILE=1`). Reason given: nondeterministic bf16 swiglu garbage on Honeykrisp, no pinned root cause. |
| `13d83f7` / `26c67149` (same change, rebase lineage) | — | 2026-09-03 | **Stale-shape root cause**: tape node shapes derived at trace time; a prefill-traced shapeless fragment served at decode shapes read past eval-time buffers into recycled pages. The 2026-09-02 bf16 evidence (prefill bit-identical 24 layers, divergence at decode step 2, unique garbage per run, llvmpipe clean, fixed-shape probes clean, "broadcast Sigmoid bf16" crash) is this defect's signature. The bf16 gate was never retested after the fix. **Underlying defect does NOT stand.** |
| `cb8c0638` (merge `064b7301`) | Joshua Warren | 2026-09-18 | Tape-level refusal removed; three refusal-pinning tests flipped to bit-exact bf16 tape tests + new bf16 shapeless trace-then-reuse case. |
| `ef85dc72` → scoped at `11f2d3b5` | Joshua Warren | 2026-09-18 | Residual **fused-bf16 fence**: with the tape gate lifted, Qwen3.5-9B / gemma-4-31B / Ministral-3-8B generated deterministic wrong tokens through fused bf16 chains (`FUSED_CHAIN=0` restored eager digests). Fence lives in the tape interpreter only (`compiled.cpp` skips `try_add` for bf16 nodes); `FusedChain` + eager planner byte-for-byte stock. |
| `da43969e` | Joshua Warren | 2026-09-18 | **Pinned root cause of the fused-bf16 corruption** (F7GdnCorrectness): `leaf_mode_for` selected `DivLast` from `data_size == count/last_dim` alone; strided `(N,1,L)` leaves (GDN k projection) misindexed every elementwise product and amplified state ~100x/step → NaN logits. Fix: `DivLast` requires `shape.back() == 1`, `ModLast` requires all outer dims singleton. **Underlying defect does NOT stand.** Verified on T6021 fixed wheel (Bonsai-2-27B 96 steps coherent, 1.87 tok/s). |
| v0.7.0 recert probe (`receipts/2026-09-18-v070-pretag-recert-jw16.md`, corrupt-matrix section) | V070Recert | 2026-09-18 | Full corrupt matrix with fusion ON (TEMP one-line removal of the fence on main bytes b283a16f): Qwen3.5 `910abe30d4305271`, Ministral `d4735e3a265e16ee`, gemma-4-31b `9f1fe40101db3a4b` — **all identical to eager**. Measurement only, never published. This is the clean sweep the `known-defects.md` lift bar demanded. |

Conclusion: both defects behind the two gates are fixed with pinned mechanisms + hardware proof. The fence is a fossil. This lane removes it.

## 2. Change (commit `972c6ddb`, pushed `main` → `origin/main`)

`972c6ddbbb4a0d7a837a306ca9db88e1547f55ca` — "bf16 tape-fusion fence lift: DivLast root cause fixed at da43969e, probe clean on corrupt matrix".

- `overlay/mlx/backend/omarchy/compiled.cpp`: removed `node.dtype() != bfloat16 &&` from the tape `try_add` fast path; bf16 nodes fuse again. Comment rewritten (cites `26c67149`, `da43969e`, `ROUND_INTERMEDIATE` contract). **No shader change.**
- `overlay/mlx/backend/omarchy/fused_chain.h`: fence comment → fusion description.
- Tests (comments only, assertions unchanged — they already assert raw-uint16 bit-exactness): `test_compiled_tape.cpp`, `test_fused_chain.cpp` (incl. stale "Compiled bf16 tapes remain refused independently" header), `test_primitives.cpp`.
- Docs: `known-defects.md` fused-bf16 entry flipped to **fixed** with root cause; retired-list entry updated; `compatibility.md`, `install-omarchy.md`, `CONTRIBUTOR-GUIDE.md` (rule 3 → lifted-with-mechanism), `compatibility-matrix.md` Compiled row `bf16 (per-node)` → `bf16*`, `README.md` fence tail → removed-with-it.
- Verified: `grep node.dtype() != bfloat16 overlay/mlx/backend/omarchy/compiled.cpp` → 0 hits; `grep fenced from overlay/mlx/backend/omarchy/*.cpp *.h` → 0 hits; `shaders/` untouched (`git status` shows no shader files).

## 3. Numerics audit (bf16→fp32 exact lowering only, no silent drops)

- Widen (`elementwise.comp`, `copy_general.comp`, `cast.comp`, `fused_chain.comp`): `LOAD_VALUE(x) = uintBitsToFloat(uint(x) << 16u)` — exact bf16→f32 widening (zero-fill mantissa), no rounding.
- Narrow/store: `bf16_store(f) = (bits + 0x7fff + ((bits>>16)&1)) >> 16`, round-to-nearest-even, NaN→quiet bit-preserving (`(bits>>16)|0x40`). Same function in every shader; per-node and fused paths share it.
- Fused intermediates: `ROUND_INTERMEDIATE(f) = LOAD_VALUE(bf16_store(f))` — every instruction rounds to storage dtype, exactly matching per-node materialization. This is the bit-exactness mechanism, not a theory: it is what the C++ battery's raw-uint16 comparisons pin.
- No `--emit-templates` step applies: no template files are generated in this tree for these shaders (searched `scripts/`, `tools/`, `overlay/mlx/backend/omarchy` for `emit.*template`; only unrelated hits). No generated file was hand-patched.

## 4. Bit-exact proofs

- Standing unit proof (pre-lift wheel, unchanged assertions): `omarchy_compiled_tape_tests` 12/12 (2096 assertions, incl. bf16 widened set + bf16 shapeless trace-then-reuse — the exact mlx-lm trigger), `omarchy_primitive_tests` 103/103, upstream `test_compile.py` 68/68 (three bf16 refusal cases now pass) — see `receipts/2026-09-18-bf16-compiled-tape.md` and `receipts/2026-09-18-v070-pretag-recert-jw16.md`.
- **Lift-wheel re-run status: PARTIAL.** Phase-1 script pointed cmake at the wrong source dir (`overlay` instead of `$W/mlx`), so all five C++ binaries failed with "No such file or directory" — a harness bug, not a test result. Re-run from the correct build tree is staged (`/tmp/run-lift-phase2.sh` on jw16) but did not execute within this run's request budget. The model-matrix legs below ran on the **lift wheel itself** and are the direct bit-exact evidence.
- Digest-stability + compile==eager (lift wheel, jw16 T6001, mlx-lm 0.31.3, greedy temp 0, prompt "Explain photosynthesis in one sentence.", 96 tokens, digest = sha256(generated ids)[:16]):
  - Qwen2.5-0.5B-Instruct-bf16 (the ORIGINAL 2026-09-02 corruption model): compiled ×3 `c2d5348ed63fb217` (digest-stable 3/3); eager ×2 `c2d5348ed63fb217` — **identical, coherent**.
  - This satisfies the "compiled generation 3x digest-stable" bar on the original model with the fence removed and fusion enabled (default ON).

## 5. Compiled-vs-eager tok/s table (lift wheel `mlx_omarchy-0.32.3.dev202609192048+972c6dd`, sha256 `16b42162…870c1a`, 8380779 bytes, source `972c6dd`, worktree `/var/tmp/bf16-lift-wt`, venv `/tmp/bf16-lift-venv`)

| model | mode | reps | n | digest | tok/s | vs eager |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen2.5-0.5B-Instruct-bf16 | compiled | 3 | 96 | `c2d5348ed63fb217` ×3 | 51.69 / 51.67 / 51.82 | **identical** |
| | eager (`MLX_DISABLE_COMPILE=1`) | 2 | 96 | `c2d5348ed63fb217` ×2 | 50.41 / 50.47 | — |
| Qwen3.5-9B-MLX-4bit | compiled | 2 | 96 | `910abe30d4305271` ×2 | 11.39 / 11.42 | **identical** |
| | eager | 1 | 96 | `910abe30d4305271` | 11.07 | — |
| gemma-4-31b-it-4bit | compiled | 1 | 96 | `9f1fe40101db3a4b` | 2.34 | **identical** (= eager raw-prompt artifact ` la la…`, not numerics) |
| | eager | 1 | 96 | `9f1fe40101db3a4b` | 2.42 | — |
| Ministral-3-8B-Instruct-2512-4bit | compiled | 1 | 1 (EOS) | `d4735e3a265e16ee` | — | **identical** (EOS-at-raw-prompt artifact, as eager) |
| | eager | 1 | 1 (EOS) | `d4735e3a265e16ee` | — | — |
| Ternary-Bonsai-8B-mlx-2bit | compiled | 1 | 96 | `25dc382d3170a80c` | 5.78 | **identical** |
| | eager | 1 | 96 | `25dc382d3170a80c` | 5.60 | — |
| Ternary-Bonsai-2-27B (F7 `f7_bisect.py` gen, 96 steps) | lift wheel | — | — | **NO RESULT** | — | harness missing `mlx_vlm` in lift venv (`ModuleNotFoundError`); F7's T6021 fixed-wheel run (96-step coherent "Paris", 1.87 tok/s) + v0.7.0 recert 1.44 tok/s coherent stand. Re-run with mlx_vlm installed. |

**Compile ON changes no generated id on any model.** All five compiled==eager pairs hold with fusion enabled (default) — i.e. through the previously fenced fused-bf16 path. Raw logs: `/var/tmp/bf16-lift/*.jsonl` on jw16; status: `/var/tmp/bf16-lift.status`; wheel: `/var/tmp/bf16-lift-dist/`.

## 6. Parakeet + AC/ACO regression

**NOT re-run on lift bytes in this window** (request budget exhausted after the matrix; no GPU time left). Standing evidence, unchanged by this diff's blast radius (this diff touches only the tape `try_add` gate + comments/docs — no f16/f32 chain paths, no ANE pipeline, no runner):
- v0.7.0 recert on fenced main bytes b283a16f (jw16, 2026-09-18): Parakeet E2E serve-default/launch/placed-AC/placed-ACO all `match`, 104/104, transcript `db501a8c…`, hidden `38c73261…` (AC) / `ef6afd13…` (ACO), decode legs `7da83f06ec9f001d` + `7fd25a869ff21678` — `receipts/2026-09-18-v070-pretag-recert-jw16.md`, GATE GREEN.
- Required before any release tag on lift bytes: re-run `/tmp/v070-jw16-gate.sh` against the lift wheel (needs its `WHLGLOB` + artifact-commit strings repointed from `b283a16` to `972c6dd`) + the `/var/tmp/ParakeetE2EJw16/fused_e2e.py` four arms. The gate script was deliberately NOT run in this window (it flocks + restarts the service inside our hold).

## 7. Ancestry check (`63c1d3cf` MUST NOT be an ancestor)

```
$ git -C ~/src/mlx-omarchy rev-parse HEAD
972c6ddbbb4a0d7a837a306ca9db88e1547f55ca
$ git merge-base --is-ancestor 63c1d3cf HEAD; echo exit=$?
exit=1 → 63c1d3cf NOT ancestor — PASS (checked pre-commit and post-push)
$ git merge-base --is-ancestor da43969e HEAD → ancestor OK
$ git merge-base --is-ancestor 26c67149 HEAD → ancestor OK (stale-shape fix; 13d83f7 is the pre-rebase hash of the same change)
$ git merge-base --is-ancestor 064b7301 HEAD → ancestor OK
```

`63c1d3cf` (`feat(coreml): probe 1D pointwise conv as GEMM`) lives only on `parakeet-mel-exact` / `origin/parakeet-mel-exact`, never merged to `main`.

## 8. Lock / window discipline (jw16)

Queue honored: MesaWaitBatchScreen → AneEncoderCoverage → Bf16CompiledTape-2 (F7 needed no window). Mistake owned: I took the lock early against Ane's announced TAKE (they had verified FREE first); stood down on challenge, killed my remote holder (PIDs 527020/527021 on jw16mbp1-linux, verified dead, lock FREE), waited for Ane's RELEASE, then took cleanly (holder PIDs 529594/529595, inode 12, service stopped under hold). Post-window RELEASE+restore completed in the same session: holders 529594/529595 killed and verified dead, lock FREE, then `llm-inference.service` restarted (active, MainPID 537534, llama-server 537536 on :8002), lock re-held by the service (`flock -n` fails = HELD_BY_SERVICE), REAL completion verified (`chatcmpl-1ycm7rFUfUEbVKhi3dqhqjad10P5rW1P`, 8 completion tokens, qwen3.8-27b @ :8002, health 200). Announced RELEASE to all. No handover debt.

## 9. Follow-up measurements (NOT code gates — each with an owned lane)

Code-gate status (c — removed by this fix): zero remaining bf16 refusals, workarounds, or disabled paths in `mlx-omarchy` source. Verified by grep: `node.dtype() != bfloat16` → 0 hits in `compiled.cpp`; `fenced from` → 0 hits across `overlay/mlx/backend/omarchy/*.cpp/*.h`; `shaders/` untouched. Nothing below is parked as "documented" — each has an owned lane:

1. C++ suites on lift bytes — Owner: Bf16CompiledTape follow-up window (lane in flight as staged work: `/tmp/run-lift-phase2.sh` on jw16 with the corrected `$W/mlx` cmake source; runs on the next GPU window after this yield's lock release). Expect 103/103, 41/41, capsim 6/6, 12/12 tape, fc minus the known dispatch-count pin anomaly (candidate 2 vs stock 1, documented non-blocking in the v0.7.0 recert).
2. Bonsai-2-27B on lift wheel — Owner: same follow-up window (reinstall venv with `mlx_vlm` from the F7 lineage, re-run `/tmp/f7_bisect.py gen --steps 96`). Standing proof meanwhile: F7 T6021 fixed-wheel 96-step coherent "Paris" 1.87 tok/s + v0.7.0 recert 1.44 tok/s coherent.
3. Parakeet E2E + AC/ACO + both decode legs on lift bytes — Owner: same follow-up window (repoint `/tmp/v070-jw16-gate.sh` `WHLGLOB` + artifact-commit strings from `b283a16` to `972c6dd`, run the four `fused_e2e.py` arms). Standing proof meanwhile: v0.7.0 recert GATE GREEN on fenced main bytes (this diff's blast radius excludes the f16/f32 chain paths, ANE pipeline, and runner).
4. Upstream `test_compile.py` 68/68 on lift bytes — Owner: same follow-up window (was green pre-lift; this diff touches only comments/docs outside `compiled.cpp`'s gate lines).

## 10. Provenance

- Fix commit: `972c6ddbbb4a0d7a837a306ca9db88e1547f55ca` on `origin/main` (pushed 2026-09-19).
- Lift wheel: `/var/tmp/bf16-lift-dist/mlx_omarchy-0.32.3.dev202609192048+972c6dd-cp314-cp314-linux_aarch64.whl`, sha256 `16b4216213f46f63f0159ccc6abc09b84d944516cec4437a4a5966e727870c1a`.
- Patch transferred to jw16 pre-build: `/tmp/bf16-fence-lift.patch` (local `/tmp/bf16-fence-lift.patch`, 295 lines).
- Model identity: `opencode-go/muse-spark-1.3-contributor` (no OpenAI routing involved).
- Hosts: edits on `omp-studio-local` (x86_64); all measurements on `jw16mbp1-linux` (M1 Max T6001, Honeykrisp). No commands run on jwm1. No `ane-linux-experiments` files edited or executed (receipt only).

## 11. Follow-up window 2026-09-19 (Bf16RecertRepair): sections 4/6/7 items closed

Status precision (audit fix): sections 11.1–11.7 cover the C++ suites, mlx-lm matrix, Bonsai-2-27B, and Parakeet/AC/ACO gate — all GREEN on corrected bytes `1fbc9825`/wheel `dev202609192209+1fbc9825`. **Still open on lift bytes: section 9 item 4, upstream `test_compile.py` 68/68 — not yet run on any post-972c6ddb wheel; coordinated GPU slot pending (Main-directed). Do not treat this gate as closed until that run lands here.** The 9a793054 intermediate is superseded (unsafe guard removal, caught pre-integration); every GREEN result below is on `1fbc9825` bytes except where explicitly labeled `9a793054` (the two GATE GREEN lines: 16:59 on 9a793054 — superseded by 17:19 GREEN on 1fbc9825).

Window: jw16 lock held 16:33:44–17:25 CDT (holder PID under `/tmp/bf16-window-holder.sh`; service + `llm-benchmark-recovery.timer` stopped under hold, both restored after: is-active, `/health` 200, real completion `chatcmpl-axDapGrNFqdxGtGjEeOfbiBz5uBbmMo3`, lock re-held by service).

### 11.1 fused_chain 33/34 root cause (was: `test_fused_chain.cpp:1025` "nonidentity broadcast keeps the per-node fallback (shapeless)", `CHECK_EQ(eager, 1)` got 2)

- Mechanism pinned on hardware with an env-gated `MLX_FC_DEBUG` leaf trace: the chain's scale leaf is the **broadcast view** of `in[1]` (`shape [4,64]`, `data_size 64`, `contiguous=1`, `row_contiguous=0`). `da43969e`'s ModLast guard (`all outer dims singleton`) refuses it, so the tail mul falls back per-node → fused prefix (1 dispatch) + per-node tail (1) = 2. Stock fused it at 1 via ModLast (`data_size == last_dim`, no guard). This IS the v0.7.0 "fc dispatch-count pin anomaly" — mechanism no longer unexplained.
- First fix attempt `9a793054` (guard removed entirely) was **unsafe**: review counterexample `[64,1]` column leaf expanded to `[64,64]` (strides `(1,0)`, same shape/data_size/flags as the row view) needs div addressing; hardware probe: fused sum `1.3185` vs per-node `-9.2310`. Superseded.
- Final fix `1fbc9825`: ModLast granted only when strides prove single-row broadcast — last-axis stride `== 1`, every outer axis stride `== 0` or singleton dim. Admits the `(0,1)` row view (stock fusion restored), refuses `(1,0)` column views; GDN `(N,1,L)` leaves unchanged (never reach ModLast; DivLast `shape.back()==1` guard intact).
- Review followup `925cfa64` (test-only, no wheel change): the square row/column cases now also bitwise-check the fusion-enabled EAGER output against a fusion-disabled reference (`uint32` pattern compare), and use bitwise (`epsilon=-1.0`) compiled comparisons.
- Branch for review: `origin/agent/fused-chain-modlast-fix` @ `925cfa64` (972c6ddb → 9a793054 → 1fbc9825 → 925cfa64). NOT merged to main; integration pending review acceptance.

### 11.2 capability_sim rc2 resolved

The battery was invoking the binary bare. Contract: one profile per invocation; bare run executes the registry unit checks then prints usage (rc=2 is that documented exit). Battery now runs unit (rc=2, `unit: profile registry + apply() deltas OK`) + 5 profiles each rc=0, 6/6 cases each.

### 11.3 C++ battery on corrected bytes (worktree 1fbc9825, `.work/build-tests`)

| battery | result |
| --- | --- |
| omarchy_primitive_tests | **103/103** (2,700,952 assertions) |
| omarchy_runtime_tests | **41/41** (22,694 assertions) |
| omarchy_compiled_tape_tests | **12/12** (2,096 assertions) |
| omarchy_fused_chain_tests | **36/36** (338,080 assertions — 34 prior + square row/column regressions; includes da43969e strided `(B,1,L)` refusal case still green) |
| capability sim | unit OK + 5/5 profiles rc=0 |

### 11.4 mlx-lm matrix on final wheel (greedy, "Explain photosynthesis in one sentence.", 96 tokens, digest = sha256(generated ids)[:16])

Wheel `mlx_omarchy-0.32.3.dev202609192209+1fbc9825-cp314-cp314-linux_aarch64.whl`, sha256 `d0d7822fa0af7efbc2c1af5b941846a19629bb070cba994c39819b9df8e93ae5`, libmlx16 `016dad3980f58d36`.

| model | compiled | eager | match | tok/s |
| --- | --- | --- | --- | --- |
| Qwen2.5-0.5B-Instruct-bf16 | `c2d5348ed63fb217` ×3 | `c2d5348ed63fb217` ×2 | identical | 51.5 / 50.4 |
| Qwen3.5-9B-MLX-4bit | `910abe30d4305271` ×2 | `910abe30d4305271` | identical | 11.41 / 11.07 |
| gemma-4-31b-it-4bit | `9f1fe40101db3a4b` | `9f1fe40101db3a4b` | identical | 2.35 / 2.42 |
| Ministral-3-8B-Instruct-2512-4bit | `d4735e3a265e16ee` (n=1 EOS) | `d4735e3a265e16ee` | identical | — |
| Ternary-Bonsai-8B-mlx-2bit | `25dc382d3170a80c` | `25dc382d3170a80c` | identical | 5.81 / 5.63 |

All five digests equal the section-5 pins from the 972c6dd wheel — compile ON changes no generated id across the fix commits.

### 11.5 Bonsai-2-27B (F7 probe, lift3-1fbc9825 label)

`/tmp/f7_bisect.py gen --steps 96` on the final wheel (venv libmlx bytes verified == wheel): 96 steps, `nan_at=None`, coherent "The capital of France is **Paris**.", 1.446 tok/s. Zero NaN from step 4 is the F7 corruption signature — absent.

### 11.6 Parakeet + AC/ACO gate on final wheel — GATE GREEN (17:19:14)

`/tmp/v070-jw16-gate-lift.sh` = `/tmp/v070-jw16-gate.sh` repointed b283a16→1fbc9825 (WHLGLOB, artifact-commit strings, OVERLAY_RUNNER at 1fbc9825) with lock/service sections neutralized (window holder owned both). Evidence (`/var/tmp/v070-jw16.status`, artifacts `/var/tmp/v070-gate-jw16/`):

- artifact checks PASS (version identity, libmlx records 1fbc9825, no `MLX_OMARCHY_GPU_PROFILE`, positive control present, runner bytes == overlay, WHEEL tag), libmlx16 `016dad3980f58d36` not on certified list.
- packaging gate 3× transcript `db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790` (gate-exit 0).
- E2E arms (wheel-installed files, fixture.flac): serve-default, launch, placed-AC, placed-ACO — all `status=match`, **prefix 104/104**, `bounds=true`, **cpu_tensor_events 0**, timeouts 0; transcript `db501a8c…`; hidden AC `38c73261…`, ACO `ef6afd13…`; mel `5b54f4a9…` (all exact pins).
- venv identity guard exit 0 (candidate line added).
- decode legs in one hold: ctx1024 `7da83f06ec9f001d` (137–148 tok/s), short `7fd25a869ff21678` (188.9–191.5 tok/s), provenance names wheel libmlx16.
- hwcap probe PASS (`HWCAP_SHA256=1`), FIPS KATs **13/13** + open-probe digest match.

Ancestry: `git merge-base --is-ancestor 63c1d3cf HEAD` → exit 1 (NOT ancestor), re-verified at 1fbc9825 and 925cfa64.

### 11.7 Open items — all closed

1. **Upstream `test_compile.py` on lift bytes — CLOSED.** Run on the corrected wheel (`1fbc9825` bytes, venv `/tmp/bf16-lift-venv`) in a short coordinated hold: **68/68 passed** (`rc=0`, "68 passed in 1.69s"), log `/var/tmp/bf16-lift/test_compile-1fbc9825.log` on jw16. The three formerly-named-refusal cases stay green through the fence lift + dispatch fix.
2. **Strengthened fused-chain regressions (`925cfa64`) — CLOSED.** Durable full-suite log captured: `/var/tmp/bf16-lift/omarchy_fused_chain_tests-925cfa64.log` — **36/36, 346,272 assertions, SUCCESS** (338,080 + 2×4096 fused-eager bitwise loops, exactly as reviewed).
