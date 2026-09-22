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
