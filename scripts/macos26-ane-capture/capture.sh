#!/usr/bin/env bash
# Capture orchestrator. Runs ON the Mac (jw14m2).
# Usage: bash capture.sh    (kit dir = this dir; artifacts land in ./artifacts)
set -u
KIT="$(cd "$(dirname "$0")" && pwd)"
ART="$KIT/artifacts"
rm -rf "$ART"; mkdir -p "$ART"

{ echo "== host identity $(date -u +%Y-%m-%dT%H:%M:%SZ) =="; sw_vers; uname -a; \
  id -un; hostname; } > "$ART/version.txt" 2>&1

python3 "$KIT/ane_probe.py" "$ART" >"$ART/ane-probe.stderr" 2>&1
PROBE_RC=$?
echo "probe_rc=$PROBE_RC" >> "$ART/version.txt"

bash "$KIT/mint_probe.sh" "$ART" >"$ART/mint-probe.log" 2>&1
MINT_RC=$?
echo "mint_rc=$MINT_RC" >> "$ART/version.txt"

tar -czf /tmp/jw14m2-macos26-capture.tar.gz -C "$KIT" artifacts 2>/dev/null
shasum -a 256 /tmp/jw14m2-macos26-capture.tar.gz
echo "CAPTURE_DONE probe_rc=$PROBE_RC mint_rc=$MINT_RC"
