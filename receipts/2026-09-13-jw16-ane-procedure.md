# jw16 M1 Max ANE procedure (2026-09-13)

Host: `jw16mbp1-linux` (J316c / T6001). Kernel: `7.1.6-1-1-ARCH`.
llama-server and recovery timer: inactive. No reboot. No `insmod`.

## What was done

1. `omarchy-ane` `feature/t6001-ane-bind` `3946f76f82f1040c9f20b84692159ceb6aee31b9`
   - `ane_force_power()` accepts `apple,t6000-pmgr`.
   - T6000 `ane_sys` / `ane_sys_cpu` offsets `0x268` / `0x2c8`, selected by **label** so east PMGR `uart6`/`dpa4` at the same offsets is not used.
   - T8103 offsets `0x470` / `0xc000` unchanged.
2. `omarchy-linux` `feature/t6001-ane-bind` `595840935e8001fad4d0ebf1ce6102a445dfe91a`
   - Disabled overlay `arch/arm64/boot/dts/apple/t6001-j316c-ane.dtso` only.
   - Sourced fields: `compatible = "apple,t6000-ane"`; `engine` `0x284000000+0x02000000`; AIC die 0 IRQs `770`/`771` (`0x302`/`0x303`) `IRQ_TYPE_LEVEL_HIGH`.
   - `status = "disabled"`.
3. Module built on the live jw16 headers. `ane.ko` SHA-256 `624c69d718edd116b644d462245f88d5adc529fc821868f314107130539a5b88`. vermagic `7.1.6-1-1-ARCH`. Not inserted.
4. Overlay compiles and merges against a **symbolized source** DTB. Live FDT has no `/__symbols__`. `/sys/kernel/config/device-tree/overlays` is absent. Overlay was **not** applied.

## How a later bind must proceed (do not skip)

Forbidden: GRUB `devicetree` whole-tree replace (boots 1 core). Forbidden: `insmod` before every driver consumer is present.

Still unsourced (do not invent):

- `iommus`: Linux DART provider + stream ID. ADT `sids = 0xa001` is not a Linux SID cell.
- `reg-names` for DART windows `0x285800000`, `0x285810000`, `0x285820000`, `0x285804000` → `dart0`/`dart1`/`dart2`/provider.
- `power-domains`: ordered list including the missing Linux `ANE-SYS-V` leaf. Do not substitute `ps_ane_sys` / `ps_ane_sys_cpu`.

When those three exist:

1. Keep the node `status = "disabled"` in the packaged DTB.
2. Enable only in `t6001-j316c.dts`.
3. Deliver via `update-m1n1` from packaged DTBs, then reboot once.
4. Insert the kernel-matched `ane.ko` only after `26xxxxxx.ane` exists.
5. Require `/dev/accel/accel0` before any smoke.

## Final host state

ANE FDT node absent. Module not loaded. `/dev/accel/accel0` absent. llama inactive.
