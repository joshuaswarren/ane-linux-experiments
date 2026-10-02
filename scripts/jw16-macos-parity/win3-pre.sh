#!/bin/bash
# win3-pre.sh — NORM_XCACHE pre-timing checks (no cells): SPIR-V/AGX dump of the
# candidate kernel with stdout capture + norm bitcheck tables (serve / cand-on / cand-off).
set -u
OUT=/var/tmp/classratio/w3
mkdir -p "$OUT"; cd "$OUT" || exit 1
PYS=/var/tmp/v072-venv-fused/bin/python3
PYC=/var/tmp/classratio-venv/bin/python3
for i in $(seq 1 60); do
  L=$(cut -d' ' -f1 /proc/loadavg)
  P=$(head -1 /proc/pressure/cpu | grep -o 'avg10=[0-9.]*' | cut -d= -f2)
  ok=$(python3 -c "print(1 if float('$L')<0.5 and float('$P')==0.0 else 0)")
  [ "$ok" = "1" ] && break
  sleep 10
done
echo "quiet gate: load=$L psi=$P"
{ date -u +%FT%TZ; echo "boot $(cat /proc/sys/kernel/random/boot_id)"; } > env.txt

# --- dump: base vs xcache pipelines (stdout capture; AGX prints there)
cat > dump_one.py <<'PYEOF'
import mlx.core as mx
bf16 = mx.bfloat16
mx.random.seed(0)
x = mx.random.normal((1, 1, 2048)).astype(bf16)
w = mx.random.normal((2048,)).astype(bf16)
mx.eval(mx.fast.rms_norm(x, w, 1e-6))
print("DUMP-DONE")
PYEOF
MESA_SHADER_CACHE_DISABLE=true AGX_MESA_DEBUG=shaders "$PYS" dump_one.py > dump-base.txt 2>/dev/null
MESA_SHADER_CACHE_DISABLE=true AGX_MESA_DEBUG=shaders MLX_OMARCHY_NORM_XCACHE=1 "$PYC" dump_one.py > dump-xcache.txt 2>/dev/null
echo "dump base bytes=$(wc -c < dump-base.txt) xcache bytes=$(wc -c < dump-xcache.txt)"

# --- bitchecks
"$PYS" /var/tmp/classratio/norm_bitcheck.py > bit-serve.json 2> bit-serve.err
"$PYC" /var/tmp/classratio/norm_bitcheck.py > bit-ksoff.json 2> bit-ksoff.err
MLX_OMARCHY_NORM_XCACHE=1 "$PYC" /var/tmp/classratio/norm_bitcheck.py > bit-on.json 2> bit-on.err
"$PYS" - <<'PYEOF'
import json
tables = {}
for name in ("bit-serve", "bit-ksoff", "bit-on"):
    try:
        d = json.load(open(name + ".json"))
        tables[name] = d.get("table_sha256", "?")
    except Exception as e:
        tables[name] = "ERR %r" % (e,)
print("TABLES", json.dumps(tables))
same = len(set(tables.values())) == 1
print("BITCHECK", "PASS" if same else "FAIL")
PYEOF
sha256sum ./* > SHA256SUMS 2>/dev/null
echo PRE-DONE
