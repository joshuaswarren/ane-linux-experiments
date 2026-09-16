#!/usr/bin/env bash
# TermA cdmbarrier probe: does the per-launch kitchen-sink CDM_BARRIER cost
# real decode wall? (Microbench said no-op on trivial kernels; decode kernels
# are 1-1216 workgroups with true dependencies.)
# Arms: stock installed driver | wt-default | wt-nocdmbarrier | wt-usccdmbarrier
# 3 interleaved rounds, ctx1053/32 only, MEASUREMENT probe (digests recorded
# per the known worktree-build digest caveat, not gated).
set -uo pipefail
W=/var/tmp/TermASplit
PY=/var/tmp/V060PIN-venv2/bin/python
BENCH=/var/tmp/Jwm1AneAccelSmoke2-a9f14124/scripts/bench_decode.py
MODEL=/home/joshuawarren/models/Qwen2.5-0.5B-Instruct-4bit-mlx
WHEEL=/var/tmp/V060-rel/mlx_omarchy-0.32.2.dev202609161852+2e252962-cp314-cp314-linux_aarch64.whl
WT_ICD=/home/joshuawarren/src/mesa-wt-dispatchfloor/dispatchfloor-icd.json
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=$W/spirv
P_CTX=$(cat $W/prompt-ctx1024.txt)
OUT=$W/cdm-probe.ndjson
: > "$OUT"

arm() { # $1 name $2 env-string
  local name=$1 envs=$2
  for r in 1 2 3; do
    local out
    out=$(env $envs "$PY" "$BENCH" --model "$MODEL" --prompt "$P_CTX" \
      --tokens 32 --temp 0.0 --seed 0 --warmup-tokens 4 --wheel "$WHEEL" 2>/dev/null | tail -1)
    echo "{\"arm\":\"$name\",\"round\":$r,$(echo "$out" | sed 's/^{//')" >> "$OUT"
    echo "$name r$r: $(echo "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["decode_tps"], d["ids_sha256_16"])')"
  done
}

echo "== stock (installed 6f6afc8 pkg) =="
arm stock ""
echo "== wt default =="
arm wtdef "VK_DRIVER_FILES=$WT_ICD"
echo "== wt nocdmbarrier =="
arm nocdm "VK_DRIVER_FILES=$WT_ICD HK_PERFTEST=nocdmbarrier"
echo "== wt usccdmbarrier =="
arm usccdm "VK_DRIVER_FILES=$WT_ICD HK_PERFTEST=usccdmbarrier"

python3 - "$OUT" <<'EOF'
import json,sys,statistics
rows=[json.loads(l) for l in open(sys.argv[1])]
by={}
for r in rows: by.setdefault(r["arm"],[]).append(r["decode_tps"])
base=statistics.median(by.get("stock",[0]))
for a,v in by.items():
    m=statistics.median(v)
    print(f"{a:8s} med={m:.2f} tok/s  delta={100*(m-base)/base:+.2f}%  runs={[round(x,2) for x in v]}")
EOF
