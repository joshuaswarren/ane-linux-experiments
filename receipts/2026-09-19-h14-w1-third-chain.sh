#!/bin/bash
# H14 W1 third attempt — ONE-SHOT exec chain (amended protocol, pushes done pre-RT2).
# Runs under `timeout -k 10 150 sudo -n bash`. Every step tee'd to /tmp/h14/ on-box.
set -o pipefail
echo "===CHAIN-BEGIN $(date -Is)==="

echo "===STEP:readonly-probe $(date -Is)==="
timeout -k 5 25 python3 -u /tmp/h14/h14_readonly_probe.py 2>&1 | tee /tmp/h14/third-probe.out
echo "===PROBE-EXIT:$? $(date -Is)==="

# Conditional raise: bringup stage1 only if the probe found ane_cpu unpowered.
if grep -q "not powered" /tmp/h14/third-probe.out; then
  echo "===STEP:bringup-stage1 $(date -Is)==="
  timeout -k 5 20 python3 -u /tmp/h14/h14_bringup.py --stage 1 2>&1 | tee /tmp/h14/third-bringup1.out
  echo "===BRINGUP-EXIT:$? $(date -Is)==="
fi

echo "===STEP:hello-dry $(date -Is)==="
timeout -k 5 20 python3 -u /tmp/h14/h14_rtkit_hello.py --dry 2>&1 | tee /tmp/h14/third-hello-dry.out
echo "===DRY-EXIT:$? $(date -Is)==="

echo "===STEP:hello-real-set-ap-on $(date -Is)==="
timeout -k 5 25 python3 -u /tmp/h14/h14_rtkit_hello.py --set-ap-on 2>&1 | tee /tmp/h14/third-hello-real.out
echo "===REAL-EXIT:$? $(date -Is)==="

echo "===CHAIN-END $(date -Is)==="
