# RUN-RECEIPT — T6021 ANE bring-up over m1n1 USB proxy (2026-09-22, M2ProxyRun)

m1-host = m1-host (proxy host, Linux/Asahi), m2-host = m2-host (parked at m1n1 proxy, boot.bin.proxy-only 9ad08653).

## Pre-run link state (08:26–08:30 CDT)
- `m2proxy-linkcheck` on m1-host: `roles: port0:host [device] port1:host [device] partners: port0=attached port1=attached roothubs:0 ttyACM:none`
- Link settled UFP (device role active) on both ports; dwc3 never probed this boot (0 root hubs); no 1209:316d in dmesg.
- `usb_mode` not readable without kernel WARN/taint (usb_mode_show oops) — usb2/usb3 vs usb4 cannot be confirmed from software.
- Blocked on physical replug (deterministic trigger, RUNBOOK addendum 08:15; software role writes forbidden — they wedge dwc3-apple permanently until reboot).
- Requested replug from Main at 08:27 CDT.

## Deployment during wait
- m1-host:/var/tmp/m2proxy/m2proxyrun-poll.sh — 30 s linkcheck poll + cdc_acm fallback (modprobe when root hubs exist but no ttyACM); log: /var/tmp/m2proxy/state/m2proxyrun-poll.log. Launched 08:27:12, running.
- m1n1-proxy-watcher systemd unit: active since 08:18:59 (auto-fires checklist + chainload hook when ttyACM appears).

## Link evidence (08:26–08:40 CDT)
- 08:34:13 port1 (charger side) flipped host; its xHCI probed (usb1/usb2 root hubs); zero downstream devices (no 1209:316d). cdc_acm fallback modprobe fired, no ttyACM.
- 08:40:00 root hubs gone again (charger removed); port0 (data link, m2-host) stayed UFP/device the whole time.
- Main's conclusion: on every attach m1n1 wins PD source; m1-host settles sink/device. phy-apple-atc logs "USB4 not implemented; falling back to USB2" — USB4 was NOT the blocker.

## Root cause (m1n1 source, .work/m1n1)
- Stock m1n1 never sends a data-role swap 4CC. tps6598x.c only does SSPS powerup + IRQ mask/restore; CD3218 stays in Apple boot policy (prefers source) → M2 is always DFP/source, host Mac settles UFP → gadget never enumerates.
- No ADT knob; only build knob is USE_DEBUG_USB (KIS debug-usb path, unrelated to role).
- Fix: issue "SWUF" (swap to UFP) on every hpm after IRQ masking in usb_init_i2c (usb.c), with one 500 ms-delayed retry.

## Patched image (built 08:43 CDT)
- Source: .work/m1n1 (build tag "4184923-dirty") + SWUF patch (usb.c usb_init_i2c). Built with aarch64-linux-gnu-gcc; rust target aarch64-unknown-none-softfloat added.
- m1-host:/var/tmp/m2proxy-staging/boot.bin.proxy-swuf — sha256 6dc0ec5d20f6069ddebab7e06a79e2ea3430c58c364321afbf840aff7274ebb4
- Proxy path unchanged (no chainload config → parks at proxy, same as 9ad08653 proxy-only). Note: original was asahi-boot m1n1 1.6.1; this is the checkout build, so shas differ by construction.

## Install paths for boot.bin.proxy-swuf on m2-host ESP
- (A) Once any proxy link exists: proxyclient ESP write from the proxy session (before chainload), then reboot into the patched image for a deterministic-UFP park.
- (B) M2UnparkViaMacos: boot m2-host macOS, mount ESP, sudo cp staging/boot.bin.proxy-swuf /boot/efi/m1n1/boot.bin, verify sha, reboot (parks at proxy again, now with SWUF).

## Run log (readbacks)
(pending — blocked on a fixed-role data link; Joshua sourcing USB-C hub with USB-A + A-to-C cable)

## Outcome
(pending)

## ESP restore
(pending — boot.bin.pre-proxy 153170e0…ad1ff5 restore per RUNBOOK step 6 after the run)

---

# INSTALL + RUN OUTCOME — M2SwufInstallRun (2026-09-22 08:47–09:10 CDT, macOS route)

m1-host = m1-host, m2-host = m2-host. Install route = (B) macOS slice (no proxy link ever existed, so (A) was impossible).

## Step 1 — image transport (08:47–08:53)
- Source: m1-host:/var/tmp/m2proxy-staging/boot.bin.proxy-swuf, sha256 6dc0ec5d20f6069ddebab7e06a79e2ea3430c58c364321afbf840aff7274ebb4 — verified on m1-host, workstation (~/tmp/m2swuf/), and m2-host macOS (/tmp/) — all three identical.
- m2-host macOS pre-login SSH up 08:52 (m2-host-lan → M2-HOST.local, macOS 27.0, arm64).

## Step 2 — ESP swap on m2-host macOS (08:53)
- ESP identified: disk0s4 "EFI - OMARC", FAT32, 524.3 MB (NOT Apple's disk0s1 APFS_ISC). User mount refused; `sudo diskutil mount disk0s4` OK → /Volumes/EFI - OMARC.
- Prior state verified: m1n1/boot.bin sha256 9ad086536d4b4f871530ad5231bf8eea8063bbf5ff9189ae713584ed74158fdd (= proxy-only, as staged).
- Backup written: m1n1/boot.bin.proxy-only.bak (sha re-verified 9ad08653…, 1114112 B).
- Patched image written: m1n1/boot.bin (884736 B) + side copy m1n1/boot.bin.proxy-swuf; on-ESP sha256 re-verified 6dc0ec5d…4ebb4. boot.bin.old untouched.
- `diskutil eject disk0s4` failed ("Unmount of disk0 failed…" — whole-disk eject); partition itself unmounted cleanly (verified "disk0s4 was already unmounted").

## Step 3 — reboot into patched default (08:57:30)
- Announced to all 08:55 (~2 min ahead). `sudo /sbin/shutdown -r now` accepted 08:57:30 ("Shutdown NOW!").
- Post-reboot: m2-host times out on LAN 192.0.2.0 AND tailnet 203.0.113.1 → NOT macOS, NOT Omarchy ⇒ parked on proxy-swuf as designed.

## Step 4 — bring-up over the charge cable: NO ENUMERATION (08:57–09:10)
linkcheck readbacks on m1-host (verbatim, all identical):
```
08:59:40 roles: port0:host [device] port0-partner: port1:[host] device port1-partner: partners: port0=attached port1=attached roothubs:2 ttyACM:none
09:00:13 (same)
09:00:50 (same)
09:02:37 (same)
09:03:46 (same)
```
- m1-host dmesg: PD/CC partner attached the whole time (port0:host), but ZERO device-attach events after 08:57:52 (m1-host's own xhci bus re-register) — no 05ac:1905, no 1209:316d, no cdc_ncm, no ttyACM. m1n1-proxy-watcher: "No entries" (never fired).
- Key contrast (from M2ProxyRun's earlier capture): during the macOS window the SAME cable/port enumerated 05ac:1905 "Mac" (high-speed NCM) — cable + xHCI + signalling are proven good. After parking on proxy-swuf, the M2 produces no USB device whatsoever.
- Conclusion: the SWUF outcome is unobservable without console, but the m1n1-side gadget never came up — consistent with a silent m1n1 usb_phy_bringup / dwc3 gadget failure on T6021 (all failure paths are silent 'continue'), independent of the role swap. Checklist (ane_bringup.py) never ran; no RTKit handshake; no SCRATCH7 poll.

## Consequence + recovery state
- Chainload return (omarchy-now.sh --chainload) is IMPOSSIBLE: it needs the dead gadget. boot.bin IS the parked image ⇒ every m2-host boot re-parks.
- Only return path: physical boot picker (hold power) → choose macOS (NOT Omarchy). Then restore via macOS SSH:
  `sudo cp /var/tmp/m2proxy-staging/boot.bin.pre-proxy /Volumes/ESP/m1n1/boot.bin` → expect sha256 153170e065383767a47bc234e02344ecdc09d03f4003d92e6a2d6e464fad1ff5, reboot once.
- ESP state right now: boot.bin = proxy-swuf (6dc0ec5d), boot.bin.proxy-only.bak = 9ad08653, boot.bin.pre-proxy = 153170e0 on the Linux root (/var/tmp/m2proxy-staging/) — RESTORE PENDING, not yet executed.

## Outcome
INSTALL: COMPLETE and verified. RUN: FAILED — no proxy enumeration, checklist never fired, blocked on console-less m1n1 T6021 USB bring-up. m2-host parked; recovery requires hands (boot picker → macOS).

## Closure (09:4x CDT — macOS-host differential)
- m2-host rebooted to Omarchy Linux after the macOS experiment; m1-host watcher active, link partners attached, still zero M2 devices.
- macOS-host run result (M2ProxyMacosHost): NOTHING enumerated from parked m2-host there either — system_profiler/ioreg show zero USB devices, no /dev/cu.usbmodem. Bring-up never started (no transport; no RVBAR/READY readings).
- Differential CLOSED: cable + hub + both hosts' xHCI proven good (05ac:1905 macOS-NCM enumeration earlier). The fault is definitively inside the parked m1n1 image's USB gadget bring-up on this T6021 (silent usb_phy_bringup/dwc3 failure).
- m2-host ESP NOT yet restored: still parked on proxy-swuf (6dc0ec5d). No transport exists, so restore goes via the physical boot-picker lane (next lane: M2M1n1Hook per Main; return image boot.bin.pre-proxy 153170e0…ad1ff5 staged on m2-host).
