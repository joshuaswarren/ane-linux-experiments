#!/usr/bin/env bash
# Detached launcher for the gdn-fuse window on the target host.
set -euo pipefail
exec 9>/tmp/m1-gpu.lock
flock -w 3600 9
bash /var/tmp/jgd-fuse/window-gdnfuse.sh \
  /var/tmp/jgd-fuse/mlx_omarchy-0.32.3.dev202609231648+57c3963ad-cp314-cp314-linux_aarch64.whl
