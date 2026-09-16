#!/usr/bin/env bash
# Bump PKGBUILD to the G13X trim commit and build on jwm1 (aarch64).
set -uo pipefail
sed -i "s/^_commit=.*/_commit=d71c94ec4ecdc081eca49034e34ae5fb30fc8de3/" /home/joshuawarren/src/mesa-pkg-20260908/PKGBUILD
grep -E "^_commit|^pkgrel" /home/joshuawarren/src/mesa-pkg-20260908/PKGBUILD
bash /home/joshuawarren/src/mesa-pkg-20260908/m1-mesa-pkg-build.sh
echo "build rc=$?"
ls -t /home/joshuawarren/src/mesa-pkg-20260908/*.pkg.tar.xz | head -2
