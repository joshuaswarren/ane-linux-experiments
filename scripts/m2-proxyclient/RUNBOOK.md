# m1n1 proxyclient bring-up plan — T6021 ANE ASC on m2-host

Single variable vs every 2026-09-21 Linux arm (`receipts/2026-09-21-t6021-host-tm/`):
RVBAR is written **with the kext mode bits** (`0x0081010000000001`) **before**
the core leaves reset, from the proper quiesce context (m1n1 stage 1 owns the
machine; no Linux kernel, no watchdog). Everything else replays the proven
ANE_Init order: power cycle ane_cpu → RVBAR → map selene → RUN → poll
SCRATCH7 for `0x08042006` → RTKit handshake.

Verified against:
- ADT capture `~/var/tmp/m2-macos-capture-20260921/ane0-dt.txt`
  (`python3 t6021_consts.py` — all 18 checks green)
- `tools/ane-hunter/driver_consts.py` (engine 0x284000000, TM 0x285C00000)
- NIGHT-SUMMARY §3/§4 (RVBAR 0x285050000, CPUCTL 0x285400044, SCRATCH7
  0x285840064, READY 0x08042006, wake 0xF7FBDFF9, mode-bit composition)

## Files

| file | role |
|---|---|
| `t6021_consts.py` | every address + `validate()` cross-check (run standalone) |
| `ane_bringup.py` | the session script (a)–(e); `--dry-run` = reads only |
| `mock_proxy.py` | stub ASC; happy path + `--mock-latched-rvbar` negative path |

## Physical instruction for Joshua (the ONLY manual step)

Use a USB-C data cable (any quality USB-C/USB-C cable; avoid charge-only). On
**m2-host (the M2 MacBook Pro)** use the **left-rear USB-C port** (the
one nearest the hinge on the left side); on **the proxy host (the 16"
M1 laptop)** any USB-C port works. Plug one end into each machine. That is the
whole action: m2-host will be sitting at the m1n1 proxy (after the staged
cutover below), the cable enumerates the proxy as `/dev/ttyACM*` on proxy-host
within ~5 s, and the watcher service (`m1n1-proxy-watcher`) fires the entire
checklist automatically — you should see nothing on either screen except,
optionally, the proxy host's log: `journalctl -u m1n1-proxy-watcher -f`. Receipts land
in `/var/tmp/m2proxy/receipts/2026-09-22-m2-proxyclient-prep/` on proxy-host and
sync to the workstation `receipts/` dir of the same name.

## Boot side (one-time, m2-host)

### Staged cutover on m2-host (as of 2026-09-22 06:55 — files staged, NOT installed)

m2-host's live boot payload is `/boot/efi/m1n1/boot.bin`
(m1n1 + DTBs + gzip u-boot + appended config, written by `update-m1n1`).
iBoot loads that exact file each boot, so a same-path file swap is the
whole switch — the Apple boot-object blessing is untouched and the Omarchy
default is restored by copying one file back.

Already staged on m2-host in `/var/tmp/m2proxy-staging/`:

| file | sha256 | what |
|---|---|---|
| `boot.bin.pre-proxy` | `153170e0…ad1ff5` | exact copy of the live Omarchy boot.bin (the return image) |
| `boot.bin.proxy-only` | `9ad08653…4158fd` | bare `/usr/lib/asahi-boot/m1n1.bin` (m1n1 1.6.1, proxy compiled in, NO chainload config → sits at the USB proxy forever) |

Cutover (operator, when Joshua is ready to plug the cable):

```sh
ssh m2-host
sudo cp /var/tmp/m2proxy-staging/boot.bin.proxy-only /boot/efi/m1n1/boot.bin
sudo reboot
```

After reboot the box idles at the m1n1 proxy: no Linux, no ssh, no display
output — the ONLY way in is the USB cable to proxy-host, which is exactly the
armed state we want. Nothing is lost; the watchdog/freezes classes do not
exist here (no Linux kernel runs).

Return to Omarchy (from proxy-host, over the same proxy — no cable swapping):

```sh
omarchy-now.sh            # dry-run: prints image/sha/device status, changes nothing
omarchy-now.sh --chainload  # stops the watcher, chainloads boot.bin.pre-proxy, boots Omarchy
```

`omarchy-now.sh` lives at `/var/tmp/m2proxy/omarchy-now.sh` (symlinked into
`~/.local/bin` on the proxy host). It verifies the return image against sha
`153170e0…ad1ff5` BEFORE stopping the watcher — a missing or mismatched
image is a clean no-op that leaves the watcher running. The chainload
(`proxyclient/tools/chainload.py`) loads the pre-proxy boot.bin into the
running m1n1 and jumps to it; the ESP is never written.

Image resolution: `--image PATH` > `/var/tmp/m2proxy/boot.bin.pre-proxy` >
the proxy host's own `/boot/efi/m1n1/boot.bin`. The local fallback works
because `update-m1n1` concatenates m1n1 + u-boot-nodtb + all apple dtbs, so
the same file boots the m2-host's t6021; its u-boot then loads grub from
m2-host's ESP as normal. Version parity (proxy host vs m2-host, from the
staging receipt): m1n1 1.6.1-1 = 1.6.1-1; uboot-asahi 2026.07.asahi2-1;
no separate asahi-dtbs package (dtbs ship inside the m1n1/uboot builds).
The hashes nevertheless differ (local 41a39ac7… vs 153170e0… — each host's
`update-m1n1` embeds its own config), so a sha mismatch is refused unless
the image was given explicitly via `--image PATH`; the refusal names the
override and prints `pacman -Q m1n1 uboot-asahi` as the parity check.

The watcher also self-terminates its own run: after each checklist pass (or
abort) it invokes `omarchy-now.sh --chainload --image /boot/efi/m1n1/boot.bin`
(Main's 2026-09-22 override: the proxy host's image is explicitly trusted so a
cable-in can never strand the box at the logo), so every cable-in ends with
the box back in Omarchy.

or, from m2-host's side once it boots Linux again, verify and clean up
(this restore is what stops future reboots from re-parking at the proxy):

```sh
ssh m2-host 'sudo cp /var/tmp/m2proxy-staging/boot.bin.pre-proxy /boot/efi/m1n1/boot.bin && sudo sha256sum /boot/efi/m1n1/boot.bin'
# expect 153170e065383767a47bc234e02344ecdc09d03f4003d92e6a2d6e464fad1ff5
# then reboot once to confirm stock Omarchy boots; afterwards the next
# `update-m1n1` run (kernel/agent update) will rewrite boot.bin normally.
```

The proxy-only image is deleted with `/var/tmp/m2proxy-staging/` once the
experiment window closes. `boot.bin.old` (update-m1n1's own backup) was not
touched.

### Host tooling already live on proxy-host (2026-09-22 06:55, all verified)

- venv `/var/tmp/m2proxy-venv` (pyserial 3.5, construct, pyelftools);
  m1n1 proxyclient at `~/src/m1n1` (symlinked into
  `/var/tmp/m2proxy/scripts/.work-m1n1-proxyclient`); scripts + selene
  fixture under `/var/tmp/m2proxy/`.
- udev rule `/etc/udev/rules.d/99-m1n1-proxy.rules`: m1n1 CDC gadget
  (VID `1209` PID `316d`, per `src/usb_dwc3.c`) → MODE 0666, no
  ModemManager claim.
- systemd service `m1n1-proxy-watcher` (active, `Restart=always`) running
  `/var/tmp/m2proxy/watch.sh`: polls every 2 s for a `1209:316d` ttyACM*,
  and on first appearance runs the full checklist (a)–(e) — constants →
  device → `--dry-run` → `--mock` sanity → THE RUN — tee'd to
  `/var/tmp/m2proxy/receipts/2026-09-22-m2-proxyclient-prep/run-<stamp>.log`
  and scp'd to the workstation receipt dir of the same name. Abort file
  `/tmp/ane-bringup.abort` still kills any poll instantly.

1. **m1n1 stage 2 with the proxy enabled.** m2-host already chainloads through
   the Asahi bootstrap; build/install m1n1 with the default config — the m1n1
   proxy runs on the USB serial gadget as soon as the cable is connected.
   If the current bootstrap is a Linux-only install, boot m1n1 once via
   1TR/USB boot object built with `m1n1/m1n1.macho` + `m1n1/build-uboot.sh`
   is NOT needed (no U-Boot; the bare proxy in `m1n1.macho` is enough).
2. **USB gadget mode:** m1n1 enumerates as a USB serial device on the host
   automatically (`/dev/ttyACM*` on Linux host, cu.usbmodem* on macOS host).
   Nothing to configure on m2-host — the cable IS the switch.
3. **Host-side pip requirements** (any host; this workstation):

   ```sh
   python3 -m pip install --user pyserial construct pyelftools
   # m1n1 proxyclient tree:
   git clone --depth 1 https://github.com/AsahiLinux/m1n1 ~/src/m1n1
   ```

4. Point the script at the tree (it inserts `scripts/m2-proxyclient/.work-m1n1-proxyclient`
   into sys.path):

   ```sh
   ln -sfn ~/src/m1n1/proxyclient scripts/m2-proxyclient/.work-m1n1-proxyclient
   ```

5. Selene comes from the hunter fixtures
   (`tools/ane-hunter/fixtures/t602x_ane0_fw_selene_rc4x.macho`, sha `9f7915c4…`);
   re-fetch from m2-host `/lib/firmware/apple/ane/` if absent.

## The 10-minute checklist (once the cable is in)

```sh
cd <repo>/scripts/m2-proxyclient

# 0. (30 s) constants still valid
python3 t6021_consts.py                       # expect: VALIDATION PASS

# 1. (30 s) device present
ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null      # note the device, export it
export M1N1DEVICE=/dev/ttyACM0                # adjust

# 2. (1 min) reads-only smoke: ADT dump + RVBAR/SCRATCH7/CPUCTL state
python3 ane_bringup.py --dry-run              # expect: READS-ONLY DONE
#   expected live state: RVBAR 0x10000000001 (latched), SCRATCH7 0x0,
#   CPU_STATUS 0x28 — matches every post-watchdog read from the night.

# 3. (2 min) the arm — one variable, mode bits
python3 ane_bringup.py --mock                 # stub sanity (optional)
python3 ane_bringup.py                        # THE RUN
```

Interpreting the run:

| outcome | reading | next step |
|---|---|---|
| `[poll] SCRATCH7-READY MATCH=True` + `[e] handshake complete` | **mode-bit hypothesis CONFIRMED** — first ASC boot ever on this box | TQ contract `.work/2026-09-21-t6021-host-tm-contract.md` on the running selene |
| `[d] ABORT no READY … CPU_STATUS=0x28` | silent-park stands even with mode bits — RVBAR composition still incomplete (FWIM_DVA ≠ 0x10000000000?) | check `SCRATCH1:SCRATCH0` after publish path; consider kext FWIM DVA from `*(dev+0x978)+0x18` |
| `[b] ABORT RVBAR readback … write not accepted` | proxy-context RVBAR also ignores writes pre-reset | abort; do NOT reset/ps-cycle from any host; capture with `--dry-run` and stop |
| USB drop / no READY and box unresponsive | — | reboot m2-host (watchdog will anyway); nothing on the Linux side to clean up |

## Safety

- Every poll bounded (kext bounds: Poll A/B = 1000 × 1 ms); every proxy
  command under `alarm(5)`.
- Abort file: `touch /tmp/ane-bringup.abort` stops any poll instantly.
- `--dry-run` writes nothing (read-only pre-flight).
- m1n1 stage 1 owns the whole machine — the Linux freeze classes (posted
  ioremap, kernel-context ps-cycle) do not exist on this path.
- Log every step; the script's stdout is the receipt (tee to
  `receipts/2026-09-22-m2-proxyclient-prep/`).

## 2026-09-22 addendum — host-role determinism + re-park procedure (M2ProxyLive, live USB debugging on proxy-host)

### proxy-host host-role mechanics (asahi kernel, cd321x/tps6598x PD)

- The asahi cd321x driver exposes no Type-C data-role-set: sysfs
  `echo host > /sys/class/typec/portN/data_role` returns EPERM whenever the
  write would actually change the role (a same-role write is a no-op that
  does NOT re-trigger dwc3). Chip-level 4CC `SWDF` written to the PD
  controller (i2c-0 addr 0x38/0x3f reg 0x08) was accepted but did not flip.
- Initial data role is decided by the VBUS/source arbitration: whoever wins
  source wins DFP (host). Two laptops re-roll this on every plug and every
  boot. Empirically reliable setup:
  **proxy-host on its own charger (any other port) + data cable on the other
  port** — an externally powered proxy-host keeps VBUS and settles host/DFP.
- dwc3-apple glue driver state machine (drivers/usb/dwc3/dwc3-apple.c):
  dwc3 core probe is DEFERRED until the first cable-connect event
  (DWC3_APPLE_PROBE_PENDING -> connect -> core probe -> xhci). Forcing the
  probe by writing role files out of order leaves the core in a failed state
  (`DWC3 controller soft reset failed` -110, then every retry -EBUSY on
  0x38228c100) that ONLY a reboot clears.
- Therefore the deterministic bring-up is: boot proxy-host (charger attached) with
  the data cable ALREADY PLUGGED at proxy-host's end, then unplug/wait 5 s/replug
  the data cable so the kernel sees a fresh connect event in host role.
  Never write the data_role files.

### `m2proxy-linkcheck` (deployed on proxy-host: /usr/local/bin/m2proxy-linkcheck)

One line: per-port data_role, partner usb_mode, root-hub count, ttyACM
device; rc 0 only when the m1n1 gadget is enumerated. Healthy link reads:

```
roles: port0:[host] device port1:host [device] partners: port0=usb3 port1= roothubs:2 ttyACM:/dev/ttyACM0
```

- `port0-partner usb_mode=usb3` with `roothubs:0` = link up, gadget
  presenting, but dwc3 never initialized (wedged or pre-connect event):
  unplug/replug the data cable once; if still 0 root hubs, reboot proxy-host.

### Re-park procedure (redo the experiment after m2-host returns to Omarchy)

The proxy park is one file: `/boot/efi/m1n1/boot.bin` on m2-host.

```sh
# 1. stage the proxy image (idempotent; staged copy already verified)
ssh m2-host 'sudo cp /var/tmp/m2proxy-staging/boot.bin.proxy-only /boot/efi/m1n1/boot.bin \
  && sha256sum /boot/efi/m1n1/boot.bin'   # expect 9ad08653…4158fd

# 2. reboot m2-host (operator: Main standing GO covers the cutover reboot)
ssh m2-host 'sudo reboot'
#    box parks at the m1n1 proxy (Asahi logo, no ssh)

# 3. within ~60 s the m1n1 USB gadget attaches; proxy-host host side:
ssh proxy-host 'm2proxy-linkcheck'   # want roothubs:2 and ttyACM:/dev/ttyACM0
#    (if roothubs:0: replug data cable once; if still 0: reboot proxy-host)

# 4. watcher fires automatically: journalctl -u m1n1-proxy-watcher -f
#    receipt: /var/tmp/m2proxy/receipts/2026-09-22-m2-proxyclient-prep/run-*.log
#    -> scp'd to workstation receipts/2026-09-22-m2-proxyclient-prep/

# 5. return to Omarchy (post-run hook does this automatically; manual form):
ssh proxy-host 'omarchy-now --chainload --image /boot/efi/m1n1/boot.bin'
#    -> chainloads proxy-host's boot.bin into the RUNNING m1n1 (no ESP write),
#       m2-host boots Omarchy; ssh returns in ~60 s

# 6. restore the Omarchy ESP default for future boots:
ssh m2-host 'sudo cp /var/tmp/m2proxy-staging/boot.bin.pre-proxy /boot/efi/m1n1/boot.bin \
  && sha256sum /boot/efi/m1n1/boot.bin'   # expect 153170e0…ad1ff5
```

Total redo time once the link is proven: ~5 minutes. Every step leaves a
receipt (sha lines, linkcheck line, run log, omarchy-now log block).
