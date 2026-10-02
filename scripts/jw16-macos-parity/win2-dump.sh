#!/bin/bash
# win2-dump.sh — AGX NIR/ISA dump of the deployed norm-family pipelines, stdout capture.
set -u
OUT=/var/tmp/classratio/w2
mkdir -p "$OUT"; cd "$OUT" || exit 1
PY=/var/tmp/v072-venv-fused/bin/python
for i in $(seq 1 60); do
  L=$(cut -d' ' -f1 /proc/loadavg)
  P=$(head -1 /proc/pressure/cpu | grep -o 'avg10=[0-9.]*' | cut -d= -f2)
  ok=$(python3 -c "print(1 if float('$L')<0.5 and float('$P')==0.0 else 0)")
  [ "$ok" = "1" ] && break
  sleep 10
done
echo "quiet gate: load=$L psi=$P"
MESA_SHADER_CACHE_DISABLE=true AGX_MESA_DEBUG=shaders "$PY" /var/tmp/classratio/dump_kernels.py \
  > agx-shaders.txt 2> dump-notes.txt
echo "dump rc=$? stdout_bytes=$(wc -c < agx-shaders.txt)"
gzip -f agx-shaders.txt
sha256sum agx-shaders.txt.gz dump-notes.txt > SHA256SUMS
