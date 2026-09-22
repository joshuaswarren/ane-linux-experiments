# m1-host (m1-host) USB bring-up — live log, 2026-09-22 (M2ProxyLive)

## Symptom at start
- `/sys/bus/usb/devices` completely empty (not even root hubs) on m1-host despite
  dwc3_apple/dwc3/xhci modules loaded.
- Type-C port0 (controller 382280000.usb) had a PD partner attached.

## Root cause chain
1. Boot settles the port in UFP (device) data role; the asahi cd321x (tps6598x)
   driver exposes no data-role-set, so sysfs role swaps return EPERM
   (`echo host > /sys/class/typec/portN/data_role` → Operation not permitted).
2. On the first link, PD auto-negotiated host and xhci enumerated usb1/usb2
   (dwc3-apple rebind confirmed harmless). Subsequent replugs re-rolled the PD
   data role; some links settle UFP → no USB bus at all.
3. Chip-level `SWDF` (swap-to-DFP) 4CC was issued directly to the PD controller
   (i2c bus 0 addr 0x38, CMD1 0x08, byte-wise — pasemi adapter lacks block
   write). Command register accepted the write (non-!CMD response 0x00004004)
   but the data role did not flip.

## Fixes applied on m1-host
- Tooling replicated from the 16-inch replica host: `/var/tmp/m2proxy` (scripts, selene fixture,
  watch.sh, watch.service), `/var/tmp/m2proxy-venv`, proxyclient copied to
  `~/src/m1n1/proxyclient` (same absolute path the scripts symlink expects).
- Verification on m1-host: `t6021_consts.py` → VALIDATION PASS; `ane_bringup.py
  --mock --fw selene/...macho` → SCRATCH7-READY 0x8042006 MATCH, MOCK DONE.
- udev `/etc/udev/rules.d/99-m1n1-proxy.rules` (tty 1209:316d MODE 0666).
- systemd `m1n1-proxy-watcher` enabled+active; permission fix: chown -R
  joshuawarren /var/tmp/m2proxy (sudo copies had made it root-owned, unit
  could not mkdir receipts/state).
- Post-run hook per Main's override: live watch.sh line
  `"$M2ROOT/omarchy-now.sh" --chainload --image /boot/efi/m1n1/boot.bin`
  (sha256 0891ae996903903f41a76d3fab847dad2aa1b6a817d0901136fa1203bba92826;
  ReturnPath repo snapshot aa95932).
- ane.ko loaded (lsmod).

## Waiting on
Physical replug (cable flipped end-for-end) to re-roll PD orientation so m1-host
settles host; m1n1's gadget then enumerates as /dev/ttyACM* and the watcher
fires the checklist automatically.

## Status
- ttyACM: NOT YET (polling every 5 s).

## Addendum 08:15 — root cause + state as of park end

- Root cause found in asahi dwc3-apple glue (drivers/usb/dwc3/dwc3-apple.c):
  dwc3 core probe is deferred to the first cable-connect event; forced role
  writes probe it out of order → soft reset -110 → permanent EBUSY until
  reboot. Deterministic host setup documented in RUNBOOK addendum
  (charger + data port split, replug after boot, never write data_role).
- Partner usb_mode=usb3 observed on port0 while [host] — m1n1's gadget
  signals at PD level, but dwc3 never initialized this boot (0 root hubs),
  so no ttyACM ever appeared; the checklist has not yet run on real HW.
- Deployed on m1-host: /usr/local/bin/m2proxy-linkcheck (one-line link state).
- m1n1-usb-host.service (role-write oneshot) was installed then DISABLED —
  its writes are what wedged the driver; keep it disabled.
- Park ended: m2-host booted to macOS by operator for boot-image restore.
  Re-park procedure (5-min redo) written into RUNBOOK addendum.
- Post-run hook live on m1-host watch.sh:
  omarchy-now.sh --chainload --image /boot/efi/m1n1/boot.bin
  (sha 0891ae996903903f41a76d3fab847dad2aa1b6a817d0901136fa1203bba92826).

## Addendum 08:35 — USB4 link discovery

Fresh-boot linkcheck showed port0-partner usb_mode=usb4: with a Thunderbolt
cable the two Macs enter USB4 alt-mode, and m1n1's USB2 gadget can never
enumerate (dwc3 gets no USB2/3 role — the deeper reason the wedged boots
never came up). Software refusal is unavailable on this kernel: altmode
`active` writes to port0.0/port0.1 are rejected, usb_mode is read-only.
FIX: physical USB 2.0-only cable (Apple charge cable). Everything else on
the m1-host side is deployed and deterministic (charger split, replug-after-boot
connect event, watcher + chainload hook armed, linkcheck one-liner).

## Addendum 08:45 — taint fix + ane.ko identity

- m2proxy-linkcheck rewritten to avoid reading typec partner usb_mode (the
  attr whose usb_mode_show WARNs/taints the kernel every poll). New version
  reads data_role + partner-dir presence + tty nodes only; deployed at
  m1-host:~/bin/m2proxy-linkcheck (also in repo scripts/m2-proxyclient/).
- ane.ko boot-persistent module identity: updates/ane.ko sha
  82411a46bbeca04f (version 6fa243a-dirty) == /var/tmp/ane-6fa-src/ane/ane.ko.
  The verified cached-BO 104-pin build 4ebcfc10 was NOT found in the common
  /var/tmp candidates (restore 14ff769f, guard b47b6480, guard-v2 99e8b8b5).
  Not swapped: replacing the boot module with an unverified .ko would defeat
  the fix; awaiting the verified artifact from its owner.

## Correction 08:55 — ane.ko identity resolved (AneInProcessSubmit, verified)

updates/ane.ko 82411a46bbeca04f IS the correct cached-BO 104-pin build
(param-bearing; writecombine=N present; bit-reproducible from
/var/tmp/ane-6fa-src). The 4ebcfc10 sha I was hunting was the superseded
pre-param build. No swap required; boot autoloads the verified build.
