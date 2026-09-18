#!/usr/bin/env bash
# Oracle-mint toolchain check + T6021 H13/H14 probe pair. Run ON the Mac.
# Usage: bash mint_probe.sh ART_DIR
#
# Legs:
#  1. Bridge build (tools/ane-compile-hwx.mm, vendored) + sha16 lineage check
#     against the 2026-09-17 macstudio/jw14m2 tool (52336 B,
#     2026-08-31-mil-oneop-proof.md).
#  2. Refused-route probe (mint.sh): records whether the 2026-09-17
#     ANECCompile matmul-MIL dialect refusal still holds on this OS.
#  3. e5rt working route (mint_aneforge.py, canonical workroot): oproj
#     TargetArchitecture h14g + h13 = the T6021 H13/H14 probe pair; .e5
#     shas are comparable to the 2026-09-17 archived mints.
# Mutations: /tmp only (scratch copies, canonical mint workroot, venv).
set -u
ART="$1"
KIT="$(cd "$(dirname "$0")" && pwd)"
cd "$KIT"
LINEAGE_SHA16="3d13fc85c2a6baa0"
ARCHIVED_OPROMJ_SHA16="9351e29807fcaf34"   # jw14m2 oproj h14g, 2026-09-17

say() { printf '%s\n' "$*" | tee -a "$ART/mint-summary.txt"; }
: > "$ART/mint-summary.txt"
say "== mint probe $(date -u +%Y-%m-%dT%H:%M:%SZ) =="

# --- leg 1: bridge build + lineage -------------------------------------
say "== bridge build =="
xcrun clang++ -std=c++17 -fblocks -framework Foundation \
  -F/System/Library/PrivateFrameworks -framework ANECompiler \
  ane-compile-hwx.mm -o ane-compile-hwx >"$ART/bridge-build.log" 2>&1
BUILD_RC=$?
say "bridge_build_rc=$BUILD_RC"
BUILD_OK=false
if [ $BUILD_RC -eq 0 ]; then
  SHA="$(shasum -a 256 ane-compile-hwx | cut -d ' ' -f1)"
  say "bridge_sha256=$SHA"
  say "bridge_bytes=$(stat -f %z ane-compile-hwx)"
  case "$SHA" in
    "$LINEAGE_SHA16"*) say "lineage_match=true" ;;
    *) say "lineage_match=false expected_sha16=$LINEAGE_SHA16" ;;
  esac
  BUILD_OK=true
else
  say "bridge_build FAILED:"
  say "$(sed -n '1,20p' "$ART/bridge-build.log")"
fi

# --- leg 2: refused-route capability probe ------------------------------
if $BUILD_OK; then
  for TARGET in h14g h13; do
    say "== refused-route probe oproj $TARGET =="
    WORK="$ART/work-refused-$TARGET"
    rm -rf "$WORK"; mkdir -p "$WORK"
    cp ane-compile-hwx make_capture.py mint.sh "$WORK/"
    ( cd "$WORK" && bash mint.sh oproj "$TARGET" "$WORK" ) \
      >"$ART/refused-route-$TARGET.log" 2>&1
    say "refused_route_$TARGET bridge_exit=$(grep -o \
      'bridge_exit=[0-9]*' "$ART/refused-route-$TARGET.log" | head -1) " \
      "hwx=$(grep -c NO_HWX_EMitted "$ART/refused-route-$TARGET.log") " \
      "(2026-09-17 baseline: bridge_exit=1, NO_HWX_EMITTED)"
    rm -rf "$WORK"
  done
fi

# --- leg 3: e5rt working route (H13/H14 probe pair) ---------------------
AF_DIR=""
for d in "$HOME/src/ANEForge" /tmp/ANEForge-scratch /tmp/ANEForge; do
  [ -f "$d/aneforge/__init__.py" ] && { AF_DIR="$d"; break; }
done
if [ -z "$AF_DIR" ] && ssh -o BatchMode=yes -o ConnectTimeout=6 \
    macstudio true >/dev/null 2>&1; then
  say "fetching aneforge scratch from macstudio (BatchMode)"
  if rsync -a macstudio:src/ANEForge/ /tmp/ANEForge-scratch/ \
      >>"$ART/mint-summary.txt" 2>&1; then
    AF_DIR="/tmp/ANEForge-scratch"
  fi
fi
PY=""
for py in "$HOME/src/ANEForge/.venv/bin/python" \
          "/tmp/ANEForge-scratch/.venv/bin/python" python3; do
  { command -v "$py" >/dev/null 2>&1 || [ -x "$py" ]; } || continue
  "$py" -c "import numpy" >/dev/null 2>&1 && { PY="$py"; break; }
done
if [ -n "$AF_DIR" ] && [ -z "$PY" ]; then
  # Scratch venv + numpy — /tmp only, same documented mutation as the
  # 2026-09-17 jw14m2 mint run.
  say "no numpy python found; scratch venv at /tmp/t6021-mint/venv"
  PY="/tmp/t6021-mint/venv/bin/python"
  if [ ! -x "$PY" ]; then
    python3 -m venv /tmp/t6021-mint/venv >>"$ART/mint-summary.txt" 2>&1 \
      && "$PY" -m pip install -q numpy >>"$ART/mint-summary.txt" 2>&1
  fi
  "$PY" -c "import numpy" >/dev/null 2>&1 || PY=""
fi

if [ -n "$PY" ] && [ -n "$AF_DIR" ]; then
  # py3.9 needs the __future__ annotations patch (2026-09-17 precedent);
  # never patch an existing checkout — work on a /tmp copy.
  case "$AF_DIR" in
    /tmp/*) SCRATCH="$AF_DIR" ;;
    *)
      SCRATCH="/tmp/ANEForge-scratch"
      say "copying $AF_DIR -> $SCRATCH (no in-place patches)"
      rsync -a "$AF_DIR/" "$SCRATCH/"
      AF_DIR="$SCRATCH"
      ;;
  esac
  if [ "$("$PY" -c 'import sys;print(sys.version_info<(3,10))')" = "True" ]
  then
    find "$AF_DIR/aneforge" -name '*.py' -print0 | while IFS= read -r -d '' f; do
      grep -q "from __future__ import annotations" "$f" \
        || sed -i '' '1i\
from __future__ import annotations\
' "$f"
    done
    say "py3.9 scratch: applied __future__ annotations patch"
  fi
  say "== e5rt mint oproj h14g+h13 (canonical workroot /tmp/anec-mint-normalized) =="
  PYTHONPATH="$AF_DIR" "$PY" "$KIT/mint_aneforge.py" oproj \
    >>"$ART/mint-summary.txt" 2>&1
  say "e5rt_mint_rc=$?"
  find /tmp/anec-mint-normalized/oproj -name '*.e5' \
    -exec shasum -a 256 {} \; >>"$ART/mint-summary.txt" 2>&1
  H14="$(find /tmp/anec-mint-normalized/oproj/cache_h14g -name '*.e5' 2>/dev/null | head -1)"
  H13="$(find /tmp/anec-mint-normalized/oproj/cache_h13 -name '*.e5' 2>/dev/null | head -1)"
  if [ -n "$H14" ] && [ -n "$H13" ]; then
    if cmp -s "$H14" "$H13"; then say "h14g_equiv_h13=true"; else
      say "h14g_equiv_h13=false"; fi
    say "h14g_e5_sha16=$(shasum -a 256 "$H14" | cut -c1-16)"
    say "archived_oproj_sha16_2026-09-17=$ARCHIVED_OPROMJ_SHA16"
  else
    say "e5_probe_pair=MISSING (see mint-summary tail)"
  fi
  plutil -extract CFBundleShortVersionString raw \
    /System/Library/PrivateFrameworks/ANECompiler.framework/Versions/A/Resources/Info.plist \
    >/dev/null 2>&1 \
    && say "anecompiler_version=$(plutil -extract CFBundleShortVersionString raw \
       /System/Library/PrivateFrameworks/ANECompiler.framework/Versions/A/Resources/Info.plist 2>/dev/null)"
else
  say "e5rt_route=unavailable reason=no_aneforge_or_numpy_route af=$AF_DIR py=$PY"
fi
say "== mint probe done =="
