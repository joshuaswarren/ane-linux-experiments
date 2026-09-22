#!/bin/sh
# m2proxy-linkcheck — one-line USB proxy link state for the proxy-host -> m2-host m1n1 link.
# Prints: port roles | partners (usb_mode) | root hubs | ttyACM device.
# Exit 0 only when the m1n1 proxy gadget (ttyACM*) is enumerated.
for p in /sys/class/typec/port*; do
    [ -d "$p" ] || continue
    role=$(cat "$p/data_role" 2>/dev/null)
    if [ -d "$p-partner" ]; then
        mode=$(cat "$p-partner/usb_mode" 2>/dev/null)
        ptn="$ptn ${p##*/}=$mode"
    fi
    roles="$roles ${p##*/}:$role"
done
hubs=$(ls /sys/bus/usb/devices/ 2>/dev/null | grep -c "^usb" )
acm=$(ls /dev/ttyACM* 2>/dev/null | head -1)
echo "roles:${roles:-none} partners:${ptn:-none} roothubs:$hubs ttyACM:${acm:-none}"
[ -n "$acm" ] && exit 0
exit 1
