#!/bin/bash
# Box-side ps-word table: idle samples, then samples across 30 s of a proven
# ANE encoder loop. Only the always-on pmgr block is read: the kext gate
# waits on ane_sys_mpm, which macOS never raises, so engine ranges stay gated.
OUT=/tmp/pstable-$(date +%H%M%S)
sudo -n mkdir -p "$OUT" && sudo -n chown "$(id -u)" "$OUT"
LOG="$OUT/run.log"
say() { echo "$(date +%T.%N | cut -c1-12) $*" >> "$LOG"; }
anep() { sudo -n timeout 8 powermetrics --samplers cpu_power -i 500 -n 1 2>/dev/null | grep -i "ANE Power"; }
dump() {
  sudo -n mkdir -p "$OUT/$1"
  say "$1 $(anep)"
  sudo -n ~/ane-cap2/aneregdump "$OUT/$1" 2>&1 | grep -E "^ps " >> "$LOG"
  sudo -n cp "$OUT/$1/pmgr-ps.bin" "$OUT/$1.pmgr" 2>/dev/null
}
say "start load=$(sysctl -n vm.loadavg)"
pgrep -f encoder_bench >/dev/null && { say "encoder already running - abort idle set"; exit 1; }
for i in 1 2 3; do dump idle$i; sleep 2; done
cd ~/m2bench || exit 1
./encoder_bench ./encoder.mlpackage ./feat_f32.bin ./mask_i32.bin ane 5 900 "$OUT/enc.bin" > "$OUT/enc.log" 2>&1 &
EP=$!
say "encoder pid $EP"
for i in $(seq 1 30); do
  sleep 2
  P=$(anep); say "wait t=$((i*2))s $P"
  case "$P" in *"ANE Power: 0 mW"*|"") ;; *) break ;; esac
done
for i in $(seq 1 10); do dump load$i; sleep 1; done
kill -0 "$EP" 2>/dev/null && say "encoder still running after load set" || say "encoder ended before load set finished"
wait "$EP"; say "encoder rc=$?"
sleep 3
dump after1
sudo -n chmod -R a+r "$OUT"
say "done"
