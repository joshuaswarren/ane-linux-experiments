#!/bin/bash
# Box-side working-state engine capture with the frozen kext (932d3b9b) and
# the runtime ranges.txt in ~/ane-cap3. Idle dump first (engine ranges gated),
# then gated attempts during a proven ANE encoder loop, then an after dump.
KIT=~/ane-cap3
OUT=/tmp/cap3-$(date +%H%M%S)
sudo -n mkdir -p "$OUT" && sudo -n chown "$(id -u)" "$OUT"
LOG="$OUT/run.log"
say() { echo "$(date +%T.%N | cut -c1-12) $*" >> "$LOG"; }
anep() { sudo -n timeout 8 powermetrics --samplers cpu_power -i 500 -n 1 2>/dev/null | grep -i "ANE Power"; }
dump() {
  sudo -n mkdir -p "$OUT/$1"
  say "$1 $(anep)"
  sudo -n "$KIT/aneregdump" "$OUT/$1" "$KIT/ranges.txt" >> "$LOG" 2>&1
  local rc=$?
  say "$1 rc=$rc"
  return $rc
}
say "start load=$(sysctl -n vm.loadavg) boottime=$(sysctl -n kern.boottime | sed 's/.*} //')"
shasum -a 256 /Library/Extensions/ANERegDump.kext/Contents/MacOS/ANERegDump >> "$LOG"
pgrep -f encoder_bench >/dev/null && { say "encoder already running - abort"; exit 1; }
dump idle
cd ~/m2bench || exit 1
./encoder_bench ./encoder.mlpackage ./feat_f32.bin ./mask_i32.bin ane 5 900 "$OUT/enc.bin" > "$OUT/enc.log" 2>&1 &
EP=$!
say "encoder pid $EP"
for i in $(seq 1 30); do
  sleep 2
  P=$(anep); say "wait t=$((i*2))s $P"
  case "$P" in *"ANE Power: 0 mW"*|"") ;; *) break ;; esac
done
ok=0
for i in $(seq 1 8); do
  dump load$i && ok=$((ok + 1))
  [ "$ok" -ge 2 ] && break
  sleep 1
done
say "gated attempts done, passes=$ok"
kill -0 "$EP" 2>/dev/null && say "encoder still running" || say "encoder ended early"
wait "$EP"; say "encoder rc=$?"
grep -o '"placement":{[^}]*}' "$OUT/enc.log" >> "$LOG"
sleep 3
dump after
sudo -n chmod -R a+r "$OUT"
say "done"
