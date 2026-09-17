# Entry-point divergence RESOLVED: island-B staging vintage, not the runner; o-proj certified on main's runner bytes, both hosts
# 2026-09-17, AneEntryPointBisect

Supersedes the "entry-point divergence" framing in
`receipts/2026-09-17-entry-point-divergence.md` and the "composite runner is
the sole regression vector" reading in
`receipts/2026-09-17-encoder-ane-oproj-channel-derive.md` (FINAL section).

## Root cause (single-variable proven)

Main's runner (main@4c0adbde `overlay/tools/coreml/vulkan_encoder.py`, sha256
`4f93726bbc7d9c2006d5ad8931dc96a01bf1b982c28a45b8d13b99bcf7d03da2`) dispatches
island B by the CANONICAL name `island-select-8head` (lines 689, 1340). The
E2EREV-lineage runners dispatch `-scratch417` (E2EREV `eedb7c48…` lines
576/1187; ported erev_o `fbd816e38c6d9251…` lines 576/1211). The deployed
bundles dirs carried TWO different mints under those two names:

| island | bytes (prog) | manifest toolchain | vintage |
|---|---|---|---|
| deployed `island-select-8head` (both hosts) | `d40ec023…` | mil-hwxc `83d486b1…` | STALE — pre-`7ab3eb5`, the wrong-lane-10728 vintage (mtime 09-14 10:12) |
| deployed `island-select-8head-scratch417` | `0879c627…` | mil-hwxc `7ab3eb5…` | the scratch fix |
| wheel `share/mlx-omarchy/parakeet-1/bundles/island-select-8head` | `0879c627…` | mil-hwxc `b61de468…` | fixed; program byte-identical to scratch417 |
| deployed `island-attn-a-kt` / `island-pv` | `d05e193a`/`a3aa2fe1`, `76496b74` | — | Sep-14 vintage; cert-green under E2EREV (pins hit) — equivalent vintage, not the cause; wheel re-mints are `cf0ecac2`+`b801f621` / `3ae36f21` |

So: same harness, same worker/lib, same bundles dir → E2EREV green (reads the
fixed scratch417 bytes), main's runner red (reads the stale canonical bytes),
wheel entry green (ships the fixed canonical bytes and pin-verifies). The
runner file never determined the outcome — the island-B NAME it dispatches
did. Nothing was wrong with main's runner; no gate changed.

Falsification of earlier attributions: "the 02:04 composite runner is the
regression" and "the 5eed0068-era runner base itself fails (b865b805)" both
conflated runner identity with island-B selection — every runner in that
lineage that loads the canonical name hits the stale mint.

Decisive flip (jwm1, R1): only `island-select-8head` content swapped to the
scratch417 pair (program `0879c627` + its manifest), everything else identical
to the red run (pure main runner `4f93726b`, deployed worker `d2b461fc`, fill
lib `04a17653`, launch mode, PLACED=ABC) → GREEN: match, 72 submissions,
104/104, transcript `db501a8c…` EXACT, hidden `38c73261…`, bounds PASS.

## Certification — main's runner bytes + the three O hunks

Runner of record: `044f297f` content = main's bytes + exactly the three
additive O-dispatch hunks, sha256
`e93500d25a4a43f94bf6b1e6225c778f0865fe8c5afdbc1db2dccec36de40e2d`;
`63c1d3cf` not-ancestor asserted. Bundles: deployed dir with ONLY the select
swap (`bundles-sf`). Worker `d2b461fc…`, fill lib `04a17653…`. Gates: nothing
relaxed, references untouched.

Controls first:

- jwm1 R0 (erev_o certified arm, deployed bundles as-is, ABCO): match, 96
  subs, 104/104, bounds PASS, transcript `db501a8c`, hidden FULL sha re-pinned
  `ef6afd137f1610901c1bce9cf4c9e199edc430c37bd4aeb27caa4622692d5e88`.
- jw16 J0 (same): match, 96 subs, 104/104, bounds PASS, `db501a8c`,
  hidden `ef6afd13…` — bit-identical cross-host.

Cert arms (all: status match, emissions 104/104, first_divergence null,
transcript `db501a8c…` EXACT, bounds PASS, mel bit-exact, 0 timeouts, 0
cpu_tensor_events, gate PASS):

| arm | host | runner | PLACED | subs | hidden | encoder_ane wall_ms | ane exec_ms |
|---|---|---|---|---|---|---|---|
| R2 ABC | jwm1 | e93500d2 | ABC | 72 | `38c73261` | 10231.8 | 5060.2 |
| R3 ABCO | jwm1 | e93500d2 | ABCO | 96 | `ef6afd13` | 11373.2 | 6161.9 |
| J1 ABC (pure main bytes, bisect arm) | jw16 | 4f93726b | ABC | 72 | `38c73261` | 8282.0 | 4518.2 |
| J2 ABC | jw16 | e93500d2 | ABC | 72 | `38c73261` | 7947.4 | 4534.3 |
| J3 ABCO | jw16 | e93500d2 | ABCO | 96 | `ef6afd13` | 9249.6 | 5713.0 |

rel_l2 vs ane reference: ABC 0.02304 (both hosts), ABCO 0.02351 (both hosts) —
the accepted o-proj substitution class.

## Placement cost (per Main's read, quoted)

jwm1: ABCO − ABC = +1141 ms wall / +1102 ms exec. jw16: +1302 ms wall /
+1179 ms exec. Consistent with the submit-cost decomposition (read staging 30%,
IPC 18%, interference 48% of ane_exec; AneSubmitCostIsolation receipt
`510d2b6`): per-island launch mode charges a host round-trip per island, and
ABCO adds 24 of them.

## Ship decision (Main, this date)

1. Ship main's bytes + the three O hunks with placement DEFAULT OFF. Already
   true of the bytes: `os.environ.get("MLX_OMARCHY_PLACED", "ABC")` — unset
   env = ABC (attention/select/pv only); `ABCO` is the explicit opt-in. The
   +1141 ms cost above is the reason it stays opt-in until
   `AneRoundtripLevers` (read-back ~0.5 s, interference ~1.26 s, residency
   2.4 s bound) make it a win.
2. Deployed dirs CONVERGED on the wheel's canonical fixed mint this session:
   `/var/tmp/jwm1-encoder-islands/bundles/island-select-8head` and
   `/var/tmp/jw16-encoder-islands/bundles/island-select-8head` now carry
   `0879c627…` (scratch417 pair, which the wheel's canonical program equals
   byte-for-byte); the stale `d40ec023…` copies are preserved beside them as
   `island-select-8head.stale-d40ec023.bak`. Any dir still carrying
   `d40ec023` is a latent wrong-answer trap for canonical-name dispatchers.
3. Resident-batch ABCO re-measure: see R4 below.

## R4: resident-batch ABCO — instrument gap, measured number deferred to the wheel rebuild

Not measurable on any existing jwm1/jw16 instrument; pairing matrix, all
tried live (logs `/var/tmp/jwm1-ep-bisect/r4{,b,c,d}.log`):

| worker | libane | resident client | result |
|---|---|---|---|
| fill worker `d2b461fc` (CLI+serve, positional fill) | 04a17653 fill | TdtLoopDefault `ane_resident` (has `begin_batch`) | worker rejects `batch DEADLINE_MS` — its serve grammar is `submit/quit` only (`expected 'submit BUNDLE' or 'quit'`) |
| `AneResidentCache` resident worker (older) | — | same | no `begin_batch` at all (`AttributeError`) |
| main-strict build serve worker (V051 battery worker; `batch` protocol) | 04a17653 via `--libane` | TdtLoopDefault | protocol OK, but its worker-side positional validation rejects input-first o-proj bundles at load (`task stream does not name every surface`) — the fb4dfa86/f1539d54 fill never engages on that vintage |

The branch's own worker source (`overlay/tools/mlx-omarchy-ane-worker/main.cpp`
@ f1539d54) has BOTH: `batch DEADLINE_MS | batch-end` grammar and dlopen'd
libane (`--libane` honored, per CMakeLists), so the wheel rebuild
(`MLX_OMARCHY_ANE_DEVICE=ON`) ships the missing instrument naturally. R4 = one
run the moment that wheel exists; do not conclude o-proj placement is a loss
on its merits until then.

Directional only (NOT a measurement): resident-batch ABC (3 islands, pristine
battery) ran 8.3–8.6 s total pipeline vs 13.6 s launch-mode ABC here, so the
per-island host round-trip dominates launch mode; the +1141 ms ABCO cost is a
per-island launch-mode figure and the worst case.

## jw16 unlock protocol (was misread as a leaked-fd defect)

`llm-inference.service` on jw16 DESIGNEDLY holds `/tmp/m1-gpu.lock`: ExecStart
is `flock --nonblock /tmp/m1-gpu.lock exec llama-server …` and the inherited
fd (llama-server fd 3) is the intended steady state. Consequences observed
today: "lock released" claims based on process exit are wrong while the
service lives; a blocking `flock -w 900` queue silently sits behind the
service instead of failing fast; and the service crash-loops on its own
`--nonblock` (~04:59, NRestarts=2, self-healed) whenever an agent's arm holds
the lock. The unlock is `sudo systemctl stop llm-inference.service` FIRST,
then flock, then restart the service. Lock inode 12 was never unlinked.

## Artifacts

- jwm1: `/var/tmp/jwm1-ep-bisect/` (bisect.sh, gate.py, bundles-sf,
  out-r0../out-r4, R0-hidden.full, red-reference preserved at
  `/var/tmp/ParakeetE2ECurrentWheel/out-red-815b046c`).
- jw16: `/var/tmp/jw16-ep-bisect/` (jw16_cert.sh, gate.py, bundles-sf,
  out-j0../out-j3, J0-hidden.full). Runner copies:
  `/var/tmp/ParakeetE2EJw16/vulkan_encoder_main{,_o}.py`.
- Wheel shipped set (reference): extracted at
  `/var/tmp/jwm1-ep-bisect/wheelx` from
  `mlx_omarchy-0.32.2.dev202609161842+33084356` (also verified identical
  vintages in `dev202609170611+b8e5300`).
