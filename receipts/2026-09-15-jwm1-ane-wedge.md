# jwm1 ANE wedge and reboot (2026-09-15)

Host `jwm1-linux` (T8103), driver `6fa243a`, boot `95872130`.

## Event

`dmesg` 21:44:36 local:

```
ane 26bc04000.ane: tm completion failed: -110, finish lines=0; preserving resources until reboot
ane 26bc04000.ane: wedged: refusing bo free   (x4)
ane 26bc04000.ane: wedged: preserving bo mapping   (x4)
```

22:01:17: `wedged: refusing bo init` (x3) when IslandReexport2 tried island
submits.

## Attribution

`TdtGpuStep2` E2E stage wrote `/var/tmp/TdtGpuStep2/e2e-after/encoder_hidden.npy`
at 21:44:31. Its report: 72 island submits, 0 timeouts, exec 5054 ms,
worker `762dd1de`, status match. The wedge is 5 s after its last write, on
teardown. No other lane submitted between 21:40 and 21:46 (LandHostLeaves,
EncoderCoopmatShader, TdtGpuLoop, IslandReexport2 all confirmed).

IslandReexport2 executed `ane-add-fp16-1x512` at ~21:38 on a healthy device
(pre-wedge); its "lanes 16-511 unwritten" observation is unproven until a
clean re-run.

## Recovery

- `rmmod ane` refused: `Module ane is in use`, refcnt 1 with zero
  `/dev/accel/accel0` fd holders and zero worker processes. The driver pins
  its own reference on wedge.
- `/sys/bus/platform/drivers/ane/unbind` does not exist (bind attrs
  suppressed).
- Rebooted 22:12:46 (`systemctl reboot`). Back 22:13:17, boot `700eaeea`.
  `jwm1-ane.service` loaded `6fa243a` from
  `~/src/omarchy-ane-lifecycle-rebase/ane/ane.ko`, refcnt 0.
- Smoke 22:15: control-64el exact, 1x512 identical, 1x896 identical,
  errno110 0, lock reacquire PASS.

## Driver gap (omarchy-ane)

After `tm completion failed: -110` the driver's only recovery is a reboot.
It holds a module ref, offers no unbind, and refuses `bo init` forever. A
dedicated inference box should not need a reboot to clear one timed-out
task. Wanted: a bounded TM reset path (engine reset + BO teardown) that
returns the device to a fresh state, or at minimum an unbind that drops
the pinned ref so `rmmod`/`insmod` works.

## Trigger (mlx-omarchy)

The wedge followed a 72-submit E2E teardown on a worker that had been
running for ~5 s. The batched island path (`d8c9afce`, 1 submit) has not
wedged. Until the driver can recover, prefer the batched path and keep the
per-submit deadline.
