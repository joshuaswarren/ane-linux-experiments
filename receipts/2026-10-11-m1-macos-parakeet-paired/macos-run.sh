#!/bin/bash
# H415 macOS side (run on the 13-inch M1 under macOS, nothing else on the Mac). Usage: macos-run.sh <workdir with encoder_bench.swift feat_f32.bin mask_i32.bin gold_f16.bin>
# Interleaved arms ane, all, ane, all; each 3 warmups + 15 timed reps; dumps kept for the bit-exact check on the CT.
set -uo pipefail
W=${1:?workdir}
cd "$W" || exit 1
R=$W/results; mkdir -p "$R"
{
  date -u; sw_vers; uname -a; sysctl -n machdep.cpu.brand_string hw.memsize
  echo "--- pmset"; pmset -g | head -20; pmset -g therm
  echo "--- load"; sysctl -n vm.loadavg; ps -Ao pcpu,comm -r | head -8
  echo "--- coreml"; defaults read /System/Library/Frameworks/CoreML.framework/Resources/Info.plist CFBundleVersion 2>/dev/null
  echo "--- swift"; swiftc --version 2>&1 | head -2
  echo "--- inputs"; shasum -a 256 encoder_bench.swift feat_f32.bin mask_i32.bin gold_f16.bin
} > "$R/identity.txt" 2>&1
M=$(find "$HOME/.cache/mlx-omarchy/parakeet-reference" -name encoder.mlpackage -maxdepth 6 2>/dev/null | head -1)
[ -n "$M" ] || { echo "NO MODEL under ~/.cache/mlx-omarchy/parakeet-reference" | tee "$R/ABORT.txt"; exit 2; }
echo "model $M" >> "$R/identity.txt"
( cd "$(dirname "$M")" && [ -f .sha256sums ] && shasum -c .sha256sums 2>&1 | tail -3 ) >> "$R/identity.txt" 2>&1
[ -x ./encoder_bench ] || swiftc -O encoder_bench.swift -o encoder_bench > "$R/swiftc.log" 2>&1 || { echo "swiftc failed" | tee "$R/ABORT.txt"; exit 3; }
shasum -a 256 encoder_bench >> "$R/identity.txt"
caffeinate -dimsu -w $$ &
sleep 20
for i in 1 2; do
  for u in ane all; do
    echo "load1_pre=$(sysctl -n vm.loadavg | awk '{print $2}') $(date -u +%T)" > "$R/run-$u-$i.pre"
    ./encoder_bench "$M" feat_f32.bin mask_i32.bin "$u" 3 15 "$R/out-$u-$i.bin" > "$R/run-$u-$i.json" 2> "$R/run-$u-$i.err"
    echo "$u $i rc=$? $(head -c 160 "$R/run-$u-$i.json")"
    sleep 15
  done
done
echo "load_end=$(sysctl -n vm.loadavg) $(date -u +%T)" >> "$R/identity.txt"
echo DONE
