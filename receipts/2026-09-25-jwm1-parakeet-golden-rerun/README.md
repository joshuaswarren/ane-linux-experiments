# 2026-09-25 — jwm1 Parakeet golden re-run after the post-reboot hang — PASS bit-exact on installed ane a9a5f60 (Jwm1Parity6)

Owner: Jwm1Parity6. Host: jwm1-linux (T8103), Omarchy, kernel
7.1.13-3-2-ARCH. Installed module:
`/lib/modules/7.1.13-3-2-ARCH/updates/ane.ko` at omarchy-ane main
`a9a5f60`, srcversion `CD235EAE3669B084F6D63DA`, parameters
`dart_contain=Y map_mode=3 allow_unqualified=N`, DART containment
`armed: 3` (dmesg). libane + libane_python on the box are rebuilt from the
same `a9a5f60`.

## 1. The hang we are closing

The first golden run after the reboot to `a9a5f60` (Jwm1Parity5) hung 40
minutes inside `fused_e2e` and was killed. That run left NO kernel trace:
`dmesg` on this boot shows only module-init lines at t=87 s (TM/TQ enable
writes, `DART containment armed: 3`), and no ANE, DART or fault line after
them. So the hang was userspace-side and silent, not a DART fault. Cause
unknown; it did not come back (section 3).

## 2. Instrumented re-run

`/var/tmp/parity6/golden-watch.sh` wraps `combined-parakeet.sh
t8103-host` with: a 600 s hard cap per rep (`timeout -k 30 600`), and a
watchdog that at 540 s captures cmdline, status, wchan, syscall,
`/proc/<pid>/stack` plus every thread stack, a py-spy dump of the python
and each child (ANE worker included), the full dmesg tail and the ANE
driver parameters — then kills the rep. The watchdog never fired: all
three reps finished in about 2.5 minutes total (13:34:42-13:37:10 CT).

Config: `COMBINED_PY=/var/tmp/jwm1-parity3-venv`
(`COMBINED_WHEEL_ALLOW=1`), `COMBINED_SRC=/var/tmp/IslandsExecJwm1/
encoder-source`, whole-encoder bundle
`/var/tmp/encoder-whole-jwm1/bundle`, `MLX_OMARCHY_TDT_HOST=1`,
`MLX_OMARCHY_DEFER_COMMIT=1`, `ANE_ISLAND_MODE=resident-batch`.

## 3. Result: PASS, bit-exact, 3/3 reps

Output: `/var/tmp/encoder-whole-jwm1/combined-20260925T133442/`
(e2e-report.json per rep). Watchdog log:
`/var/tmp/parity6/golden-20260925T133442/` (combined.log, main-rc.txt,
`MAIN_RC=0`).

Every layer check passed in each rep:

| check | result |
| --- | --- |
| mel (3001x128) + mask | bit_exact true, max_abs_err 0.0, mask exact |
| encoder input features (1x3000x128) | bit_exact true, max_abs_err 0.0 |
| encoder hidden (1x375x640), mask sum 375 | bit_exact true, max_abs_err 0.0, all bounds pass |
| tokens (TDT layer 6) | `tokens_match: true` (must match exactly), durations and frame indices match |
| transcript (layer 7) | sha256 `db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790` equals the native golden sha |
| status | `match` in all 3 reps |

`encoder_hidden.npy` is byte-identical across the three reps:
sha256 `554a3d66f6885a3552d531d509bbd30d632d5bd424296028e8c1523f9f6f4ec4`.
ANE exec per rep: 140.318 / 140.529 / 141.117 ms, 1 submission, 0
timeouts, `worker_starts 1`, `cpu_tensor_events 0`. Decoder mean 5.471 ms
per call, joint mean 1.41 ms.

## 4. Verdict

The golden contract passes bit-exact (transcript, tokens, durations,
frame indices, tensor checks) on the INSTALLED `a9a5f60` module. The
40-minute hang did not come back under the armed timeout. The watchdog
stays at `/var/tmp/parity6/golden-watch.sh` for future runs; if the hang
returns it now leaves a full stack + py-spy + dmesg capture at 9 minutes
and stops the contract instead of burning 40 minutes.

Pass rule context: this closes the highest-priority jwm1 lane item; the
ANE module swap to `a9a5f60` is now certified end to end (bundle battery
34/34 from Jwm1Parity5 + this golden).
