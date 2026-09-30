#!/bin/bash
# jw16 Linux GPU cells, same protocol as run-gpu-cells.sh (macOS):
#   decode 64/128/256/512 (one process, 5 passes), prefill 512/1024/2048 (5 processes).
# llm-inference discipline: stop, verify inactive + lock free, flock the run, restore
# via trap, verify health 200 AND a real completion probe.
# usage: run-linux-cells.sh OUTDIR [cells...]   cells default: d64 d128 d256 d512 pf512 pf1024 pf2048
# env: VK_DRIVER_FILES / MLX_OMARCHY_* / HK_* pass through (A/B arms), TAG label prefix.
set -u
# Window discipline: this script owns its whole window (stop, flock, restore). Refuse when nested in
# gpuwin.sh (nested flock on /tmp/m1-gpu.lock deadlocks and our restore would restart the service
# mid-window); otherwise take the same outer mutex so cell runs serialize with gpuwin windows.
if [ -n "${GPUWIN_HELD:-}" ]; then echo "refusing: do not run cell scripts inside gpuwin.sh; call them directly" >&2; exit 2; fi
exec 9>/tmp/gpuwin.mutex; flock -w 7200 9 || { echo "gpuwin mutex timeout" >&2; exit 1; }
OUT="${1:?outdir}"; shift
CELLS="${*:-d64 d128 d256 d512 pf512 pf1024 pf2048}"
TAG="${TAG:-linux}"
PY=${PY:-/var/tmp/v072-venv-fused/bin/python3}
BENCH=$HOME/bench-scripts/qwen38-mlx-bench.py
MODEL=$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/0867d98bfb174b042d88461c0e*)
grep -q 'max_tokens=a.new_tokens' "$BENCH" || { echo "bench lacks max_tokens fix"; exit 1; }
mkdir -p "$OUT"
restore_service () {
  echo "=== restore llm-inference $(date -Iseconds) ==="
  sudo systemctl start llm-inference.service
  local ok="" key rc
  for _ in $(seq 1 45); do
    if curl -sf -m 3 http://127.0.0.1:8002/health >/dev/null 2>&1; then ok=1; break; fi
    sleep 2
  done
  if [ -z "$ok" ]; then echo "health: FAILED"; return 1; fi
  echo "health: 200"
  key=$(sudo cat /etc/llm-inference/api-key) || return 1
  rc=$(curl -sS -m 60 http://127.0.0.1:8002/v1/chat/completions \
    -H "Authorization: Bearer $key" -H 'Content-Type: application/json' \
    -d '{"model":"default","messages":[{"role":"user","content":"Say Pacific"}],"max_tokens":8}' \
    | "$PY" -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['finish_reason'])" 2>/dev/null)
  echo "completion probe finish: ${rc:-FAILED}; is-active: $(systemctl is-active llm-inference.service)"
}
trap 'restore_service' EXIT
echo "=== stop llm-inference $(date -Iseconds) ==="
sudo systemctl stop llm-inference.service; sleep 2
echo "service after stop: $(systemctl is-active llm-inference.service); lock holders: [$(fuser /tmp/m1-gpu.lock 2>&1 || true)]"
{ date -u; uname -r; cat /proc/loadavg; cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | tr '\n' ' '; echo
  env | grep -E '^(VK_|MLX_OMARCHY|HK_)'; "$PY" -m pip list 2>/dev/null | grep -Ei '^(mlx|mlx-lm|mlx-omarchy|numpy) '
  vulkaninfo --summary 2>/dev/null | grep -E 'deviceName|driverInfo'; } > "$OUT/env.txt" 2>&1
B() { "$PY" "$BENCH" --model "$MODEL"/ --prompts "$HOME/bench-scripts/qwen38-2b-prompts.jsonl" --limit 1 "$@"; }
BD=${BD:-/var/tmp/appbar/prefill_breakdown.py}
export -f B; export PY BENCH MODEL OUT TAG CELLS BD
flock -w 900 /tmp/m1-gpu.lock bash -c '
for c in $CELLS; do
  case $c in
    d*) N=${c#d}; echo "--- decode $N $(date -u +%FT%TZ)"
        B --new-tokens $N --warmup 1 --passes 5 --prefill-tokens 512 --label $TAG-$c-n5 --out $OUT/qwen-gpu-$c-n5.json > $OUT/$c.log 2>&1 || echo "$c FAILED" ;;
    pf*) P=${c#pf}; for i in 1 2 3 4 5; do echo "--- prefill $P run $i $(date -u +%FT%TZ)"
        B --new-tokens 32 --warmup 1 --passes 1 --prefill-tokens $P --label $TAG-$c-$i --out $OUT/qwen-gpu-$c-$i.json > $OUT/$c-$i.log 2>&1 || echo "$c-$i FAILED"; done ;;
    bd*) T=${c#bd}; echo "--- breakdown $T $(date -u +%FT%TZ)"
        $PY $BD $MODEL $T 5 > $OUT/$c.json 2> $OUT/$c.err || echo "$c FAILED" ;;
    so*) T=${c#so}; echo "--- subops $T $(date -u +%FT%TZ)"
        $PY ${BD%/*}/mixer_subops.py $MODEL $T 5 > $OUT/$c.json 2> $OUT/$c.err || echo "$c FAILED" ;;
  esac
done'
( cd "$OUT" && sha256sum ./*.json ./*.log ./*.txt > SHA256SUMS )
echo LINUX-CELLS-DONE
