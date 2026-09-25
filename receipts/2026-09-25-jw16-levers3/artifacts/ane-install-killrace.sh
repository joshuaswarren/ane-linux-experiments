#!/usr/bin/env bash
# ANE step (Main directive): install omarchy-ane 5a22ee3 (ane_boost) persistently
# on T6001, reload it, then run the kill-race battery (test/kill-race, N
# iterations) and the guard check. ANE only: no GPU lock, llm-inference untouched.
set -uo pipefail
W=/var/tmp/levers3/omarchy-ane
K=/usr/lib/modules/$(uname -r)/updates/ane.ko
N=${N:-10}
echo "== before: $(modinfo -F version $K) installed; loaded $(cat /sys/module/ane/version 2>/dev/null || echo none); users=$(sudo -n lsof -t /dev/accel/accel0 2>/dev/null | tr '\n' ' ')"
[ -e "$K.a9a5f60" ] || sudo -n cp -a "$K" "$K.a9a5f60"
sudo -n cp "$W/ane/ane.ko" "$K" && sudo -n depmod -a && echo "installed: $(modinfo -F version $K) sha=$(sha256sum $K | cut -c1-16)"
sudo -n rmmod ane && sudo -n modprobe ane && sleep 2
echo "loaded: $(cat /sys/module/ane/version) boost_idle_ms=$(cat /sys/module/ane/parameters/boost_idle_ms) map_mode=$(cat /sys/module/ane/parameters/map_mode) dart_contain=$(cat /sys/module/ane/parameters/dart_contain)"
ls -la /dev/accel/accel0
sudo -n dmesg | grep -i "ane " | tail -6
echo "== kill-race x$N =="
cd "$W/test/kill-race" && make -s all && SECONDS=0 && ./main.out "$N" 2>&1 | tee "$O/kill-race.log"; echo "kill-race rc=${PIPESTATUS[0]} in ${SECONDS}s"
sudo -n dmesg | tail -20 > "$O/dmesg-after-killrace.txt"
grep -ci "wedge\|error\|fault" "$O/dmesg-after-killrace.txt" | sed 's/^/dmesg wedge|error|fault lines: /'
echo "== guard check =="
cd "$W/test/guard" && make -s check 2>&1 | tail -3
echo "loaded after battery: $(cat /sys/module/ane/version) boost_idle_ms=$(cat /sys/module/ane/parameters/boost_idle_ms)"
echo ANE_INSTALL_DONE
