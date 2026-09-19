# hk/agx-wait-batching cleanup — debug content stripped, screenable series on mesa-1

Date: 2026-09-19. Lane: MesaWaitBatchClean (dev box only, no GPU time taken).
Repo: `github.com/joshuaswarren/mesa-1` (canonical; old fork untouched).

## Inputs

- Source branch: `hk/agx-wait-batching`. Audited tip `14eb6778a69` (audit
  `receipts/2026-09-19-mesa-branch-audit.md`) was later currency-merged with
  trunk; the pushed tip at cleanup time was `40905e2f2c4` (= `14eb6778a69` +
  merge of `honeykrisp-omarchy` `d8d4e1c500b`). The merge touched only
  trunk-side files — `agx_insert_waits.c` and `test/test-insert-waits.cpp`
  are byte-identical between `14eb6778a69` and `40905e2f2c4` (verified,
  empty diff). All cleanup work is against `40905e2f2c4`.
- Clean branch based on current trunk tip `d8d4e1c500b`, so the GPU lane
  gets trunk currency without carrying the raw merge commit.

## Per-commit buckets (the 11 commits)

| # | commit | subject | bucket |
|---|---|---|---|
| 1 | `84fcd220de1` | carry scoreboard state across divergent if/else regions | **(a) functional** — frames, entry-state snapshot, carry across fallthrough |
| 2 | `8818596cca8` | WIP debug: log frame pushes | **(c) debug** — 2 fprintf lines |
| 3 | `2a6eb586547` | WIP debug2: per-block terminator dump | **(c) debug** — 11 fprintf lines |
| 4 | `8f3169a4342` | resolve if/else merge lazily at else-arrival | **(a) functional** — lazy merge, no up-front merge index |
| 5 | `c3cebc011bd` | fix frame detection, restore hazard scoping, add firing proof logs | **mixed** — functional parts (frame-shape checks, hazard scoping) retained; the "firing proof logs" (unconditional `AGXWAITS` fprintf on every compile) dropped |
| 6 | `30ffef135e0` | conservative scoreboard carry, pop_exec close, two slots | **(a) functional** — sum-with-clamp merge accounting, pop_exec close rule, `AGX_NUM_SLOTS=2` + static assert |
| 7 | `f11106ddfb0` | host capacity/hazard tests for wait insertion | **(b) tests** |
| 8 | `93a3bcf78f0` | guard wait-insertion entry print against bare test contexts | **(c) instrumentation** — null-guard existed only to keep the entry debug print from crashing bare test contexts; print removed, guard goes with it |
| 9 | `29020ee569c` | skip the pointless end-of-shader drain again | **(a) functional** — restores exit-block drain elision |
| 10 | `4eae6e5b5bb` | fix insert-waits test block wiring, assert capacity invariant | **(b) tests** |
| 11 | `14eb6778a69` | reference mirrored constants in insert-waits test | **(b) tests** |

## Clean series

`hk/agx-wait-batching-clean` @ **`13d0bc50062628c64e17a2912d514ee06fad093b`**
(based on `honeykrisp-omarchy` `d8d4e1c500b`), two commits:

1. `2e512559005` — **agx: carry scoreboard state across divergent if/else
   regions in wait insertion.** The functional change, one commit. Mechanism:
   walk the shader as regions instead of blocks; open a frame at each
   if_icmp/if_fcmp whose then arm starts at the layout successor and whose
   else block is the branch target; carry pending scoreboard state across
   fallthrough inside a region; union write-sets and sum pending counts
   (clamped) at else-arrival, force-draining any slot driven past
   `AGX_MAX_PENDING`; close a frame when a block is entered whose
   predecessor ends with pop_exec past the else; drain at block exit only on
   real control transfers; exit block still never drains; two scoreboard
   slots pinned by `_Static_assert` against the 1-bit IR field; unclosed
   frames only over-approximate (extra waits, never lost waits);
   `AGX_DBG_WAIT` still selects the trivial drain.
2. `13d0bc50062` — **agx/compiler: host capacity/hazard tests for wait
   insertion.** The 4-test gtest suite (byte-identical to the branch's) plus
   its meson registration.

Original branch `hk/agx-wait-batching` untouched (verified: remote tip still
`40905e2f2c4` after push).

## Only debug content was dropped — proof

`git diff 40905e2f2c4 13d0bc500626` over the whole tree is exactly:

```
 src/asahi/compiler/agx_insert_waits.c | 36 -----------------------------------
 src/asahi/compiler/meson.build        |  1 +
 2 files changed, 1 insertion(+), 36 deletions(-)
```

- `agx_insert_waits.c` −36 lines: all 10 `fprintf(stderr, "AGXWAITS: …")`
  sites (entry, else-arrival, overflow-drain, close, ACCEPT, reject-shape,
  reject-target-NULL, reject-frames-full, drain, carry), the `if (overflow)`
  wrapper that the overflow print was the entire body of, the two print-only
  `else if` branches of the frame-acceptance chain, the print-only trailing
  `else` of the drain condition, and the `drained` counter that fed only a
  print. Line-by-line diff reviewed: every removed line is an fprintf, a
  continuation of one, an empty wrapper, or the counter. Zero functional
  lines changed. The `ctx->nir` null-guard from `93a3bcf78f0` disappears
  with the entry print it guarded.
- `meson.build` +1: **fix, not debug** — the original `f11106ddfb0` had
  *replaced* `test/test-lower-parallel-copy.cpp` with
  `test/test-insert-waits.cpp` in the test sources list, silently dropping
  trunk's parallel-copy suite (file still in tree, test gone from build).
  The clean branch registers both.
- `test/test-insert-waits.cpp`: byte-identical to `40905e2f2c4`'s.
- Everything else: identical to both tips (clean branch = trunk content).

So: dropped = debug/instrumentation only; changed = one test-build repair.

## Build + test results (dev box, x86_64, no GPU)

- `meson setup` minimal (`-Dtools=asahi -Dmesa-clc=enabled`, no drivers,
  `-Dbuild-tests=true`). Toolchain note for future lanes on this box:
  Debian 12 ships neither LLVMSPIRVLib (needs LLVM-19-matched ≥15, has only
  14/15) nor SPIRV-Tools ≥2024.1 (has 2023.1.1). Built locally into
  `~/.local` and reused via `PKG_CONFIG_PATH=$HOME/.local/lib/pkgconfig`:
  SPIRV-LLVM-Translator v19.1.7 (LLVMSPIRVLib 19.1.0.0) and SPIRV-Tools
  2026.3.1; `libclang-19-dev` apt-installed (root-approved). Sources in
  `/tmp/SPIRV-LLVM-Translator`, `/tmp/SPIRV-Tools`. MesaUpstreamPrep is
  reusing the same prefix — no race.
- `ninja src/asahi/compiler/libasahi_compiler.a` — **built clean, 446/446
  targets**, including the rewritten `agx_insert_waits.c`. No warnings
  surfaced from the changed file.
- `ninja src/asahi/compiler/agx_tests` — built.
- **gtest run, observed:** full suite `58 tests from 8 test suites … PASSED`
  (12 ms, CPU-only, no GPU needed — pure IR-level tests). Filtered view of
  the relevant suites, all `[ OK ]`:
  - `InsertWaits.RawHazardWaitsAtUse`
  - `InsertWaits.SlotCapacityWaitsBeforeIssue`
  - `InsertWaits.DivergentWawWaitsInElseArm`
  - `InsertWaits.MergeReaderSeesCarriedPending`
  - `LowerParallelCopy.*` ×10 (the restored suite — would have been absent
    on the raw branch)
- `meson test agx_tests`: `Ok: 1, Fail: 0`.
- No `AGXWAITS` output appears in the test run — prints are gone.

## Screening brief for the GPU lane

**Status change since the audit:** the raw branch was screened on jw16 today
by MesaPortAndWork — `receipts/2026-09-19-agx-wait-batching-jw16.md`:
digest-clean everywhere, perf-neutral (+0.2 % coopmat-off, ±0.5 % coopmat-on,
inside noise), verdict **NO-LAND at `40905e2f2c`**, kept unmerged as
safe-to-revisit. This cleanup changes no functional code (proof above), so
that screen's verdict carries over to the cleaned tip.

If a lane picks up `hk/agx-wait-batching-clean`, do not re-derive; the
battery is:

1. **Equivalence gate (cheap, do this first):** build the cleaned tip,
   run the jw16 warmup digest gate. Expected: `7fd25a869ff21678` short /
   `7da83f06ec9f001d` ctx1024 — identical to the `40905e2f2c` arm, proving
   the debug-strip changed no codegen. Mismatch ⇒ stop, the equivalence
   proof is broken.
2. **If the gate matches:** the existing paired battery verdict
   (NO-LAND, perf-neutral in both AGX_SIMDMAT regimes) transfers to this
   tip. No new battery required just for the cleanup.
3. **If a fresh perf read is wanted anyway** (e.g. the AGX_SIMDMAT default
   gets restored, changing the economics): paired interleaved battery,
   base = `honeykrisp-omarchy` `d8d4e1c500b` package vs clean-tip package,
   both arms at the same `AGX_SIMDMAT` state (record it — the trunk default
   is off and costs ~24 % on its own), `cb_ab.py` 12 rounds, 32-token greedy,
   Qwen2.5-0.5B Q4, digest + libmlx pins fatal per run. Win = short-decode
   median improvement beyond the ±3 % row wander with all digest gates
   green; anything inside noise = no-land, same rule that rejected
   device-load-coh7 and fma-ceiling-unroll.
4. `hk/agx-wait-batching` (raw) can be deleted once this receipt and the
   jw16 receipt are archived; the cleaned branch supersedes it.

## Artifacts

- mesa-1: branch `hk/agx-wait-batching-clean` @ `13d0bc50062628c64e17a2912d514ee06fad093b` (pushed)
- Build tree: `/tmp/wt-waitclean/build-clean` (worktree; disposable — config
  recipe recorded above)
- Toolchain: `~/.local` (LLVMSPIRVLib 19.1.0.0, SPIRV-Tools 2026.3.1)
