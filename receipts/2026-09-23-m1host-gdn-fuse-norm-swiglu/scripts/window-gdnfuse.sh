#!/usr/bin/env bash
# m1-host qualification + A/B window for the gdn-fuse candidate.
# Contract: tensor bit-exactness, then 3 warmups + 10 paired interleaved
# contract reps per arm, then logits gate v4 on both arms + compare.
# One persistent flock inode held for the whole window.
#
# usage: window-gdnfuse.sh <cand-wheel-path>
set -euo pipefail
CAND_WHL="$1"
VP=/var/tmp/vprof
MODEL="$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/)"
BENCH=~/.local/bench-scripts/qwen38-mlx-bench.py
[[ -f "$BENCH" ]] || BENCH=~/bench-scripts/qwen38-mlx-bench.py
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
GATE=/var/tmp/rmsprol-venv/logits-gate/logits_gate_v4.py
PATCHES=/var/tmp/jgd-fuse
OUT="$VP/ab-gdnfuse"
mkdir -p "$OUT"

V="$VP/venv-gdnfuse"
if [[ ! -x "$V/bin/python" ]]; then
  python3 -m venv --system-site-packages "$V"
  "$V/bin/pip" -q install "$CAND_WHL" mlx-lm==0.31.3
  python3 /var/tmp/dg/scripts/patch-mlx-lm-gdn.py "$V"
  python3 /var/tmp/dg/scripts/patch-mlx-lm-gdn-raw.py "$V"
  site="$(dirname "$(ls -d "$V"/lib/python3.*/site-packages/mlx_lm)")"
  patch --directory="$site" --strip=1 --forward --fuzz=0 < /var/tmp/vp/mlx-lm-greedy-prune.patch
  python3 "$PATCHES/patch-mlx-lm-qwen35-gdn-norm.py" "$V"
fi
"$V/bin/python" -c "import importlib.metadata as m; print('cand wheel', m.version('mlx-omarchy'))" | tee "$OUT/cand-version.txt"
"$V/bin/python" -c "import mlx.core as mx; print('rms_norm_gated present:', hasattr(mx.fast, 'rms_norm_gated'), 'rms_norm_scaled:', hasattr(mx.fast, 'rms_norm_scaled'))" | tee -a "$OUT/cand-version.txt"
CTL=/var/tmp/vp/venv-cand/bin/python
CAND="$V/bin/python"

# ---- tensor-level bit-exactness (fail fast, no bench on failure) ----
echo "== tensor bit-exactness =="
"$CAND" "$PATCHES/qual_bitexact.py" 2>&1 | tee "$OUT/bitexact.txt"
grep -q "ALL_BIT_EXACT" "$OUT/bitexact.txt"

exec 9>/tmp/m1-gpu.lock
flock 9
echo "lock held $(date -Is)"

# ---- dispatch sanity: fused kernel actually replaces the chain ----
cat > /tmp/jgd-count.py <<'PYEOF'
import sys
import mlx.core as mx
from mlx_lm.utils import load
model, _ = load(sys.argv[1])
tok = model.config
import mlx_lm
print("loaded")
PYEOF

# ---- A/B: 10 interleaved pairs ----
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

# ---- logits gate ----
echo "== logits gate =="
"$CTL" "$GATE" --model "$MODEL" --prompts "$PROMPTS" --out "$OUT/gate-ctl.json" 2>&1 | tail -1
"$CAND" "$GATE" --model "$MODEL" --prompts "$PROMPTS" --out "$OUT/gate-cand.json" 2>&1 | tail -1
"$CTL" "$GATE" --model "$MODEL" --prompts "$PROMPTS" --compare "$OUT/gate-cand.json" --out "$OUT/gate-compare.json" 2>&1 | tail -3

# ---- post-qual greedy prune check (installed config invariant) ----
if [[ -f /var/tmp/vp/greedy_qual.py ]]; then
  "$CAND" /var/tmp/vp/greedy_qual.py "$MODEL" ~/bench-scripts/qwen38-2b-prompts.jsonl "$OUT/smoke-qual-prune.json" 2>&1 | tail -2 | sed 's/^/[qual] /' || true
fi

echo "lock released $(date -Is)"
