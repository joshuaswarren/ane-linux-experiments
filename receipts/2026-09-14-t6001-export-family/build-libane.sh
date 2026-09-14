#!/usr/bin/env bash
# Build the derived-channel libane on jw16 (T6001, aarch64) from the pinned
# omarchy-ane libane sources at ane-parity 20d24ad.
#
# The pin is the libane SOURCES at that commit, not the branch: ane-parity
# lacks omarchy-ane main 8554583 entirely, which is where the T6001 module
# bind, the SET genpd wiring and ane/t6001-j316c-set-domains.dts live. Nothing
# here rebuilds the kernel module -- jw16's is already loaded and bound to
# 285c04000.ane -- and ane/src/uapi/drm/ane_accel.h is byte-identical between
# 8554583 and 20d24ad, so the userspace ABI is the same object either way.
#
# The resulting .so digest is host-specific and will NOT equal jwm1's
# bf4dbe5482d9eefd137108b88c3cb807f8cf3fdb32e02d6ed5314fea52201d95: that build
# used jwm1's compiler, this one uses jw16's. The commit is the pin; the digest
# is a record of this build, not a cross-host equality claim.
#
# Command line is the one recorded in
# receipts/2026-09-14-1x896-channel-polarity.json reproduction preconditions.
set -euo pipefail

W=${1:-/var/tmp/T6001ExportFamily-20260914}
SRC=$W/libane-src

echo "gcc=$(gcc --version | head -1)"
echo "arch=$(uname -m)"

cd "$SRC/libane"
gcc -shared -fPIC -std=gnu99 -O3 -Wall -Wextra \
  -o "$W/libane-polarity.so" \
  -I. -I/usr/include/libdrm -I../ane/src/uapi/drm \
  ane.c -ldrm
echo "built=$W/libane-polarity.so"
sha256sum "$W/libane-polarity.so"

# The derivation is header-only and device-free, so its self-test runs here as
# a host check before any submit. Six cases; a failure means the derived map
# cannot be trusted on this architecture and the submits must not proceed.
cd "$SRC/test/bind"
make all >/dev/null
echo "--- bind self-test on $(uname -m) ---"
./main.out --self-test
echo "--- derived role-to-channel map for every program to be submitted ---"
./main.out \
  "$W/control/bundle/program-0.anec" \
  "$W/control/bundle/program-1.anec" \
  "$W/staged/ane-add-fp16-1x512/model.anec" \
  "$W/staged/ane-add-fp16-1x896/model.anec"
