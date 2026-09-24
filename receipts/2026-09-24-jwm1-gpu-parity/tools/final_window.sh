#!/usr/bin/env bash
# Final measurement window for the jwm1 SDPA-port lane (2026-09-24).
# Three interleaved arms under one flock:
#   ctl-base : denom-b4757ac-venv (bf8793f)  — the receipted 17.46 baseline stack
#   ctl-lineage: venv-base (2df890483 rel/v0.7.3, no SDPA) — clean SDPA-only control
#   cand     : venv-cand (f9d7bb21d = rel/v0.7.3 + SDPA hd256) — the port
# 10 interleaved reps x 1 pass (warmup 3) + one 10-pass anchor per arm.
# Then: paired stats (cand vs each ctl), budget profile via diag wheel,
# microbench, family bench.
set -uo pipefail
LOCK=/tmp/m1-gpu.lock
OUT=/var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/raw
SDPA_RAW=$OUT/sdpa-hd256
PROF_RAW=$OUT/profile
CAND_VENV=/var/tmp/m1-sdpa256/venv-cand
DIAG_VENV=/var/tmp/m1-sdpa256/venv-diag
BASE_VENV=/var/tmp/m1-sdpa256/venv-base
CTL_VENV=/var/tmp/denom-b4757ac-venv
MODEL=$HOME/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/0867d98bfb174b042d88461c0e7c97b86b34b381
BENCH=$HOME/src/ane-linux-experiments/benchmarks/qwen38-mlx-bench.py
PROMPTS=$HOME/src/ane-linux-experiments/benchmarks/qwen38-2b-prompts.jsonl
TOOLS=/var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/tools
mkdir -p "$SDPA_RAW" "$PROF_RAW"

run_arm() { # run_arm <venv-python> <tag> <rep>
  local py="$1" tag="$2" rep="$3"
  if [ -e "${SDPA_RAW}/contract-${tag}-r${rep}.json" ]; then
    echo "skip ${tag}-r${rep} (exists)"
    return 0
  fi
  MLX_DISABLE_COMPILE=1 MLX_COMMIT_TAG="${tag}-r${rep}" "$py" "$BENCH" \
    --model "$MODEL" --prompts "$PROMPTS" \
    --limit 10 --warmup 3 --passes 1 --new-tokens 32 --prefill-tokens 512 \
    --label "${tag}-r${rep}" \
    --out "${SDPA_RAW}/contract-${tag}-r${rep}.json" \
    2> "${SDPA_RAW}/console-${tag}-r${rep}.log"
  echo "[$(date -Is)] done ${tag}-r${rep}"
}

run_anchor() { # run_anchor <venv-python> <tag>
  local py="$1" tag="$2"
  if [ -e "${SDPA_RAW}/contract-${tag}-p10.json" ]; then
    echo "skip ${tag}-p10 (exists)"
    return 0
  fi
  MLX_DISABLE_COMPILE=1 MLX_COMMIT_TAG="${tag}-p10" "$py" "$BENCH" \
    --model "$MODEL" --prompts "$PROMPTS" \
    --limit 10 --warmup 3 --passes 10 --new-tokens 32 --prefill-tokens 512 \
    --label "${tag}-p10" \
    --out "${SDPA_RAW}/contract-${tag}-p10.json" \
    2> "${SDPA_RAW}/console-${tag}-p10.log"
  echo "[$(date -Is)] done ${tag}-p10"
}

(
  flock -w 3000 9 || { echo "flock timeout"; exit 3; }

  CTL_PY=$CTL_VENV/bin/python
  CAND_PY=$CAND_VENV/bin/python
  if [ -x "$BASE_VENV/bin/python" ]; then BASE_PY=$BASE_VENV/bin/python; else BASE_PY=""; fi

  echo "arms: ctl(bf8793f)=$CTL_PY cand(f9d7bb2)=$CAND_PY base(2df8904)=${BASE_PY:-skipped}"
  for rep in 1 2 3 4 5 6 7 8 9 10; do
    run_arm "$CTL_PY" ctl-sdpa256 "$rep"
    run_arm "$CAND_PY" cand-sdpa256 "$rep"
    [ -n "$BASE_PY" ] && run_arm "$BASE_PY" base-sdpa256 "$rep"
  done
  run_anchor "$CTL_PY" ctl-sdpa256
  run_anchor "$CAND_PY" cand-sdpa256
  [ -n "$BASE_PY" ] && run_anchor "$BASE_PY" base-sdpa256
) 9>"$LOCK"

echo "== paired stats =="
python3 "$TOOLS/paired_decode.py" --out-dir "$SDPA_RAW" --tag sdpa256 2>&1 || true
# base-arm paired stats if present
if [ -n "$BASE_PY" ]; then
  for i in 1 2 3 4 5 6 7 8 9 10; do
    [ -e "$SDPA_RAW/contract-base-sdpa256-r$i.json" ] || continue
  done
  python3 - <<'PYEOF'
import json, math, os
sd = "/var/tmp/jwm1-gpu-parity-wt-ane/receipts/2026-09-24-jwm1-gpu-parity/raw/sdpa-hd256"
def med(v):
    v = sorted(v); return v[len(v)//2]
try:
    base = [json.load(open(f"{sd}/contract-base-sdpa256-r{i}.json"))["decode_tok_rate"]["median"] for i in range(1, 11)]
    cand = [json.load(open(f"{sd}/contract-cand-sdpa256-r{i}.json"))["decode_tok_rate"]["median"] for i in range(1, 11)]
    diffs = [c - b for c, b in zip(cand, base)]
    n = len(diffs); m = sum(diffs)/n
    sd = math.sqrt(sum((x-m)**2 for x in diffs)/(n-1)) if n > 1 else 0
    se = sd/math.sqrt(n)
    t = 2.262  # df=9
    print(f"base->cand paired delta {m:+.3f} +/- {t*se:.3f} (95%), ratio {sum(cand)/sum(base):.4f}")
    open(f"{sd}/paired-base-cand.txt","w").write(f"cand vs base(2df8904): {m:+.3f} +/- {t*se:.3f} (95% CI), ratio {sum(cand)/sum(base):.4f}\n")
except FileNotFoundError:
    print("base arm incomplete; skipping base->cand pairing")
PYEOF
fi

if [ -e "${PROF_RAW}/budget-installed.md" ]; then echo "skip budget profile (exists)"; else
echo "== budget profile (decode + prefill, diag wheel) =="
(
  flock -w 3000 9 || exit 3
  MLX_DISABLE_COMPILE=1 MLX_OMARCHY_GPU_PROFILE="${PROF_RAW}/prof-installed.jsonl" \
    "$DIAG_VENV/bin/python" "$TOOLS/prof_decode.py" \
      --model "$MODEL" --prompts "$PROMPTS" --prompt-idx 0 --new-tokens 32 \
      --markers "${PROF_RAW}/markers-installed.jsonl"
  python3 "$TOOLS/profile_analyze.py" \
    --profile "${PROF_RAW}/prof-installed.jsonl" \
    --markers "${PROF_RAW}/markers-installed.jsonl" \
    --out-prefix "${PROF_RAW}/analyze-installed"
  python3 "$TOOLS/budget_report.py" \
    --profile "${PROF_RAW}/prof-installed.jsonl" \
    --markers "${PROF_RAW}/markers-installed.jsonl" \
    --wall-ms 57.27 --out "${PROF_RAW}/budget-installed.md"
) 9>"$LOCK"
fi

echo "== microbench =="
[ -e "$SDPA_RAW/microbench-cand.json" ] || MLX_DISABLE_COMPILE=1 "$CAND_PY" "$TOOLS/microbench_sdpa_hd256.py" --out "$SDPA_RAW/microbench-cand.json" --reps 300 || true
[ -e "$SDPA_RAW/microbench-ctl.json" ] || MLX_DISABLE_COMPILE=1 "$CTL_PY" "$TOOLS/microbench_sdpa_hd256.py" --out "$SDPA_RAW/microbench-ctl.json" --reps 300 || true

echo "== family bench =="
[ -e "$OUT/families-installed-current.json" ] || bash "$TOOLS/run_family_bench.sh" "$CTL_VENV" "$MODEL" "$OUT/families-installed-current.json" 2>&1 | tail -3 || true
python3 "$TOOLS/family_delta.py" --linux "$OUT/families-installed-current.json" --out "$OUT/family-delta-current.md" || true

echo "== window complete =="
