# t8103-host main-consolidation battery — both mains hardware-validated (2026-09-25)

Owner: Jwm1Parity3. Directive (Main, 2026-09-25): before any new lever,
build + install both fresh mains on jwm1 and run the ANE control battery,
the Qwen GPU digest, and the Parakeet golden fixture; bisect any
regression to the merge before fixing.

## Shas under test

| artifact | sha | note |
|---|---|---|
| omarchy-ane kmod | `9a0ec81` (`v0.1.0-265-g9a0ec81`, srcversion `0BE464B0928DD42B1E96D0F`) | BranchMerge consolidation; built on-box, installed to `/lib/modules/7.1.13-3-2-ARCH/updates/ane.ko`, reloaded clean. Prior `9ad8474` module backed up at `~/ane-9ad8474-backup.ko` |
| mlx-omarchy wheel | `af737871e` → `mlx_omarchy-0.32.3.dev202609251248+af73787`, sha256 `a295c1ccd1c63ca8678a77d41a788b916729be73dafa12d377a7bb146d872b9d` | built on-box (`DEV_RELEASE=1`, whole-encoder bundle staged from `/var/tmp/encoder-whole-jwm1/bundle`), installed to fresh venv `/var/tmp/jwm1-parity3-venv`; GDN fast+raw+greedy patches all applied, `mx.fast.gated_delta_update_raw` and `mx.fast.greedy_quantized_argmax` both present |
| mlx-omarchy main (test fix) | `ce91f5b8e` | h13 python suite fix (below), pushed to origin/main, verified on jwm1 |

origin/main had advanced one M2-lane commit past 9a0ec81 (`340f3a4`
patch_timer_freq, M2FwStart-2's backport, null-validated on-box); the
kmod was pinned at `9a0ec81` per the battery directive.

## Gate verdicts

| gate | result | evidence |
|---|---|---|
| `omarchy_runtime_tests` (+ copy_offset, info --trace-smoke) | **PASS** | gate script (set -euo) exit 0; info JSON: `module_version v0.1.0-265-g9a0ec81`, accel0 present, ANE available |
| `omarchy_primitive_tests` | **PASS** | gate exit 0 under `/tmp/m1-gpu.lock` |
| `test_h13_package_to_bundle.py` | **FAILED 1F+2E → FIXED** | see bisect below |
| `omarchy_ane_bundle_tests` (C++) | **PASS** | 34/34 cases, 5904/5904 assertions, SUCCESS |
| Qwen GPU digest | **PASS, pins identical** | see table below |
| Parakeet golden fixture | **PASS x3** | see below |

dmesg on the new driver shows the merged DART-containment feature
(`DART containment armed: 3`).

## Qwen GPU contract (venv `/var/tmp/jwm1-parity3-venv`, n=10 prompts, 32 new tokens, prefill 512, MLX_DISABLE_COMPILE=1)

| metric | this battery | certified final row (f252747) | macOS |
|---|---:|---:|---:|
| decode tok/s median (r1) | 37.52 (min 37.14 max 37.95) | 37.36 | 47.05 |
| decode tok/s median (p10) | 37.41 | — | |
| ttft tok/s median | 50.88 / 49.67 (r1 / p10) | 49.98 | 99.12 |
| pure prefill tok/s (512) | 217.59 | 234.14 (219.2 earlier row) | 343.73 |
| 1-pass digest | **`486872c410629f1d`** | identical | |
| 10-pass digest | **`dbf704971617fdfc`** | IDENTICAL to certified (bit-exact) | |

Verdict: no regression; bit-exactness holds across the kmod + wheel
change; prefill bucket (0.64x) unchanged.

## Parakeet golden fixture (certified runner `combined-parakeet.sh t8103-host`, COMBINED_PY=parity3 venv, COMBINED_WHEEL_ALLOW=1, COMBINED_SRC=/var/tmp/IslandsExecJwm1/encoder-source)

- Identity pins all certified: bundle `13c74423…`, libane-strict
  `d06222a8…`, worker `84e8cc8f…`, fused_e2e `aaacba7a…`,
  vulkan_encoder `2dbaace1…`.
- 3 reps rc=0: encoder_hidden `554a3d66…` x3 identical; transcript sha
  `db501a8c…` exact; cpu_tensor_events 0; control `host`.
- ane_exec_ms 141.1 / 140.4 / 140.6 (engine bucket vs macOS 113-122
  unchanged).
- Rep1 wall includes one-time spirv cache compile (fresh $P per run).

## Regression: h13 python test drift (predates the consolidation)

`test_h13_package_to_bundle.py` failed 1F+2E/15. Bisect (pure python,
on-box):

- `be2726e6f` (pre-merge base): FAILED 1F+2E — **not** caused by
  BranchMerge's 4 consolidations.
- `48a3b90ff` (test's own last update): OK 15/15.
- `7750f6092` "ane-export: trust declared channels, verify integrity":
  FAILED — breakage enters here.
- `a12f34789` "declared channels must equal the task-stream-derived
  channels": FAILED (same).

Cause: the module reworked the channel contract (declared==derived,
STRICT_BIND mirror, `_ANEC_PAYLOAD_OFFSET` rename) but the 3 stale cases
still asserted the removed `.struct` attribute and the old "channel
mapping" message. The python failure also short-circuited
`run-ane-bundle-tests.sh` (set -euo) BEFORE the C++ suite ran — the C++
suite was run separately above and passes.

Fix (Main-directed): `ce91f5b8e` — 3 cases rewritten to assert the new
contract (declared input channels [6,5] vs task stream; output
direction [4] vs [5]); stale `.struct`/wording assertions deleted;
fixture builder uses stdlib `struct` + renamed `_ANEC_PAYLOAD_OFFSET`.
Suite 15/15 OK locally and on jwm1; full bundle gate green.

## Handoff

- Battery venv: `/var/tmp/jwm1-parity3-venv` (wheel af737871e + mlx-lm
  0.31.3 + patches). Qwen JSONs: `/var/tmp/jwm1-parity3/qwen/`.
- Driver tree: `/var/tmp/jwm1-parity3-ane` (9a0ec81 kmod built here).
- mlx-omarchy build tree: `~/q38-build/mlx-omarchy` at main.
- macOS grouped window (Qwen ANE denominator `/tmp/macos-retry.sh` +
  encoder powermetrics) remains PARKED pending M2FwStart-2's hv gap.
