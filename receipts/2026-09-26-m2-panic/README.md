# M2 Linux boot panic: Undefined Instruction in apple-dcp DPC preprobe (2026-09-26)

Camera frame m2now-0731.jpg (sha256
d5e3315f3365ebdd54727ab2543d318b47d9624a7db30f836a303e6f9b4b5e67),
taken 07:31 from jwm1 /dev/video1, shows a forward-reading kernel boot
log over the mirrored Omarchy lock screen. This is a user-observed boot
panic, not the old lock-screen frame.

Lines transcribed from the cropped fault band (m2-panic-fault.jpg crop
of the same frame; some hex digits uncertain at camera distance):

- `Internal error: Oops - Undefined Instruction: 0000000000000000 [#1] SMP`
- `Modules linked in: phy_apple_atc(+) appledrm(+) drm_gpu_helper apple_tunable ...`
- `apple-dcp 298b00000.dcp: Failed to get dp-phy: -517`
- `CPU: 0 UID: 0 PID: 280 Comm: (udev-worker) Tainted: G S`
- `Hardware name: Apple MacBook Pro (14-inch, M2 Max, 2023) (DT)`
- `pstate: 61400009 (nZcv daif +PAN -UAO -TCO +DIT -SSBS BTYPE=--)`
- `pc : __arm64_sys_call+0x49/0x6e0`
- Footer: `7.1.13-ARCH-m2mbox #2 PREEMPT(full)`
- `Tainted: [S]=CPU_OUT_OF_SPEC`

Evidence chain:
- The previous (warm) chainload also failed to reach ssh within 5 min.
- ResetCounter-2026-09-26-074137.diag from macOS: boot failure count 1,
  faults wdog/reset_in1.
- No new kernel panic-full file on macOS (Linux panics do not land
  there). No macOS kernel panic involved: boot history shows a clean
  07:41 macOS boot after.
- ESP untouched in the attempt (43ec6090 still on disk0s4; bless still
  /dev/disk2s2). The failure is in the running kernel, not the image.

Reading: the m2mbox test kernel executes an undefined instruction while
udev probes apple-dcp (DisplayPort controller; the dp-phy -517 defer is
adjacent in the same lines). A UDEV-worker Oops during probe disables
that path without remounting anything. [INFERENCE] This is a test-kernel
regression or a stale DT binding, not the ANE work: no ane module line
appears in the visible log, and the ANE rtclient was never loaded on
this boot.

Repair path, none executed yet:
1. Boot the stock kernel: grub second Linux menuentry
   ("linux-asahi", vmlinuz-linux-asahi + initramfs-linux-asahi.img),
   already on /boot and in the catcher cache.
2. Re-run: catcher (pid 125230, intact) then leg 1 once Linux answers.
3. The m2mbox kernel needs its dcp/phy config checked before reuse.

Stale-watcher cleanup this session: /var/tmp/m2proxy/watch.sh PID 666
killed (left only sleep child, then gone), respawn PID 126722 killed and
verified gone with no ane_bringup/omarchy-now children. Single serial
owner now: catcher pid 125230; no /dev/ttyACM* present (M2 in macOS).
