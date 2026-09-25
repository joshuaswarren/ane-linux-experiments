#!/bin/bash
# From "M2 ssh answers" to a staged, vermagic-checked 265bb63 module.
# Runs on the workstation. Reads only on the M2 until the final copy into
# /var/tmp/ane-psform; builds happen in the macstudio ALARM chroot.
set -euo pipefail
M2=jw14m2-linux
SRCDIR=oa-psform-265bb63-130937
OUT=/tmp/m2kstart/first-minute-$(date +%H%M%S)
mkdir -p "$OUT"
say() { echo "$(date +%T) $*" | tee -a "$OUT/run.log"; }

say "identity"
ssh -o BatchMode=yes $M2 'hostname; uname -r; uptime; cat /proc/cmdline;
    ls /proc/device-tree/soc | grep -E "^(mailbox@285408000|ane@284000000)$" || echo "MISSING mailbox/ane node";
    ls /proc/device-tree/reserved-memory | grep -iE "ane|asc-firmware" || echo "no ane reserved-memory";
    lsmod | grep -iE "ane|rtclient|mbox" || echo "no ane modules";
    ls /lib/firmware/apple 2>/dev/null | grep -i ane' | tee -a "$OUT/identity.txt"
KVER=$(ssh -o BatchMode=yes $M2 uname -r)
BUILD=$(ssh -o BatchMode=yes $M2 "readlink -f /usr/lib/modules/$KVER/build")
BN=$(basename "$BUILD")
say "kernel $KVER build tree $BUILD"

say "copy build tree to macstudio"
ssh -o BatchMode=yes $M2 "tar -C $(dirname "$BUILD") -czf - $BN" |
    ssh -o BatchMode=yes macstudio "mkdir -p ~/src/m2-headers/$KVER && tar -xzf - -C ~/src/m2-headers/$KVER"
ssh -o BatchMode=yes macstudio "du -sh ~/src/m2-headers/$KVER/$BN; ls ~/src/m2-headers/$KVER/$BN/.config ~/src/m2-headers/$KVER/$BN/Module.symvers" |
    tee -a "$OUT/run.log"

say "build 265bb63 in the chroot"
ssh -o BatchMode=yes macstudio "~/src/build-t6021-ko.sh ~/src/m2-headers/$KVER/$BN ~/src/$SRCDIR ~/src/ko-265bb63-$KVER" |
    tee "$OUT/build.log"
scp -q macstudio:"src/ko-265bb63-$KVER/ane_t6021_rtclient.ko" "$OUT/"
sha256sum "$OUT/ane_t6021_rtclient.ko" | tee -a "$OUT/run.log"

say "stage on the M2"
ssh -o BatchMode=yes $M2 'mkdir -p /var/tmp/ane-psform'
scp -q "$OUT/ane_t6021_rtclient.ko" $M2:/var/tmp/ane-psform/
ssh -o BatchMode=yes $M2 "cd /var/tmp/ane-psform && sha256sum ane_t6021_rtclient.ko &&
    modinfo -F vermagic ane_t6021_rtclient.ko && modinfo -F version ane_t6021_rtclient.ko &&
    modinfo -F parm ane_t6021_rtclient.ko | grep -E '^(fw_start_mpm_off|fw_start_venc_gates):'" |
    tee -a "$OUT/run.log"
say "staged; OUT=$OUT"
