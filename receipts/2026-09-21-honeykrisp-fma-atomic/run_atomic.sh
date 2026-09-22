#!/usr/bin/env bash
# Run the atomicOr lane-loss repro N rounds; print one line per failing round.
# Usage: run_atomic.sh [rounds]
cd "$(dirname "$0")"
rounds="${1:-150}"
export VK_DRIVER_FILES="${2:-tip.icd.json}"
[ -f in16.bin ] || printf '\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0' > in16.bin
fail=0
for r in $(seq 1 "$rounds"); do
  ./compute_runner atomic_lane.spv in16.bin atomic-out.bin 262144 256 2>/dev/null
  bad=$(python3 - <<'PY'
import struct
d = open('atomic-out.bin','rb').read()
bad = 0
for w in range(16384):
    e = ((0x0400 + 2*w + 1) << 16) | (0x0400 + 2*w)
    v = struct.unpack_from('<I', d, 4*w)[0]
    if v != e:
        bad += 1
print(bad)
PY
)
  if [ "$bad" != "0" ]; then
    echo "round $r FAIL bad_words=$bad"
    cp atomic-out.bin "atomic-fail-r$r.bin"
    fail=$((fail+1))
  fi
done
echo "ATOMIC-DONE rounds=$rounds failing_rounds=$fail"
