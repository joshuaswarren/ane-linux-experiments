# v0.6.8 wheel candidate prepared — build + full jw16 gate, NOT published (2026-09-18)

## Verdict

**v0.6.8 candidate wheel built from mlx-omarchy main `68e3bfd0` on jw16 and the
FULL jw16-side release gate is GREEN on those exact bytes. NOT PUBLISHED: the
both-host gate is a product gate (every prior release ran jwm1+jw16) and jwm1
is hard-blocked (`receipts/2026-09-18-jwm1-macos-root-deadlock.md`). Publish
happens only when the jwm1 gates run or the owner explicitly waives the second
host. `63c1d3cf` is NOT-ANCESTOR of `main` (re-checked before any push; not
pushed anyway).**

## Artifact

- wheel: `mlx_omarchy-0.32.2.dev202609181230+68e3bfd-cp314-cp314-linux_aarch64.whl`
- sha256: `24e8447b355bd89dc3327ce90b374361d00aeb08d2b7809a0e9a0c8c9e11460a`
- size: 8,319,902 bytes
- source commit stamped in version local segment: `68e3bfd` (main, `68e3bfd0`)
- libmlx16 (sha256-16 of `mlx/lib/libmlx.so` in the wheel): `53132738e023ad56`
- installed dist version: `0.32.2.dev202609181230+68e3bfd`
- build: detached worktree `/var/tmp/v068-build/mlx-omarchy` at `68e3bfd0`,
  `DEV_RELEASE=1 scripts/build-wheel.sh` (aarch64 ⇒ ANE worker + bundles +
  strict libane surface). A first build attempt raced with a zombie relaunch
  and was discarded; the wheel above is from a single clean rebuild after
  `rm -rf .work/mlx dist`.
- location: jw16 `/var/tmp/v068-build/mlx-omarchy/dist/` (dev box mirror not
  needed pre-publish; re-hash after any scp per docs/release.md)

## Gate results (all on the built bytes, jw16 T6001 M1 Max)

Driver: `.local/v068-release/v068-jw16-gate.sh` (deployed jw16
`/var/tmp/v068-gate/`); status log `/var/tmp/v068-jw16.status`; artifacts
`/var/tmp/v068-gate-jw16/`. llm-inference stopped for the lock and confirmed
`active` after; one mid-gate probe-source loss (`/tmp/conv-lane` pruned) killed
a continuation before its restore step — service restored manually and noted
in the status log; probes rerun from `/var/tmp/v067-gate/`.

1. **Artifact checks** (local-mode equivalent of `verify-release-assets.py`,
   which itself requires an uploaded release and therefore runs after publish):
   version identity filename = dist-info = METADATA =
   `0.32.2.dev202609181230+68e3bfd`; build commit `68e3bfd` recorded in
   `libmlx.so`; stable build (no `MLX_OMARCHY_GPU_PROFILE` string) with the
   `MLX_DISABLE_COMPILE` positive control present; WHEEL tag
   `cp314-cp314-linux_aarch64` matches filename; wheel's
   `coreml/vulkan_encoder.py` sha256 `789aaec3…f4af74` == overlay bytes at
   `68e3bfd0`. **PASS**
2. **Packaging gate** (`gate-jwm1.sh`: fresh venv, clean HOME, installed
   surface only, all CLI verification checks pass incl. emissions 104/104,
   cpu_tensor_events 0, decode_control gpu-loop): exit 0, transcript
   `db501a8c080380ea…` EXACT on all 3 runs. **PASS**
3. **E2E arms on wheel-installed files** (`fused_e2e.py` against the wheel's
   own coreml pkg, runner, bundles, worker, libane; fixture FLAC + golden):
   - serve-default (no env — the shipped default): match, subs 1, **all pins
     EXACT** transcript `db501a8c…` / hidden `38c73261…` / mel `5b54f4a9…`,
     104/104, bounds PASS, cpu_tensor_events 0, 0 timeouts, enc_wall 6342.2 ms
   - `ANE_ISLAND_MODE=launch`: match, subs 48, same pins EXACT, 104/104,
     cpu_ev 0, 0 timeouts, enc_wall 6666.3 ms
   (ACO arms are dev-bundle-only — `island-oproj-*` is not in the shipped
   bundle set, so the wheel gate covers the shippable AC surface.)
4. **venv-identity-guard --expect**: `V068REL-venv` PASS with
   `--expect 53132738e023ad56` against a v068 gate copy of
   `certified-libmlx-identities.txt` carrying one LOCAL candidate line
   (`v0.6.8-candidate-68e3bfd`, marked pre-publish). The canonical certified
   list gets the candidate line only at/after release. PYTHONPATH-shadowing
   check exercised and clean.
5. **Decode legs, both inside ONE flock hold** (fresh `V068REL-venv`,
   `mlx_lm==0.31.3` matching the certified venvs, HF_HUB_OFFLINE,
   MLX_DISABLE_COMPILE, provenance line asserted to name the candidate
   libmlx): ctx1024 `7da83f06ec9f001d` EXACT (152.35 tok/s), short
   `7fd25a869ff21678` EXACT (191.35 tok/s). **PASS**
6. **hwcap + KATs on the DEPLOYED libmlx.so**: `HWCAP_SHA256=1`; 13/13 FIPS
   180-4 KATs passed; open-probe 964.5 MB/s. **PASS**

## Release notes draft (v0.6.8)

> # v0.6.8 — encoder runner: AC default, PIPE async_eval, PIPE_OPS conv
> cadence, serve-mode default
>
> The Parakeet encoder-runner stack gets four default-on cuts, each
> digest-screened on jw16 before landing (all pins EXACT:
> transcript `db501a8c…`, hidden `38c73261…`/`ef6afd13…` (ACO), mel
> `5b54f4a9…`, 104/104, `cpu_tensor_events` 0, 12/12 arms):
>
> - **PLACED=AC default** (`af5394e0`) — island B is digest-neutral dead
>   weight; dropping it cuts the launch wall −2038 ms (−18.7%).
> - **PIPE async_eval** (`e4cba239`) — issue-only async_eval per GPU
>   statement keeps the Vulkan queue saturated between island drains;
>   eval phase 6301 → 51 ms; AC launch 8840 → 7655 ms.
> - **PIPE_OPS conv cadence** (`56f2ce0f`) — async_eval at conv statements
>   only beats per-statement issue in both modes (AC launch 6561 vs 7706 ms).
> - **Serve-mode default** (`3611cd59`) — resident transport pays spawn once
>   and beats launch (5805 vs 6535 ms); `ANE_ISLAND_MODE=launch` restores the
>   old path.
> - **Dynamic resident registration** (`4cbb7ec8`) — resident preload follows
>   registered family bundles instead of a static list, fixing ACO under the
>   serve default.
>
> Net on jw16: encoder wall **10873 → 3422 ms** (AC serve median, ~3.2×;
> per-stage medians in `4cbb7ec8`: AC serve 3422, ACO serve 3797, AC launch
> 4220, ACO launch 4810 ms). The conv-family screen (`V`) cuts the wall
> further (−11.0% launch / −24.3% resident) but breaks the transcript digest
> 101/104 and stays NO-SHIP — the digest is the product contract. Decode
> digest pins hold: ctx1024 `7da83f06ec9f001d`, short `7fd25a869ff21678`
> (jw16: 152.35 / 191.35 tok/s on this wheel).

Number provenance: per-cut numbers are the commit messages on `main`
(`af5394e0`, `e4cba239`, `56f2ce0f`, `3611cd59`, `4cbb7ec8`); 10873 baseline
is the ticket-quoted pre-cut ABC launch wall (commit-math from `af5394e0`
gives ~10878 — reconcile against the conv-lane E2E report before publishing
the notes); the ticket's "conv 96/101 + device 9/9" figures did not match
anything found in receipts — grounded equivalents are 101/104 (V arms
transcript break, NO-SHIP) and the device gate table (24/24/24/1/1 bundles,
worst rel_l2 0.000219, `receipts/2026-09-18-conv-placement-screen.md`).

## Publish blocker

- jwm1 gates NOT run (short/ctx decode pins + transcript ×3 + KAT on jwm1's
  uploaded-equivalent bytes) — hard-blocked by
  `receipts/2026-09-18-jwm1-macos-root-deadlock.md` (macOS root deadlock; no
  NOPASSWD sudo, Linux side down).
- `verify-release-assets.py <tag>` must run against the UPLOADED release after
  publish (needs the tag to exist); local artifact checks above are its
  pre-publish equivalent, not a substitute.
- Required platforms: a stable release carries linux_x86_64 (cp311, dev box)
  AND linux_aarch64 (cp314). Only the aarch64 candidate is built; the x86_64
  wheel is cut from the same commit at publish time.
- Post-publish: add `53132738e023ad56` to the canonical
  `certified-libmlx-identities.txt` (and jw16 `/var/tmp/v063-jw16/scripts/`).

## Artifacts

- jw16: `/var/tmp/v068-build/` (worktree + build.log), `/var/tmp/v068-gate/`
  (driver + continuation), `/var/tmp/v068-gate-jw16/` (gate outputs: pins,
  guard, legs.txt, kat.txt, hwcap.txt, packaging/), `/var/tmp/V068REL-venv`
  (kept as the candidate venv; identity `53132738e023ad56`).
- driver source: `.local/v068-release/v068-jw16-gate.sh` (this repo).
