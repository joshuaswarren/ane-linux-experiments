#!/usr/bin/env bash
# Clean-environment gate battery for jwm1 (Jwm1Kernels2, 2026-09-25).
# Same battery as the 958783d9 receipt (kexp/dft_gates.sh, untracked scratch)
# plus an explicit debug/trace env guard so every measurement is honest
# regardless of the invoking shell. Run on jwm1.
set -uo pipefail
exec 9>/tmp/m1-gpu.lock
flock -w 1200 9 || exit 3
echo "LOCK-HELD $(date -Is)"

# --- env guard: contracts must never run with debug/trace instrumentation ---
for v in MLX_OMARCHY_TRACE_DISPATCH MLX_OMARCHY_GPU_PROFILE HK_PERF HK_PERFTEST \
         AGX_CDM_SKIP_MODE MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_TRACE_SUBMIT; do
  if [ -n "${!v:-}" ]; then
    echo "ENV-GUARD: unsetting $v='${!v}'"
    unset "$v"
  fi
done
echo "ENV-GUARD-CLEAN: $(env | grep -cE '^(MLX_OMARCHY|HK_PERF|HK_PERFTEST|AGX_)' || true) matching vars remain"

# --- pinned wheel: exact installed baseline build (7c0bd851) ---
WHEEL=~/q38-build/out2/mlx_omarchy-0.32.3.dev202609252026+7c0bd851-cp314-cp314-linux_aarch64.whl
V=/var/tmp/jwm1-parity3-venv/bin
$V/pip install -q --force-reinstall --no-deps "$WHEEL" 2>&1 | tail -1
$V/python -c "import mlx.core as mx; import mlx_omarchy; print('installed', mx.metal.is_available())"
$V/pip show mlx-omarchy | grep -E "^Version"

M=$(ls -d ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/ | head -1)
B=~/src/ane-linux-experiments/benchmarks/qwen38-mlx-bench.py
P=~/src/ane-linux-experiments/benchmarks/qwen38-2b-prompts.jsonl
OUT=/tmp/dft-gates-clean
mkdir -p $OUT

for PASSES in 1 3 10; do
  MLX_COMMIT_TAG=clean-$PASSES $V/python $B --model "$M" --prompts $P \
    --limit 10 --warmup 3 --passes $PASSES --new-tokens 32 --prefill-tokens 512 \
    --label clean-gate-$PASSES --out $OUT/contract-$PASSES.json 2>$OUT/bench-$PASSES.err
  python3 - "$OUT/contract-$PASSES.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
dec = d["decode_tok_rate"]["median"]; pre = d["pure_prefill"]["pure_prefill_tok_rate"]
ttft = d["ttft_tok_rate"]["median"]; dig = d["ordered_records_sha256"][:16]
print(f"passes_result decode={dec} prefill512={pre} ttft={ttft} digest={dig}")
PY
done

cd /var/tmp/jwm1-parity3
echo "=== validate_chain"
$V/python validate_chain.py 2>/dev/null | tail -3
echo "=== corpus"
$V/python corpus_gate.py 2>/dev/null | tail -3
echo "=== chain wall"
$V/python chain_bench.py 64 5 2>/dev/null | tail -1
echo "=== mel wall"
$V/python mel_bench.py 2>/dev/null | tail -1
echo "=== contract3 (full Parakeet pipeline + gates)"
CONTRACT_PKG=~/q38-build/mlx-omarchy/overlay/tools $V/python contract3.py 2>$OUT/contract3.err | tail -6
echo "DONE $(date -Is)"
