# Driver lifecycle rebase (2026-09-14)

omarchy-ane `origin/main` is `6fa243a` (fast-forward `8554583..6fa243a`).
That commit is the lifecycle-correct `b66ca80` driver plus T6001 deltas,
runtime-PM resume before the first engine MMIO, ane-parity derived-channel
libane with `STRICT_BIND` refuse of a positional map, and a quoted uapi
include.

`8554583` is no longer on `main`. It copied the T6001 bring-up driver onto
`main` and dropped the managed lifecycle. Do not load it.

## Commits on main

| SHA | Change |
|---|---|
| `cc56538` | restore lifecycle-correct driver from `b66ca80` |
| `f4e62e8` | `pm_runtime` resume before first engine MMIO |
| `442882a` | merge `ane-parity` (derived-channel libane) |
| `5113ef6` | report positional channel map; refuse it under `STRICT_BIND` |
| `6fa243a` | include uapi header by quoted path |

## Hosts

### jw16mbp1-linux (T6001)

Reloaded earlier in `DriverLifecycleRebase` to `6fa243a`. Module stayed
loaded. No second reload this session.

### jwm1-linux (T8103)

Live module before reload: `f2a3e5e+lifecycle6`
(`srcversion DD43701FCB506056A340587`), systemd unit
`jwm1-ane.service` insmod from
`/home/joshuawarren/src/omarchy-ane-h13-f261a6c/ane/ane.ko`.

Reload 2026-09-14T12:07:43-05:00 → 12:07:45-05:00, boot_id
`95872130-fd28-4d67-8247-03a0e8b61202` unchanged, uptime from
2026-09-13 09:43:25 unchanged.

- workers 0, ANE lock free, refcnt 0
- `ane.ko` sha256 `53039586a21438477a530a47f7b9dfa7e586302dae81dd52765ebcb0e5b192b6`
- `rmmod` rc 0, `insmod` rc 0
- after: version `6fa243a`, srcversion `3D83D6E0B587342305BE5C0`, refcnt 0
- dmesg: `[drm] Initialized ane 1.0.0 for 26bc04000.ane on minor 0`
- `runtime_status=active`, `/dev/accel/accel0` `root:render` 666

Netconsole on this host does not deliver (wld0 `192.168.3.66/23`, receiver
`192.168.10.235` off-link). Capture is on-host dmesg. No reset.

## Smoke on 6fa243a (jwm1, one iteration each, 5000 ms deadline)

Script `/var/tmp/DriverLifecycleRebase-20260914/run-jwm1.sh`.
libane `ffe037f3ae9bc1e11fc248608507962a6d4868ff6e64a636050b7c32363d1a9f`.
Worker `762dd1de868b52e4d6ffa30e18d842d9341db463b06aef2355f18fb1eb248929`.

| Program | exit | wall_ms | bytes |
|---|---|---|---|
| control-64el schema4-add-mul | 0 | 7 | worker reported exact; saved vs fixture differs at signed-zero lanes only (same baseline as prior 64-el receipts) |
| reexport-1x512 | 0 | 6 | identical `ad367dfea76ff961d1ffa60c4bf5225965c5ce8df5a39ea43701042af6eeb31a` |
| reexport-1x896 | 0 | 6 | identical `4767878ff0264fa99b5e68066df3c35dda3b8790b44987338a3fbb8f8eb2c5d4` |

Post: workers 0, lock reacquire PASS, quarantine 0 bytes, errno110 this boot 0,
boot_id unchanged.

## Not done here

- `jwm1-ane.service` still points at `omarchy-ane-h13-f261a6c`. A reboot
  would load that older ko until the unit is retargeted.
- mlx-omarchy `bundle.cpp` vacuous channel check is still open.

resolved_model: this session (`xai-oauth/grok-4.6`).
