#!/bin/bash
# win5-ksoff.sh — depth arms for the candidate wheel env-OFF (wheel-vs-kernel attribution).
set -u
OUT=/var/tmp/classratio/w5
mkdir -p "$OUT"; cd "$OUT" || exit 1
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
CELL() { local tag="$1" n="$2"; shift 2; env "$@" "$PYC" "$BENCH" --model "$MODEL"/ \
  --prompts "$HOME/bench-scripts/qwen38-2b-prompts.jsonl" --limit 1 --warmup 1 --passes 5 \
  --prefill-tokens 512 --new-tokens "$n" --label "$tag-d$n" --out "$OUT/$tag-d$n.json" \
  > "$OUT/$tag-d$n.log" 2>&1; }
CELL ksoff2 64
CELL ksoff 128
CELL ksoff 256
CELL ksoff 512
/var/tmp/v072-venv-fused/bin/python3 - "$OUT" <<'PYEOF'
import json, glob, os, sys
out = sys.argv[1]
for f in sorted(glob.glob(os.path.join(out, "*.json"))):
    d = json.load(open(f))
    r = d.get("decode_tok_rate", {})
    print("%-14s %-14s %8.2f %8.2f %8.2f" % (os.path.basename(f)[:-5], str(d.get("ordered_records_sha256","?"))[:12], r.get("median",-1), r.get("min",-1), r.get("max",-1)))
PYEOF
sha256sum ./* > SHA256SUMS 2>/dev/null
echo W5-DONE
