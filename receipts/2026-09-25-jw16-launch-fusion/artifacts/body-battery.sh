#!/usr/bin/env bash
# Window battery: (1) determinism probes on the serving venv (fusion paths
# forced off, buffer cache off) - a digest other than bc519c03 means the
# alternative path is not bit-identical to the fused one, i.e. any
# timing-dependent path selection is a nondeterminism source; (2) the
# interleaved 10-pass battery: installed driver vs the no-split driver
# (VK_DRIVER_FILES override, system ICD untouched), PAIRS pairs.
set -uo pipefail
D=/var/tmp/levers2
MODEL="$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*)"
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
BENCH=~/bench-scripts/qwen38-mlx-bench.py
VENV=${VENV:-/var/tmp/v072-venv-fused}
NOSPLIT=/var/tmp/levers/icd/41ccf96.icd.json
PAIRS=${PAIRS:-10}
echo "venv=$VENV wheel=$($VENV/bin/pip list 2>/dev/null | grep mlx-omarchy) nosplit=$(sha256sum /var/tmp/levers/icd/libvulkan_asahi.so.41ccf96 | cut -c1-16) installed=$(sha256sum /usr/local/lib/libvulkan_asahi.so.d3fa18e | cut -c1-16)"
contract(){ # label passes [env...]
  local label=$1 passes=$2; shift 2
  env "$@" MLX_COMMIT_TAG="$label" "$VENV/bin/python" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" \
    --limit 10 --warmup 3 --passes "$passes" --new-tokens 32 --prefill-tokens 512 \
    --label "$label" --out "$O/contract-$label.json" >> "$O/contract-$label.console" 2>&1
  python3 $D/summ.py "$O/contract-$label.json"
}
if [ "${PROBES:-1}" = 1 ]; then
  echo "== determinism probes (3-pass) =="
  contract probe-fusedgemv0 3 MLX_OMARCHY_FUSED_GEMV=0
  contract probe-fusedchain0 3 MLX_OMARCHY_FUSED_CHAIN=0
  contract probe-nocache 3 MLX_OMARCHY_NO_BUFFER_CACHE=1
  contract probe-trio0 3 MLX_OMARCHY_FUSED_TRIO=0
fi
echo "== interleaved 10-pass battery: installed (ctl) vs no-split (cand), $PAIRS pairs =="
for i in $(seq 1 "$PAIRS"); do
  contract "bat-ctl-p10-$i" 10
  contract "bat-nosplit-p10-$i" 10 VK_DRIVER_FILES=$NOSPLIT
done
echo "== battery summary =="
for f in "$O"/contract-bat-*.json; do python3 $D/summ.py "$f"; done | awk '{print $1, $NF, $0}' | sort | awk '{d=$0; sub(/^[^ ]+ [^ ]+ /,"",d); print d}' | grep -o "bat-[a-z]*-p10-[0-9]* .*digest=[0-9a-f]*" | sed 's/decode=\([0-9.]*\).*digest=/\1 /'
