#!/usr/bin/env bash
# Step 4 phase B: which of the CDM_BARRIER bits the G13X trim dropped
# (0x178 -> upstream 0xfffff) closes the no-split race? Logit pins under the
# no-split + mask-knob build (2aefdd5), HK_CDM_BARRIER_MASK per arm.
# Phase C: the 09-24 dep-skip (92ac13a rebased on 2aefdd5 = 5a520cf, barriers
# routed through the mask-aware flush) with the kitchen-sink set and
# MLX_OMARCHY_GATED_BARRIERS=1 - i.e. the skip of the per-launch barrier
# between mlx-proven-disjoint launches, with the corrected flush set.
# Then 3-pass contracts for timing on the arms that pin.
set -uo pipefail
D=/var/tmp/levers3
VENV=${VENV:-/var/tmp/v072-venv-fused}
MODEL="$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*)"
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
BENCH=~/bench-scripts/qwen38-mlx-bench.py
ICD=/var/tmp/levers/icd
REPS=${REPS:-3}
echo "icd=$(tr -d ' \n' < /usr/share/vulkan/icd.d/asahi_icd.aarch64.json) nosplit-knob=$(sha256sum $ICD/libvulkan_asahi.so.nosplit | cut -c1-16) depskip=$(sha256sum $ICD/libvulkan_asahi.so.depskip | cut -c1-16)"
pin(){ # label [env...]
  local label=$1; shift
  env "$@" "$VENV/bin/python" $D/logitpin.py --model "$MODEL" --prompts "$PROMPTS" --limit 10 --new-tokens 32 --passes 1 --warmup 1 \
    --label "$label" --out "$O/pin-$label.json" 2>> "$O/pin-$label.console" | tee -a "$O/pins.txt"
}
contract(){ # label passes [env...]
  local label=$1 passes=$2; shift 2
  env "$@" MLX_COMMIT_TAG="$label" "$VENV/bin/python" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" \
    --limit 10 --warmup 3 --passes "$passes" --new-tokens 32 --prefill-tokens 512 \
    --label "$label" --out "$O/contract-$label.json" >> "$O/contract-$label.console" 2>&1
  python3 $D/summ.py "$O/contract-$label.json" | tee -a "$O/contracts.txt"
}
NS=$ICD/nosplit.icd.json; DS=$ICD/depskip.icd.json
until [ "$(python3 -c 'import os;print(int(os.getloadavg()[0]*100))')" -lt 120 ]; do sleep 5; done
pin "ctl-r0"
for r in $(seq 1 "$REPS"); do
  echo "== rep $r =="
  pin "ns-178-r$r"     VK_DRIVER_FILES=$NS HK_CDM_BARRIER_MASK=0x178
  pin "ns-17f-r$r"     VK_DRIVER_FILES=$NS HK_CDM_BARRIER_MASK=0x17f
  pin "ns-1f8-r$r"     VK_DRIVER_FILES=$NS HK_CDM_BARRIER_MASK=0x1f8
  pin "ns-1f78-r$r"    VK_DRIVER_FILES=$NS HK_CDM_BARRIER_MASK=0x1f78
  pin "ns-e178-r$r"    VK_DRIVER_FILES=$NS HK_CDM_BARRIER_MASK=0xe178
  pin "ns-f0178-r$r"   VK_DRIVER_FILES=$NS HK_CDM_BARRIER_MASK=0xf0178
  pin "ns-fffff-r$r"   VK_DRIVER_FILES=$NS HK_CDM_BARRIER_MASK=0xfffff
  pin "ds-178-g-r$r"   VK_DRIVER_FILES=$DS HK_CDM_BARRIER_MASK=0x178   MLX_OMARCHY_GATED_BARRIERS=1
  pin "ds-fffff-g-r$r" VK_DRIVER_FILES=$DS HK_CDM_BARRIER_MASK=0xfffff MLX_OMARCHY_GATED_BARRIERS=1
  pin "ds-fffff-r$r"   VK_DRIVER_FILES=$DS HK_CDM_BARRIER_MASK=0xfffff
done
echo "== compare vs ctl-r0 =="
python3 $D/logitcmp.py "$O/pin-ctl-r0.json" "$O"/pin-*.json | sort
echo "== timing: 3-pass contracts, 2 interleaved reps =="
for r in 1 2; do
  contract "t-ctl-r$r" 3
  contract "t-ns-fffff-r$r" 3   VK_DRIVER_FILES=$NS HK_CDM_BARRIER_MASK=0xfffff
  contract "t-ds-fffff-g-r$r" 3 VK_DRIVER_FILES=$DS HK_CDM_BARRIER_MASK=0xfffff MLX_OMARCHY_GATED_BARRIERS=1
  contract "t-ns-178-r$r" 3     VK_DRIVER_FILES=$NS HK_CDM_BARRIER_MASK=0x178
done
echo BARRIER_B_DONE
