# jw16 venv identity hygiene — repins, non-certified markers, identity guard (2026-09-18)

Verdict: **one drifted venv repinned to its certified wheel and EXACT on both
decode pins; the certification-grade venvs were audited 61-venv-deep; the
drift mechanism (release gates sharing `V064REL-venv`) is fixed at the
driver; and a cheap identity guard now refuses any non-certified or
PYTHONPATH-shadowed venv loudly before a pin lane can start.** No gate was
weakened; no venv was upgraded past certified content.

Origin: `receipts/2026-09-18-encoder-conv-device-gate.md` environment note —
pre-gates failing on `/var/tmp/jw16gap-venv` and `V064REL-venv` before the
digest pins were reached.

## Certified identity list (built from wheel bytes, not memory)

Hashed the libmlx member inside every certified wheel on jw16
(`/var/tmp/v063-jw16/`), cross-checked against the bisect table in
`receipts/2026-09-17-gpu-matmul-bisect.md`:

| build | wheel | libmlx16 | jw16 evidence |
| --- | --- | --- | --- |
| V063REL | `1ed1dab` (asset `dcb84f7b…`) | `a10cebf540565ccf` | release gate GREEN, both pins exact |
| V064REL | `112c32c` (asset `a2ddd188…`) | `224a9597cf938424` | release gate GREEN, both pins exact |
| V065REL | `7b05e93` | `1a9a9206bcee4f21` | gate GREEN, ctx1024 pin exact |
| V066BASE | `2f58ead` | `06e43c203e85a16a` | gate GREEN; base arm pins exact (decode-two-pass) |
| V067REL | `fb649d8` | `e9e709f38331ff10` | gate GREEN (KAT); both pins exact as barrier-screen base |

Canonical copy: `receipts/certified-libmlx-identities.txt` (also deployed to
jw16 `/var/tmp/v063-jw16/scripts/`, next to the guard).

## The actual drift, root-caused

- `V064REL-venv` carried `e9e709f38331ff10` (`0.32.2.dev202609172230+fb649d8`)
  — the **v0.6.7 release wheel**, not v0.6.4. Mechanism: the v0.6.6 and v0.6.7
  gate drivers reuse `VENV=/var/tmp/V064REL-venv`
  (`/var/tmp/v066-gate/v066-jw16-gate.sh:18`, `/var/tmp/v067-gate-driver.sh:18`)
  and `pip install --force-reinstall` their wheel into it; the v0.6.7 gate
  (17:42 Sep 17) left v0.6.7 installed in the v0.6.4-named venv. Any later
  lane pinning `V064REL-venv` hits an identity pre-gate failure before its
  digest pins — exactly the ConvDeviceGate note.
- The other two observed identities are lane venvs that legitimately hold
  non-certified builds: `65a641e4…` = `MelFrontendPerf/venv-cache`
  (`05015a76` mel lane), `84664140…` = `jw16gap-venv` (`266813b` fix
  candidate). `84664140` also shadowed runs via the E2E PYTHONPATH.
- Everything else in the census is per-lane A/B scratch (base/cand arms of
  closed lanes) — never certification-grade, now refused by the guard by
  default.

## Repairs

1. **`V064REL-venv` repinned to the certified V064REL wheel**
   `mlx_omarchy-0.32.2.dev202609171442+112c32c-cp314-cp314-linux_aarch64.whl`
   — sha256 asserted `a2ddd18824610be0…bbd8a46` (matches the v0.6.4 release
   asset expectation in the v064 driver) before install,
   `pip install --no-deps --force-reinstall`. Post-repair: dist
   `0.32.2.dev202609171442+112c32c`, libmlx16 `224a9597cf938424`
   (full `224a9597cf93842447b58d1be054413129f145a0e378df8139cd24b940aacd62`).
2. **Root cause fixed in the gate drivers** so the clobber cannot recur:
   v067 driver → `VENV=/var/tmp/V067REL-venv`, v066 gate script →
   `VENV=/var/tmp/V066REL-venv` (v063/v064/v065 drivers already had their own
   venvs). Diffs vs backups are exactly the one line each; backups kept as
   `*.pre-venvhygiene-20260918` beside the scripts.
3. **Evidence venvs marked loudly non-certified** (`.mlx-NONCERTIFIED`
   marker carrying the reason; guard quotes it on refusal):
   `/var/tmp/jw16gap-venv` (266813b fix candidate — kept as the decode-gap
   receipt's reproducible artifact, hence marked, not repinned),
   `/var/tmp/decodetp-venv` (283aa076 ship candidate, pre-release),
   `/var/tmp/MelFrontendPerf/venv-cache` (05015a76 mel stack + known
   PYTHONPATH-shadowing source), `~/.local/share/mlx-omarchy-test-venv`
   (provenance self-test fixture).

## Identity guard (where the pre-gates run)

`venv-identity-guard.py` — repo root here, deployed to
jw16 `/var/tmp/v063-jw16/scripts/` beside `bench_decode.py`/`mlx_provenance.py`
with the certified list beside it. Per venv, no mlx import, no GPU:
marker file → refuse with reason; installed libmlx16 → must be on the
certified list; loaded identity resolved in PYTHONPATH-then-venv order →
must equal installed (catches the site-dir shadowing class); optional
`--expect LIBMLX16` strict pin. Exit 3 = refuse, message names the venv,
identity, and the list. Self-check of all four verdict paths passed locally
before deploy (`pass / not-certified / marker / shadowing`).

Post-repair sweep on jw16 (exit codes observed):

```
PASS /var/tmp/V063REL-venv  (a10cebf540565ccf, V063REL)
PASS /var/tmp/V063PIN-venv  (a10cebf540565ccf, V063REL)
PASS /var/tmp/V064REL-venv  (224a9597cf938424, V064REL)   <- repaired
REFUSE jw16gap-venv / decodetp-venv / MelFrontendPerf/venv-cache / test-venv: marked NON-CERTIFIED
REFUSE DecodeTrioRun/venv-trio, SdpaKvJw16/venv-base, SwigluRmsJw16/venv-cand, DecodeCompileAB/venv-ab: not on certified list
certified set exit=0, refuse set exit=3
```

## Decode digest-pin verification (one window, protocol per discipline record)

TAKE announced to Main → `sudo systemctl stop llm-inference` (active →
inactive) → `flock -w 900 /tmp/m1-gpu.lock` (inode **12**, never
stolen/unlinked) → pins → service restarted → `is-active=active` confirmed
(MainPID 140814) → RELEASE announced. Hold ≈ 9 s wall; /tmp 30 G asserted.
Pins fatal, identity expectations fatal
(`pins.jsonl` in `receipts/2026-09-18-jw16-venv-identity-hygiene/`):

| venv | leg | ids digest | pin | identity | decode tok/s |
| --- | --- | --- | --- | --- | ---: |
| V064REL-venv (repaired) | short | `7fd25a869ff21678` | EXACT | `224a9597cf938424` | 190.88 |
| V064REL-venv (repaired) | ctx1024 | `7da83f06ec9f001d` | EXACT | `224a9597cf938424` | 122.83 |
| V063REL-venv (hold check) | short | `7fd25a869ff21678` | EXACT | `a10cebf540565ccf` | 189.48 |
| V063REL-venv (hold check) | ctx1024 | `7da83f06ec9f001d` | EXACT | `a10cebf540565ccf` | 149.46 |

All four provenance lines `verified=match`. The repaired venv produces the
release-certified digests on its certified wheel — the repair is right.

## Inventory census (61 venvs, jw16, 2026-09-18)

Identity = sha256(`site-packages/mlx/lib/libmlx.so`)[:16], the value the
pre-gates pin; collected without importing mlx
(`jw16-venv-inventory.jsonl` beside this receipt is the raw data).

| venv (jw16) | dist version | libmlx16 | verdict / should pin to |
| --- | --- | --- | --- |
| `~/.local/share/mlx-omarchy-test-venv` | `0.32.2.dev202609122106+b41e2b74` | `f2d45e601f05dd22` | lane A/B scratch — non-certified, guard refuses |
| `~/venv-agxgen` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/DecodeCompileAB/venv-ab` | `0.32.2.dev202609122355+b41e2b74` | `03b3f4b9024927f9` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/DecodeEpilogueFold/venv-base` | `0.32.2.dev202609141639+b79a4b68` | `fdfc6a6db21e4f23` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/DecodeEpilogueFold/venv-cand` | `0.32.2.dev202609141752+52f73e4f` | `d3f23ef7d6fb0b3c` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/DecodeEpilogueFold/venv-gepin` | `0.32.2.dev202609150054+6110078e` | `758f0d0ef81bc086` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/DecodeEpilogueFold/venv-probe` | `0.32.2.dev202609142212+a3e9f486` | `8e6271bd38658c1f` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/DecodeEpilogueFold/venv-rms` | `0.32.2.dev202609142212+a3e9f486` | `2070c87f0bad4687` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/DecodeTrioRun/venv-cross` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/DecodeTrioRun/venv-rp-arm` | `0.32.2.dev202609151843+1c49674f` | `648af9bec65110ed` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/DecodeTrioRun/venv-rp-base` | `0.32.2.dev202609151835+1014a76e` | `af9138141dcd98c3` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/DecodeTrioRun/venv-trio` | `0.32.2.dev202609151800+14c6ca92` | `8c42a5e4e1593a66` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/DecodeTrioRun/venv-trio-diag` | `0.32.2.dev202609150920+519d7336` | `1091c35e6b835aeb` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/DecodeTrioRun/venv-trio-diag2` | `0.32.2.dev202609150907+519d7336` | `4ee867ad6a2a5baf` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/DecodeTrioRun/venv-trio-diag3` | `0.32.2.dev202609151056+519d7336` | `963e6fa9339e7e5b` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/E2E296/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/E2EREV/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/MelFrontendPerf/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/MelFrontendPerf/venv-cache` | `0.32.2.dev202609141626+05015a76` | `65a641e4a9e69737` | MARKED non-certified (05015a76 evidence) |
| `/var/tmp/SdpaBlockB/venv-cand` | `0.32.2.dev202609170332+dfdb0efc` | `5eff33ac3b437d4c` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/SdpaKvJw16/venv-base` | `0.32.2.dev202609161430+0101d673` | `8c074587ea72ffae` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/SdpaKvJw16/venv-cand` | `0.32.2.dev202609161501+3ea2d3c7` | `92bc21d5fb6c3290` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/SdpaKvMajorJw16/venv-base` | `0.32.2.dev202609161544+d28aa303` | `7b551e283fbc3c7c` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/SdpaKvMajorJw16/venv-cand` | `0.32.2.dev202609161621+aba82b49` | `f0bada5e71b41bf6` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/SwigluRmsJw16/venv-base` | `0.32.2.dev202609152131+1deb70f1` | `6d61d44acbc51c3e` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/SwigluRmsJw16/venv-cand` | `0.32.2.dev202609152134+a21b3c81` | `f256391d06bc6cd8` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/SwigluRmsJw16/venv-diag-cand` | `0.32.2.dev202609152244+diag.a21b3c8` | `860d007163358829` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/SwigluRmsJw16/venv-diag-rms` | `0.32.2.dev202609152310+diag.af332e7` | `f4704f98d9c340cf` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/SwigluRmsJw16/venv-rms` | `0.32.2.dev202609152355+c2fc9246` | `79e5c0c14b02e390` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/TermAJW16/venv` | `0.32.2.dev202609161852+2e252962` | `edf956df086d13d5` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/V063PIN-venv` | `0.32.2.dev202609171159+1ed1dab` | `a10cebf540565ccf` | **certified V063REL** — correct |
| `/var/tmp/V063REL-venv` | `0.32.2.dev202609171159+1ed1dab` | `a10cebf540565ccf` | **certified V063REL** — correct |
| `/var/tmp/V064REL-venv` | `0.32.2.dev202609172230+fb649d8` | `e9e709f38331ff10` | census: held V067REL build (drift) — **REPAIRED to certified V064REL**, now `171442+112c32c` / `224a9597cf938424`, pins EXACT |
| `/var/tmp/decode-trio/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/decodetp-venv` | `0.32.2.dev202609172006+283aa076` | `aa5615cea4e584f7` | MARKED non-certified (283aa076 evidence) |
| `/var/tmp/decodetp-wt/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/gemv-rmsnorm/.work-stale-v1/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/gemv-rmsnorm/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/jw16-v061-parity/v061-venv` | `0.32.2.dev202609170611+b8e5300` | `9a72c3b84c74e7b3` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/jw16gap-venv` | `0.32.2.dev202609171916+266813b` | `846641408618cc9c` | MARKED non-certified (266813b evidence) |
| `/var/tmp/jw16gap-wt/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/main-base/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/mlx-omarchy-prof-b41e2b74/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/mlx-omarchy-prof-b41e2b74/venv-diag` | `0.32.2.dev202609141516+b41e2b74` | `d92f6e7cb408fbbb` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/mlx-omarchy-prof-main/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/mlx-omarchy-prof-main/venv-diag` | `0.32.2.dev202609170303+99b7104c` | `9da7017aec47edea` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/qmm-fat-jw16/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/qmm-fat-jw16/venv-run` | `0.32.2.dev202609142107+fat.02b0a7f418f5e8239ade60960e394c50095d406c` | `a172fed8be7caf8d` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/qmm-inline/venv-inline` | `0.32.2.dev202609170801+11fe4725` | `56cca3427e09573f` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/qmm-tilem-ab-20260914/venv` | `0.32.2.dev202609141611+23102851` | `b59c8b757da69da6` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/qmm-tilem/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/qmmceil/venv` | `0.32.2.dev202609171941+diag.6f70d4fa` | `83d20eefad8033ee` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/qmmceil/work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/rmsnorm-epilogue/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/rmsnorm-epilogue/venv-test` | `0.32.2.dev202609142212+a3e9f486` | `b1019bf60c1647c6` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/rope-pair-land/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/tdt-control-fb4/venv-gate` | `0.32.2.dev202609141801+fb4dfa86` | `6afd5bc8830634b3` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/tdt-control/venv-ctl` | `0.32.2.dev202609141629+5cf58f7c` | `18d8c65f192441fb` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/tdt-ctest/venv-gate` | `0.32.2.dev202609141744+deb9c72b` | `2577ca973a4a6a81` | lane A/B scratch — non-certified, guard refuses |
| `/var/tmp/tdt-stack/.work/venv-build` | `—` | `—` | no mlx stack (build scratch) |
| `/var/tmp/tdt-stack/venv-gate` | `0.32.2.dev202609141624+38d5ebfb` | `141090a7b2e0c92b` | lane A/B scratch — non-certified, guard refuses |

Notes on census classes: `.work/venv-build` entries are per-lane wheel-build
scratch with no mlx install (identity `—`); base/cand/diag/trio/… venvs are
closed-lane A/B arms whose whole point is a non-certified build — they stay
exactly as they are, and the guard now refuses them by default instead of a
confusing mid-run pin break. No lane scratch venv was repinned: repinning
closed-lane arms would erase their receipt-reproducibility for no benefit.

## What was deliberately not done

- No venv upgraded toward any newer build (rule: never past certified).
- No formatter/lint passes; no project-wide suites (per assignment).
- jwm1 untouched. `63c1d3cf` untouched.
- The closed-lane drivers under `.local/jw16gap/` keep their historical pins
  (they are receipt artifacts); any re-run must pin explicitly, and the guard
  now says so loudly up front.
