#!/bin/bash
# QwenAneExport512 jwm1 window: max_len 513 staged Qwen ANE export, io_layout-patched.
# Builds libane + bindings from the staged kit, patches a COPY of the pristine staged
# ANECs with the io_layout plan (sha-guarded), runs the staged runner.
# usage: window.sh verify|bench|prefill
#   verify   10 prompts x 32 greedy tokens vs chunk_00 (expect STAGED-QWEN-LINUX PASS)
#   bench    contract decode timing: 3 warmups, 10 reps (compare_denominator.py vs fedd4da)
#   prefill  pure 512-token prefill leg, same timing boundary as the macOS 11.74 tok/s
#            denominator (fedd4da section 7): 3 timed walls of the whole staged-decode
#            generate (512 prompt ids + 1 generated token), rate = 512/median(wall)
set -euo pipefail
MODE=${1:?verify|bench|prefill}
KIT=/var/tmp/qwen38-513-kit
ANEC=/var/tmp/qwen38-513-anec
OUT=/var/tmp/qwen38-513-out
PY=/var/tmp/jwm1-parity3-venv/bin/python
mkdir -p "$OUT"
if [ ! -f "$KIT/.built" ]; then
  mkdir -p "$KIT"
  tar -xzf /var/tmp/qwen38-513-kit.tgz -C "$KIT"
  (cd "$KIT" && sha256sum -c SHA256SUMS.anec >/dev/null && echo "anec sha256 check OK")
  make -C "$KIT/libane" libane >/dev/null
  make -C "$KIT/bindings/python/dylib" libane_python >/dev/null
  touch "$KIT/.built"
fi
if [ ! -d "$ANEC" ]; then
  cp -a "$KIT/export" "$ANEC"
  python3 "$KIT/tools/staged-qwen/io_layout.py" apply --plan "$KIT/io-layout-513.json" \
    --export "$ANEC" --anec "$ANEC/programs/prog_%03d.anec" | tail -3
fi
cd "$OUT"
EXTRA=()
[ "$MODE" = bench ] && EXTRA=(--warmups 3 --reps 10)
if [ "$MODE" = prefill ]; then
  EXTRA=(--prefill-ids "$KIT/prefill-ids.json" --prefill-tokens 512)
fi
timeout -s TERM 5400 env PYTHONPATH=/var/tmp/gguf-py "$PY" \
  "$KIT/tools/staged-qwen/staged_qwen_runner.py" --gguf /var/tmp/Qwen3.8-2B-Q4_K_M.gguf \
  --export "$ANEC" --libane-so "$KIT/bindings/python/dylib/libane_python.so" \
  --ref /var/tmp/chunk_00.json --mode "$MODE" "${EXTRA[@]}" 2>&1 | tee "$OUT/$MODE.log"
exit "${PIPESTATUS[0]}"
