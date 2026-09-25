#!/bin/bash
set -u
cd /var/tmp/ascdbg
PA=0x10098c40000
r() { echo "$*" | sudo -n ./ascdbg.sh cmds 2>&1 | grep -oE '[0-9a-f]{8,16}$' | tail -1; }
snap() {
  local s=""
  for o in 0x1840048 0x184004c 0x1840050 0x1840054 0x1840058 0x184005c 0x1840060 0x1840064; do s="$s $(r r32 $o)"; done
  echo "$1 scratch0-7:$s status=$(r r32 0x1400048) a2i=$(r r32 0x1408110) i2a=$(r r32 0x1408114) recv0=$(r r64 0x1408830) slot0w1=$(r phys $((PA+4)) 1) irq53=$(awk '/mailbox-recv/{s=0;for(i=2;i<=13;i++)s+=$i;print s}' /proc/interrupts)"
}
snap pre
echo "--- publish cmd table base: SCRATCH0=0x1fb08000 SCRATCH1=0"
echo "w32 0x1840048 0x1fb08000" | sudo -n ./ascdbg.sh cmds >/dev/null 2>&1
echo "w32 0x184004c 0x0" | sudo -n ./ascdbg.sh cmds >/dev/null 2>&1
echo "--- WAKE: SCRATCH7=0xf7fbdff9"
echo "w32 0x1840064 0xf7fbdff9" | sudo -n ./ascdbg.sh cmds >/dev/null 2>&1
snap t0
START=$(date +%s)
for t in 1 2 5 10 20 30 45 60; do
  sleep_to=$t
  while [ "$(( $(date +%s) - START ))" -lt "$sleep_to" ] 2>/dev/null; do sleep 0.2; done
  snap t$t
done
