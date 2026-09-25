#!/bin/bash
# Restore stock boot.bin on the Omarchy stub from macOS - one set -euo pipefail
# script with before/after hash checks. ESP unmounted before exit.
set -euo pipefail
ESP_DEV="${1:-disk0s4}"
BAK=$HOME/m2stub-backup-20260923-0901
STOCK_SHA=a3f533b9879cd0129d78d3d73715b3c9214e297459c7661c4195a9c2bc2683b2
echo "== 1. backup integrity"
(cd / && shasum -a 256 -c "$BAK/shas.txt") || { echo "BACKUP CORRUPT"; exit 1; }
echo "== 2. mount ESP read-write"
sudo -n diskutil mount "$ESP_DEV" >/dev/null
ESP=$(diskutil info "$ESP_DEV" | awk -F': *' '/Mount Point/{print $2}')
[ -f "$ESP/m1n1/boot.bin" ] || { echo "ESP $ESP_DEV has no m1n1/boot.bin"; exit 1; }
echo "== 3. before"
BEFORE=$(shasum -a 256 "$ESP/m1n1/boot.bin" | cut -d' ' -f1)
echo "before=$BEFORE (expect aneresv 31bd993e)"
cp "$ESP/m1n1/boot.bin" "$BAK/boot.bin.aneresv-$(echo "$BEFORE" | cut -c1-8)"
echo "== 4. restore"
cp "$BAK/boot.bin.stock" "$ESP/m1n1/boot.bin"
sync
AFTER=$(shasum -a 256 "$ESP/m1n1/boot.bin" | cut -d' ' -f1)
echo "after=$AFTER"
[ "$AFTER" = "$STOCK_SHA" ] || { echo "RESTORE MISMATCH"; exit 1; }
cmp "$BAK/boot.bin.stock" "$ESP/m1n1/boot.bin" && echo "cmp: byte-identical"
echo "== 5. unmount ESP"
sudo -n diskutil unmount "$ESP_DEV"
diskutil info "$ESP_DEV" | grep -q 'Mounted: *Yes' && { echo "UNMOUNT FAILED"; exit 1; }
echo "RESTORED-STOCK-OK before=$BEFORE after=$AFTER"
