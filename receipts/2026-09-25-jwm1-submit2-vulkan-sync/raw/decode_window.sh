#!/usr/bin/env bash
# One small Qwen contract window under ftrace + CPU-freq sampling.
set -uo pipefail
exec 9>/tmp/m1-gpu.lock
flock -w 900 9 || exit 3

MODEL=$(ls -d "$HOME"/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/ | head -1)
BENCH=$HOME/src/ane-linux-experiments/benchmarks/qwen38-mlx-bench.py
PROMPTS=$HOME/src/ane-linux-experiments/benchmarks/qwen38-2b-prompts.jsonl
VENV=/var/tmp/jwm1-parity3-venv/bin/python
OUT=/tmp/submitwin
mkdir -p "$OUT"

# CPU freq sampler: every 30ms, policy0+policy2 cur freq + busy pid
(
  for i in $(seq 1 400); do
    f0=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq 2>/dev/null)
    f2=$(cat /sys/devices/system/cpu/cpufreq/policy2/scaling_cur_freq 2>/dev/null)
    echo "$(date +%s.%N) $f0 $f2" >> "$OUT/cpu_freq.log"
    sleep 0.03
  done
) &
SAMPLER=$!

echo 1 | sudo -n tee /sys/kernel/tracing/events/gpu_scheduler/enable >/dev/null
echo 1 | sudo -n tee /sys/kernel/tracing/events/dma_fence/enable >/dev/null
echo 1 | sudo -n tee /sys/kernel/tracing/tracing_on >/dev/null

MLX_DISABLE_COMPILE=1 MLX_COMMIT_TAG=submitwin "$VENV" "$BENCH" \
  --model "$MODEL" --prompts "$PROMPTS" \
  --limit 2 --warmup 1 --passes 1 --new-tokens 32 --prefill-tokens 512 \
  --label submitwin \
  --out "$OUT/contract-submitwin.json" \
  2> "$OUT/console.log"

RC=$?
echo 0 | sudo -n tee /sys/kernel/tracing/tracing_on >/dev/null
echo 0 | sudo -n tee /sys/kernel/tracing/events/gpu_scheduler/enable >/dev/null
echo 0 | sudo -n tee /sys/kernel/tracing/events/dma_fence/enable >/dev/null
kill "$SAMPLER" 2>/dev/null
sudo -n cp /sys/kernel/tracing/trace "$OUT/trace.txt"
sudo -n chmod 644 "$OUT/trace.txt"
chmod 644 "$OUT/cpu_freq.log" 2>/dev/null
echo "RC=$RC"
grep -E "decode_tok|prefill|ttft|digest" "$OUT/console.log" | head -8
tail -2 "$OUT/console.log"
