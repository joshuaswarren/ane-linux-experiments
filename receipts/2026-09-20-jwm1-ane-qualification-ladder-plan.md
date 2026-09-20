# jwm1 T8103 ANE qualification ladder plan — exact pins (2026-09-20; gated on Main)

Lane: Jwm1AnePlan. Context: the paired recovery
([receipt](2026-09-20-jwm1-ane-paired-recovery/receipt.md)) restored execution
(one exact fp16 smoke). This plan pins every artifact for the full ladder.
Nothing below runs without Main's go; each step ends in a dated receipt.

## Restored base (verified 2026-09-20)

| layer | pin |
|---|---|
| live DT | five-provider ane@26bc04000 node + 3 DARTs with `apple,dma-range 0xe0000000` (dtb `4ec4b87f…`, payload `41a39ac7…`) |
| driver module | guard v2 `ane.ko` sha256 `99e8b8b5…` (`omarchy-ane 9875ef0`, kbuilt vermagic-exact on jwm1, loaded non-persistent, wedged=0) |
| userspace | `libane.a` `9b60216e…` + `libane_python.so` `76fedabb…` (44dd9bf tree, jwm1 build) |
| proven-equivalent | fp16 64-el add-mul exact smoke PASS (this date) |

## Step 1 — eight-package compiler qualification (+ overflow)

Runner: `mil-hwx-compiler @5271ab0` `tools/h13_run_linux.py` (+ `h13_reference.py`,
`research/inspect_anec.py`, `research/h13_td.py`), libane-library = the staged
`libane_python.so`. Packages: `build/m1-closeout-20260906/` —
01-add-legacy, 02-add-runtime-native, 03-mul-scalar, 04-matvec-k256-n512,
05-softmax-512, 06-chain-add-mul (already passed once today), 07-runtime-matmul-64,
08-mlp-768-1024-768. Protocol per the 2026-09-06 M1 native progress receipt:
3 warmups + 30 measured iterations per package, every output matched on every
iteration. Overflow case: finite-input `+inf` — inputs [65504, 65504] through
the add package, expected first output `+inf`, ABI-1 result "all outputs
match" (all under the pre-submit guard: a gated-island regression is now a
clean -ENODEV, not a wedge).

## Step 2 — schema-4 bundle add-then-mul (the September smoke, re-earned)

Bundle: `ane-linux-experiments/.local/ane-v064-wt/receipts/2026-09-13-h13-v2-to-schema4/bundle/`
(program-0.anec `a3aa2fe1…`, program-1.anec `860de06c…`, manifest
`schema4-attn-select-island`) — historical pass reference
[2026-09-13-jwm1-schema4-ane-smoke.json](2026-09-13-jwm1-schema4-ane-smoke.json):
exact fp16, 2 iterations. Runner/library pair per that receipt; worker/binary
pins re-derived from the pinned trees, recorded before the run.

## Step 3 — islands E2E (o-proj + attention)

Prior proof: 2026-09-17 certification on the old boot (historical dated
evidence). Re-run the island bundles through the H13 worker on the restored
stack; acceptance = the documented exact-output contract per island.

## Step 4 — 100-run warm soak

Pattern: [2026-09-16-parakeet-100-run](2026-09-16-parakeet-100-run) — 100
warm runs, zero drift, no reset/timeout, no positive memory trend; genpd
cycle check optional per Main.

## Step 5 — only after 4

Parakeet encoder pins / Qwen3.8 ANE paths, per the standing contracts
(104/104-style pins; never loosened numeric thresholds).

## Standing constraints

- GPU lock protocol for any GPU-adjacent measurement; ANE-only steps need no
  lock.
- No persistence (module stays staged/insmod-only until Main says otherwise).
- Any fault → STOP, preserve journal (persistent) + netconsole
  (non-delivering on this wifi path — journal only), receipt, Main.

## Addendum — Steps 2-4 exact pins (Main directive: no vagueness)

Step 2 (schema-4 add-mul re-earn) — exact historical recipe, verbatim from
`ane-v064-wt/receipts/2026-09-13-ane-worker-validation/run-once.sh`:

- Fixture: `.local/ane-v064-wt/overlay/tests/omarchy/ane/fixtures/
  h13-explicit-chain-add-mul` (present; `source.json` pins schema
  `mil-hwxc.h13-anec-package.v2`, payload shas `9a6a6a9a…`/`62595e4a…`,
  compiler binary sha `b3587e4d…`, source commit `b12b03f1…`).
- Worker: rebuilt from the pinned `ane-v064-wt` mlx-omarchy tree
  (`scripts/prepare-mlx.sh` + cmake `-DMLX_OMARCHY_ANE_DEVICE=ON
  -DOMARCHY_ANE_INCLUDE_DIR=<libane@f261a6c worktree>` + ninja
  `mlx-omarchy-ane-worker` `omarchy_ane_worker_tests`). The historical
  worker binary itself (schema4-smoke `5e315017…`) is NOT in any owned
  archive (old root wiped; verified) — the rebuild from pinned sources is
  the faithful path. Heavy ninja build → runs in its own coordination
  window.
- libane for the worker: f261a6c worktree (worktree from `omarchy-ane`
  `f261a6c`, present in the local repo).
- Bundle conversion: `overlay/tools/ane-export/h13_package_to_bundle.py`
  (present) — note: its `--compiler-source` tree
  (`~/src/mil-hwxc-h13-ea903c4`) is NOT in owned archives; the converter's
  provenance fields will cite the preserved `source.json` data instead of
  the lost tree.
- Run: `mlx-omarchy-ane-worker --bundle … --libane … --deadline-ms 5000
  --iterations 2 --input a=… --input b=… --expect y=…` with deterministic
  64-el inputs (the generator is embedded in run-once.sh), inside
  `/tmp/m1-gpu.lock`, with the run-once preflight/post-verify blocks.

Step 3 (islands E2E): the preserved converted bundle
`ane-v064-wt/receipts/2026-09-13-h13-v2-to-schema4/bundle/`
(`schema4-attn-select-island`, program-0 `a3aa2fe1…`, program-1
`860de06c…`, 213 task descriptors) through the same worker; acceptance =
exact outputs per the bundle's logical_result contract.

Step 4 (soak): 100 warm repetitions of the Step-2 worker command
(`--iterations 2` per run, run 100×), zero drift across runs (per-run
output sha256 all identical), no reset/timeout, journal clean; the
parakeet-100-run pattern's preflight/post-verify blocks reused.

Missing-and-must-recover items (owned archives searched, absent): the
September patched `t8103-j293.dtb` (recoverable only via the provider
re-derivation already staged), and the historical worker binary
(recoverable only via the pinned-source rebuild above).

## Addendum 2 — Step 5 provisioning DONE via fleetcopy (staged; execution gated on Main)

Copied jw16 → jwm1 (tar relay, hashes verified by size, 2026-09-20 ~17:1x UTC):
`/var/tmp/V071REL-venv` (115M, v0.7.1 runtime venv at the same absolute path),
`/var/tmp/encwall-v071/base` (runner), `/var/tmp/jw16-conv-place/bundles-conv`
(ANE bundles), `/var/tmp/jw16-oproj-place/{mlx-omarchy-ane-worker,
libane-strict-fill.so}`, `/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ` (SPIRV
cache), `/var/tmp/EncoderParityAne/capture` (golden capture). Execution of
the Parakeet E2E on the ANE remains gated on Main until the Steps 3-4 island
gate closes (golden regeneration or semantics RE) per the standing
"Steps 3-4 close first" ordering.

## Addendum 3 — macOS golden regeneration: environment staged; adaptation required (Main directive)

Switch tooling: `asahi-bless 0.4.2-1` IS installed on jwm1 Linux
(/usr/bin/asahi-bless) — the macOS one-boot switch is remotely drivable.
NativeQ4ExactReproduction: CPU reproduction in flight; their jwm1 GPU runs
NOT started; they will request the exclusive slot and send explicit RELEASE
before jwm1 touches — the OS-switch window opens after that release.

ESP staging DONE: `/boot/efi/ANE-GOLDEN-REQ/` holds the four input bins +
island bundle (manifest + 2 programs), hashes verified — readable from the
macOS side (FAT32) after the switch.

Adaptation finding (source-checked): an off-the-shelf macOS path to execute
raw `.anec` programs with injected inputs does NOT exist in owned trees —
`mil-hwxc.mm` is the compiler, ANEForge runs full models via the documented
model-level flow (the historical goldens were ANEForge full-model captures;
milrun.py then evaluated layer 0 in numpy). The macOS golden for arbitrary
injected inputs therefore requires a small macOS development item (a .anec
runner over the macOS ANE userland client) OR ANEForge model surgery to
inject the staged tensors. Recommendation: treat this as its own gated lane;
the Linux-side artifacts (inputs, references, verifier, mismatch outputs)
are frozen and hash-pinned in the ladder receipt for whichever path Main
picks.
