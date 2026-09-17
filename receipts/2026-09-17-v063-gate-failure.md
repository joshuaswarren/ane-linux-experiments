# v0.6.3 gate failure root-caused: /tmp ENOSPC + defective driver, NOT map_mode — all pins hold on both hosts, nothing published (2026-09-17)

Verdict: **ALL SIX GATES GREEN ON THE SHIPPED v0.6.3 WHEEL; TAG `v0.6.3`
(`1ed1dab6`) STAYS UNPUBLISHED.** The reported red was environmental:
`/tmp` (7.6 GiB tmpfs) exhausted mid-gate — `OSError: [Errno 28] No space
left on device` during encoder-source emit — compounded by a defective
release driver (`v063-gates.sh` ran the pinned decode with an ambient
python that has no `mlx`/`mlx_lm`, and left scratch behind when
SIGPIPE-killed). `map_mode=3` is exonerated by a full single-variable A/B
on the shipped stack. **No revert; the default stays 3 on both laptops.**
`63c1d3cf` never merged, not touched, not needed.

## 1. The reported evidence, re-examined

| reported | finding |
| --- | --- |
| transcript "corrupted with garbage tail `........... Юн Ю`", pin `db501a8c…` broken | **False alarm.** The tail is part of the certified golden itself: `tools/coreml/parakeet-reference.lock` (`transcript.txt` → `db501a8c…`), `tests/.../tokenizer_golden.json`, and the macOS `native_transcript` recorded in `receipts/2026-09-15-parakeet-e2e-current-wheel.json`. Parakeet TDT genuinely emits this tail on fixture 1089-134686-0000. The pin **held** in every run examined (9/9 jwm1 runs + 3/3 jw16 runs). |
| "No `e2e-report.json` in run-1/2/3" | Category error: the packaging gate writes `transcribe-report.json` (present, `status: match`, `checks_failed: []` in all three morning runs). `e2e-report.json` belongs to the `fused_e2e` harness, which is not part of this gate. |
| `gate-exit=1` then `141` | Harness artifacts. `141` = SIGPIPE from the invoking channel: that attempt died after run-3, before its scratch cleanup, orphaning **1.6 GiB** in `/tmp/parakeet-gate.6gTFlR` — the direct seed of the later ENOSPC. The `exit=1` attempt's log was truncated by the next attempt; it does not reproduce in clean conditions. |
| `decode-exit=3` twice | `v063-gates.sh` ran `scripts/bench_matrix.py` with jwm1's **ambient python3, which has neither `mlx` nor `mlx_lm`** → every leg skipped → `measured_legs: 0` → exit 3. The v0.6.2 pinned-decode procedure (fresh venv + `mlx-lm==0.31.3` + wheel `--no-deps` + `HF_HUB_OFFLINE=1`) was not followed. No model ever ran. |

## 2. Bisect table (jwm1/T8103, module `1fc2e02`, wheel `dcb84f7b…`, worker `cc1caa6e…`, libane `56b46234…`)

| # | arm | map_mode | /tmp | gate result | transcript | encoder_hidden |
|---| --- | --- | --- | --- | --- | --- |
| 0 | morning `v063-gates.sh` runs (07:04–07:06) | 3 | adequate | 3× `status=match`, checks empty; driver died post-run (exit 1/141) | `db501a8c…` ×3 | `38c73261…` ×3 |
| 1 | v1 arm A (07:18), clean driver | 3 | **647 MiB free → ENOSPC** | **FAIL** — transcribe 1–3 `OSError: Errno 28` in `mil_adapter` emit; identity + provenance checks fail downstream | — | — |
| 2 | v1 arm B — INVALID: `sudo -n tee` of `map_mode=0` silently lost when the launching ssh parent died | (3) | ENOSPC | n/a (superseded) | — | — |
| 3 | v2 arm A (07:28), scratch cleaned, supervisor-held parent, readback-asserted mode writes | **3** | 3 GiB | **GATE PASS, exit 0** | `db501a8c…` ×3 | `38c73261…` ×3 |
| 4 | v2 arm B (07:30) | **0** | 3 GiB | **GATE PASS, exit 0** | `db501a8c…` ×3 | `38c73261…` ×3 |
| 5 | jw16/T6001 gate (07:31), live default | **3** | 32 GiB | **GATE PASS, exit 0** | `db501a8c…` ×3 | `38c73261…` ×3 |

Pinned decode leg (v0.6.2 procedure: fresh venv, `mlx-lm==0.31.3`, wheel
`--no-deps`, `HF_HUB_OFFLINE=1 MLX_DISABLE_COMPILE=1`, under
`flock -w 900 /tmp/m1-gpu.lock`, pinned 0.5B snapshot `a5339a41…`):

| host | ctx1024 `generated_ids_sha256_16` | decode tok/s | prefill tok/s | exit |
| --- | --- | ---: | ---: | --- |
| jwm1 | **`7da83f06ec9f001d`** (pin, bit-exact) | 104.79 | 1109.1 | 0 |
| jw16 | **`7da83f06ec9f001d`** (pin, bit-exact) | 141.44 | — | 0 |

(v0.6.2 measured 105.12 / 1111.07 on jwm1 — same digest.)

## 3. Cause

`/tmp` is a 7.6 GiB **tmpfs** on jwm1; the gate `mktemp`s ~2 GiB there
(venv + 480 MB reference fetch + encoder-source emission). Chain:
SIGPIPE-killed gate attempt → orphaned 1.6 GiB scratch → 647 MiB free →
`ENOSPC` inside `mil_adapter.add_fp16` during encoder-source emit → all
three transcribes fail → identity + provenance checks fail → gate red.
Reproduced on demand (arm 1, full traceback), passes deterministically
after cleaning gate-owned scratch (arms 3–5). Zero ANE wedge signatures in
`dmesg` at any point.

`map_mode` is **not** the variable: arms 3 and 4 change exactly one thing
(mode 3 ↔ 0, readback-asserted) and the outputs are byte-identical to each
other and to the certified pins, on the shipped strict worker
(`cc1caa6e`) — the stack the cached-mapping default was never qualified
against. This also closes the "fill-lib performs a flush that `cc1caa6e`
omits" question for gate purposes: no flush-correctness delta exists for
the shipped stack. The collector commits `8b8a4a25`/`64b0395b`/`1ed1dab6`
touch `scripts/collect_*.py` + tests (macOS telemetry) only — inert for
the encoder path; no axis remained to bisect once the failure was shown
environmental.

## 4. Disposition

- **Nothing published.** The GitHub release was not created; the tag stays
  where it is. The wheels are correct — but the release procedure that
  produced the red is not, so re-gate with the corrected driver before
  publishing; if any code changes first, cut a NEW version rather than
  re-pointing the pushed tag.
- **`map_mode` default stays 3.** Restored and readback-verified on jwm1
  (`restored map_mode=3`); live default 3 on jw16. The −6.2%/−8.2% win
  stands on the shipped stack per this receipt.
- **Driver defects to fix before the next release run** (documented in
  `.local/v063-gate-failure/`): (a) decode leg must use the dedicated
  `V063PIN` venv + `HF_HUB_OFFLINE=1`, never the ambient python;
  (b) stdout must go to a file, not a pipe that can SIGPIPE the gate;
  (c) a killed gate leaks its tmpfs scratch — clean `/tmp/parakeet-gate.*`
  and require ≥3 GiB free before gating.
- Environment risk flagged, not touched: `/tmp/swift-bin-aur` (4.8 GiB,
  foreign) can push any `/tmp`-mktemp gate back into ENOSPC.
- `63c1d3cf` never merged — bisect used shipped artifacts only.

## 5. Both-host verification

| | jwm1 (T8103) | jw16 (T6001, M1 Max) |
| --- | --- | --- |
| module | `1fc2e02` | `1fc2e02` |
| map_mode (live, after) | **3** (restored, readback-verified) | **3** |
| clean-install gate | GATE PASS ×2 (mode 3 and mode 0) | GATE PASS (mode 3) |
| transcript `db501a8c…` ×3 | yes (×9 runs total on the day) | yes |
| `encoder_hidden` `38c73261…` ×3 | yes | yes |
| mel bit-exact `5b54f4a9…` | yes | yes |
| `cpu_tensor_events` | 0 | 0 |
| decode digest | `7da83f06ec9f001d` | `7da83f06ec9f001d` |
| `llm-inference.service` | n/a | stopped for the lock, restarted, `active`, lock re-held (`flock --nonblock` rearmed) |

## 6. Not claimed

- The morning attempt's `exit=1` has no surviving log; its attribution to
  the ENOSPC mode is inference from the reproduced deterministic failure
  and the debris timeline, not from its own (truncated) log.
- No flush-behaviour study of fill-lib vs strict workers was performed —
  moot for this gate, open as hardening work.
- jw16 prefill tok/s not quoted (field not extracted from that report).

## 7. Artifacts

- Drivers: `.local/v063-gate-failure/{v063-bisect.sh,v063-bisect2.sh,v063-jw16.sh,v063-jw16-decode.sh}`
- jwm1: `/var/tmp/v063-bisect2.status`, `/var/tmp/v063-bisect2-{A,B}/`,
  `/var/tmp/v063-bisect-decode.json`
- jw16: `/var/tmp/v063-jw16.status`, `/var/tmp/v063-jw16-gate/`,
  `/var/tmp/v063-jw16-decode.json`
- ENOSPC traceback: `/var/tmp/v063-bisect-A/gate.log`
