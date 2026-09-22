#!/bin/sh
# m2proxy-linkcheck - one-line USB proxy link state (avoids typec attrs that WARN on read).
for p in /sys/class/typec/port*; do
    [ -d "$p" ] || continue
    role=$(cat "$p/data_role" 2>/dev/null)
    if [ -d "$p-partner" ]; then ptn="$ptn ${p##*/}=attached"; fi
    roles="$roles ${p##*/}:$role"
done
hubs=$(ls /sys/bus/usb/devices/ 2>/dev/null | grep -c "^usb")
acm=$(ls /dev/ttyACM* 2>/dev/null | head -1)
echo "roles:${roles:-none} partners:${ptn:-none} roothubs:$hubs ttyACM:${acm:-none}"
[ -n "$acm" ] && exit 0
exit 1
