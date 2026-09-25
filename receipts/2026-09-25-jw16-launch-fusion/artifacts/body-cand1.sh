#!/usr/bin/env bash
# Window cand1: control anchor, 4-weight group alone, + swiglu fold, census,
# poison-freed digest check. Same venv recipe on both sides (candidate venv
# is a copy of the serving venv with only the wheel swapped).
set -uo pipefail
D=/var/tmp/levers2
MODEL="$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*)"
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
BENCH=~/bench-scripts/qwen38-mlx-bench.py
CTL=/var/tmp/v072-venv-fused
CAND=$D/venv-cand
WHEEL=$(ls /var/tmp/levers/mlx/dist/mlx_omarchy-*.whl | head -1)
echo "wheel=$WHEEL sha=$(sha256sum "$WHEEL" | cut -c1-16)"
contract(){ # venv label [env...]
  local venv=$1 label=$2; shift 2
  env "$@" MLX_COMMIT_TAG="$label" "$venv/bin/python" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" \
    --limit 10 --warmup 3 --passes "${PASSES:-3}" --new-tokens 32 --prefill-tokens 512 \
    --label "$label" --out "$O/contract-$label.json" >> "$O/contract-$label.console" 2>&1
  python3 $D/summ.py "$O/contract-$label.json"
}
census(){ # venv label
  "$1/bin/python" $D/census.py "$MODEL" "$PROMPTS" "$O/census-$2" 4 2>> "$O/census-$2.trace"
  python3 - "$O/census-$2.trace" <<'EOF'
import sys,re,collections
lines=open(sys.argv[1]).read().splitlines()
segs=[];cur=None
for l in lines:
    if l.startswith('TOKEN_END'): cur=[]
    elif l.startswith('TOKEN_BEGIN') and cur is not None: segs.append(cur);cur=None
    elif cur is not None: cur.append(l)
print("census dispatches/token:",[sum('DISPATCH' in l for l in s) for s in segs])
c=collections.Counter(re.search(r'kernel=(\d+)',l).group(1) for l in segs[0] if 'DISPATCH' in l)
print("census kernels:",sorted(c.items(),key=lambda kv:-kv[1]))
EOF
}
if [ ! -x "$CAND/bin/python" ]; then
  echo "== creating candidate venv (copy of serving venv) =="
  cp -a "$CTL" "$CAND"
fi
echo "== install candidate wheel into venv-cand =="
"$CAND/bin/python" -m pip install --force-reinstall --no-deps -q "$WHEEL" 2>&1 | tail -2
"$CAND/bin/python" -m pip list 2>/dev/null | grep -i "mlx"
"$CTL/bin/python" -m pip list 2>/dev/null | grep -i "mlx-omarchy"
echo "== ctl anchor =="
contract "$CTL" ctl-r1
echo "== cand A: 4-weight group only (swiglu still compiled) =="
contract "$CAND" candA-r1
echo "== apply swiglu-eager patch to venv-cand =="
python3 /var/tmp/levers/mlx/scripts/patch-mlx-lm-swiglu-eager.py "$CAND"
echo "== cand B: 4-weight group + swiglu fold =="
contract "$CAND" candB-r1
echo "== census cand B =="
census "$CAND" candB
echo "== ctl with MLX_OMARCHY_POISON_FREED=1 (stale-read probe) =="
contract "$CTL" ctl-poison-r1 MLX_OMARCHY_POISON_FREED=1
echo "== second reps =="
contract "$CTL" ctl-r2
contract "$CAND" candB-r2
