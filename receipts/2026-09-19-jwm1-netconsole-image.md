# jwm1 netconsole boot image — NOT QUALIFIED, do not flash

Date: 2026-09-19. Corrected 2026-09-19 ~16:40 after a fresh live-device audit
(esp-live-1634.img, see 2026-09-19-jwm1-esp-recovery-2.md).
Image: `/var/tmp/jwm1-esp/esp-netconsole.part`
SHA256: `9f4f2489c53f34b47f5d937112c4713992fee4d9a99c2e57193d47ba81a866e6`

**Status: NOT QUALIFIED. This image must NOT be flashed to disk0s4, and its
netconsole parameter must not be cited as working telemetry.** The original
text below claimed it was "ready to be `dd`'d"; that readiness claim was
false and is retracted. Evidence, all from bytes read in this session:

1. jwm1's only NIC is Wi-Fi (brcmfmac). Kernel netconsole cannot associate
   Wi-Fi — association requires wpa_supplicant in userspace. The verified
   `INITRD.REC` (sha `23739973ebd799a8…`) contains **no wpa_supplicant and
   no brcmfmac firmware** (substring-verified against the full 83,415,040-byte
   decompressed main archive), and no `ip=` on the kernel command line, so
   netconsole has no address and no link at early boot.
2. Boot-time netconsole registers once at module init and does not retry when
   the interface appears later, so it cannot even report the emergency-mode
   failure class "late" on this box.
3. The parameter syntax is wrong in every variant produced today:
   - this image: `netconsole=6666@/,6668@192.168.3.103/5c:e9:1e:7a:d0:17` —
     empty source IP, no source device.
   - `esp-final-verified.part` (600c, sha `600cdd58…`, **disqualified as a
     write source** for the same reason) and the `/etc/modprobe.d/netconsole.conf`
     shipped inside `INITRD.REC`
     (`options netconsole netconsole=6668@192.168.3.103/wlan0,6666@192.168.10.235/04:f4:1c:92:4c:c8`):
     the collector's IP (jw14m2, 192.168.3.103) used as the *source*, bound to
     `wlan0`, with jw16 (192.168.10.235) as target.
4. Coverage honesty: netconsole is a kernel feature. It covers neither
   GRUB-level failures ("you need to load the kernel first") nor early-kernel
   panics before a NIC is up — the two failure modes this recovery actually
   exhibits. On this box, as built, it covers nothing.
5. Not flashed: the live ESP as of 2026-09-19 16:33 (fresh full-device read,
   sha `e8f3cd801c9cc0508e2cf64a1b522d315c92dbfa0af049f6ff086c5458d3740d`)
   carries **no netconsole parameter**.
6. Earlier claims that a UDP 6668 collector was armed on jw14m2 are void: the
   arming job matched its own shell via pgrep; `ss -lun` showed NO_LISTENER.

If early-boot remote visibility is genuinely needed later: attach a USB
ethernet adapter, include that NIC driver + firmware in the initramfs, add
`ip=` to the command line, and use a correct
`netconsole=<src-port>@<src-ip>/<dev>,<tgt-port>@<tgt-ip>/<tgt-mac>`. Until
then the honest statement stands: a failed jwm1 boot is remotely invisible and
requires one console trip.

---

## Original text (retained for the record — readiness claim retracted)

This image incorporates the filesystem fixes from `esp-recovery.part` (search --file instead of --fs-uuid, allowing GRUB to find the kernel on the FAT32 partition rather than btrfs), and adds `netconsole=6666@/,6668@192.168.3.103/5c:e9:1e:7a:d0:17` to the kernel command line.
It directs netconsole to `jw14m2-linux` on the LAN. Note that if jwm1 boots via Wi-Fi (`wlan0`), early-boot netconsole will likely fail to associate before userspace `wpa_supplicant` starts, so a hardware ethernet dongle may be required to catch kernel panics.

It is ready to be `dd`'d to the ESP (`disk0s4`) when a console trip is made.
