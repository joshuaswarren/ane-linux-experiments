# Mesa upstream/correctness — upstream submission prep

Date: 2026-09-19. Author: MesaUpstreamPrep (agent).
Repo: `joshuaswarren/mesa-1` (only; the old `joshuaswarren/mesa` fork was
not used for any step). Worktree: `~/src/mesa-upprep` (branch
`upstream/correctness-rebased`), clone at `~/src/mesa-1`.

## Result

- **Branch pushed:** `upstream/correctness-rebased` at
  `64efc6b0a56692d12ab2c943db51a1e48e8daee6` on `mesa-1`.
- **Historical tip untouched:** `upstream/correctness` still
  `aa4fee0d5f759380e219b050c08f803dec5b773b` (verified via ls-remote after push).
- **Rebased onto upstream Mesa main:** `590bf21d918c86908d96d1f4590ecd25b9657171`
  ("anv: implement VK_INTEL_device_info", 2026-09-18 20:00:52 +0000,
  gitlab.freedesktop.org/mesa/mesa, fetched read-only; its push URL is
  disabled locally).
- **Build:** full narrow build green — x86-64, `-Dvulkan-drivers=asahi
  -Dgallium-drivers= -Dllvm=enabled -Dbuild-tests=true` (776/776 targets,
  gcc, LLVM 19): compiles `agx_nir_algebraic.py` generation, the new
  `nir_op_ubfe` isel case in `agx_compile.c`, and the regenerated
  `nir_builder_opcodes.h`. Environmental fix needed: `/usr/local/bin`
  glslang 16.5.0 rejects upstream's `astc_decoder.glsl` under plain `-V`;
  Debian's `/usr/bin/glslangValidator` 12.0.0 compiles it (PATH reorder,
  no repo changes).
- **Tests run (scoped, all pass):** `mesa:nir_tests`,
  `mesa:nir_algebraic_parser`, `mesa:agx_tests`, `mesa:libasahi_tests`,
  `mesa:agx2_disasm`, `mesa:agx2_python_disasm`, `mesa:asahi_layout_tests`
  — 7/7 OK. Direct proof of the nir commit: stock generator emits 24
  `fp_math_ctrl` references in the header, our build emits 48 — the
  "grows exactly 24 lines, twelve two-line defaulting blocks" claim is
  reproduced exactly.
- **Not built/run:** full `meson test` suite, Piglit, dEQP, any Apple
  hardware. Dev box has no GPU; no performance or hardware verdicts in
  this receipt. Hardware claims below come from the fork's own receipts
  and are carried over only because the rebased code is byte-identical.

## Per-commit table (original series, 6 commits ahead of fork main 4a34ded300c)

| # | SHA (orig) | Subject | Files | What it changes | Trunk state | Rebase outcome |
|---|---|---|---|---|---|---|
| 1 | 9a70fd45c5a | agx: keep the mod-32 shift count when fusing ushr+iand into ubfe | agx_nir_algebraic.py | Fuses `iand(ushr(a,b),mask)` only when b<32 or masked `iand(b,31)`; fixes zero-return miscompile for shift counts >= 32 | in trunk, byte-identical patch as 149c44d2f5c | **rebased clean** -> `a08c33d0cb4` |
| 2 | 473e74fbf3b | agx: represent the fused shift-then-mask as ubfe, not ubitfield_extract | agx_nir_algebraic.py, agx_compile.c | Fusion now emits SM5 `ubfe` (defined mod-32) + isel case mapping ubfe->bfeil with width-0=0; removes the undefined-offset case NIR may exploit as poison | in trunk, byte-identical patch as 490b7c16908 | **rebased clean** -> `e5c9c740142` |
| 3 | 5b14829a662 | agx: correctly rounded fdiv/frcp, faithful log/log2, exact sin/cos reduction | agx_compile.c/.h, agx_nir.h, new agx_nir_lower_math.c (567 lines), meson.build | Replaces hw-log2/sin/frcp paths with an exact-fma library: Markstein fdiv32, double-float log, Cody-Waite + Payne-Hanek sin/cos; drops `lower_fdiv` | in trunk as variant 2022ddeae30 (same subject; different patch shape; final file states identical to series tip — 0-line tree diff on all four touched files) | **STOPPED — judgment call, see below** |
| 4 | 90d43f10c09 | agx: lower the fdiv that int64 lowering and the perspective divide emit late | agx_compile.c, agx_nir.h, agx_nir_lower_math.c | Adds a late fdiv-only pass; fixes "Unhandled ALU op fdiv" abort for f2i64/f2u64 and perspective-correct varyings | in trunk, byte-identical patch as e93242f3a61 | skipped (depends on #3's file) — likely fork-specific: the fork dropped `lower_fdiv` in 2022ddeae30; upstream still has `.lower_fdiv = true` and runs its refiner after `nir_lower_idiv` |
| 5 | 7c6aa47ce96 | agx: handle flush-to-zero in precise fp32 division, log and sine | agx_nir_lower_math.c | Normalized-mantissa division so refinement never flushes; log2 computed directly (kills contraction-dependent bits on 26.8% of inputs); signed zero for sin(0) | in trunk, byte-identical patch as 838e31f4d95 | skipped (depends on #3's file) |
| 6 | aa4fee0d5f7 | nir: pass FP_MATH_CTRL to the builder generator | nir_builder_opcodes_h.py | Template referenced FP_MATH_CTRL without import/render arg; mako rendered UNDEFINED and skipped 12 builder-defaulting blocks — NoContraction dropped in every driver | in trunk, byte-identical patch as 864b4e88941 | **rebased clean** -> `64efc6b0a56` |

**Audit correction (verified, not trusted):** the branch audit claimed #5 and
#6 are "work not yet in trunk". False. `git patch-id` maps #5 -> trunk
838e31f4d95 and #6 -> trunk 864b4e88941 byte-identically, and the series-tip
tree equals the trunk tree on every file the series touches. Only #3 has no
patch-equivalent on trunk (its content landed reshaped as 2022ddeae30).
**The entire series is already trunk content; the branch is a re-sequenced
replay for upstream consumption.**

## Why the rebase stopped at #3 (precise conflict report)

Upstream main independently carries overlapping reviewed work with a
different architecture:

- `libagx_frcp()` in `agx_compile.c` (introduced by f6905926923, "agx:
  lower exact frcp", 2024-08-12): 1-step Newton-Raphson refinement,
  gated on `nir_alu_instr_is_exact(alu)`, NaN-guard for infinite inputs.
  Its comment: "nir_lower_idiv relies on correctly rounded frcp. This is
  therefore load bearing for integer division on all APIs."
- `agx_nir_options` keeps `.lower_fdiv = true` (agx_compile.h:350); fdiv
  splits into `fmul*frcp` via `nir_opt_algebraic`, and
  `agx_nir_lower_fdiv` (an frcp refiner) runs after `nir_lower_idiv` in
  `agx_preprocess_nir`.

Cherry-picking #3 onto upstream main **applied textually clean and
silently deleted all of the above** (verified on the rejected candidate
c23a07391ea before backing it out): `libagx_frcp` gone, the
exactness-gating refiner replaced by the fork's always-refine
`agx_nir_lower_fdiv`, `.lower_fdiv` removed. Deciding whether upstream
should adopt Markstein division + always-refined frcp32 in a new
`agx_nir_lower_math.c` at the cost of deleting f6905926923's reviewed
machinery is an upstream-intent decision, not a mechanical conflict
resolution — so per instructions the commit was dropped and the series
left clean, not guessed. #4/#5 depend on `agx_nir_lower_math.c` and were
skipped with it. Note #5's FTZ fixes are real content upstream lacks
(upstream's refinement runs on raw operands and likely shares the
denormal-flush defect — unverified here; would need re-derivation against
`libagx_frcp` and Apple hardware to prove).

Also upstream-main-relevant facts checked: upstream defines `nir_op_ubfe`
(SM5 mod-32 semantics, nir_opcodes.py:1288), does NOT set `has_bfe` for
AGX (so NIR never forms ubfe on its own — commit 2's premise holds
upstream), and had no `nir_op_ubfe` isel case (commit 2 adds it).
`lower_sm5_shift` exists upstream (agx_nir_algebraic.py:16). The fork's
`fuse_ubfe` region was byte-identical to upstream's, so commits 1-2
applied without any code drift; `git diff` pre-amend vs post-amend chain
is empty, and pre-push tree == worktree tree (b04bca59b65).

## Style audit vs current docs/submittingpatches.rst (read from upstream/main, not memory)

Violations found and FIXED (message-only rewrites; zero code changes):

1. Commit 1: non-standard `Bug:` lead; internal names mlx-omarchy /
   bool-scatter / reduce_general / masked_scatter / s_scan; "mlx-omarchy
   suites ... AGX_SIMDMAT=1" block (AGX_SIMDMAT does not exist upstream).
   -> reworded to observable facts, kept every measured number, dropped
   the internal-suite block.
2. Commit 1: wrong-code fix with no `Fixes:` tag -> added
   `Fixes: 7193849f302 ("agx: Fuse ubitfield_extract")` (upstream commit
   that introduced the unmasked fusion, 2023-11-02). Also nominates it
   for stable backport per upstream's stable-tag process.
3. Commit 2: opens "Follow-up to 149c44d, addressing Dj's review note on
   the omacom board" — fork SHA + internal board -> "Follow-up to the
   previous commit."
4. Commit 2: internal receipt reference and mlx-omarchy suite block ->
   replaced with the hardware statement already in the message
   (20/20 reproducer, byte-identical disassembly).
5. Commit 2: internal variant name `byte_dyn_const` in the NIR example ->
   "the constant-count fused form".
6. Commit 3: fixes a live upstream regression (854911aeab2) with no
   `Fixes:` tag -> added `Fixes: 854911aeab2 ("nir: add fp_math_ctrl as
   intrinsic index")`.

Checked and NOT violations: no Signed-off-by (docs: "not required, but
not discouraged"); prefixes (`agx:`, `nir:`) match the touched files'
history; all message lines <= 75 chars; no merge/WIP/debug/fixup commits;
one logical change per commit; series builds and passes the scoped suites
at the tip (bisectability of the full 7-suite run per commit was not
exercised).

## Things that would block or complicate submission (for the human)

1. **GitLab account + fork push** — submission itself is deliberately not
   done. Push `upstream/correctness-rebased` (64efc6b0a56) to a personal
   freedesktop fork and open the MR with the text below; tick "Allow
   commits from members who can merge to the target branch".
2. **AI-disclosure decision (2026 upstream rules):** current
   submittingpatches.rst requires disclosure when "AI" was involved in
   the creative process of the code (`Assisted-by:` / `Generated-by:`
   tags) and bars AI-written commit messages/MR text. Whether the agx
   commits need an `Assisted-by:` tag, and the final wording, is the
   author's call — decide before opening the MR. The commit texts above
   are rewrites of Joshua's existing commit messages.
3. **The math trilogy (#3-#5) is NOT in the MR** — blocked as described.
   If pursued upstream, it must be re-derived against upstream's
   `libagx_frcp` architecture, with hardware FTZ evidence for the
   denormal cases; do not push the textual-apply version (c23a07391ea was
   discarded for deleting upstream's reviewed code).
4. **Subject nuance:** commit 1's subject says "into ubfe" but at that
   point in the series the fusion still emits `ubitfield_extract` (the
   switch is commit 2). Historical subject kept; if a reviewer objects,
   retitle to "...when fusing ushr+iand" before submission.
5. **Author email** is `816217+joshuaswarren@users.noreply.github.com`;
   freedesktop GitLab may want a real address on file for the MR author.

## Ready-to-paste MR text

Title:
`agx: fix miscompile in dynamic shift-then-mask fusion; nir: restore fp_math_ctrl builder defaulting`

Description:

```markdown
Two independent correctness fixes, one per subsystem.

## agx: dynamic shift-then-mask miscompile (commits 1-2)

`iand(ushr(a, b), (1 << bits) - 1)` has been fused to
`ubitfield_extract(a, b, bits)` since 7193849f302 ("agx: Fuse
ubitfield_extract"). NIR's ushr only uses the low 5 bits of its count
(and nir_opt_algebraic relies on that to strip explicit count masks), but
ubitfield_extract has no wrap: an offset >= 32 is undefined in NIR and
reads as zero on the hardware (bfeil). Any shader doing a dynamic
shift-then-mask with a count >= 32 got zero. Commit 1 fuses only when the
count is a constant below 32 and inserts an explicit `iand(b, 31)`
otherwise; commit 2 changes the fused form to SM5 `ubfe`, which is
defined to take offset and width modulo 32, removing the undefined case
instead of defending against it, and adds the isel mapping to bfeil
(width 0 reads as zero, so it gets its own case). Commit 2 produces
byte-identical machine code.

## nir: fp_math_ctrl builder defaulting was silently missing (commit 3)

854911aeab2 ("nir: add fp_math_ctrl as intrinsic index") added an
`FP_MATH_CTRL in opcode.indices` block to the nir_builder_opcodes_h.py
mako template, but never imported the index or passed it to render().
Mako resolves the unknown name to UNDEFINED and skips the block, so the
generated header has been missing the twelve fp_math_ctrl defaulting
blocks since then: NoContraction was dropped in every driver that relies
on the builder default (e.g. cooperative-matrix ops). The generated
header grows exactly 24 lines with this fix.

## Per-commit summary

1. `agx: keep the mod-32 shift count when fusing ushr+iand into ubfe`
   - fixes the >= 32 shift-count miscompile; Fixes:
     7193849f302 ("agx: Fuse ubitfield_extract")
2. `agx: represent the fused shift-then-mask as ubfe, not
   ubitfield_extract` - removes the undefined-offset case from the fused
   form; same machine code
3. `nir: pass FP_MATH_CTRL to the builder generator` - restores the 12
   builder-defaulting blocks; Fixes: 854911aeab2 ("nir: add fp_math_ctrl
   as intrinsic index")

## Testing

- agx commits, on Apple M1 (G13G B1), standalone Vulkan compute
  reproducer (20 variants, 1024 lanes each, host-compared): stock Mesa
  26.1.7 fails 9/16 base variants and 4/4 boundary variants (e.g. count
  exactly 32: 1016/1024 lanes wrong); with commit 1, 20/20 pass with 0
  mismatches. Commit 2: 20/20 before and after, byte-identical
  disassembly on all 20 (same machine code, so no performance delta is
  possible). These hardware runs were done on the author's tree; the
  rebased code is patch-identical.
- Branch as pushed: x86-64 build of the Asahi Vulkan driver plus NIR
  (meson: vulkan-drivers=asahi, llvm enabled), full build green; meson
  test passes for nir_tests, nir_algebraic_parser, agx_tests,
  libasahi_tests, agx2_disasm, agx2_python_disasm, asahi_layout_tests.
  Generated-header check: fp_math_ctrl references go 24 -> 48, the exact
  24-line growth claimed.
- Not run here: Piglit, dEQP, full unit suite, and no Apple-hardware run
  of the rebased branch itself (build environment has no Apple
  silicon); no performance claims are made.

The nir commit is 2 lines and independent; happy to split into two MRs if
that reviews better.
```

## Reproduce

```sh
git fetch origin
git worktree add ../mesa-upprep -b upstream/correctness-rebased origin/upstream/correctness-rebased
# rebased series:
git log --oneline 590bf21d918c..upstream/correctness-rebased   # 3 commits
# build (x86):
meson setup build -Dvulkan-drivers=asahi -Dgallium-drivers= -Dplatforms= \
  -Dglx=disabled -Degl=disabled -Dgbm=disabled -Dllvm=enabled -Dbuild-tests=true
# (Debian box: PATH=/usr/bin:$PATH so glslang 12.0.0 is used, and
#  PKG_CONFIG_PATH=$HOME/.local/lib/pkgconfig for LLVMSPIRVLib 19.1.0.0
#  + SPIRV-Tools 2026.3.1 built by the MesaWaitBatchClean lane)
ninja -C build && meson test -C build mesa:nir_tests mesa:agx_tests
```
