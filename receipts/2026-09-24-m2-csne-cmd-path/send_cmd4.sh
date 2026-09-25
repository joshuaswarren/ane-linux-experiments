#!/bin/bash
set -u
cd /var/tmp/ascdbg
sudo -n insmod ane_ascdbg.ko
one() { echo "$*" | sudo -n ./ascdbg.sh cmds >/dev/null 2>&1; }
val() { echo "$*" | sudo -n ./ascdbg.sh cmds 2>&1 | grep -oE '[0-9a-f]{8}$' | tail -1; }
echo "--- VENC"
one vw32 0x3e0 0x1000000f; sleep 0.5
for o in 0x8000 0x8008 0x8010 0x8018; do one vw32 $o 0xf; done; sleep 0.4
echo "leaf = $(val vr32 0x8008)"
echo "--- TCR15 x3"
for b in 0x1800000 0x1810000 0x1820000; do one w32 $((b+0x103c)) 2; done
sudo -n rmmod ane_ascdbg
echo "--- map"
cd /var/tmp/ane-rtb2
sudo -n insmod ane_t6021_rtclient_fixed.ko fw_cache_test=1 fw_map_only=1
echo "MAP:$?"
echo "--- release"
cd /var/tmp/ascdbg
sudo -n insmod ane_ascdbg.ko
for i in 0 1 2 3 4 5 6 7; do one w32 $((0x1840050+4*i)) 0; done
one w32 0x1400044 0
one w32 0x1400044 0x10
sleep 3
echo "status = $(val r32 0x1400048)"
python3 -c "
import subprocess
def phys(pa,n):
    out=subprocess.run(['./ascdbg.sh','cmds'],input='phys %s %d\n'%(hex(pa),n),capture_output=True,text=True).stdout
    vals=[]
    for l in out.splitlines():
        p=l.split()
        if len(p)==4 and p[0]=='phys': vals.append(int(p[3],16))
    return vals
nz=sum(1 for base in range(0x100017e8000,0x10001838000,0x400) for v in phys(base,256) if v)
print('bss nonzero:',nz)
"
sudo -n rmmod ane_ascdbg
echo "--- four-command send"
sudo -n insmod /var/tmp/ascdbg/ane_csne_pmu.ko
echo "CSNE:$?"
sudo -n dmesg | grep 'csne-pmu: REPLY\|csne-pmu: done\|csne-pmu: slot' | tail -10
