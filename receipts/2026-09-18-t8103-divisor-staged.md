# T8103 (jwm1) divisor harness STAGED on macOS 14.8.9 — dry-run verified, one command ready to fire the moment macOS 26.6.2 is up (2026-09-18)

> **STATUS UPDATE 2026-09-18 (post-upgrade): RAN — see
> `2026-09-18-t8103-divisor-macos27.md`.** The fleet upgraded jwm1 straight to
> **macOS 27.0 (26A428), CoreML 3600.25.2** — not the 26.6.2/3520 this receipt
> predicted. The upgrade wiped `/tmp` (as this receipt warned it might via the
> 3-day cleaner; the upgrade did it immediately); the harness was re-staged from
> the lane scratch `/tmp/t8103-stage/` (14/14 manifest-verified, manifest
> byte-identical to the one committed here) and the model cache **survived**
> (12/12 verify). Both hard gates passed unchanged on the actual env: OS-GATE
> 27.0 ≥ 26, COREML-GATE 3600.25.2 ≥ 3520. Preflight went 14 pass / 0 fail /
> 0 blocked (the two BLOCKED lines below cleared exactly as designed). Battery
> ran with the 104-token guard holding 22/22; no self-pin. Divisors:
> `.ane` 259.9 ms / `.all` 266.7 ms median all-10 — **cross-OS-generation
> caveat applies** (27.0/3600 here vs the 292.2/305.8 reference at
> 26.6.2/3520-era): indicative, not exact; 26.6.2-matched erase-install
> re-run recorded as an owner call, not scheduled.

Verdict: **STAGED — NOT RUN, by design.** The full M1-Ultra-methodology battery
for the same-die T8103 Parakeet divisor is on jwm1 at `/tmp/t8103-divisor/`,
manifest-verified, dry-run-proven, and gated so the **only** post-upgrade step
is `ssh joshuawarren@192.168.3.66` → `cd /tmp/t8103-divisor && ./run.sh`.
No timing was taken and no CoreML8 parse was attempted pre-upgrade: CoreML
3304.7.1 on 14.8.9 provably refuses the pinned model's opset
(2026-09-17-parakeet-macos-timing-t8103.md — exit 133 at spec parse in every
compute-unit config), which is exactly why the box is mid-upgrade
(`/tmp/InstallAssistant-26.6.2.pkg`, curl pid 5307 live at staging time,
untouched; no reboot, no heavy IO, no installs).

## What is staged on jwm1 (`/tmp/t8103-divisor/` — 14 files, manifest-verified)

```
preflight.sh                  # 13-check gate; safe on ANY macOS (no CoreML parse, no build)
run.sh                        # THE post-upgrade command: gate -> release build -> .ane + .all batteries
stage-manifest.sha256         # 14-file integrity manifest (re-verified by every preflight run)
parakeet-mel-stage/           # harness, copied VERBATIM from macstudio (Package.swift, Package.resolved, Sources/{parakeet-timing,parakeet-reference-capture,mel-stage-capture})
fetch_parakeet_reference.py   # mandated downloader (verbatim from macstudio fetch-tool)
reference.py                  # its sibling module (required import; initially missed, fixed)
parakeet-reference.lock       # 12-file hash lock (verbatim)
pinned_files.txt              # (verbatim)
fixtures/1089-134686-0000.flac            # 10.435 s LibriSpeech fixture
fixtures/golden/token_ids.json            # M1-family golden token ids
fixtures/golden/transcript.txt            # golden transcript (file sha == guard sha)
out/                          # created by run.sh: preflight.log, build.log, timing-ane-*.json, timing-all-*.json, battery logs
```

**Byte-identity with the reference host**: all 9 harness-origin files
(Package.swift, Package.resolved, 3× main.swift, downloader, lock, fixture,
golden) hash **identical** to macstudio's `~/parakeet-mel-stage` and
`~/parakeet-ref-capture` — the no-fork discipline of the Ultra/T6021 receipts,
proven by `shasum -a 256` on both ends (archived:
`2026-09-18-t8103-divisor-staged/macstudio-byte-identity.txt`).

**Pins embedded in run.sh (identical to the reference methodology):**
model `b650695c2322ee5281dff48d7345b2f3a58ff018` (12 files, palettized-4bit
encoder) at the mandated cache path; SwiftPM
`parakeet-coreml-swift` @ `75aec2a1c991319657ff4dec5f602c12da6c5012`
(Package.resolved verbatim); audio sha `30885601…c2`; guard = **104 tokens** +
exact golden ids (`a175a5f9…c8`) + transcript sha
`db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790`;
`--warm 1 --runs 10` per config (`.ane` = `.cpuAndNeuralEngine`, `.all`);
`ContinuousClock` around `transcribe(audioURL:)` only, model load excluded,
guard enforced per run before a number is recorded.

Adaptation for T8103/jwm1 is **paths and nothing else**: `--models` resolves
to jwm1's cache dir (transcriber's `modelsRoot` = the direct
encoder/decoder/joint/tokenizer dir — confirmed non-recursive in the pinned
library source); expected device `Apple M1` / `MacBookPro17,1` asserted by
preflight (the harness self-reports chip/hw_model/CoreML version in every
JSON's `environment`).

## Dependencies checked on 14.8.9 now (preflight re-checks all of these post-upgrade)

| dep | state on 14.8.9 (2026-09-18) |
| --- | --- |
| python3 | PASS — 3.9.6 (system). Post-upgrade failure mode: CLT shim may need `xcode-select --install`; preflight FAILs with that hint if so |
| coremltools | **ABSENT — recorded, and NOT required**: the harness is Swift-only (proven on jw14m2, T6021 receipt). No pip install performed or planned |
| swift / Xcode CLT | PASS — Apple Swift 5.10 (CLT); built this exact tree clean in 38.7 s on 09-17 |
| pinned model cache | PASS — mandated downloader `verify`: **"OK: 12 files verified"** at `~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c…` (du note: jwm1 holds 459 MB; macstudio's 923 MB total includes a 465 MB `tdt-staging/` export scratch — the pinned commit dir is 459 MB on both; nothing is missing) |
| power / thermal / disk | PASS — AC connected (100 %), therm clean, 99 GiB free |

## Dry-run on 14.8.9 (everything that does NOT need a CoreML8 parse)

- `./preflight.sh` → **exit 3, 12 pass / 0 fail / 2 blocked**. The only BLOCKED
  lines are `OS-GATE macOS 14.8.9 < 26` and `COREML-GATE 3304.7.1 < 3520` —
  precisely the upgrade, nothing else. Full log archived:
  `2026-09-18-t8103-divisor-staged/preflight-dryrun-14.8.9.log`.
- `./run.sh` → **refuses at the gate, exit 3**, prints "still pre-upgrade …
  Run after reboot into macOS 26.x", and creates **no `.build` dir** — no
  build, no model load, no CoreML parse. Gate plumbing proven end-to-end.
- Staging bugs this dry-run caught and fixed before they could burn the
  post-upgrade window: (1) the downloader needs sibling `reference.py`;
  (2) it has no shebang → must be invoked as `python3 …`; (3) laptop
  `pmset -g ps` is two lines (AC line is not `tail -1`); (4) `run.sh` now sets
  `pipefail` so `tee` cannot mask a guard-refusal exit code.

## Post-upgrade procedure (the only step)

```sh
ssh joshuawarren@192.168.3.66     # LAN address; the TS alias `jwm1` times out as of 2026-09-18
cd /tmp/t8103-divisor && ./run.sh
```

run.sh then: hard preflight gate (CoreML `CFBundleVersion` ≥ 3520 via
`plutil`, macOS ≥ 26, chip/model, manifest re-hash of all 14 staged files,
model re-verify, fixture/golden re-hash, AC/thermal/disk) → `swift build -c
release` (40–90 s; SwiftPM fetch already proven on this host, cache intact,
`GIT_CONFIG_GLOBAL/SYSTEM=/dev/null` scrubbed against the jw14m2-style ssh-config
breakage) → `.ane` battery → `.all` battery → medians printed. Expect a fresh
ANE compile on first load per config (27–45 s, T6021/Ultra precedent;
recorded as load, excluded from walls) and ~10 × 0.3 s measured runs; the
whole thing is minutes. Success signal: `READY:` from preflight, 11/11 guard
holds per battery, `timing-ane-m1ultra-reference.json` +
`timing-all-m1ultra-reference.json` in `out/`.

**Escape hatch** (not expected to be needed): the 104-token guard is an
M1-family invariant (holds on T6000/T6001/T8103-class; only T6021 diverged, at
token 99). If T8103 were to fail it: `./run.sh --self-pin` mints a
T8103-local golden (3× `parakeet-reference-capture`, shas must agree across
all three, else it refuses) and re-runs the batteries against it — the exact
T6021 self-pin precedent. Such numbers would be labelled t8103-selfpin and
would NOT be token-for-token comparable with the 292.2 ms Ultra reference.

After the run: archive `out/` JSONs + logs to
`receipts/2026-09-18-t8103-divisor-run/` and write the divisor receipt
(medians vs 292.2 ms ANE / 305.8 ms `.all` M1-Ultra and the Linux jwm1 legs;
like-for-like stage definitions per the Ultra comparability note).

## Survival + safety

- macOS `/tmp` is on the Data volume and **survives the upgrade reboot**
  (only the 3-day periodic cleaner removes old files) — run within 3 days of
  2026-09-18, or re-stage from this receipt's manifest.
- Footprint on jwm1: `/tmp/t8103-divisor/` (22 KB staged) + `/tmp/t8103-preflight-verify.log`
  + `out/preflight.log` from the dry-runs. No installs, no pip, no sudo, no
  launchd, no reboot; the upgrade curl (`/tmp/InstallAssistant-26.6.2.pkg`,
  pid 5307) was never touched; largest IO was the one-time 459 MB hash verify.

## Not claimed

- No timing numbers of any kind; no CoreML8 parse attempted on 14.8.9.
- No build executed pre-upgrade — deliberately: the on-host post-upgrade
  build is part of the methodology (binaries must link the new CoreML), and
  the build path itself is already proven on this host+tree.
- Post-upgrade success is **predicted, not verified**: everything before the
  CoreML gate is proven; the gate itself must PASS after the upgrade
  (3304.7.1 refuse / 3520.5.1 accept are the only empirical endpoints known).

## Artifacts

`receipts/2026-09-18-t8103-divisor-staged/`:
`preflight-dryrun-14.8.9.log` (full 13-check output, exit 3),
`stage-manifest.sha256` (the 14-file manifest pushed to jwm1),
`macstudio-byte-identity.txt` (macstudio-side shasum of the 9 harness-origin
files).
