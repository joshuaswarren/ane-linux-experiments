#!/usr/bin/env bash
# TermA suite gate: omarchy_runtime_tests (41 cases) under the candidate
# driver emission, both arms. VK driver = worktree build3 ICD.
set -uo pipefail
export VK_DRIVER_FILES=/home/joshuawarren/src/mesa-wt-dispatchfloor/dispatchfloor-icd.json
BIN=/home/joshuawarren/src/mlx-omarchy/.work/build/tests/omarchy/omarchy_runtime_tests
W=/var/tmp/TermASplit
echo "== arm: default emission (mask unset) =="
timeout 900 "$BIN" > "$W/suite-default.log" 2>&1
echo "rc=$?"
tail -4 "$W/suite-default.log"
echo "== arm: k1f0 emission =="
HK_CDMBARBITS=1F0 timeout 900 "$BIN" > "$W/suite-k1f0.log" 2>&1
echo "rc=$?"
tail -4 "$W/suite-k1f0.log"
