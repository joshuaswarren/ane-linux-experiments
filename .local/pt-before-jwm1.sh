#!/bin/bash
# ParakeetTransport: wait for the rebuild to finish, then run the two
# before-passes (instrumentation-only wheel, inline transport).
set -euo pipefail
for i in $(seq 1 120); do
  if grep -q "\[receipt\] worker:" /var/tmp/pt/logs/rebuild.log 2>/dev/null; then
    break
  fi
  sleep 5
done
echo "rebuild done at $(date -Iseconds)"
tail -4 /var/tmp/pt/logs/rebuild.log
bash /var/tmp/jwm1-pt/run.sh before-1
bash /var/tmp/jwm1-pt/run.sh before-2
echo "before passes complete $(date -Iseconds)"
