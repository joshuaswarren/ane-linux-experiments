#!/usr/bin/env bash
/var/tmp/TermAJW16/venv/bin/pip install -q /var/tmp/TermAJW16/mlx_omarchy-0.32.2.dev202609161852+2e252962-cp314-cp314-linux_aarch64.whl
/var/tmp/TermAJW16/venv/bin/python -c "import mlx.core; print('venv ready')"
setsid /var/tmp/termA-jw16-deploy.sh > /var/tmp/TermAJW16/deploy.log 2>&1 < /dev/null &
echo "deploy-started pid=$!"
