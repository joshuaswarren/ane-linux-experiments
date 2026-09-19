# H14/T6021 W3-driver eight-domain fix — MODULE LOADS AND STAYS LOADED on jw14m2; the W3 kill is dead; mailbox transport falsified and deferred (2026-09-19)

Verdict: **DRIVER WORKING on the proven surface.** `ane_t6021.ko` (omarchy-ane
`feat/t6021-ane-driver-w4`, four commits e20da17→HEAD, pushed) loads on
jw14m2-linux with `allow_unqualified=1`, verifies all EIGHT ANE pmgr islands
(ACTUAL=0xf, BUSY clear, ane_cpu AUTO_ENABLE clear), passes the power gate, and
reads the full phase1-proven ASC status whitelist in-kernel: **RVBAR=0x00000001
(selene released by iBoot), VERS=0x000e3044, RTB status=0x00000001 — the exact
value the K14 kext poll-loops for — RTB+7c=0x30, GPIO0-7=0, EDPRCR=0**. That is
the phase1 "coprocessor ALIVE" evidence set, now produced by the driver.
load → rmmod → reload all exit 0; no SError, no panic, box alive. The RTKit
MGMT HELLO exchange is deliberately deferred (see §4): the assumed mailbox at
ANE+0x1608xxx is a falsified inference, not a tuning gap.

## 1. What landed (all pushed on `feat/t6021-ane-driver-w4`)

| commit | change |
| --- | --- |
| e20da17 | Driver consumes all EIGHT islands; gate added; stage-2 reads restricted to the phase1 whitelist (CPU_CONTROL/+0x1608xxx dropped); overlay list re-ordered to the proven raise order (sys_mpm→td→base→set1..4, ane_cpu last) |
| f7a470d | ps words VERIFY-ONLY in the driver (see §3 freeze); `h14_bringup.py --stage 1` named in the gate error |
| transport gate | `rtkit_transport=1` opt-in; default load = status-only bring-up, IRQ request + drain skipped |
| overlay doc | installed-tree `apple,always-on` delta documented in `ane/t6021-j414c-ane.dts` |

DTB install (decompile-edit-recompile of the booted tree, sha-verified at each
step; fdtoverlay not used): `4eec6e23` (W3) → `f301ded6` (8-domain list,
one-line diff) → `20ec1fb0` (+ `apple,always-on` on the eight chain nodes,
8-line diff). Backups: `/var/tmp/t6021-j414c.dtb.pre-w4-20260919`,
`.pre-w5-20260919`. `update-m1n1` rebuilt `boot.bin` both times.

## 2. The W3 kill is fixed — the eight-domain chain was the delta

Boot-proven FDT now carries `power-domains = <0x1f5 0xb5 0xb6 0xb7 0xb8 0xb9
0x1f1 0x1f0>` (eight, phase1 order) and boot logs EIGHT `sync_state() pending
due to 284000000.ane` lines (W3 showed six). `ane_td@4008` and `ane_base@4010`
raise with the chain (phandles 0xb5/0xb6 were already in the stock DTB — the
set1..4 parent cascade — so no new fragments were needed).

## 3. New kill datum: kernel-context ps-word writes freeze t6021; ADT gate/clock thread closed

- **09:39 freeze**: the driver's flag-clear RMW (`0x3ff`) to `pmgr+0x2e0` —
  byte-identical to phase1's twice-proven userspace RMW — stalled `insmod`
  before its next dev_info; watchdog reset at +62 s. The identical write from
  `/dev/mem` is clean. Driver consequence: ps words are verify-only; the
  AUTO_ENABLE clear belongs to the userspace tool.
- **09:50 freeze (SExternal-Abort on CPU1, PID insmod)**: with the FULL raise +
  auto-clear verified in-kernel and the entire whitelist read clean, the first
  read of `ANE+0x1608114` (the m1n1-ASC-analogy mailbox) SError'd the machine;
  console died mid-SError-decode, watchdog reset ~72 s later. Same block family
  hung the phase1 zero-write probe (09-18, reduced state).
- **ADT gate 473 / clock-ids closed with data** (m1n1 struct-exact parse of the
  j414c ADT): ANE-SYS-V (id2 473) is `PMGR_FLAG_VIRTUAL` with NO parents and NO
  ps word — m1n1's `pmgr_adt_power_enable` writes nothing for it; ane0's
  clock-ids [318-321] decode to **VENC_PIPE4/5, VENC_ME0/1** (an Apple ADT
  artifact — video-encoder clocks on the ANE node). Nothing in the ADT remains
  that the m1n1 oracle would enable and Linux does not.
- The +0x1608xxx mailbox was only ever m1n1-t8103-layout analogy: the K14 kext
  never reads that block at runtime, t6001 (H13: TM/TQ, no RTKit mailbox) and
  t8103 (m1n1: TM/TQ) have no precedent there. Falsified; the transport lane
  must pin the real register source from the kext (doorbell write site,
  `rtbuddyEndpointSendMessage` callers) before any further touch.

## 4. Operational shape now (jw14m2-linux, kernel 7.1.13-3-1-ARCH)

1. Boot: the eight chain nodes carry `apple,always-on`, so apple-pmgr-pwrstate
   raises the seven boot-gated islands at probe (proven transition class; words
   read `0x3ff`, bit 28 hw-consumed) and genpd can NEVER power them down —
   genpd idle/unload writes are the freeze class.
2. Before insmod: `sudo python3 /var/tmp/h14_bringup.py --stage 1` (userspace
   RMW) clears AUTO_ENABLE on the never-transitioned ane_cpu (`0x1f0003ff` →
   `0x0f0001ff`; post-write readback shape). The driver gate refuses with this
   instruction if it is skipped.
3. `sudo insmod /var/tmp/ane-t6021-w4/ane_t6021.ko allow_unqualified=1` —
   load, verify, whitelist read, banner "status-only bring-up, transport
   deferred". rmmod/reload cycle verified clean (always-on ⇒ no genpd writes on
   unload). Stability: loaded module up across a 16-min boot and the final
   boot's full cycle + watch window, dmesg SError/panic count 0.
4. The HELLO exchange needs `rtkit_transport=1` AND a real transport address —
   do NOT enable it against +0x1608xxx (SExternal-Abort, proven twice).
5. Module version prints "unknown" on-box (staging dir has no .git) — cosmetic.

## 5. Artifacts

- omarchy-ane `feat/t6021-ane-driver-w4` @ HEAD (e20da17, f7a470d, transport
  gate, overlay doc), pushed. Module sha256 `9f4db5bd…` (verify-only build).
- DTBs: `/tmp/t6021-j414c-w4.dtb` `f301ded6…`, `/tmp/t6021-j414c-w5.dtb`
  `20ec1fb0…`; installed sha re-verified on-box; backups above.
- Netconsole capture: omp-studio-local `/var/log/fleet-netconsole.log`
  (sender 192.168.3.103:6668) — 09:39 freeze seam (stall at the pmgr RMW, no
  SError, watchdog +62 s), 09:50 SError seam (whitelist clean → SError on
  CPU1), and the final clean load/unload/reload trail.
- ADT parse: m1n1 `adt.py` + `liblzfse` on the mined `DeviceTree.j414cap.im4p`
  (venv /tmp/venv-m1n1); gate-473/clock-318-321 chain dumps in the transcript.
- Open-source exemption: no screenshots; pushed branch + this receipt + the
  netconsole log are the artifacts. jwm1, jw16 untouched.

## 6. Next lane

Static: disasm the kext's host→fw doorbell write site (`rtbuddyEndpointSendMessage`
tail / `SetupEndpoints` encoder) to pin the real doorbell register — the only
remaining unknown in the transport. Then `rtkit_transport=1` with the pinned
address, MGMT HELLO, and W4 submission stands as already staged.
