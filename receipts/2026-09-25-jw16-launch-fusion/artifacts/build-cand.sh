#!/usr/bin/env bash
# Build the candidate wheel from the checked-out branch in the on-device
# worktree (incremental cmake build dir reuse). The branch is pushed to the
# device clone from the workstation (the device has no GitHub key).
set -uo pipefail
cd /var/tmp/levers/mlx
echo "tree: $(git log --oneline -1) branch=$(git branch --show-current)"
export MLX_OMARCHY_WHOLE_BUNDLE_DIR=/var/tmp/encoder-whole/bundle
stamp=$(date -u +%Y%m%dT%H%M%SZ)
log=/var/tmp/levers2/wheel-build-$stamp.log
echo "log: $log"
SECONDS=0
bash scripts/build-wheel.sh >> "$log" 2>&1
rc=$?
echo "build rc=$rc in ${SECONDS}s"
ls -la dist/
tail -3 "$log"
echo BUILD_DONE
