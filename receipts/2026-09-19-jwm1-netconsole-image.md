# jwm1 netconsole boot image

Date: 2026-09-19
Image: `/var/tmp/jwm1-esp/esp-netconsole.part`
SHA256: `9f4f2489c53f34b47f5d937112c4713992fee4d9a99c2e57193d47ba81a866e6`

This image incorporates the filesystem fixes from `esp-recovery.part` (search --file instead of --fs-uuid, allowing GRUB to find the kernel on the FAT32 partition rather than btrfs), and adds `netconsole=6666@/,6668@192.168.3.103/5c:e9:1e:7a:d0:17` to the kernel command line.
It directs netconsole to `jw14m2-linux` on the LAN. Note that if jwm1 boots via Wi-Fi (`wlan0`), early-boot netconsole will likely fail to associate before userspace `wpa_supplicant` starts, so a hardware ethernet dongle may be required to catch kernel panics.

It is ready to be `dd`'d to the ESP (`disk0s4`) when a console trip is made.