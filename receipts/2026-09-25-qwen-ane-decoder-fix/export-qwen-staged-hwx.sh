#!/bin/sh
# Export the compiled staged-Qwen ANE programs to standalone HWX, for the Linux side
# (omarchy-ane consumes ANEC converted from fresh HWX via tools/hwxv2-to-anec.py).
#
# Run ON THE LAPTOP'S macOS right after run-qwen-ane.sh (same boot -> same ANE family
# as the Linux side of that laptop). Every ANEForge program compiled during the run
# leaves a content-addressed entry (model.mil + weights.bin + cache/) under
# ~/Models/.aneforge-cache; this recompiles each one through ANECCompile into a
# standalone Mach-O HWX.
#
# usage: export-qwen-staged-hwx.sh SINCE_EPOCH OUT_DIR [ANE_COMPILE_HWX]
#   SINCE_EPOCH  programs whose model.mil mtime >= this are exported (use the epoch
#                captured before `run-qwen-ane.sh`, e.g. `date +%s`)
#   OUT_DIR      output dir; gets prog_NNN/model.hwx + prog_NNN.log
#   ANE_COMPILE_HWX  path to the ane-compile-hwx driver (built from
#                tools/ane-compile-hwx.mm if omitted and no binary beside this script)
set -eu
SINCE=${1:?usage: export-qwen-staged-hwx.sh SINCE_EPOCH OUT_DIR [ANE_COMPILE_HWX]}
OUT=${2:?usage: export-qwen-staged-hwx.sh SINCE_EPOCH OUT_DIR [ANE_COMPILE_HWX]}
KIT="$(cd "$(dirname "$0")" && pwd)"
DRIVER=${3:-$KIT/ane-compile-hwx}
if [ ! -x "$DRIVER" ]; then
  SRC=""
  for c in "$KIT/ane-compile-hwx.mm" "$KIT/../tools/ane-compile-hwx.mm"; do
    [ -f "$c" ] && SRC="$c" && break
  done
  [ -n "$SRC" ] || { echo "ane-compile-hwx driver not found (pass it as arg 3)"; exit 1; }
  echo "== building ane-compile-hwx from $SRC"
  xcrun clang++ -O2 -fobjc-arc -framework Foundation "$SRC" -o "$KIT/ane-compile-hwx"
  DRIVER="$KIT/ane-compile-hwx"
fi
mkdir -p "$OUT"
n=0; ok=0
for d in "$HOME"/Models/.aneforge-cache/*/; do
  [ -f "$d/model.mil" ] || continue
  m=$(stat -f %m "$d/model.mil")
  [ "$m" -ge "$SINCE" ] || continue
  n=$((n + 1))
  name=$(printf 'prog_%03d' "$n")
  if "$DRIVER" "$d" "$OUT/$name" >"$OUT/$name.log" 2>&1 && [ -f "$OUT/$name/model.hwx" ]; then
    ok=$((ok + 1))
    echo "$name OK $(du -h "$OUT/$name/model.hwx" | cut -f1) ($(basename "$d"))"
  else
    echo "$name FAILED ($(basename "$d")) - see $OUT/$name.log"
  fi
done
echo "EXPORTED $ok/$n programs -> $OUT"
[ "$ok" -eq "$n" ]
