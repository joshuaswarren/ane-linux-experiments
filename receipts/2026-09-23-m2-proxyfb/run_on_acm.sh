#!/bin/bash
# Wait for the M2 m1n1 proxy ACM, then: probe, read-only ANE dump, chainload stock boot.bin.
set -u
PC=$HOME/m2proxy/m1n1-1.6.1/proxyclient
STOCK=$HOME/m2proxy/boot-stock-a3f533b9.bin
DEADLINE=$((SECONDS + ${1:-1500}))
cd "$PC" || exit 1
[ "$(sha256sum "$STOCK" | cut -c1-8)" = a3f533b9 ] || { echo "stock image sha mismatch"; exit 1; }
dev=""
while [ $SECONDS -lt $DEADLINE ]; do
	if [ -e /dev/ttyACM0 ]; then dev=/dev/ttyACM0; break; fi
	sleep 0.5
done
[ -n "$dev" ] || { echo "no ACM by deadline $(date -u +%T)"; exit 1; }
echo "ACM $dev at $(date -u +%T)"
sleep 1
run() { sudo -n env PYTHONPATH=$HOME/m2proxy/pylib:. M1N1DEVICE=$dev "$@"; }
timeout 180 run python3 $HOME/m2proxy/m2_proxy_dump.py
echo "dump rc=$? at $(date -u +%T)"
timeout 180 run python3 tools/chainload.py -r "$STOCK"
echo "chainload rc=$? at $(date -u +%T)"
