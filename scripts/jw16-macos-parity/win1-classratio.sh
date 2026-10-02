#!/bin/bash
# win1.sh — Jw16ClassRatio Linux leg: chain2 full run (serving venv) + AGX shader dumps.
# Runs INSIDE gpuwin.sh. Quiet gate + env receipts first; no timing claims from the dump arm.
set -u
OUT=/var/tmp/classratio/w1
mkdir -p "$OUT"; cd "$OUT" || exit 1
VENV=/var/tmp/v072-venv-fused
PY="$VENV/bin/python"

echo "--- env $(date -u +%FT%TZ)"
cat /proc/sys/kernel/random/boot_id
uptime
psichk=$(cat /proc/pressure/cpu | head -1); echo "PSI: $psichk"
"$PY" -m pip list 2>/dev/null | grep -Ei '^(mlx|mlx-lm|numpy) ' | tee pip.txt

# Quiet gate: load1 < 0.5 and PSI some avg10 0.00, up to 10 min.
for i in $(seq 1 60); do
  L=$(cut -d' ' -f1 /proc/loadavg)
  P=$(head -1 /proc/pressure/cpu | grep -o 'avg10=[0-9.]*' | cut -d= -f2)
  ok=$(python3 -c "print(1 if float('$L')<0.5 and float('$P')==0.0 else 0)")
  [ "$ok" = "1" ] && break
  sleep 10
done
echo "quiet gate: load=$L psi=$P after $i tries"

echo "--- chain2 linux full $(date -u +%FT%TZ)"
MESA_SHADER_CACHE_DISABLE=true "$PY" /var/tmp/classratio/chain_costs_decode2.py \
  > chain2-linux.json 2> chain2-linux.err
echo "chain2 rc=$? bytes=$(wc -c < chain2-linux.json)"

echo "--- agx shader dumps $(date -u +%FT%TZ)"
AGX_MESA_DEBUG=help "$PY" -c "import mlx.core" 2> agx-debug-help.txt >/dev/null
head -50 agx-debug-help.txt
MESA_SHADER_CACHE_DISABLE=true AGX_MESA_DEBUG=shaders "$PY" /var/tmp/classratio/dump_kernels.py \
  > dump-notes.json 2> agx-shaders.txt
dump_rc=$?
echo "dump rc=$dump_rc stderr_bytes=$(wc -c < agx-shaders.txt)"
[ "$dump_rc" -ne 0 ] || gzip -f agx-shaders.txt

echo "--- gdn trace arm $(date -u +%FT%TZ)"
MESA_SHADER_CACHE_DISABLE=true MLX_OMARCHY_TRACE_DISPATCH=1 "$PY" /var/tmp/classratio/trace_gdn.py \
  > gdn-trace.txt 2>&1
echo "trace rc=$? lines=$(wc -l < gdn-trace.txt)"

echo "--- done $(date -u +%FT%TZ)"
sha256sum chain2-linux.json dump-notes.json gdn-trace.txt agx-shaders.txt* pip.txt > SHA256SUMS 2>/dev/null
