#!/bin/bash
# win4-cells.sh — Jw16ClassRatio NORM_XCACHE paired-cell gate window.
# Arms: ctl = serving venv; cand = classratio-venv + MLX_OMARCHY_NORM_XCACHE=1;
#       ctl2 = serving again; ksoff = classratio-venv env unset (inertness).
# Digests must pin at d64/d128/d256/d512 in every arm; ksoff == pins.
set -u
OUT=/var/tmp/classratio/w4
mkdir -p "$OUT"; cd "$OUT" || exit 1
PYS=/var/tmp/v072-venv-fused/bin/python3
PYC=/var/tmp/classratio-venv/bin/python3
BENCH=$HOME/bench-scripts/qwen38-mlx-bench.py
MODEL=$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/0867d98bfb174b042d88461c0e*)
for i in $(seq 1 60); do
  L=$(cut -d' ' -f1 /proc/loadavg)
  P=$(head -1 /proc/pressure/cpu | grep -o 'avg10=[0-9.]*' | cut -d= -f2)
  ok=$(python3 -c "print(1 if float('$L')<0.5 and float('$P')==0.0 else 0)")
  [ "$ok" = "1" ] && break
  sleep 10
done
echo "quiet gate: load=$L psi=$P"
{ date -u +%FT%TZ; echo "boot $(cat /proc/sys/kernel/random/boot_id)"; } > env.txt

CELL() { local py="$1" tag="$2" n="$3"; shift 3; env "$@" "$py" "$BENCH" --model "$MODEL"/ \
  --prompts "$HOME/bench-scripts/qwen38-2b-prompts.jsonl" --limit 1 --warmup 1 --passes 5 \
  --prefill-tokens 512 --new-tokens "$n" --label "$tag-d$n" --out "$OUT/$tag-d$n.json" \
  > "$OUT/$tag-d$n.log" 2>&1; }

CELL "$PYS" ctl 64
CELL "$PYC" cand 64 MLX_OMARCHY_NORM_XCACHE=1
CELL "$PYS" ctl2 64
CELL "$PYC" ksoff 64
for N in 128 256 512; do
  CELL "$PYS" ctl $N
  CELL "$PYC" cand $N MLX_OMARCHY_NORM_XCACHE=1
done

"$PYS" - "$OUT" <<'PYEOF'
import json
import sys
import glob
import os

out = sys.argv[1]
print("%-10s %-14s %8s %8s %24s" % ("arm", "digest12", "med", "min", "max"))
for f in sorted(glob.glob(os.path.join(out, "*.json"))):
    try:
        d = json.load(open(f))
        r = d.get("decode_tok_rate", {})
        print("%-10s %-14s %8.2f %8.2f %24s" % (
            os.path.basename(f)[:-5],
            str(d.get("ordered_records_sha256", "?"))[:12],
            r.get("median", -1), r.get("min", -1), r.get("max", -1)))
    except Exception as e:
        print(os.path.basename(f), "ERR", repr(e))
PYEOF
sha256sum ./* > SHA256SUMS 2>/dev/null
echo W4-DONE
