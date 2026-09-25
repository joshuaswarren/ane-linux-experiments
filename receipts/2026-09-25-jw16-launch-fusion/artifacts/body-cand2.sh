#!/usr/bin/env bash
# Window cand2: isolate each lever. Arms (all the same venv recipe):
#   ctl   = serving venv (3232b1f wheel)
#   ctlS  = copy of serving venv + swiglu-eager patch (fold on the installed wheel)
#   candA = venv-candA: candidate wheel (4-weight group), no venv patches
#   candC = venv-cand: candidate wheel + swiglu-eager + qgate-split
# Interleaved 3-pass contracts, then a census of candC.
set -uo pipefail
D=/var/tmp/levers2
MODEL="$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*)"
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
BENCH=~/bench-scripts/qwen38-mlx-bench.py
CTL=/var/tmp/v072-venv-fused
CTLS=$D/venv-ctlS
CANDA=$D/venv-candA
CAND=$D/venv-cand
SCRIPTS=/var/tmp/levers/mlx/scripts
WHEEL=$(ls /var/tmp/levers/mlx/dist/mlx_omarchy-*.whl | head -1)
SITE=lib/python3.14/site-packages/mlx_lm/models
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
echo "== venvs =="
[ -x "$CTLS/bin/python" ] || cp -a "$CTL" "$CTLS"
[ -x "$CANDA/bin/python" ] || { cp -a "$CTL" "$CANDA"; "$CANDA/bin/python" -m pip install --force-reinstall --no-deps -q "$WHEEL" 2>&1 | tail -1; }
# venv-cand: refresh the mlx-lm model files from the serving venv, then patch.
for f in activations.py qwen3_next.py qwen3_5.py; do cp "$CTL/$SITE/$f" "$CAND/$SITE/$f"; done
rm -rf "$CAND/$SITE/__pycache__" "$CTLS/$SITE/__pycache__"
python3 $SCRIPTS/patch-mlx-lm-swiglu-eager.py "$CTLS"
python3 $SCRIPTS/patch-mlx-lm-swiglu-eager.py "$CAND"
python3 $SCRIPTS/patch-mlx-lm-qwen3next-qgate-split.py "$CAND"
for v in "$CTL" "$CTLS" "$CANDA" "$CAND"; do echo "$v: $("$v/bin/python" -m pip list 2>/dev/null | grep mlx-omarchy) swiglu=$(grep -c 'swiglu-eager' $v/$SITE/activations.py) qgate=$(grep -c 'q_gate_proj' $v/$SITE/qwen3_next.py)"; done
echo "== interleaved contracts =="
contract "$CTL"   ctl-r1
contract "$CTLS"  ctlS-r1
contract "$CANDA" candA-r1
contract "$CAND"  candC-r1
echo "== census candC =="
census "$CAND" candC
contract "$CTL"   ctl-r2
contract "$CTLS"  ctlS-r2
contract "$CANDA" candA-r2
contract "$CAND"  candC-r2
contract "$CTLS"  ctlS-r3
contract "$CAND"  candC-r3
contract "$CTL"   ctl-r3
contract "$CANDA" candA-r3
