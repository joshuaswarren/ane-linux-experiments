# TM -110 bounded recovery (2026-09-15)

Hosts: jwm1-linux (T8103, `ane@26bc04000`), jw16mbp1-linux (T6001,
`ane@285c04000`). Branch `fix/tm-recovery` on `joshuaswarren/omarchy-ane`;
tip `dcc3e5b`. Builds verified clean (0 errors) on both hosts.

## Shipped state

- **jwm1: PASS.** `b52064c` loaded and healthy; provoke → recovery → exact
  smoke proven on-device, no reboot.
- **jw16: NOT PROVEN.** `dcc3e5b` recovery clears the wedge and the task's
  completion events fire (`finish lines=3`), but the TM_STATUS idle bit
  never asserts post-reset, so every submit still returns -110 on T6001.
  jw16 restored to known-good `6fa243a` (healthy, refcnt 0). `main` NOT
  pushed (both-hosts bar not met).

## The fix (as merged on the branch)

On a tm completion timeout (`-110`), `ane_tm_recover()` (ane_tm.c):

1. `ane_pd_cycle()`: force suspend/resume each attached genpd partition
   device (`ane->pd_dev[i]`, 5 on T8103; single-domain path cycles the
   device itself). Each force pair pins a second usage ref first — without
   it `force_suspend` marks `needs_force_resume` only when a ref beyond the
   probe ref is held and `force_resume` would leave the partition gated
   (pm_runtime_need_not_resume: usage_count <= 1). T8103 topology check:
   5 power-domain phandles in `ane@26bc04000/power-domains`; genpd links
   `genpd:0..4:26bc04000.ane`.
2. `ane_tm_enable()` re-arms the tm (power-on reset cleared the register
   file; nothing else calls runtime_resume on the multi-pd path).
3. Success = every force pair completed. The post-cycle TM_STATUS is logged
   but cannot arbitrate: T6001 reads 0x0 at hardware reset where probe
   found firmware-left state (this was `b52064c`'s failure on jw16, fixed
   by `dcc3e5b`). The next submit is the functional oracle; a still-dead
   engine wedges again and the preserve path re-engages.
4. Wedge clears, module pin (`__module_get`) dropped. Preserve-until-reboot
   applies only when a force pair errors.

Operators: `/sys/bus/platform/devices/{26bc,285c}04000.ane/wedged` (RO) and
`.../reset` (WO, retries recovery). `.suppress_bind_attrs` unchanged.

## Provoke recipe (deterministic, offline-gated)

The 09-14 wedge was an over-declared td_size; the current control fixtures
are the parity class (td_size = tsk_size = 0x1f8), so the provoke corrupts
the task stream instead: overwrite the final record header (stream offset
0x1d8, the 7-word dst-DMA block) with 0xDEADBEEF — the exact record the
shipped 1x896 over-fetch walked into ("write 56/59 words at register byte
address 0x2adbeef", ~1400x out of range; receipts/2026-09-14-1x896-diff.md).
Engine never reaches a well-formed end of task → TM never idle → -110.
td_size stays truthful; no bundle gate inspects the stream. Stager
(`atr-stage-provoke.py`, on both hosts at
`/var/tmp/AneTmRecovery-20260915/`) asserts: clean walk terminates exactly
at 0x1f8; corrupted walk non-exact and contains the 0x2adbeef record;
manifest `payloads[].sha256` + `release_asset.model_sha256` re-stamped
(nlohmann dump(-1,' ',true) collection hash, validated against the
declared value before patching).

## jwm1 evidence (T8103, PASS)

Window 2026-09-15T23:07:34-05:00, boot `42761e4f` (post-reboot to clear the
earlier 04542dc wedge — see history). Module `b52064c`
(srcversion DA41FFBB975CAD92312161D). Worker elapsed 1004 ms (1 s completion
poll + 0.2 ms recovery):

```
[   31.990934] ATR-RECOVERY PROVOKE BEGIN
[   33.011961] ane 26bc04000.ane: tm completion failed: -110, finish lines=0
[   33.011998] ane 26bc04000.ane: recovering: power-cycling engine partitions
[   33.012215] ane 26bc04000.ane: tm recovered: idle, accepting work again
[   33.031388] ATR-RECOVERY PROVOKE END status=1
[   34.053664] ATR-RECOVERY SMOKE BEGIN
[   34.085607] ATR-RECOVERY SMOKE END status=0
```

`wedged` 0 and `refcnt` 0 immediately after the provoke (pin dropped);
healthy 64-el control (`/var/tmp/AneWorkerValidation-c05ba1df/.../bundle`,
a/b/y schema4-add-mul): worker `status=0 iterations=1`, **"verified output
y exact"**; `flock_reacquire=PASS`; no reboot (boot_id unchanged). Note:
`cmp` of the saved output vs the y fixture differs (signed-zero lanes),
same as the 2026-09-14 lifecycle receipt baseline; the worker's internal
expect-compare is the exactness oracle.

## jw16 evidence (T6001, gap documented)

Provoke reproduces identically (`tm completion failed: -110, finish
lines=0` at 175807.417, boot `f6ad865b`). Three data points:

1. `04542dc` (force pair on the consumer): gated NOTHING — the ANE node has
   no pm_domain of its own (5 attached genpd devices); the consumer's force
   pair resolved to bus-generic callbacks and just re-ran tm_enable on the
   still-stuck engine. Lesson that produced `ane_pd_cycle`.
2. `b52064c` (pd cycle + idle-or-fresh gate): partitions genuinely cycled
   (post-recovery `pm_genpd_summary`: ane_set1..4 on/active), but
   `tm not idle after reset: 0x0` → preserve path → wedged → required the
   one reboot Main authorized to clear. Root cause: T6001 hardware reset
   value 0x0 matches neither idle-bit nor the probe-time firmware state.
3. `dcc3e5b` (cycle-proof oracle): provoke → `tm recovered: partitions
   cycled, status 0x0; accepting work again`, wedged=0, pin dropped.
   Healthy smoke submit: completion EVENTS fire (`finish lines=3`) — the
   task runs — but the completion predicate
   (`*finished == 3 && (TM_STATUS & TM_IS_IDLE)`, ane_tm.c collect_events)
   never sees the idle bit post-reset → every submit -110s, auto-recovery
   clears it each time. T6001 needs a post-reset TM re-init beyond
   tm_enable (or a completion-predicate decision) before this driver can
   serve T6001. jw16 restored to `6fa243a` (healthy, refcnt 0) at 23:26.

## Operations history (both reboots were authorized)

- jwm1 reboot 23:06:44 (`42761e4f`): cleared the 04542dc preserve-path
  wedge (module self-pins; rmmod refused by design). Went in before Main's
  stop-directive landed; all later actions complied.
- jw16 reboot 23:16:38 (`2c721ec2`): explicit Main "GO" after the b52064c
  wedge. /tmp on jw16 held only lock files + my scripts.

## Build recipes

- jwm1: `KERNELDIR=$HOME/.local/apple-hardware-sdk/usr/lib/modules/7.1.6-1-1-ARCH/build`,
  `LD_LIBRARY_PATH=$HOME/.local/apple-hardware-sdk/usr/lib` (pahole/BTF),
  `make -C $KERNELDIR M=$PWD modules` in `ane/`.
- jw16: `KERNELDIR=/lib/modules/7.1.6-1-1-ARCH/build`, plain make (pahole in
  /usr/bin). Both produce `modinfo -F version` = git describe of the tip.
- jwm1-ane.service loads `~/src/omarchy-ane-lifecycle-rebase/ane/ane.ko`
  at boot — still the 6fa243a build. Retarget that checkout to the branch
  tip when the branch lands on main. jw16 has no service; module is manual.

## Locks used

- jwm1: `/tmp/m1-gpu.lock` then `/run/lock/mlx-omarchy-ane/device.lock`,
  flock, no steal (TdtGpuLoop hold waited out; EncoderCoopmatAccept
  windows honored).
- jw16: `/tmp/m1-gpu.lock` is held permanently by the llama-server router
  service (flock --nonblock exec, PID from boot) — NOT an ANE coordination
  point on this host; lanes use `/tmp/jw16-ane-device.lock` (new; /run/lock
  is root-owned).

## Not done

- main not pushed; branch `fix/tm-recovery` (dcc3e5b) is the deliverable.
- T6001 post-reset TM idle-bit gap: next step is a T6001 probe-time
  TM_STATUS dump comparison (firmware state vs post-cycle 0x0) and a look
  at whether the firmware handshake's tm init (TM_TQ_EN 0x1000 path or an
  ack sequence) restores the idle bit; alternatively relax the completion
  predicate to accept finished==3 with a bounded settle when the device
  was reset since boot.
