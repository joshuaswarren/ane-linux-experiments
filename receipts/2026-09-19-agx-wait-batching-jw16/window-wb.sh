#!/bin/bash
# Window: agx-wait-batching screen on jw16 (v0.7.1 wheel).
# Arms: base = trunk d8d4e1c500 rebuild (sha-pinned), wb = hk/agx-wait-batching merged tip 40905e2f2c.
# Digest pins fatal (short 7fd25a869ff21678, ctx1024 7da83f06ec9f001d); libmlx pin fatal.
exec > /var/tmp/cb/window-wb.log 2>&1
set -uo pipefail
L=/var/tmp/cb
cleanup() {
  echo "== restarting llm-inference $(date -Is) =="
  sudo -n systemctl start llm-inference.service
  sleep 3
  echo "post: $(systemctl is-active llm-inference.service)" | tee -a $L/service-wb.txt
}
trap cleanup EXIT
echo "== pause llm-inference $(date -Is) =="
sudo -n systemctl stop llm-inference.service || exit 1
sleep 2
echo "pre: $(systemctl is-active llm-inference.service)" | tee $L/service-wb.txt
exec 9>/tmp/m1-gpu.lock
flock -w 900 9 || { echo FLOCK-FAIL; exit 5; }
ls -i /tmp/m1-gpu.lock > $L/lock-wb.txt; cat $L/lock-wb.txt
date -u +%FT%TZ > $L/started-wb.txt
df -h /tmp | tee $L/df-wb.txt; free -g | tee $L/mem-wb.txt
avail_kb=$(df --output=avail /tmp | tail -1 | tr -d " ")
if [ "$avail_kb" -lt 3145728 ]; then echo "TMP LOW"; exit 3; fi
for arm in base wb; do
  [ -f /var/tmp/MesaL2/pkg-$arm/icd.json ] || { echo "MISSING arm $arm"; exit 4; }
done
ls -la /var/tmp/MesaL2/pkg-base/usr/lib/libvulkan_asahi.so* /var/tmp/MesaL2/pkg-wb/usr/lib/libvulkan_asahi.so*
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=$L/spirv
export MLX_OMARCHY_EXPECTED_LIBMLX_SHA256=df3d4e74c597956c
PY=/var/tmp/v071perf-venv/bin/python
B=$L/scripts/bench_decode.py
MODEL=/var/tmp/jw16gap-model
# --- per-arm warmup + digest gates (both legs, one run each; cache warming) ---
for arm in base wb; do
  export VK_DRIVER_FILES=/var/tmp/MesaL2/pkg-$arm/icd.json
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
unset VK_DRIVER_FILES
# --- 12-round paired 2-arm battery (digests fatal inside cb_ab.py) ---
timeout 7200 $PY $L/cb_ab.py \
  --bench "$B" --model "$MODEL" \
  --short-text "Hi" \
  --ctx-text "$(cat /var/tmp/TermAJW16/prompt-ctx1024.txt)" \
  --arm "base=VK_DRIVER_FILES=/var/tmp/MesaL2/pkg-base/icd.json" \
  --arm "wb=VK_DRIVER_FILES=/var/tmp/MesaL2/pkg-wb/icd.json" \
  --rounds 12 --out $L/ab-wb.json
echo "== battery rc=$? $(date -Is)"
date -u +%FT%TZ > $L/finished-wb.txt
