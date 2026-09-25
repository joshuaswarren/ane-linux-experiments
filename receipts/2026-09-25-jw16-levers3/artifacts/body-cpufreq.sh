#!/usr/bin/env bash
# Step 3: clean paired CPU-clock A/B on a quiet box, installed serving stack.
# Arms per rep (interleaved): sched = stock schedutil; floor = schedutil with
# scaling_min_freq raised to scaling_max_freq on every policy; dma = stock
# schedutil + /dev/cpu_dma_latency held at 0 (no CPU PD idle state); both.
# Every arm is restored before the next leg; the trap restores on any exit.
set -uo pipefail
D=/var/tmp/levers3
VENV=${VENV:-/var/tmp/v072-venv-fused}
MODEL="$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*)"
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
BENCH=~/bench-scripts/qwen38-mlx-bench.py
REPS=${REPS:-4}
POLICIES=(/sys/devices/system/cpu/cpufreq/policy*)
declare -A ORIG_MIN
for p in "${POLICIES[@]}"; do ORIG_MIN[$p]=$(cat "$p/scaling_min_freq"); done
DMA_PID=
state(){ for p in "${POLICIES[@]}"; do printf "%s:%s/min=%s/max=%s " "$(basename $p)" "$(cat $p/scaling_governor)" "$(cat $p/scaling_min_freq)" "$(cat $p/scaling_max_freq)"; done; printf "dma_pid=%s\n" "${DMA_PID:-none}"; }
floor_on(){ for p in "${POLICIES[@]}"; do cat "$p/scaling_max_freq" | sudo -n tee "$p/scaling_min_freq" >/dev/null; done; }
floor_off(){ for p in "${POLICIES[@]}"; do echo "${ORIG_MIN[$p]}" | sudo -n tee "$p/scaling_min_freq" >/dev/null; done; }
dma_on(){ # hold /dev/cpu_dma_latency at 0 for as long as the holder lives
  sudo -n python3 -c 'import os,signal,struct,sys
fd=os.open("/dev/cpu_dma_latency", os.O_WRONLY); os.write(fd, struct.pack("i",0)); sys.stdout.write("held\n"); sys.stdout.flush(); signal.pause()' &
  DMA_PID=$!; sleep 1; }
dma_off(){ [ -n "${DMA_PID:-}" ] && { sudo -n kill "$DMA_PID" 2>/dev/null; wait "$DMA_PID" 2>/dev/null; }; DMA_PID=; }
restore(){ floor_off; dma_off; echo "restored: $(state)"; }
trap restore EXIT
contract(){ # label passes
  local label=$1 passes=$2
  MLX_COMMIT_TAG="$label" "$VENV/bin/python" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" \
    --limit 10 --warmup 3 --passes "$passes" --new-tokens 32 --prefill-tokens 512 \
    --label "$label" --out "$O/contract-$label.json" >> "$O/contract-$label.console" 2>&1
  python3 $D/summ.py "$O/contract-$label.json"
}
echo "venv=$VENV wheel=$($VENV/bin/pip list 2>/dev/null | grep mlx-omarchy | tr -s ' ') icd=$(tr -d ' \n' < /usr/share/vulkan/icd.d/asahi_icd.aarch64.json)"
echo "start: $(state) load=$(cut -d' ' -f1-3 /proc/loadavg)"
until [ "$(python3 -c 'import os;print(int(os.getloadavg()[0]*100))')" -lt 120 ]; do sleep 5; done
for r in $(seq 1 "$REPS"); do
  echo "== rep $r =="
  echo "arm sched: $(state)";            contract "sched-r$r" 3
  floor_on;  echo "arm floor: $(state)"; contract "floor-r$r" 3; floor_off
  dma_on;    echo "arm dma: $(state)";   contract "dma-r$r" 3;   dma_off
  floor_on; dma_on; echo "arm both: $(state)"; contract "both-r$r" 3; dma_off; floor_off
done
echo "== summary (decode tok/s per arm, sorted) =="
for a in sched floor dma both; do
  printf "%-6s " "$a"; for f in "$O"/contract-$a-r*.json; do python3 -c "import json;print(round(json.load(open('$f'))['decode_tok_rate']['median'],2), end=' ')"; done; echo
done
echo CPUFREQ_BODY_DONE
