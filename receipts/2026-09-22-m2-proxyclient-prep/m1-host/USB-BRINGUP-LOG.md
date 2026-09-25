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
  owner /var/tmp/m2proxy (sudo copies had made it root-owned, unit
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

## M2ProxyRun session, 09:00 — PD role root cause + SWUF image (M2SwufInstallRun takes over)

- Cable attempts 08:26–08:48 (TB, charge-only, A-to-C behind VIA 2109:0817 hub —
  hub + Realtek LAN enumerated fine): ZERO signalling from the M2 in every case,
  not even descriptor errors. On every attach the M2 (m1n1) wins PD source and
  m1-host settles UFP/device; preferred_role=source ignored by the CD3218.
  phy-apple-atc logs "USB4 not implemented; falling back to USB2" — USB4 was
  NOT the blocker. Charge cable w/ phone test + M2 power-cycle with cable
  attached also produced nothing.
- Source findings (m1n1 v1.6.1 + checkout .work/m1n1): stock m1n1 never sends a
  data-role swap 4CC (tps6598x.c = SSPS + IRQ mask only), CD3218 stays in Apple
  boot policy (prefers source). No stage-2 USB skip in 1.6.1 (main.c:128-139
  unconditionally usb_init+usb_iodev_init before uartproxy), no SoC gating
  anywhere in the USB path (usb.c:36-39 paths; idx 0..7, silent continue;
  phy/i2c bring-up failures print only to an invisible console).
- Fix built: "SWUF" (swap-to-UFP) issued on every hpm after IRQ masking in
  usb_init_i2c (usb.c), one 500 ms-delayed retry. Image staged on m1-host:
  /var/tmp/m2proxy-staging/boot.bin.proxy-swuf
  sha256 6dc0ec5d20f6069ddebab7e06a79e2ea3430c58c364321afbf840aff7274ebb4
  (build tag 4184923-dirty; no chainload config → parks at proxy like 9ad08653).
- m2-host side now suspect for zero signalling; M2SwufInstallRun owns the macOS
  ESP install of proxy-swuf + the run. My watchers left on m1-host:
  m2proxyrun-poll.sh (30 s linkcheck + cdc_acm fallback, running);
  3 s hub-port watcher stopped at 09:00.

## M2ProxyRun session, 09:10 — macOS-NCM proof + SWUF-park result

- 09:05: m2-host (in macOS during ESP install) enumerated on m1-host usb 1-1
  high-speed as 05ac:1905 "Mac" (Apple NCM, serial WR1CQCYQ67), cdc_ncm bound,
  usb0 registered (t=2008/2061s; disconnect t=2322s = reboot). PROOF: cable,
  hub/port, xHCI, high-speed signalling and descriptor exchange all work
  end-to-end on this link.
- After m2-host rebooted parked on boot.bin.proxy-swuf (6dc0ec5d): 10+ min
  watching, NO device from the M2 (no 1209:316d, no 05ac). m1n1's CDC-ACM
  gadget is dead on this T6021 — consistent with a silent usb_phy_bringup /
  dwc3 gadget failure (all failure paths are silent 'continue' in m1n1).
  m1n1-side diff vs v1.6.1: usb.c identical except named PHY defines + SWUF
  patch; usb_dwc3.c identical.
- m2-host unreachable over ssh (parked). m1-host rebooted to macOS at 09:08
  (FleetMacOSUnattendedAccess, Main GO) — macOS is now the proxy host;
  M2ProxyMacosHost owns the run from there and will log which device
  (05ac:1905 vs 1209:316d) enumerates — the decisive differential.
- On next m1-host Linux boot: m1n1-proxy-watcher (enabled) + poll logs at
  /var/tmp/m2proxy/state/{m2proxyrun-poll,m2proxyrun-3s}.log come back.
