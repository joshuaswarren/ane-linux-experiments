#!/bin/bash
# ParakeetTransport: wait for the commit-2 rebuild, then run the two
# after-passes (shm transport).
set -euo pipefail
for i in $(seq 1 240); do
  if grep -q "\[receipt\] worker:" /var/tmp/pt/logs/rebuild2.log 2>/dev/null; then
    break
  fi
  sleep 5
done
echo "commit-2 rebuild done at $(date -Iseconds)"
tail -4 /var/tmp/pt/logs/rebuild2.log
bash /var/tmp/jwm1-pt/run.sh after-1
bash /var/tmp/jwm1-pt/run.sh after-2
echo "after passes complete $(date -Iseconds)"
