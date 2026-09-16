#!/usr/bin/env bash
# Bump PKGBUILD to the trim commit and build the mesa package.
set -euo pipefail
cd /home/joshuawarren/src/mesa-pkg-20260908
sed -i "s/^_commit=.*/_commit=73974760e06bfb9af8e0d7b954ee695f8187ed47/; s/^pkgrel=.*/pkgrel=2/" PKGBUILD
grep -E "^_commit|^pkgrel|^pkgver" PKGBUILD
nohup bash m1-mesa-pkg-build.sh > /var/tmp/TermASplit/pkgbuild.log 2>&1 &
echo "build-started pid=$!"
