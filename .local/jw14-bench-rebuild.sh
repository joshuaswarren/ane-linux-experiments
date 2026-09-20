#!/bin/bash
# Rebuild /var/tmp/jw14-bench on jw14m2-linux after a /tmp wipe (reboot).
# All deps from pip cache (no downloads), fork wheel re-seated LAST.
set -euo pipefail
H=jw14m2-linux
R=/var/tmp/jw14-bench
ssh -o BatchMode=yes $H "mkdir -p $R/logs $R/results $R/receipts /var/tmp/mesa-095cb"
scp -q -o BatchMode=yes receipts/2026-09-20-final-harness-bench_decode_vlm.py $H:$R/bench_decode_vlm.py
scp -q -o BatchMode=yes .local/v063-jw16/scripts/bench_matrix.json .local/v063-jw16/scripts/bench_decode.py $H:$R/
scp -q -o BatchMode=yes .local/ane-v064-wt/scripts/caps_sim_guard.py .local/ane-v064-wt/scripts/mlx_provenance.py $H:$R/
scp -q -o BatchMode=yes /tmp/mesa-095cb/sin_ftz.spv /tmp/mesa-095cb/sin_ftz_runner.c $H:/var/tmp/mesa-095cb/
ssh -o BatchMode=yes $H "set -e; W=\$(ls ~/src/mlx-omarchy/.work/v072-aarch64/dist/mlx_omarchy-0.32.3.dev202609201440+5b18306-*.whl); cd $R && sha256sum bench_decode_vlm.py bench_matrix.json bench_decode.py caps_sim_guard.py mlx_provenance.py | tee logs/pins.sha \
  && python -m venv venv \
  && ./venv/bin/pip -q install --no-deps \"\$W\" \
  && ./venv/bin/pip install mlx-lm==0.31.3 mlx-vlm==0.7.1 'transformers==5.17.0' numpy==2.5.3 ml_dtypes==0.6.0 tokenizers==0.23.2 huggingface_hub==1.32.0 pillow==12.3.0 requests==2.34.2 safetensors==0.8.0 2>&1 | tee logs/pip-deps.log \
  && test \$(grep -c '^Downloading' logs/pip-deps.log) -eq 0 \
  && ./venv/bin/pip -q install --force-reinstall --no-deps \"\$W\" \
  && sha256sum venv/lib/python3.14/site-packages/mlx/lib/libmlx.so \
  && ./venv/bin/python bench_decode_vlm.py --self-test \
  && cd /var/tmp/mesa-095cb && clang -O2 sin_ftz_runner.c -o sin_ftz_runner -lvulkan \
  && echo REBUILD-OK"
