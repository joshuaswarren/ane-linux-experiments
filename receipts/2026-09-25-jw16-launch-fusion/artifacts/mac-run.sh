#!/bin/bash
# jw16 (M1 Max) macOS window: core (whole-encoder CoreML, corrected
# computeUnits harness + MLComputePlan placement) and parakeet e2e legs from
# mac-reference-bundle-full.tar.gz (sha 82c1a70198fd...). Run on the Mac:
#   bash mac-run.sh ~/levers2-mac
set -uo pipefail
BASE=${1:-$HOME/levers2-mac}
cd "$BASE"
echo "sha256: $(shasum -a 256 mac-reference-bundle-full.tar.gz)"
[ -d mac-reference-bundle ] || tar xzf mac-reference-bundle-full.tar.gz
cd mac-reference-bundle
caffeinate -dimsu -w $$ &
sw_vers; sysctl -n machdep.cpu.brand_string hw.memsize; uname -m
echo "== core =="
SECONDS=0
sudo -n bash run-core.sh "$BASE/out" > "$BASE/core.log" 2>&1; echo "core rc=$? in ${SECONDS}s"
sudo -n chown -R "$(id -un)" "$BASE/out" 2>/dev/null || true
tail -5 "$BASE/core.log"
echo "== parakeet =="
SECONDS=0
if command -v swift >/dev/null 2>&1; then
  # The pinned ParakeetCLI.swift does not compile on the newer CLT (jwm1
  # 2026-09-23 deviation 2); the bundle's documented fallback is the shipped
  # arm64 bin/parakeet, taken by hiding swift from the script's PATH.
  mkdir -p "$BASE/noswift"
  printf '#!/bin/sh\nexit 127\n' > "$BASE/noswift/swift"; chmod +x "$BASE/noswift/swift"
  cp "$BASE/noswift/swift" "$BASE/noswift/swiftc"
  PATH="$BASE/noswift:$PATH" bash run-parakeet.sh "$BASE/out" > "$BASE/parakeet.log" 2>&1; echo "parakeet rc=$? in ${SECONDS}s"
else
  bash run-parakeet.sh "$BASE/out" > "$BASE/parakeet.log" 2>&1; echo "parakeet rc=$? in ${SECONDS}s"
fi
grep -E "transcript|rep10:|cold:|GATE|FAIL" "$BASE/parakeet.log" | head -20
cd "$BASE" && tar czf out.tgz out core.log parakeet.log && ls -la out.tgz
echo MAC_RUN_DONE
