#!/bin/bash
# Box-side: sustained ANE encoder loop, activity proof, then the kext poll.
# Runs detached; everything goes to $OUT/run.log so an SSH drop loses nothing.
OUT=/tmp/sustain-$(date +%H%M%S)
sudo -n mkdir -p "$OUT/dump" && sudo -n chown "$(id -u)" "$OUT"
LOG="$OUT/run.log"
say() { echo "$(date +%T.%N | cut -c1-12) $*" >> "$LOG"; }
say "start load=$(sysctl -n vm.loadavg)"
cd ~/m2bench || exit 1
./encoder_bench ./encoder.mlpackage ./feat_f32.bin ./mask_i32.bin ane 5 700 "$OUT/enc.bin" > "$OUT/enc.log" 2>&1 &
EP=$!
say "encoder pid $EP"
for i in $(seq 1 30); do
  sleep 2
  kill -0 "$EP" 2>/dev/null || { say "encoder exited early"; break; }
  P=$(sudo -n timeout 8 powermetrics --samplers cpu_power -i 500 -n 1 2>/dev/null | grep -i "ANE Power")
  say "t=$((i*2))s $P"
  case "$P" in *"ANE Power: 0 mW"*|"") ;; *) say "ANE active"; break ;; esac
done
ioreg -lw0 -r -c H11ANEIn | grep -E "CurrentPowerState" | head -n 1 >> "$LOG"
say "poll start"
sudo -n ~/ane-cap2/aneregdump "$OUT/dump" >> "$LOG" 2>&1
say "poll rc=$?"
sudo -n timeout 8 powermetrics --samplers cpu_power -i 500 -n 1 2>/dev/null | grep -i "ANE Power" >> "$LOG"
kill -0 "$EP" 2>/dev/null && say "encoder still running after poll" || say "encoder gone after poll"
wait "$EP"; say "encoder rc=$?"
tail -n 4 "$OUT/enc.log" >> "$LOG"
say "done"
