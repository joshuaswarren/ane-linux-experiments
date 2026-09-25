#!/usr/bin/env bash
# Window install: install the bit-exact candidate stack (1faf7f00 wheel +
# swiglu-eager + qgate-split venv patches) into the serving venv with a
# snapshot for revert, verify the census, then run the determinism probes,
# the 10x10-pass interleaved no-split battery and a cpufreq governor A/B.
set -uo pipefail
D=/var/tmp/levers2
CTL=/var/tmp/v072-venv-fused
SITE=lib/python3.14/site-packages
SCRIPTS=/var/tmp/levers/mlx/scripts
WHEEL=$(ls /var/tmp/levers/mlx/dist/mlx_omarchy-*.whl | head -1)
SNAP=$D/venv-fused-pre-levers2
MODEL="$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*)"
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
BENCH=~/bench-scripts/qwen38-mlx-bench.py
contract(){ # label passes [env...]
  local label=$1 passes=$2; shift 2
  env "$@" MLX_COMMIT_TAG="$label" "$CTL/bin/python" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" \
    --limit 10 --warmup 3 --passes "$passes" --new-tokens 32 --prefill-tokens 512 \
    --label "$label" --out "$O/contract-$label.json" >> "$O/contract-$label.console" 2>&1
  python3 $D/summ.py "$O/contract-$label.json"
}
echo "== pre-install state =="
"$CTL/bin/python" -m pip list 2>/dev/null | grep -i mlx
ls -d $CTL/$SITE/mlx_omarchy-*.dist-info
if [ ! -d "$SNAP" ]; then
  echo "== snapshot serving venv mlx package + model files -> $SNAP =="
  mkdir -p "$SNAP/mlx_lm_models"
  cp -a $CTL/$SITE/mlx "$SNAP/mlx"
  cp -a $CTL/$SITE/mlx_omarchy-*.dist-info "$SNAP/"
  for f in activations.py qwen3_next.py qwen3_5.py; do cp -a "$CTL/$SITE/mlx_lm/models/$f" "$SNAP/mlx_lm_models/$f"; done
  du -sh "$SNAP"
fi
echo "== install $WHEEL =="
"$CTL/bin/python" -m pip install --force-reinstall --no-deps -q "$WHEEL" 2>&1 | tail -2
python3 $SCRIPTS/patch-mlx-lm-swiglu-eager.py "$CTL"
python3 $SCRIPTS/patch-mlx-lm-qwen3next-qgate-split.py "$CTL"
rm -rf $CTL/$SITE/mlx_lm/models/__pycache__
echo "== post-install state =="
"$CTL/bin/python" -m pip list 2>/dev/null | grep -i mlx
ls -d $CTL/$SITE/mlx_omarchy-*.dist-info
echo "swiglu-eager=$(grep -c swiglu-eager $CTL/$SITE/mlx_lm/models/activations.py) qgate=$(grep -c q_gate_proj $CTL/$SITE/mlx_lm/models/qwen3_next.py) raw-route=$(grep -c gated_delta_update_raw $CTL/$SITE/mlx_lm/models/gated_delta.py) scaled=$(grep -c rms_norm_scaled $CTL/$SITE/mlx_lm/models/qwen3_5.py) gated-norm=$(grep -c rms_norm_gated $CTL/$SITE/mlx_lm/models/qwen3_next.py)"
sha256sum $CTL/$SITE/mlx/lib/libmlx.so 2>/dev/null | cut -c1-16 || find $CTL/$SITE/mlx -name "libmlx*.so*" -exec sha256sum {} \; | cut -c1-40
echo "== installed census =="
"$CTL/bin/python" $D/census.py "$MODEL" "$PROMPTS" "$O/census-installed" 4 2>> "$O/census-installed.trace"
python3 - "$O/census-installed.trace" <<'EOF'
import sys,re,collections
lines=open(sys.argv[1]).read().splitlines()
segs=[];cur=None
for l in lines:
    if l.startswith('TOKEN_END'): cur=[]
    elif l.startswith('TOKEN_BEGIN') and cur is not None: segs.append(cur);cur=None
    elif cur is not None: cur.append(l)
print("census dispatches/token:",[sum('DISPATCH' in l for l in s) for s in segs])
EOF
echo "== installed-default contract x3 (3-pass) =="
for r in 1 2 3; do contract "installed-r$r" 3; done
echo "== cpufreq governor A/B (performance vs schedutil) =="
for p in /sys/devices/system/cpu/cpufreq/policy*; do echo performance | sudo -n tee $p/scaling_governor >/dev/null; done
cat /sys/devices/system/cpu/cpufreq/policy*/scaling_governor | tr '\n' ' '; echo
contract "installed-perfgov-r1" 3
for p in /sys/devices/system/cpu/cpufreq/policy*; do echo schedutil | sudo -n tee $p/scaling_governor >/dev/null; done
cat /sys/devices/system/cpu/cpufreq/policy*/scaling_governor | tr '\n' ' '; echo
contract "installed-r4" 3
echo "== probes + no-split battery on the installed stack =="
VENV=$CTL PAIRS=${PAIRS:-10} bash $D/body-battery.sh
