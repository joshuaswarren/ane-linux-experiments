#!/usr/bin/env bash
# TermA cdm barrier group sweep: which SUBSETS of bits are correct + fast?
# 3 rounds per arm, ctx1053/32, digest pin as correctness screen.
set -uo pipefail
W=/var/tmp/TermASplit
PY=/var/tmp/V060PIN-venv2/bin/python
BENCH=/var/tmp/Jwm1AneAccelSmoke2-a9f14124/scripts/bench_decode.py
MODEL=/home/joshuawarren/models/Qwen2.5-0.5B-Instruct-4bit-mlx
WHEEL=/var/tmp/V060-rel/mlx_omarchy-0.32.2.dev202609161852+2e252962-cp314-cp314-linux_aarch64.whl
ICD=/home/joshuawarren/src/mesa-wt-dispatchfloor/dispatchfloor-icd.json
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=$W/spirv
export VK_DRIVER_FILES=$ICD
P_CTX=$(cat $W/prompt-ctx1024.txt)
OUT=$W/group-sweep.ndjson
: > "$OUT"
PIN=7da83f06ec9f001d

one() { # $1 mask-hex $2 label $3 rounds
  local mask=$1 label=$2 rounds=$3 rates=() ok=1
  for ((r=1; r<=rounds; r++)); do
    local line dg tps
    line=$(env HK_CDMBARBITS=$mask "$PY" "$BENCH" --model "$MODEL" --prompt "$P_CTX" \
      --tokens 32 --temp 0.0 --seed 0 --warmup-tokens 4 --wheel "$WHEEL" 2>/dev/null | tail -1)
    tps=$(echo "$line" | python3 -c 'import json,sys; print(json.load(sys.stdin)["decode_tps"])')
    dg=$(echo "$line" | python3 -c 'import json,sys; print(json.load(sys.stdin)["ids_sha256_16"])')
    rates+=("$tps")
    [ "$dg" = "$PIN" ] || ok=0
    echo "{\"mask\":\"$mask\",\"label\":\"$label\",\"round\":$r,\"tps\":$tps,\"digest\":\"$dg\"}" >> "$OUT"
  done
  local med
  med=$(python3 -c "import statistics,sys; print(f'{statistics.median([float(x) for x in sys.argv[1:]]):.2f}')" "${rates[@]}")
  echo "$label mask=$mask med=$med pin=$([ $ok = 1 ] && echo HOLD || echo BROKEN) rates=[${rates[*]}]"
}

one 170 designed-4-5-6-8 3
one FFF8 drop012 3
one 00F keep0123 3
one 47 keep0126 3
one 60 keep5-6 3
one 1F0 keep4-8 3
one 40 keep6 3
one 70 keep4-6 3
one 150 keep4-6-8 3
one 30 keep4-5 3
one 10 keep4 3
one 20 keep5 3
one 180 keep4-7 2
one 178 keep45678 2
one 168 keep4578-no6 2
echo DONE
