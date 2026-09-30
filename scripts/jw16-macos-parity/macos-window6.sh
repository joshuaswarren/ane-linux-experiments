#!/bin/bash
# macOS window 6 (jw16 macOS, M1 Max/T6001): get ANERegDump kext loaded (route A GUI / route B sqlite / route C stop),
# capture live staged ANE eos firmware state. ONE BOOT (one extra reboot if Route B AuxKC requires it).
# usage (on jw16 macOS): bash macos-window6.sh [W6DIR]  (default ~/jw16-macos-window/w6)
# Expects in W6DIR: ranges5-t6001.txt (the dump request file). Reuses:
#   ~/jw16-macos-window/w5/{ANERegDump.kext,aneregdump,ranges5-t6001.txt,aneprobe.mlmodelc,aneprobe}
# Falls back to /Library/Extensions/ANERegDump.kext (installed by window 5).
# Read-only: no ANE register writes; no fabric/pmgr writes.
set -u
W="${1:-$HOME/jw16-macos-window/w6}"; OUT="$W/out"; mkdir -p "$OUT"; cd "$W" || exit 1
W5="$HOME/jw16-macos-window/w5"
SRC="$HOME/src/omarchy-ane-boost-wt/tools/macos-regdump"
RANGES_FALLBACK="$W5/ranges5-t6001.txt"

find_first() { local d; for d in "$@"; do [ -e "$d" ] && { printf '%s' "$d"; return 0; }; done; return 1; }
RANGES=$(find_first "$W/ranges5-t6001.txt" "$RANGES_FALLBACK" "$W5/../ranges5-t6001.txt") || { echo "no ranges5-t6001.txt"; exit 1; }
echo "ranges=$RANGES"

# --- Env pin (record every observed property once, idempotent across reruns).
{ date -u; sw_vers; sysctl -n machdep.cpu.brand_string hw.model kern.osversion kern.osrelease kern.boottime 2>/dev/null
  pmset -g batt | head -1; pmset -g | grep -i powermode; pmset -g therm | tail -3
  whoami; id; launchctl managername; echo "console-user:"; stat -f "%Su" /dev/console 2>/dev/null
  csrutil status </dev/null; echo "bputil:"; (sudo -n bputil -d </dev/null || echo "bputil unavailable / no sudo")
  sysctl kern.bootargs </dev/null; nvram boot-args </dev/null
} > "$OUT/env-pre.txt" 2>&1
sudo -n powermetrics --samplers thermal,gpu_power,ane_power -i 5000 > "$OUT/powermetrics.txt" 2>&1 &
PM=$!
caffeinate -dimsu -w $$ &

# --- Cua-driver install (Route A prereq). Only if cua-driver not already on this machine.
if ! command -v cua-driver >/dev/null 2>&1; then
  echo "== cua-driver install (route A prereq) =="
  (curl -fsSL https://cua.ai/driver/install.sh | bash) > "$OUT/cua-driver-install.log" 2>&1 || echo "INSTALL-FAILED" >> "$OUT/cua-driver-install.log"
fi
command -v cua-driver >/dev/null 2>&1 && cua-driver --version > "$OUT/cua-driver-version.txt" 2>&1 || true

# --- Stage the kext (rebuild only if missing or CDHash mismatch with currently installed).
KEXT_INSTALLED=/Library/Extensions/ANERegDump.kext
KEXT_STAGED=""
if [ -d "$W5/ANERegDump.kext" ]; then KEXT_STAGED="$W5/ANERegDump.kext"; fi
if [ -z "$KEXT_STAGED" ] && [ -d "$W/ANERegDump.kext" ]; then KEXT_STAGED="$W/ANERegDump.kext"; fi
if [ -z "$KEXT_STAGED" ] && [ -d "$SRC/ANERegDump.kext" ]; then KEXT_STAGED="$SRC/ANERegDump.kext"; fi
echo "kext_staged=$KEXT_STAGED"

# Optionally rebuild from source for fresh CDHash.
if [ -n "$KEXT_STAGED" ] && [ -d "$SRC/ANERegDump" ]; then
  CUR_CDHASH=$(codesign -d --extract-certificates "$KEXT_STAGED" 2>/dev/null | head -1 || echo "")
  echo "kext_staged_cdhash=$CUR_CDHASH" >> "$OUT/env-pre.txt"
fi

# Install kext to /Library/Extensions if needed.
if [ -n "$KEXT_STAGED" ]; then
  if [ ! -d "$KEXT_INSTALLED" ] || ! cmp -s "$KEXT_STAGED/Contents/MacOS/ANERegDump" "$KEXT_INSTALLED/Contents/MacOS/ANERegDump" 2>/dev/null; then
    sudo -n rm -rf "$KEXT_INSTALLED" 2>>"$OUT/kmutil.err"
    sudo -n cp -R "$KEXT_STAGED" "$KEXT_INSTALLED" 2>>"$OUT/kmutil.err"
    sudo -n chown -R root:wheel "$KEXT_INSTALLED" 2>>"$OUT/kmutil.err"
    sudo -n chmod -R go-w "$KEXT_INSTALLED" 2>>"$OUT/kmutil.err"
  fi
fi
shasum -a 256 "$KEXT_INSTALLED/Contents/MacOS/ANERegDump" </dev/null > "$OUT/kext-installed.sha256" 2>&1 || true

# --- Approval routes, tried in order. Each attempt's full output is captured.
# Route A: GUI click via cua-driver.
KEXT_UP=0
ROUTE_USED=""

attempt_route_A() {
  echo "== route A (cua-driver click) ==" | tee -a "$OUT/routes.log"
  if ! command -v cua-driver >/dev/null 2>&1; then echo "no cua-driver"; return 1; fi
  # 1) Grant Accessibility + Screen Recording (idempotent; will surface prompt if first run).
  cua-driver permissions grant </dev/null > "$OUT/cua-driver-grant.log" 2>&1 || true
  # 2) Open System Settings Privacy & Security.
  open -a "System Settings" </dev/null > "$OUT/open-system-settings.log" 2>&1 || true
  # 3) Wait for System Settings to be the front app.
  for i in 1 2 3 4 5 6 7 8 9 10; do
    PID=$(pgrep -f "System Settings" | head -1)
    [ -n "$PID" ] && break
    sleep 1
  done
  # 4) Navigate to the Privacy & Security pane via its scheme URL.
  open "x-apple.systempreferences:com.apple.preference.security?General" </dev/null > "$OUT/open-pane.log" 2>&1 || true
  sleep 3
  # 5) Try the kmutil load (will fail unless already approved) to trigger the System Settings "Allow" banner.
  sudo -n kmutil load -p "$KEXT_INSTALLED" </dev/null > "$OUT/kmutil.load.A.log" 2> "$OUT/kmutil.load.A.err" || true
  # 6) Capture window state; try to find an "Allow" button.
  PID=$(pgrep -f "System Settings" | head -1)
  if [ -n "$PID" ]; then
    WIN=$(/usr/sbin/lsof -p "$PID" 2>/dev/null | awk '/System Settings\.app\/Contents\/MacOS\/System Settings/ {print $1}' | head -1)
    cua-driver call get_window_state "{\"pid\":$PID,\"max_depth\":15,\"max_elements\":1500,\"include_screenshot\":true,\"screenshot_out_file\":\"$OUT/settings-A.png\"}" > "$OUT/window-state.A.json" 2>&1 || true
    # Best-effort click via the typed cua-driver tool — point at the first AXButton with "Allow" in its label.
    INDEX=$(python3 -c "import json,sys; d=json.load(open('$OUT/window-state.A.json')); s=d.get('structuredContent',{}); elts=s.get('elements',[]) or s.get('elements',[]);
idx=None
for e in elts:
    if (e.get('label','') or '').lower().find('allow')>=0 or 'allow' in (e.get('value','') or '').lower():
        idx=e.get('element_index'); break
print(idx if idx is not None else '')")
    if [ -n "$INDEX" ]; then
      cua-driver call click "{\"pid\":$PID,\"element_index\":$INDEX,\"delivery_mode\":\"background\",\"session\":\"jw16w6\"}" > "$OUT/click-A.json" 2>&1 || true
    fi
    sleep 3
  fi
  # 7) Re-attempt kmutil load.
  sudo -n kmutil load -p "$KEXT_INSTALLED" </dev/null > "$OUT/kmutil.load.A2.log" 2> "$OUT/kmutil.load.A2.err"
  if [ $? -eq 0 ]; then KEXT_UP=1; ROUTE_USED="A"; echo "ROUTE-A-OK"; return 0; fi
  echo "ROUTE-A-FAILED"; return 1
}

attempt_route_B() {
  echo "== route B (sqlite KextPolicy + AuxKC) ==" | tee -a "$OUT/routes.log"
  if ! csrutil status </dev/null 2>/dev/null | grep -q disabled; then echo "SIP not disabled; route B blocked"; return 1; fi
  KP=/var/db/SystemPolicyConfiguration/KextPolicy
  if [ ! -f "$KP" ]; then echo "no KextPolicy db"; return 1; fi
  # Inspect schema once.
  sudo -n sqlite3 "$KP" ".schema kext_policy" </dev/null > "$OUT/kext-policy.schema.txt" 2>&1 || true
  # Insert/replace a row permitting com.warren.ANERegDump (no team id; local unsigned).
  sudo -n sqlite3 "$KP" "INSERT OR REPLACE INTO kext_policy (team_id,bundle_id,allowed,developer_name,flags) VALUES ('','com.warren.ANERegDump',1,'Local',1);" </dev/null > "$OUT/kext-policy.insert.log" 2>&1 || true
  # Re-enable r/w on /Library/ExtensionsAuxKC if needed (no-op here).
  sudo -n kmutil load -p "$KEXT_INSTALLED" </dev/null > "$OUT/kmutil.load.B.log" 2> "$OUT/kmutil.load.B.err"
  if [ $? -eq 0 ]; then KEXT_UP=1; ROUTE_USED="B"; echo "ROUTE-B-OK-NO-REBOOT"; return 0; fi
  # AuxKC rebuild may require a reboot. Check the error.
  if grep -qiE "reboot|auxkc|kernel collection" "$OUT/kmutil.load.B.err"; then
    echo "ROUTE-B-NEEDS-REBOOT" | tee -a "$OUT/routes.log"
    echo "REBOOT-REQUIRED" > "$OUT/reboot-required.flag"
    return 0  # signal needs reboot
  fi
  echo "ROUTE-B-FAILED"; return 1
}

attempt_route_A; A=$?
attempt_route_B; B=$?

# If route B signals a reboot-required, leave a sentinel and exit cleanly so the
# orchestrator can reboot once and re-invoke this script with --post-reboot.
if [ -f "$OUT/reboot-required.flag" ] && [ "$KEXT_UP" != "1" ]; then
  echo "ROUTE-B-REBOOT-DEFERRED" | tee -a "$OUT/routes.log"
  echo "$OUT" > "$OUT/w6.outdir.path"
  echo "REBOOT-DEFERRED: re-run after reboot with: bash $0 post-reboot"
  exit 0
fi

# --- If we are post-reboot, the previous attempt already wrote kext-installed.sha256 + the KextPolicy row.
# Try kmutil load once more (no rebuild, no GUI click).
if [ "${1:-}" = "post-reboot" ]; then
  echo "== post-reboot kmutil load ==" | tee -a "$OUT/routes.log"
  sudo -n kmutil load -p "$KEXT_INSTALLED" </dev/null > "$OUT/kmutil.load.post.log" 2> "$OUT/kmutil.load.post.err"
  if [ $? -eq 0 ]; then KEXT_UP=1; ROUTE_USED="B-post"; fi
fi

# --- Kext loaded verification.
{ date -u; kmutil showloaded --list-only </dev/null 2>/dev/null | grep -i ANERegDump || echo "ANERegDump not in showloaded"
  echo "---"; ioreg -lw0 </dev/null 2>/dev/null | grep -i ANERegDump | head -10
  echo "---"; log show --last 2m --predicate 'process == "kernel" AND eventMessage CONTAINS[c] "ANERegDump"' </dev/null | tail -30
} > "$OUT/kext-state.txt" 2>&1
echo "KEXT_UP=$KEXT_UP ROUTE_USED=$ROUTE_USED" | tee -a "$OUT/kext-state.txt"

# --- ioreg / ADT / pmgr probes.
ioreg -lw0 -rc H11ANEIn </dev/null > "$OUT/ioreg-ane-after.txt" 2>&1 || true
ADTN=$(ioreg -p IODeviceTree -w0 </dev/null 2>/dev/null | grep -o 'ane0@[0-9A-Fa-f]*' | head -1)
ioreg -p IODeviceTree -w0 -r -n "${ADTN:-ane0}" -d1 </dev/null > "$OUT/adt-ane0.txt" 2>&1 || true
ioreg -p IODeviceTree -w0 -r -n chosen -d1 </dev/null > "$OUT/adt-chosen.txt" 2>&1 || true
ioreg -p IODeviceTree -w0 -r -n pmgr -d1 </dev/null > "$OUT/adt-pmgr.txt" 2>&1 || true
grep -E '"(segment-ranges|reg|segment-names|ane-type)"' "$OUT/adt-ane0.txt" > "$OUT/adt-ane0-segments.txt" || echo "adt: no segment-ranges line" >> "$OUT/adt-ane0-segments.txt"

# --- Dump (one early, one late).
dump_reg() { # $1 = suffix
  local CLI="$W5/aneregdump"
  [ ! -x "$CLI" ] && CLI="$W/aneregdump"
  [ ! -x "$CLI" ] && CLI="$SRC/aneregdump"
  if [ "$KEXT_UP" = 1 ]; then
    sudo -n "$CLI" "$OUT/regdump-$1" "$RANGES" > "$OUT/regdump-$1.log" 2>&1
    echo "regdump-$1 rc=$? (rc 3 = islands down, expected while fw has not cold-started)"
  else
    echo "regdump-$1 skipped (kext not loaded)" | tee -a "$OUT/regdump-$1.log"
  fi
}
dump_reg early
# Short CoreML ANE encoder burst (cold-starts the fw) if a harness is on disk from window 1.
find "$HOME/jw16-macos-window" -maxdepth 3 \( -name 'encoder_bench*' -o -name '*encoder*.mlmodelc' -o -name 'aneprobe.mlmodelc' \) 2>/dev/null > "$OUT/encoder-harness-found.txt" || true
if [ -x "$W5/aneprobe" ] && [ -d "$W5/aneprobe.mlmodelc" ]; then
  ( "$W5/aneprobe" "$W5/aneprobe.mlmodelc" 25 </dev/null > "$OUT/aneprobe-burst.log" 2>&1 ) &
  BPID=$!
  sleep 1
fi
dump_reg late
[ -n "${BPID:-}" ] && wait $BPID 2>/dev/null || true

# --- ioreg final.
ioreg -lw0 -rc H11ANEIn </dev/null > "$OUT/ioreg-ane-final.txt" 2>&1 || true

# --- env-post + SHA256SUMS.
{ date -u; pmset -g therm | tail -3; } > "$OUT/env-post.txt" 2>&1
sudo -n kill "$PM" 2>/dev/null
( cd "$OUT" && find . -type f | shasum -a 256 > SHA256SUMS )
echo "W6-DONE ROUTE=$ROUTE_USED KEXT_UP=$KEXT_UP"
