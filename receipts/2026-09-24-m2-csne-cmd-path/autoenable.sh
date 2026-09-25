#!/bin/bash
# Parent with AUTO_ENABLE, leaves with plain 0xf, then working order.
set -u
cd /var/tmp/ascdbg
sudo -n insmod ane_ascdbg.ko
one() { echo "$*" | sudo -n ./ascdbg.sh cmds >/dev/null 2>&1; }
val() { echo "$*" | sudo -n ./ascdbg.sh cmds 2>&1 | grep -oE '[0-9a-f]{8}$' | tail -1; }

echo "--- parent AUTO_ENABLE"
one vw32 0x3e0 0x1000000f
sleep 0.5
echo "parent = $(val vr32 0x3e0)"

echo "--- leaves 0xf"
for o in 0x8000 0x8008 0x8010 0x8018; do one vw32 $o 0xf; done
sleep 0.5
echo "leaf 0x8008 = $(val vr32 0x8008)"

echo "--- TCR15 x3"
for b in 0x1800000 0x1810000 0x1820000; do one w32 $((b+0x103c)) 2; done
sudo -n rmmod ane_ascdbg

echo "--- map only"
cd /var/tmp/ane-rtb2
sudo -n insmod ane_t6021_rtclient_fixed.ko fw_cache_test=1 fw_map_only=1
echo "MAP:$?"

echo "--- release"
cd /var/tmp/ascdbg
sudo -n insmod ane_ascdbg.ko
for i in 0 1 2 3 4 5 6 7; do one w32 $((0x1840050 + 4*i)) 0; done
one w32 0x1400044 0
one w32 0x1400044 0x10
sleep 5
echo "status = $(val r32 0x1400048)"
