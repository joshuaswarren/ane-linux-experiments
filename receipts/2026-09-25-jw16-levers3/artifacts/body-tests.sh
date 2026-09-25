#!/usr/bin/env bash
# Step 1: standing omarchy battery (27 GPU suites + capability-sim) on the
# installed ICD, built from the on-device worktree at agent/jw16-levers2.
# The tests build (CPU) runs before the window; this body only executes.
set -uo pipefail
T=/var/tmp/levers/mlx/.work/build-tests/tests/omarchy
echo "tree: $(git -C /var/tmp/levers/mlx log --oneline -1) icd=$(tr -d ' \n' < /usr/share/vulkan/icd.d/asahi_icd.aarch64.json)"
pass=0; fail=0
for t in "$T"/omarchy_*_tests; do
  [ -x "$t" ] || continue
  name=$(basename "$t")
  case "$name" in omarchy_ane_runtime_tests) continue;; esac
  echo "-- $name ($(stat -c %y "$t" | cut -c1-19))"
  if timeout 1800 "$t" > "$O/battery-$name.log" 2>&1; then
    echo "battery $name: PASS $(grep -E 'test cases|assertions' "$O/battery-$name.log" | tail -2 | tr '\n' ' ')"; pass=$((pass+1))
  else
    echo "battery $name: FAIL rc=$? $(grep -E 'test cases|assertions' "$O/battery-$name.log" | tail -2 | tr '\n' ' ')"; fail=$((fail+1))
  fi
done
CS=$T/omarchy_capability_sim_tests
for prof in m1-honeykrisp-fork m1-stock-no-coopmat subgroup-size-64 small-shared-memory no-cooperative-matrix; do
  if env MLX_OMARCHY_CAPS_SIM=$prof timeout 1800 "$CS" "$prof" > "$O/capsim-$prof.log" 2>&1; then
    echo "capsim $prof: PASS $(grep -E 'assertions' "$O/capsim-$prof.log" | tail -1)"; pass=$((pass+1))
  else
    echo "capsim $prof: FAIL rc=$? $(grep -E 'assertions|refus' "$O/capsim-$prof.log" | tail -2 | tr '\n' ' ')"; fail=$((fail+1))
  fi
done
echo "battery summary: pass=$pass fail=$fail"
echo TESTS_BODY_DONE
