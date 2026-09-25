#!/usr/bin/env bash
# Stage the decode-profile venv on m1-host (no GPU lock needed: no measurements).
# Replicates the installed decode config (vp/venv-cand: a91adbf wheel +
# mlx-lm 0.31.3 + dg GDN patches + greedy prune patch) with the DIAGNOSTICS
# wheel at the same source commit a91adbf.
# usage: stage-prof-venv.sh <diag-wheel>
set -euo pipefail
WHL="$1"
VP=/var/tmp/vprof
mkdir -p "$VP"
V="$VP/venv-diag"
if [[ ! -d "$V" ]]; then
  python3 -m venv --system-site-packages "$V"
  "$V/bin/pip" -q install "$WHL" mlx-lm==0.31.3
  python3 /var/tmp/dg/scripts/patch-mlx-lm-gdn.py "$V"
  python3 /var/tmp/dg/scripts/patch-mlx-lm-gdn-raw.py "$V"
  site="$(dirname "$(ls -d "$V"/lib/python3.*/site-packages/mlx_lm)")"
  patch --directory="$site" --strip=1 --forward --fuzz=0 < /var/tmp/vp/mlx-lm-greedy-prune.patch
fi
sha256sum "$WHL" | tee "$VP/wheel.sha256"
"$V/bin/python" -c "import importlib.metadata as m; print('wheel', m.version('mlx-omarchy')); import mlx_lm; print('mlx_lm', mlx_lm.__version__)"
"$V/bin/python" -c "import mlx.core as mx; print('greedy op present:', hasattr(mx.fast, 'greedy_quantized_argmax'))"
