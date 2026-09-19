# agx-wait-batching screened on jw16 — wait-insertion rewrite is digest-clean but perf-neutral: NO-LAND. Side finding: trunk builds measure ~26 % below the installed driver, root-caused to the `AGX_SIMDMAT` opt-in flip in `f4859fb6991`

Date: 2026-09-19. Lane: MesaPortAndWork. Host: jw16mbp1-linux (Apple M1 Max,
T6001, G13C C0), kernel 7.1.6-1-1-ARCH. Wheel: v0.7.1
`mlx_omarchy-0.32.3.dev202609190758+50eeb29` (libmlx sha256 prefix
`df3d4e74c597956c`, pinned fatal on every run). Installed driver:
`mesa-honeykrisp-omarchy 26.3.0.devel.hk5deac1c-2`, untouched by this lane;
post-window state `active` confirmed after every window.

## Port (step 1 of the assignment)

`github.com/joshuaswarren/mesa-1` received all four live branches from the
`MesaBranchAudit` (receipts/2026-09-19-mesa-branch-audit.md):

| branch | mesa-1 tip | note |
|---|---|---|
| `honeykrisp-omarchy` | `d8d4e1c500` | fast-forwarded from stale `fb6237546e` to the mesa trunk tip |
| `hk/app-barrier` | `33deb56de3` | tip `69c416a6cff` + trunk merge |
| `hk/trig-invariance` | `9c3d01e06a` | tip `d1fed280ec2` + trunk merge |
| `hk/agx-wait-batching` | `40905e2f2c` | tip `14eb6778a69` + trunk merge |
| `upstream/correctness` | `aa4fee0d5f` | already current on mesa-1; left un-merged deliberately |

Currency: each `hk/*` branch was behind trunk by the landed correctness set
(byte-extract, precise-math, coopmat-shapes, cdm-barrier-trim revert, ...);
`git merge honeykrisp-omarchy` into each was clean (only
`libagx_dgc.h`/`meson.build` auto-merges). After the merge,
`git diff honeykrisp-omarchy hk/agx-wait-batching` is exactly the
wait-insertion work: `agx_insert_waits.c` (+369/−74),
`meson.build`, new `test/test-insert-waits.cpp` (+243). Screening the raw
tip `14eb6778a69` instead would have confounded the screen with missing
trunk fixes baked into the digest pins.

`upstream/correctness` is upstream-PR prep; merging the fork's
`honeykrisp-omarchy` trunk into it would poison the PR base with
fork-only commits, so it is pushed as-is.

Trig-invariance needed no GPU screen: its verdict already exists —
`mlx-omarchy/receipts/2026-09-16-mesa-trig-invariance.md` (digest gate
closed, one FMA contraction fixed at shader source, perf gate fails, the
fold does not land). The `MesaBranchAudit` had this marked "pending" and
missed that receipt; the branch's remaining value is the harness itself.

## The screen (step 2 of the assignment)

Target: `hk/agx-wait-batching` @ `40905e2f2c` — the AGX scoreboard
wait-insertion rewrite (conservative carry across divergent if/else
regions, lazy if/else merge at else-arrival, pop_exec close, two slots,
end-of-shader drain elision) plus a host capacity/hazard gtest suite.
Never screened before this window.

Two arms, extracted packages, per-arm ICDs via `VK_DRIVER_FILES`:

| arm | source | identity |
|---|---|---|
| base | package rebuilt 2026-09-19 from `d8d4e1c500` (same source as the chain-batch receipt's base pin) | `libvulkan_asahi.so` sha256 `4344c81ed4997c43…` |
| wb | package built this lane from `40905e2f2c` (makepkg, `mesa-honeykrisp-omarchy-26.3.0.devel.hk40905e2-1`) | `libvulkan_asahi.so` `93dd6cbf2c60d879…`, `vulkaninfo` = `Mesa 26.3.0-devel (git-40905e2f2c)` |

Flow (window-wb.sh, one flock hold on `/tmp/m1-gpu.lock` inode 12,
`flock -w 900`): llm-inference stopped → warmup + digest gate per arm per
leg → 12-round paired interleaved battery (`cb_ab.py`, rotating order,
32-token greedy runs, digest + libmlx pins fatal inside every run) →
llm-inference restarted, post-state `active`.

## Results

**Digest gate: clean everywhere.** Warmup gates 4/4 (both arms × both legs
hit `7fd25a869ff21678` short / `7da83f06ec9f001d` ctx1024 exactly), and
all 48 battery legs passed the fatal per-run pins (`rc=0`; any single
mismatch exits the battery). Unlike `hk/cdm-chain-batch`, which corrupted
nondeterministically at the warmup gate, the wait rewrite is
correctness-clean on the shipped decode path.

**Perf: no effect.** Battery medians (12 interleaved rounds, v0.7.1 wheel,
Qwen2.5-0.5B Q4, 32 greedy tokens):

| arm | short decode | ctx1024 decode | ctx prefill |
|---|---:|---:|---:|
| base | 141.26 | 82.59 | 2006 |
| wb | 141.51 (+0.17 %) | 82.77 (+0.22 %) | 2007 (+0.05 %) |

+0.2 % is deep inside this box's run-to-run wander (individual rows swing
±3 %; short spread 133.2–142.2). The "end-of-shader drain elision" that
should profit every dispatch is not visible in the shipped decode legs.

## Verdict: NO-LAND (both configurations)

Correct but not profitable: the wait-insertion rewrite passes every
correctness gate on jw16 and moves decode/prefill tok/s by ~0.2 % with
coopmat off and ~0.5 % with coopmat on (both inside noise). The land rule
requires a measured win; `hk/agx-wait-batching` stays unmerged on mesa-1.
What the screen does establish: the branch is safe to revisit (digest-clean,
unlike chain-batch), so if the barrier/wait economics change in a future
driver generation it can be re-screened from `40905e2f2c` without redoing
the correctness work.

## Side finding — trunk tip builds measure ~26 % below the installed driver; root cause is the `AGX_SIMDMAT` opt-in flip in `f4859fb6991`, not the build

The battery's absolute levels (short 141, ctx1024 82.6) sat far below the
same-day ladder receipt on this box (191.90 / 150.76). Controls, all one
90-second window each, same prompt "Hi", same venv/model/pins:

| arm | short decode tok/s | reading |
|---|---:|---|
| base (`d8d4e1c500`, rebuilt 2026-09-19) | 139.4 / 140.4 / 138.1 | the battery level; fans 0 RPM, box idle → **not thermal** |
| installed (`hk5deac1c-2`, built ≤2026-09-16) | 189.4 / 191.5 / 190.6 | matches the ladder receipt's 191.90 |

Same box, same wheel, same digests; only the driver binary differs. The
delta is in the **build**, not the box and (pending the disambiguation
below) not the trunk source: the installed package was built on 09-16's
toolchain, while today's makepkg pulls the current distro toolchain. The
chain-batch lane saw the same effect and read it as "cold shader cache";
this lane's controls show it is reproducible warm and idle.

**Disambiguation:** a control package rebuilt today from `5deac1c8068`
(the installed package's exact source) pins whether the ~26 % is toolchain
drift or a source regression between `5deac1c8068` and trunk tip
`d8d4e1c500`:

| arm | short decode tok/s |
|---|---:|
| `5deac1c8068` rebuilt today (window-ctrl3) | **191.6 / 191.2 / 191.8** |
| `d8d4e1c500` rebuilt today (window-ctrl) | 139.4 / 140.4 / 138.1 |
| installed `hk5deac1c-2` (window-ctrl2) | 189.4 / 191.5 / 190.6 |

**Toolchain is innocent — it is a source regression in trunk.** The exact
source that produced the installed 191 tok/s driver, rebuilt with today's
toolchain, still runs 191; only trunk tip builds drop to 141.

### Root cause: `f4859fb6991` "asahi: keep cooperative matrices opt-in"

The 13-commit range `5deac1c8068..d8d4e1c500` contains four
cdm-barrier-trim merges that net out to the sink on G13X by design, tests,
and eight codegen commits. The smoking gun is a one-line default flip in
`f4859fb6991`:

```c
-   return debug_get_bool_option("AGX_SIMDMAT", true);
+   return debug_get_bool_option("AGX_SIMDMAT", false);
```

`VK_KHR_cooperative_matrix` went from on-by-default to opt-in
(`AGX_SIMDMAT=1`). The mlx-omarchy qmm decode and prefill kernels ride the
G13 simd_matrix unit through exactly this feature (the coopmat line of
work: "QMM at 90.2 % of Honeykrisp's own coopmat ceiling"), so with the
flip they silently take software matrix lowering: −26 % short decode,
−45 % ctx1024 decode, −44…−56 % prefill — the measured signature. The flip
was the conservative gate for the partial-subgroup garbage bug
(`a2909940cbf` "Reported by Dj"), and the proper fix — software lowering
for non-multiple-of-32 workgroups — landed three commits later without the
default being restored.

**Env-var restore (verified):** running the trunk-tip build with
`AGX_SIMDMAT=1` recovers most of the loss — window-ctrl4/ctrl4c on the
`d8d4e1c500` package: 164.4 → 171.7 → 175.5 across three cold-cache runs
(the simdat switch changes compiler cache keys, so the first run eats
pipeline compiles), then settled warm: **174.5 / 175.5 / 173.8 / 174.7
tok/s** (5.7 ms/token, digest `7fd25a869ff21678` everywhere).

| configuration | short decode tok/s |
|---|---:|
| trunk `d8d4e1c500`, simmat default (off) | ~141 |
| trunk `d8d4e1c500`, `AGX_SIMDMAT=1` | ~174.5 |
| installed `hk5deac1c-2` (simmat on by construction) | ~190 |

So the opt-in flip is the dominant regression (+24 % recovered by the env
var), but a residual **−8.6 % vs the installed driver remains** with
simmat on — a second, smaller effect inside the same
`5deac1c8068..d8d4e1c500` range (candidates: `a2909940cbf`'s software
fallback paths touching shapes the HW path used to take, or
`838e31f4d95`'s flush-to-zero handling). Not attributed yet; needs the
same build-per-commit treatment, which is trunk-lane work.

**Implications:**

1. Any driver package built from trunk tip (or any `hk/*` branch of it —
   including this lane's `40905e2f2c` arms) regresses jw16 decode/prefill
   unless `AGX_SIMDMAT=1` is exported for the workload or the default is
   restored. The box is safe only because it still runs the 09-16
   installed package.
2. Restoring the default (`false` → `true`) is now guarded by
   `a2909940cbf`'s software fallback, but that is the trunk owner's call —
   the flip was deliberate. Flagged to Main with this receipt.
3. Every future arm screen must run all its arms at the same
   `AGX_SIMDMAT` state and record it; this lane's first paired battery was
   internally consistent (both arms at default-off), so its primary
   NO-LAND verdict stands, but a confirmation battery with `AGX_SIMDMAT=1`
   on both arms was run to close the caveat — see below.

### Coopmat-on confirmation battery (wb2)

Same two arms (base `d8d4e1c500`, wb `40905e2f2c`), same harness, both
with `AGX_SIMDMAT=1`, warmup digest gates per arm per leg (4/4 clean —
the generated-ID pins are simmat-invariant), 6 paired interleaved rounds:

| arm | short decode | ctx1024 decode | ctx prefill |
|---|---:|---:|---:|
| base | 175.28 | 142.41 | 3784 |
| wb | 175.02 (−0.15 %) | 143.07 (+0.47 %) | 3754 (−0.80 %) |

All deltas inside noise (this battery also ran with two leftover
servebench processes from a neighbouring lane on the box, widening rows;
the interleaved paired design absorbs common-mode load). The
wait-batching rewrite is perf-neutral in the coopmat-off and coopmat-on
regimes alike.

**Final verdict: NO-LAND in both configurations.** Correctness-clean
everywhere (28 digest-gate hits across the lane, zero mismatches),
perf-neutral everywhere measured. Unmerged on mesa-1.

## Hardware safety / coordination

- Seven GPU windows total (screen battery, three single-arm controls, the
  `5deac1c8` control, the `AGX_SIMDMAT=1` pair, the coopmat-on battery),
  all under `/tmp/m1-gpu.lock` inode 12, `flock` held one acquisition per
  window, lock never stolen or unlinked; llm-inference stopped before and
  started after each, post-state `active` (`SubState=running`) confirmed
  after the final window. The mid-lane auto-restart counter (NRestarts up
  to 18) was ServeOptionsDocs's adjacent windows' service starts racing
  their held lock — GPU-harmless, self-settled, `reset-failed` applied by
  that lane.
- GPU TAKE/RELEASE announced to all live peers around every window;
  jwm1 and jw14m2 untouched.
- Package builds (wb, `5deac1c8` control) ran outside windows (CPU-only,
  niced −10, detached).
- Note for future lanes on jw16: single-arm controls are ~90 s with warm
  caches; a fresh compiler-switch variant (like `AGX_SIMDMAT=1`) gets new
  shader-cache keys, so first runs eat pipeline compiles — warm one run
  before reading numbers.

## Artifacts

- This directory: `window-wb.sh`, `window-ctrl.sh` (base), `window-ctrl2.sh`
  (installed), `window-ctrl3.sh` (`5deac1c8` rebuilt), `window-ctrl4b.sh` +
  `window-ctrl4c.sh` (`AGX_SIMDMAT=1`), `window-wb2.sh` (coopmat-on
  battery), `prep-wb.sh`/`prep-s5de.sh`, plus `window-wb.log`, `ab-wb.json`,
  `window-ctrl{,2,3,4,4c}.log`, `window-wb2.log`, `ab-wb-simmat.json`,
  `service-wb.txt`.
- jw16: `/var/tmp/cb/` (all logs, `ab-wb.json`, `ab-wb-simmat.json`),
  `/var/tmp/wb-build/` + `/var/tmp/wb-base5de/` (build trees + logs),
  `/var/tmp/MesaL2/pkg-wb/` + `pkg-s5de/` (extracted arms).
- Mesa: `github.com/joshuaswarren/mesa-1` branch `hk/agx-wait-batching`
  @ `40905e2f2c` (unmerged; screened by this receipt).
