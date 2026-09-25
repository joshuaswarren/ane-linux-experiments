#!/usr/bin/env bash
# m1-host A/B window: ctl (installed a91adbf config) vs cand (batch-budget 4096
# wheel). One persistent flock inode for the whole window.
# Contract: warmup 3, passes 10 interleaved, prefill 512, greedy, then logits
# gate v4 on both arms + compare. usage: window-ab.sh <cand-wheel>
set -euo pipefail
CAND_WHL="$1"
VP=/var/tmp/vprof
MODEL="$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/)"
BENCH=~/.local/bench-scripts/qwen38-mlx-bench.py
[[ -f "$BENCH" ]] || BENCH=~/bench-scripts/qwen38-mlx-bench.py
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
GATE=/var/tmp/rmsprol-venv/logits-gate/logits_gate_v4.py
OUT="$VP/ab"
mkdir -p "$OUT"

V="$VP/venv-cand2"
if [[ ! -x "$V/bin/python" ]]; then
  python3 -m venv --system-site-packages "$V"
  "$V/bin/pip" -q install "$CAND_WHL" mlx-lm==0.31.3
  python3 /var/tmp/dg/scripts/patch-mlx-lm-gdn.py "$V"
  python3 /var/tmp/dg/scripts/patch-mlx-lm-gdn-raw.py "$V"
  site="$(dirname "$(ls -d "$V"/lib/python3.*/site-packages/mlx_lm)")"
  patch --directory="$site" --strip=1 --forward --fuzz=0 < /var/tmp/vp/mlx-lm-greedy-prune.patch
fi
"$V/bin/python" -c "import importlib.metadata as m; print('cand wheel', m.version('mlx-omarchy'))" | tee "$OUT/cand-version.txt"
"$VP/venv-diag2/bin/python" -c "import importlib.metadata as m; print('ctl wheel(diag venv)', m.version('mlx-omarchy'))" >> "$OUT/cand-version.txt" || true
CTL=/var/tmp/vp/venv-cand/bin/python
CAND="$V/bin/python"

exec 9>/tmp/m1-gpu.lock
flock 9
echo "lock held $(date -Is)"

runarm() { # runarm <python> <tag> <rep>
  MLX_COMMIT_TAG="$2" "$1" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" \
    --limit 10 --warmup 3 --passes 1 --new-tokens 32 --prefill-tokens 512 \
    --label "$2-r$3" --out "$OUT/contract-$2-r$3.json" 2>&1 \
    | grep -E "ordered_records|pure_prefill|decode" | tail -2 | sed "s/^/[$2-r$3] /"
}
for rep in 1 2 3 4 5 6 7 8 9 10; do
  runarm "$CTL" ctl "$rep"
  runarm "$CAND" cand "$rep"
done

echo "== logits gate =="
"$CTL" "$GATE" --model "$MODEL" --prompts "$PROMPTS" --out "$OUT/gate-ctl.json" 2>&1 | tail -1
"$CAND" "$GATE" --model "$MODEL" --prompts "$PROMPTS" --out "$OUT/gate-cand.json" 2>&1 | tail -1
"$CTL" "$GATE" --model "$MODEL" --prompts "$PROMPTS" --compare "$OUT/gate-cand.json" --out "$OUT/gate-compare.json" 2>&1 | tail -3
echo "lock released $(date -Is)"
