#!/usr/bin/env bash
# Land: commit trim, push, ff honeykrisp-omarchy, bump PKGBUILD, build package.
set -euo pipefail
cd ~/src/mesa-wt-dispatchfloor
python3 /var/tmp/termA-trim-patch.py
git add src/asahi/libagx/libagx_dgc.h
git commit -q -m "asahi: trim the per-launch CDM barrier to the designed G13X set

The kitchen-sink CDM_BARRIER emitted after every compute launch (marked
'to be safe' until the bits are understood) costs ~10 us per dispatch in
dependent compute chains: on Apple M1 (G13X), Qwen2.5-0.5B Q4 decode
spends ~2.1 ms of a ~9.8 ms token in it (receipts/2026-09-16-termA,
mlx-omarchy). Removing it entirely gains +25.6% but is
nondeterministically wrong; emitting only bits 4..8 on G13X holds the
mlx-omarchy pinned generated-ID digests 48/48 interleaved runs (both
legs) and the omarchy runtime suite (22 cases / 6189 assertions), and
measures +3.05% ctx1053 / +3.03% short decode on jwm1.

Other chips keep the full kitchen sink until measured there."
git push -q origin hk/cdm-barrier-trim
git checkout -q honeykrisp-omarchy
git merge -q --ff-only hk/cdm-barrier-trim
git push -q origin honeykrisp-omarchy
NEWC=$(git rev-parse hk/cdm-barrier-trim)
echo "trim commit: $NEWC"
cd ~/src/mesa-pkg-20260908
sed -i "s/^_commit=.*/_commit=$NEWC/; s/^pkgrel=.*/pkgrel=2/" PKGBUILD
grep -E "^_commit|^pkgrel|^pkgver" PKGBUILD
bash m1-mesa-pkg-build.sh 2>&1 | tee /var/tmp/TermASplit/pkgbuild-tail.log > /var/tmp/TermASplit/pkgbuild.log 2>&1
echo "package build rc=$?"
ls -la *.pkg.tar.xz | tail -2
