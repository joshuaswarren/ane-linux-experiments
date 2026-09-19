#!/usr/bin/env bash
# Window: wait-batching re-screen WITH AGX_SIMDMAT=1 (coopmat on).
# base vs wb, same packages as window-wb.sh, 6 paired rounds. Digests fatal.
exec > /var/tmp/cb/window-wb2.log 2>&1
set -uo pipefail
L=/var/tmp/cb
exec 9>/tmp/m1-gpu.lock
flock -w 3600 9 || { echo FLOCK-FAIL; exit 5; }
cleanup() {
  sudo -n systemctl start llm-inference.service
  sleep 3
  echo "post: $(systemctl is-active llm-inference.service)"
}
trap cleanup EXIT
echo "== lock acquired $(date -u +%FT%TZ), inode: $(ls -i /tmp/m1-gpu.lock) =="
sudo -n systemctl stop llm-inference.service || exit 1
sleep 2
echo "pre: $(systemctl is-active llm-inference.service)"
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=$L/spirv
export MLX_OMARCHY_EXPECTED_LIBMLX_SHA256=df3d4e74c597956c
PY=/var/tmp/v071perf-venv/bin/python
B=$L/scripts/bench_decode.py
MODEL=/var/tmp/jw16gap-model
# warmup + digest gates per arm per leg with simdat on (new cache keys)
for arm in base wb; do
  export VK_DRIVER_FILES=/var/tmp/MesaL2/pkg-$arm/icd.json
  export AGX_SIMDMAT=1
  for legdesc in "short:Hi:7fd25a869ff21678" "ctx1024:$(cat /var/tmp/TermAJW16/prompt-ctx1024.txt):7da83f06ec9f001d"; do
    leg=${legdesc%%:*}; rest=${legdesc#*:}; text=${rest%:*}; pin=${rest##*:}
    out=$(timeout 600 $PY $B --model "$MODEL" --prompt "$text" --tokens 32 \
      --temp 0.0 --seed 0 --warmup-tokens 4 2>&1)
    rc=$?
    dg=$(printf "%s" "$out" | grep -o "generated_ids sha256:[0-9a-f]*" | head -1 | cut -d: -f2)
    echo "== warmup $arm/$leg rc=$rc digest=$dg"
    if [ "$rc" -ne 0 ] || [ "$dg" != "$pin" ]; then
      printf "%s\n" "$out" | tail -8
      echo "== WARMUP FAIL $arm/$leg"
      exit 7
    fi
  done
done
unset VK_DRIVER_FILES AGX_SIMDMAT
export AGX_SIMDMAT=1
timeout 3600 $PY $L/cb_ab.py \
  --bench "$B" --model "$MODEL" \
  --short-text "Hi" \
  --ctx-text "$(cat /var/tmp/TermAJW16/prompt-ctx1024.txt)" \
  --arm "base=VK_DRIVER_FILES=/var/tmp/MesaL2/pkg-base/icd.json" \
  --arm "wb=VK_DRIVER_FILES=/var/tmp/MesaL2/pkg-wb/icd.json" \
  --rounds 6 --out $L/ab-wb-simmat.json
echo "== battery rc=$? $(date -Is)"
date -u +%FT%TZ > $L/finished-wb2.txt
