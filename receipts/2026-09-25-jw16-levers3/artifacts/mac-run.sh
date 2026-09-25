#!/bin/bash
# jw16 (M1 Max) macOS denominator window, three legs from
# mac-reference-bundle-full.tar.gz (sha 82c1a70198fd...):
#   core     run-core.sh    whole-encoder CoreML bench, corrected computeUnits
#                           harness + MLComputePlan placement (cpu/ane/all)
#   parakeet run-parakeet.sh audio->transcript, 4 CU arms, cold/warm/rep1-10,
#                           the jwm1 271 ms boundary = "inference" of rep10, ane arm
#   qwen-gpu run-qwen-gpu.sh Qwen3.8-2B MLX Metal contract (mlx 0.32.2,
#                           mlx-lm pinned 0.31.3 = the 180.38 row's versions)
# Run on the Mac:  nohup bash mac-run.sh ~/levers3-mac > ~/levers3-mac/run.log 2>&1 &
set -uo pipefail
BASE=${1:-$HOME/levers3-mac}
cd "$BASE"
echo "sha256: $(shasum -a 256 mac-reference-bundle-full.tar.gz)"
[ -d mac-reference-bundle ] || tar xzf mac-reference-bundle-full.tar.gz
cd mac-reference-bundle
caffeinate -dimsu -w $$ &
sw_vers; sysctl -n machdep.cpu.brand_string hw.memsize; uname -m; uptime
if sudo -n true 2>/dev/null; then SUDO="sudo -n"; else SUDO=""; echo "no passwordless sudo: powermetrics arm will be empty"; fi
echo "== core =="
SECONDS=0
$SUDO bash run-core.sh "$BASE/out" > "$BASE/core.log" 2>&1; echo "core rc=$? in ${SECONDS}s"
[ -n "$SUDO" ] && $SUDO chown -R "$(id -un)" "$BASE/out" 2>/dev/null || true
grep -E "median|CORE-BUNDLE|FAILED|placement" "$BASE/core.log" | head -12
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
grep -E "rep10:|cold:|MATCHES|DIFFERS|GATE|PARAKEET-BUNDLE" "$BASE/parakeet.log" | head -20
echo "== qwen-gpu =="
SECONDS=0
# Deviation (recorded): the bundle installs an unpinned mlx-lm; the 180.38
# denominator row ran mlx-lm 0.31.3, so pin it for a like-for-like re-run.
sed -i.orig 's/"mlx-lm"/"mlx-lm==0.31.3"/' run-qwen-gpu.sh
bash run-qwen-gpu.sh "$BASE/out" > "$BASE/qwen-gpu.log" 2>&1; echo "qwen-gpu rc=$? in ${SECONDS}s"
grep -E "python:|e2e_s|GPU-BUNDLE|MISMATCH|failed|no python" "$BASE/qwen-gpu.log" | head
PYQ="$BASE/mac-reference-bundle/venv-qwen-gpu/bin/python"; [ -x "$PYQ" ] || PYQ=python3
for j in "$BASE"/out/qwen-gpu-*/qwen38-macos-metal.json; do
  "$PYQ" - "$j" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); d=j["decode_tok_rate"]; pp=j.get("pure_prefill") or {}
print(f"qwen-gpu: decode={d['median']} tok/s ttft={j['ttft_tok_rate']['median']} prefill={pp.get('pure_prefill_tok_rate')} e2e={j.get('e2e_s',{}).get('median')} digest={j['ordered_records_sha256'][:8]} mlx={j['meta'].get('mlx_dist_version')} mlx_lm={j['meta'].get('mlx_lm_version')} py={j['meta'].get('python')}")
PY
done
cd "$BASE" && tar czf out.tgz out core.log parakeet.log qwen-gpu.log && ls -la out.tgz
echo MAC_RUN_DONE
