#!/bin/bash
# run-cachedread-matrix-jwm1.sh — map_mode A/B byte-identity battery on jwm1
# (T8103). Port of jw16's run-cachedread-matrix.sh. MUST run inside the device
# window: /tmp/m1-gpu.lock held by the caller, ane refcnt 0. One module swap
# (original 96d5a88 -> map_mode variant 82a18af); every mode switch after that
# is a runtime param write. Every verify2 must produce hashes and be STABLE
# within-process; mode hashes must equal the original-module baseline
# byte-for-byte.
set -uo pipefail
P=/var/tmp/ane-submit-probe
PROBE=$P/ane-probe2
OUT=$P/cachedread-out
ORIG_KO=/home/joshuawarren/src/omarchy-ane-lifecycle-rebase/ane/ane.ko
VARIANT_KO=$P/ane-82a18af.ko
CTRL_BUNDLE=$P/bundle
RX=/var/tmp/jwm1-ep-bisect/bundles-sf
PROGS="ctrl0=$CTRL_BUNDLE/program-0.anec ctrl1=$CTRL_BUNDLE/program-1.anec a0=$RX/island-attn-a-kt/program-0.anec a1=$RX/island-attn-a-kt/program-1.anec sel=$RX/island-select-8head/program-0.anec pv=$RX/island-pv/program-0.anec"
DECOMPS="a0=$RX/island-attn-a-kt/program-0.anec a1=$RX/island-attn-a-kt/program-1.anec sel=$RX/island-select-8head/program-0.anec pv=$RX/island-pv/program-0.anec"
mkdir -p "$OUT"

wedge_count() { sudo -n dmesg | grep -cE 'tm completion failed|preserving resources|tm execution failed' || true; }
check() { # label — abort on wedge delta
  local now; now=$(wedge_count)
  if [ "$now" != "${LAST_WEDGE:-0}" ]; then
    echo "WEDGE DETECTED at $1 (dmesg wedge lines: $now)"
    exit 42
  fi
  LAST_WEDGE=$now
  echo "[ok] $1"
}

mode_set() {
  echo "$1" | sudo -n tee /sys/module/ane/parameters/map_mode >/dev/null
  echo "map_mode=$(cat /sys/module/ane/parameters/map_mode)"
}

# run_v2 <phase> <name> <anec> <reps> — run verify2, save hash lines, gate.
run_v2() {
  local phase=$1 n=$2 f=$3 reps=$4
  local out; out=$($PROBE verify2 "$f" - "$reps" 2>&1)
  echo "-- verify2 [$phase] $n reps=$reps"
  echo "$out" | grep -E 'fnv1a|verify2|failed'
  echo "$out" | grep 'fnv1a=' | sed "s/^/[$phase:$n] /" >> "$OUT/all-hashes.txt"
  echo "$out" | grep 'fnv1a=' > "$OUT/hashes.$phase.$n.txt"
  echo "$out" | grep -q 'fnv1a=' || { echo "NO HASHES for [$phase] $n — probe failed"; exit 43; }
  echo "$out" | grep -q ' STABLE' || { echo "DIVERGED within-process for [$phase] $n"; exit 44; }
}

# cmp_hashes <phase-a> <phase-b> <name> — byte-identity across phases.
cmp_hashes() {
  if diff -q "$OUT/hashes.$1.$3.txt" "$OUT/hashes.$2.$3.txt" >/dev/null; then
    echo "[identical] $3: $1 == $2"
  else
    echo "[MISMATCH] $3: $1 != $2"
    diff "$OUT/hashes.$1.$3.txt" "$OUT/hashes.$2.$3.txt" || true
    exit 45
  fi
}

LAST_WEDGE=0
echo "== step 0: state $(date -Is)"
uname -r
echo "refcnt: $(grep '^ane ' /proc/modules)"
: > "$OUT/all-hashes.txt"

echo "== step 1: original module baseline (WC+NC)"
mode_set 2>/dev/null || true
for kv in $PROGS; do run_v2 orig "${kv%%=*}" "${kv#*=}" 8; done
check "orig verify2 battery"
: > "$OUT/decomp.orig.txt"
for kv in $DECOMPS; do
  n=${kv%%=*}; f=${kv#*=}
  echo "-- decomp $n reps=20" | tee -a "$OUT/decomp.orig.txt"
  $PROBE decomp "$f" 20 2>&1 | grep -E 'us\)' | tee -a "$OUT/decomp.orig.txt"
done
check "orig decomp battery"

echo "== step 2: swap to variant module (map_mode=0 must be inert)"
sudo -n rmmod ane
sudo -n insmod "$VARIANT_KO"
sleep 1
echo "module version: $(modinfo -F version "$VARIANT_KO" 2>/dev/null)"
[ -f /sys/module/ane/parameters/map_mode ] || { echo "map_mode param MISSING"; exit 1; }
mode_set 0
for kv in $PROGS; do run_v2 var0 "${kv%%=*}" "${kv#*=}" 8; done
for kv in $PROGS; do cmp_hashes orig var0 "${kv%%=*}"; done
check "variant mode0 inert battery"

echo "== step 3: mode 1 (WC CPU + IOMMU_CACHE descriptors) — attribution"
mode_set 1
for kv in "ctrl0=$CTRL_BUNDLE/program-0.anec" "a0=$RX/island-attn-a-kt/program-0.anec"; do
  run_v2 mode1 "${kv%%=*}" "${kv#*=}" 8
done
for kv in "ctrl0=$CTRL_BUNDLE/program-0.anec" "a0=$RX/island-attn-a-kt/program-0.anec"; do
  cmp_hashes orig mode1 "${kv%%=*}"
done
check "mode1"

echo "== step 4: mode 3 (cached CPU + IOMMU_CACHE) — candidate"
mode_set 3
for kv in $PROGS; do run_v2 mode3 "${kv%%=*}" "${kv#*=}" 16; done
for kv in $PROGS; do cmp_hashes orig mode3 "${kv%%=*}"; done
check "mode3 verify2 battery (reps=16, alternating patterns)"
: > "$OUT/decomp.mode3.txt"
for kv in $DECOMPS; do
  n=${kv%%=*}; f=${kv#*=}
  echo "-- decomp $n reps=20" | tee -a "$OUT/decomp.mode3.txt"
  $PROBE decomp "$f" 20 2>&1 | grep -E 'us\)' | tee -a "$OUT/decomp.mode3.txt"
done
check "mode3 decomp battery"
echo "== mode3 floor sanity (submit floor must not move)"
$PROBE floor "$CTRL_BUNDLE/program-0.anec" 200 2>&1 | grep "us)"
check "mode3 floor"

echo "== step 5: restore original module"
if [ "${HOLD:-0}" = "1" ]; then
  echo "HOLD=1 — skipping restore; caller owns module state from here (variant loaded, map_mode=$(cat /sys/module/ane/parameters/map_mode))"
  exit 0
fi
mode_set 0 || true
sudo -n rmmod ane
sudo -n insmod "$ORIG_KO"
sleep 1
echo "restored: $(grep '^ane ' /proc/modules) version=$(cat /sys/module/ane/version 2>/dev/null)"
[ ! -e /sys/module/ane/parameters/map_mode ] && echo "[ok] map_mode param gone (original module back)"
check "module restored"

echo "== done; artifacts in $OUT"
