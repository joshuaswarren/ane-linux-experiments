# jwm1 GDN prefill 4-lane port: landed on mlx-omarchy main — pins bit-exact, decode neutral, TTFT +25%, corpus 6/6

Owner: Jwm1Kernels3, 2026-09-26 (implementation + M1 device, per Main).
Scout recovery: GdnResumeScout (agent://GdnResumeScout).

## Change (mlx-omarchy main `7d3f69ff2`, rebased on `79ded5ac4`)

Two files, nothing else:
- `overlay/mlx/backend/omarchy/shaders/gated_delta_prefill.comp`: 4-lane
  prefill scan (LANES=4 threads per Dv row, 128-thread workgroups, 32
  rows/WG; register-resident state slices, ascending lane-to-lane chain)
  — ported from the proven-correct prefill half of
  `agent/jwm1-parity8-gdn-lanes` `2d1d2a684`.
- `overlay/mlx/backend/omarchy/primitives.cpp`: prefill dispatch grids
  `Hv -> Hv * kGdnWorkgroupsPerHead(=4)` on both passes (coherent with the
  shader's `head = WorkGroupID.x / 4`) + single-chunk pass-0 skip.

Excluded per Main: the 4-lane DECODE shader + its dispatch hunk (rejected
in parity10 stage-2: dec2_s mismatch 153,105 elements AND slower 38.8 vs
39.2 tok/s — discarded, not repaired), all qmm coopmat changes (separate
lane), compute.h (already had the needed constants on main).

## Gates — interleaved base-vs-cand, one lock window, proven venv recipe
(p8-gate.sh pattern: wheel --no-deps, then mlx-lm with deps, then
apply-mlx-lm-patches.sh; bench env MLX_DISABLE_COMPILE=1)

| metric | base = main `aef33d8fa` | cand = `7b4d87b6a` |
|---|---|---|
| 1-pass digest | `486872c410629f1d` | `486872c410629f1d` (identical) |
| 10-pass digest | `dbf704971617fdfc` | `dbf704971617fdfc` (identical) |
| decode tok/s | 39.10 / 39.14 | 39.20 / 39.19 (neutral; decode untouched) |
| prefill-512 tok/s | 222.30 / 236.13 | 236.96 / 236.49 (neutral on long prompts) |
| TTFT tok/s | 56.83 / 57.25 | **71.22 / 72.55 (+25%; macOS bar 99.12)** |
| contract3 all_gates | TRUE | TRUE |
| corpus 6/6 (tok/frm/dur) | true x6 | true x6 (emissions 0/28/101/104 intact) |

TTFT gain is consistent across cand's early (cooler) and late (warmer)
slots while base stayed 56.8-57.3 — if anything understated. The GDN
prefill scan dominates short-prompt TTFT, which is why prefill-512 (attn/
mlp heavy) stays neutral while TTFT moves.

## Installed state (verified)

Gate venv `/var/tmp/jwm1-parity3-venv` = wheel
`0.32.3.dev202609261411+7b4d87b6a`. Installed-pass confirmation: digest
`486872c410629f1d` bit-exact, decode 39.20, prefill 225.15, TTFT 69.69;
corpus 6/6 tok/frm/dur true (journal gdn-install.service 09:54). NOTE:
`dft_gates_clean.sh` force-reinstalls its own pinned `7c0bd851` wheel on
its next invocation — re-pin that harness to the main-built wheel if the
7b4d87b6a baseline should persist across harness runs (Main's call).

## Corpus asset map (canonical, hashed — handed to Jw16Levers8 for jw16)

fixture.flac `30885601173f96b0...` (/var/tmp/ParakeetE2E/audio),
fixture_v03 `8a94d738...`, v1 `b9541731...`, v5 `ddc49b65...`, v10
`872e0e6a...` (/var/tmp/parity8/audio), 1089-134686-0000.wav
`a7a1b5c9...` (/var/tmp/jwm1-ane-step2). Harness
/var/tmp/jwm1-parity3/corpus_gate.py (audio files as argv); jwm1-hardcoded
infra paths (PKG/WHOLE/RUNNER/WORKER/LIBANE/SOURCE/BUNDLES) listed in the
hub handoff; jw16 needs its own T6001 worker build.

## Ops forensics (for the next lane running detached device work)

1. nohup AND setsid-via-ssh both died with their ssh session (systemd user
   session teardown). Durable pattern: `sudo systemd-run --unit=<name>
   --collect --uid=joshuawarren --gid=joshuawarren
   --setenv=HOME=/home/joshuawarren bash <script>` + EXIT trap writing
   RUNNER_EXIT to a status file. Verified surviving disconnects.
2. `/tmp/m1-gpu.lock` is joshua-owned on a sticky tmpfs with
   fs.protected_regular: root (system units) cannot open it (EACCES ->
   flock usage errors) — lock-taking units must run as joshuawarren.
3. build-wheel.sh requires MLX_OMARCHY_SOURCE_COMMIT (non-git trees) and
   MLX_OMARCHY_WHOLE_BUNDLE_DIR=/var/tmp/encoder-whole-jwm1/bundle
   (parakeet-encoder-whole pin; 458 MB, refusal is deliberate).
4. venv creation must use system python3 (bvenv -m venv yields pip-less
   venvs); bvenv python is for pip wheel invocations.

## Main-pin cutover (post-M2-window, 2026-09-26)

7d3f69ff2 wheel built via build-wheel.sh (recipe in
`harness/dft_gates_main_pin.sh`, staged to ~/q38-build/out2/). Re-pinned
harness run (unit gdn-mainpin): Version `0.32.3.dev202609261526+7d3f69ff2`
installed — NO downgrade; pins 1/3/10 all bit-exact
(486872c410629f1d / bc519c03c4ef5fd1 / dbf704971617fdfc); decode
39.18-39.26, prefill512 225.0-227.0, TTFT 67.5-67.8 tok/s (was 56.8-57.3);
contract3 all_gates TRUE. Harness pin update itself = 774a3499.
