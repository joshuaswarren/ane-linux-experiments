#!/bin/sh
# m1n1 proxy watcher — on the proxy host, watching the parked m2-host (T6021 ANE bring-up).
# Waits for the m1n1 USB serial gadget (VID 0x1209 PID 0x316d, /dev/ttyACM*),
# then runs the RUNBOOK checklist (a)-(e), teeing everything to the receipt
# dir and scp'ing it to the workstation. Durable under /var/tmp/m2proxy/.
set -u
M2_VID=1209
M2_PID=316d
M2ROOT=/var/tmp/m2proxy
M2VENV=/var/tmp/m2proxy-venv
M2SCRIPTS=$M2ROOT/scripts
M2PY=$M2VENV/bin/python
M2FW=$M2ROOT/selene/t602x_ane0_fw_selene_rc4x.macho
M2RECEIPTS=$M2ROOT/receipts/2026-09-22-m2-proxyclient-prep
M2STATE=$M2ROOT/state
WORKSTATION=workstation   # scp target for receipts; set per deployment
WSRECEIPTS=~/src/ane-linux-experiments/receipts/2026-09-22-m2-proxyclient-prep

mkdir -p "$M2RECEIPTS" "$M2STATE"

last_dev=""
while :; do
    dev=""
    for d in /dev/ttyACM* /dev/ttyUSB*; do
        [ -e "$d" ] || continue
        sysdev=$(udevadm info -q path "$d" 2>/dev/null)
        [ -n "$sysdev" ] || continue
        vid=$(cat "/sys${sysdev}/../idVendor" 2>/dev/null || \
              cat "/sys${sysdev}/../../idVendor" 2>/dev/null)
        pid=$(cat "/sys${sysdev}/../idProduct" 2>/dev/null || \
              cat "/sys${sysdev}/../../idProduct" 2>/dev/null)
        if [ "$vid" = "$M2_VID" ] && [ "$pid" = "$M2_PID" ]; then
            dev=$d
            break
        fi
    done

    if [ -n "$dev" ] && [ "$dev" != "$last_dev" ]; then
        stamp=$(date +%Y%m%d-%H%M%S)
        log=$M2RECEIPTS/run-$stamp.log
        echo "$(date -Iseconds) m1n1 proxy appeared at $dev" | tee -a "$log"
        cd "$M2SCRIPTS" || exit 1
        {
            echo "=== checklist (a)-(e), $stamp ==="
            echo "--- (a0) constants ---"
            "$M2PY" t6021_consts.py
            echo "--- (a1) device ---"
            echo "M1N1DEVICE=$dev"
            echo "--- (a2) dry-run reads-only ---"
            M1N1DEVICE=$dev "$M2PY" ane_bringup.py --dry-run
            echo "--- (a3) mock sanity ---"
            "$M2PY" ane_bringup.py --mock --fw "$M2FW"
            echo "--- (a4) THE RUN ---"
            M1N1DEVICE=$dev "$M2PY" ane_bringup.py --fw "$M2FW"
            rc=$?
            echo "=== done rc=$rc at $(date -Iseconds) ==="
        } >>"$log" 2>&1
        scp -q "$log" "$WORKSTATION:$WSRECEIPTS/" || true
        # Return-to-Omarchy: once the checklist ran (or aborted), chainload the
        # pre-proxy boot.bin so m2-host boots Omarchy instead of staying parked.
        # omarchy-now.sh exits non-zero BEFORE stopping the watcher if the
        # return image is missing or sha-mismatched, so the watcher survives.
        if [ -x "$M2ROOT/omarchy-now.sh" ]; then
            echo "=== return-to-Omarchy ===" >>"$log"
            "$M2ROOT/omarchy-now.sh" --chainload --image /boot/efi/m1n1/boot.bin >>"$log" 2>&1
            rc2=$?
            [ $rc2 -eq 0 ] || echo "omarchy-now rc=$rc2 (image missing/sha mismatch/device gone; watcher stays up)" >>"$log"
        last_dev=$dev
        fi
    elif [ -z "$dev" ]; then
        last_dev=""
    fi
    sleep 2
done
