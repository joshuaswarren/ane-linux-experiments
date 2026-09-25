#!/bin/bash
# Poll M2 macOS; when up, restore stock boot.bin, verify, check default boot, reboot to Linux.
set -u
J="ssh -J macstudio -i $HOME/.ssh/id_rsa_2025 -o IdentitiesOnly=yes -o ConnectTimeout=10 -o BatchMode=yes"
H=$M2_MACOS_HOST
end=$((SECONDS + ${1:-3600}))
until timeout 25 $J $H 'hostname; sw_vers -productVersion; uptime' 2>/dev/null; do
	[ $SECONDS -ge $end ] && { echo "macOS not up by deadline $(date -u +%T)"; exit 1; }
	sleep 20
done
echo "macOS up $(date -u +%T)"
scp -q -J macstudio -i "$HOME/.ssh/id_rsa_2025" -o IdentitiesOnly=yes /tmp/m2kstart/restore-stock.sh $H:/tmp/restore-stock.sh || exit 1
timeout 120 $J $H 'sudo -n bash /tmp/restore-stock.sh disk0s4' || { echo "RESTORE FAILED, not rebooting"; exit 1; }
boot=$(timeout 30 $J $H 'd=$(bless --getBoot); echo "$d $(diskutil info "$d" | awk -F": *" "/Volume Name/{print \$2}")"' 2>&1)
echo "getBoot=$boot"
case "$boot" in
/dev/*" Omarchy") ;;
*) echo "default boot is not the Omarchy stub, not rebooting"; exit 2 ;;
esac
echo "reboot to Linux issued $(date -u +%T)"
timeout 30 $J $H 'sudo -n shutdown -r now' 2>&1 | tail -2
