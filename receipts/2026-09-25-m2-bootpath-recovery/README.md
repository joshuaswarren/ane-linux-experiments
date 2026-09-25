# M2 boot path after the macOS window: U-Boot hangs, proxy chainload, recoveryOS (2026-09-25)

After the macOS capture window, the M2 would not boot Omarchy through U-Boot.
The m1n1 43ec stage-1 proxy and its NVMe access work. Two consecutive stub
boot failures then sent every reset, including USB-PD VDM resets, into the
Omarchy stub's paired recoveryOS. This receipt records what was observed and
the tooling that boots Linux over the proxy without U-Boot.

## Timeline (CDT)

- 13:08: `bless --mount /Volumes/Omarchy --setBoot` from the M2's macOS.
  `--getBoot` gives /dev/disk3s2 (Omarchy). The ESP boot.bin is the
  standing 43ec6090 (receipt 58b0917); the ESP was not written.
- 13:09:06: reboot from macOS. jwm1 dmesg shows the 43ec proxy enumerate at
  13:09:12 and leave 61 s later (PROXY60 window). The screen stops at the
  U-Boot countdown: banner `(Sep 09 2026 - 09:58:39 +0000)`,
  `MacBook Pro (14-inch, M2 Max, 2023)`, three `1 USB Device(s) found`,
  `scanning usb for storage devices... 0 Storage Device(s) found`,
  `Hit any key to stop autoboot: 0`, then nothing. The camera frame at the
  1280x720 maximum crops the left edge. No network came up. The mirrored
  OMARCHY box with a password field in the frames is jwm1's own lock screen
  reflected in the M2's glass, not an M2 prompt.
- 13:29: Joshua's cold reset. The jwm1 catcher latched the proxy inside the
  window and ran a read-only ident (`ident-catch.log`, `gpt.json`). m1n1's
  own NVMe came up clean: `rtkit(nvme): booting with version 12`,
  `nvme_init 1`. GPT: p4 FAT ESP, p5 ext4 /boot (2 GiB), p6 btrfs root
  (no LUKS), p7 RecoveryOSContainer.
- 13:29:07 + 2.5 s: the ident process exited and the USB device vanished.
  **43ec stage 1 leaves the proxy the moment the client closes the port** and
  falls through to stage 2 / U-Boot. That boot also never reached Linux; the
  panel went dark with no U-Boot text.
- 13:41:09 and 13:48:55: `sudo macvdmtool reboot` from jwm1's macOS
  (macvdmtool built from AsahiLinux/macvdmtool b22ae51; `nop` selected hpm0,
  `Connection: Source`, which is the M2 link). Both answered
  `Rebooting target into normal mode... OK`.
- After each VDM reset the M2 enumerated about 26 s later as Apple 05ac:1905
  "Mac" with two CDC-NCM functions and an `anri` RemoteXPC interface, not
  as the m1n1 proxy. `remotectl show` on jwm1: Mac14,5, J414cAP, OS 13.5
  (22G74), `OSInstallEnvironment => true`: the Omarchy stub's paired
  recoveryOS. Ports 22/445/548/5900 were closed on its link-local address.
  Its advertised `ssh` and `logRelay` services refused `remotectl netcat`
  (`Unable to connect`); heartbeat worked. No remote shell.

## Reading

- The U-Boot countdown hang happened on the first stub boot after macOS. A
  cold reset followed by m1n1's own NVMe bring-up was clean, so ANS2 was
  healthy at that point. The cause of the U-Boot hang is not isolated.
- The recoveryOS routing fits iBoot's boot-failure policy (the jw16 pattern
  in bba3e86). The ResetCounter at 12:52 already read `Boot failure count: 1`,
  and the 13:10 and 13:30 stub boots both failed before an OS came up. Only a
  booted OS, or m1n1's `PMU.reset_panic_counter()`, clears the counter.
- Getting out takes one action at the M2's recovery screen (Restart, or
  Startup Options -> Omarchy). No remote path was found.

## Tooling (tools/)

- `m2boot.py`: GPT plus a minimal extent-only ext4 reader over proxy
  `nvme_read`; `extract_boot()` pulls vmlinuz*, initramfs*, grub.cfg and its
  devicetree targets, loader entries, and the t6021 DTBs from /boot.
- `m2_linux_boot.py`: one unbroken proxy session. It resets the PMU panic
  counter, extracts on the first catch (cached afterwards), boots exactly
  grub's first menuentry (kernel, initrds, devicetree, args) plus `panic=30`,
  using tools/linux.py's sequence inline. U-Boot is not involved.
- `m2_boot_loop.sh` (jwm1 Linux, /dev/ttyACM0) and `m2_boot_loop_macos.sh`
  (jwm1 macOS, /dev/cu.usbmodem*, perl alarm, DRYRUN=1 mode): arm, catch,
  chainload, at most 3 boots per arming. The macOS bundle imports cleanly on
  Python 3.9.
- `m2_first_minute.sh`: from "ssh answers" to a staged 265bb63 module. It
  copies the M2's kernel build tree to macstudio, builds in the dg-alarm
  chroot, stages with sha and vermagic.
- `m2_run_265.sh`: the fw_start run in the macOS power form
  (fw_start_mpm_off=1, fw_start_venc_gates=0) under a userspace-petted
  hardware watchdog, disarmed by magic close on a clean run.

Camera frames are kept in private evidence (`frames-SHA256SUMS`).
