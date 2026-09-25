#!/usr/bin/env bash
# Step 4 phase A: per-step logit fingerprints (logitpin.py, 1 pass x 10 prompts
# x 32 tokens) across driver arms, REPS interleaved reps each. A stale read
# that only flips a token at a near-tie in 1/1000 records still perturbs the
# logits of most steps, so this sees it in one pass. Arms:
#   ctl        system ICD (d3fa18e: split at every barrier, set 0x178)
#   nosplit    41ccf96 (no split, 0x178)                 - the battery's 12/1000 arm
#   ns-mask178 2aefdd5 build (no split + mask knob), HK_CDM_BARRIER_MASK=0x178 (knob equivalence)
#   ns-kitchen 2aefdd5 build, HK_CDM_BARRIER_MASK=0xfffff (upstream kitchen sink, bits 0-19)
#   sp-kitchen 49de6c2 build (split + mask knob), HK_CDM_BARRIER_MASK=0xfffff
set -uo pipefail
D=/var/tmp/levers3
VENV=${VENV:-/var/tmp/v072-venv-fused}
MODEL="$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*)"
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
ICD=/var/tmp/levers/icd
REPS=${REPS:-5}
DUMP="8:0,8:5,8:6,7:15,7:19,1:14,4:25"
echo "venv=$VENV wheel=$($VENV/bin/pip list 2>/dev/null | grep mlx-omarchy | tr -s ' ') icd=$(tr -d ' \n' < /usr/share/vulkan/icd.d/asahi_icd.aarch64.json)"
for f in $ICD/libvulkan_asahi.so.41ccf96 $ICD/libvulkan_asahi.so.nosplit $ICD/libvulkan_asahi.so.mask /usr/local/lib/libvulkan_asahi.so.d3fa18e; do echo "$(basename $f) sha=$(sha256sum $f | cut -c1-16) mask_knob=$(strings $f | grep -c HK_CDM_BARRIER_MASK)"; done
pin(){ # label [env...]
  local label=$1; shift
  env "$@" "$VENV/bin/python" $D/logitpin.py --model "$MODEL" --prompts "$PROMPTS" --limit 10 --new-tokens 32 --passes 1 --warmup 1 \
    --label "$label" --out "$O/pin-$label.json" ${DUMP:+--dump "$DUMP"} 2>> "$O/pin-$label.console" | tee -a "$O/pins.txt"
}
until [ "$(python3 -c 'import os;print(int(os.getloadavg()[0]*100))')" -lt 120 ]; do sleep 5; done
for r in $(seq 1 "$REPS"); do
  echo "== rep $r =="
  pin "ctl-r$r"
  pin "nosplit-r$r"    VK_DRIVER_FILES=$ICD/41ccf96.icd.json
  pin "ns-mask178-r$r" VK_DRIVER_FILES=$ICD/nosplit.icd.json HK_CDM_BARRIER_MASK=0x178
  pin "ns-kitchen-r$r" VK_DRIVER_FILES=$ICD/nosplit.icd.json HK_CDM_BARRIER_MASK=0xfffff
  pin "sp-kitchen-r$r" VK_DRIVER_FILES=$ICD/mask.icd.json    HK_CDM_BARRIER_MASK=0xfffff
  DUMP=
done
echo "== compare vs ctl-r1 =="
python3 $D/logitcmp.py "$O/pin-ctl-r1.json" "$O"/pin-*.json | sort
echo BARRIER_A_DONE
