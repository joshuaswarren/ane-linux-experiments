# jw16 T6001 ANE current procedure (2026-09-13)

Supersedes the bind-only note in `receipts/2026-09-13-jw16-ane-procedure.md`.

## Live state

- Host: `jw16mbp1-linux` (J316c / T6001), kernel `7.1.6-1-1-ARCH`.
- `/dev/accel/accel0` bound `285c04000.ane`, DRM 1.0.0.
- SET0 `0x28e08c000` ACTUAL=`0xf` while the device is runtime-active. Idle suspend gates it (`ACTUAL=0`); `open(/dev/accel/accel0)` restores `0xf` via genpd (`receipts/2026-09-13-jw16-set0-after-resume.json`). Do not write `0xf`.
- 64-el schema-4 add-mul: exact fp16, y `bade941d…`, 100/100 soak.
- 1x896 remains forbidden.

## Pins

| item | value |
| --- | --- |
| omarchy-ane | `feature/t6001-ane-bind` `eb7dfe7` (SET overlay) on `0ab3758` (DRM 1.0.0) |
| overlay | `ane/t6001-j316c-set-domains.dts` |
| omarchy-linux | `feature/t6001-ane-bind` `9247b41f4` (j316c enables ANE+SET1..4) |
| worker | `575e2acd…` graph `5584d0fd…` libane `1ab9d95d…` |

## After reboot

The live FDT overlay is not a packaged `update-m1n1` DTB. Expect SET0 gated (`ACTUAL=0`) and TM `-110` until the overlay (or a packaged board DTB) is applied again.

1. Fabric quiet. Netconsole on. Do not write SET `0xf`.
2. Apply `ane/t6001-j316c-set-domains.dts` the same way as `receipts/2026-09-13-t6001-set-domains.md`.
3. `readl` SET0: want `0x000003ff` (ACTUAL=`0xf`). Abort → stop. Do not retry as write.
4. One 64-el add-mul only. Stop on `-110`. Never 1x896.

Product cutover is a packaged board DTB, not this overlay.

## Idle

`runtime_status=suspended` is normal at refcnt 0. That is not a lost bind.
The next worker open resumes genpd and SET. Do not poke SET registers.

## Forbidden

Userspace `0xf` to SET, range-1 as TM, GRUB whole-tree DTB, 1x896, looping `-110`.
