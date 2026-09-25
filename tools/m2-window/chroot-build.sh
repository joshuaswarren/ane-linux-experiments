#!/usr/bin/env bash
# Runs ON macstudio (host side of docker): one ALARM-chroot wheel build.
# argv: <7-char commit>  ; expects $HOME/m2-wheel-stage/<commit>/src.tgz.
# Produces the wheel + build.log next to src.tgz. Fresh tree per run: the
# chroot image carries a stale /alarmroot/work from earlier lanes, so the
# repo dir is wiped and the wheel must stamp the requested commit.
set -euo pipefail
COMMIT="${1:?usage: chroot-build.sh <7-char-commit>}"
DIR="$HOME/m2-wheel-stage/$COMMIT"
BUNDLE="$HOME/src/ane-artifacts/encoder-whole/bundle"
cd "$DIR"

docker run --rm --privileged \
  -v "$DIR":/stageout \
  -v "$BUNDLE":/bundle-staging:ro \
  -e COMMIT="$COMMIT" \
  dg-alarm-py314:sep23 /bin/bash -c '
set -e
rm -rf /alarmroot/work/dg-repo
mkdir -p /alarmroot/work/dg-repo /alarmroot/work /alarmroot/bundle-staging
tar xzf /stageout/src.tgz -C /alarmroot/work/dg-repo
mount -o bind /dev /alarmroot/dev
mount -t proc proc /alarmroot/proc 2>/dev/null || true
mount -o bind /bundle-staging /alarmroot/bundle-staging
set +e
chroot /alarmroot /usr/bin/env -i \
  HOME=/root PATH=/opt/py314/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  MLX_OMARCHY_WHOLE_BUNDLE_DIR=/bundle-staging DEV_RELEASE=1 \
  MLX_OMARCHY_SOURCE_COMMIT=$COMMIT \
  bash -c "cd /work/dg-repo && bash ./scripts/build-wheel.sh > /work/build.log 2>&1; rc=\$?; tail -60 /work/build.log; exit \$rc"
RC=$?
set -e
# container-side copies: /stageout and /alarmroot are only visible here,
# outside the chroot.
cp /alarmroot/work/build.log /stageout/build.log
ls /alarmroot/work/dg-repo/dist/*+$COMMIT-cp314-*.whl >/dev/null 2>&1 \
  && cp /alarmroot/work/dg-repo/dist/*+$COMMIT-cp314-*.whl /stageout/
exit $RC
'

echo "== chroot build done =="
ls -la "$DIR"
