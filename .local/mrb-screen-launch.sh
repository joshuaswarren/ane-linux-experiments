#!/usr/bin/env bash
# MesaRegressionBisect generic screen launcher with llm-inference race guard:
# stop service, try the lock briefly; if a restarting service grabbed it in
# between, stop it again and retry. Always restart llm-inference on exit.
set -u
trap 'sudo systemctl start llm-inference.service' EXIT
ok=0
for i in $(seq 1 30); do
  sudo systemctl stop llm-inference.service
  sleep 2
  if flock -w 60 /tmp/m1-gpu.lock "$@"; then ok=1; break; fi
done
[ "$ok" = 1 ] || { echo "LAUNCHER: never got the lock" >&2; exit 9; }
