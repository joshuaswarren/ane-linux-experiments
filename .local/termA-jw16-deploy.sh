#!/usr/bin/env bash
# jw16 deployment + verification: pause llm-inference, install the
# hkd71c94e-2 package, 12-round interleaved packaged A/B, suite, restart.
set -uo pipefail
W=/var/tmp/TermAJW16
PKG=/var/tmp/TermAJW16/mesa-honeykrisp-omarchy-26.3.0.devel.hkd71c94e-2-aarch64.pkg.tar.xz
echo "== pause llm-inference =="
sudo -n systemctl stop llm-inference.service || exit 1
for i in $(seq 1 30); do
  s=$(systemctl is-active llm-inference.service)
  [ "$s" = "inactive" ] && break
  sleep 1
done
echo "service=$s"
echo "== install new package =="
sudo -n pacman -U --noconfirm "$PKG" 2>&1 | tail -2
pacman -Q mesa-honeykrisp-omarchy
echo "== extract old -1 package for the A/B baseline =="
mkdir -p $W/oldmesa
[ -f $W/oldmesa/usr/lib/libvulkan_asahi.so ] || (cd $W/oldmesa && tar -xf $W/mesa-honeykrisp-omarchy-26.3.0.devel.hk6f6afc8-1-aarch64.pkg.tar.xz)
cat > $W/oldmesa/old-icd.json <<'EOF'
{
    "ICD": {
        "api_version": "1.4.359",
        "library_arch": "64",
        "library_path": "/var/tmp/TermAJW16/oldmesa/usr/lib/libvulkan_asahi.so"
    },
    "file_format_version": "1.0.1"
}
EOF
echo "== 12-round interleaved packaged A/B =="
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=$W/spirv
MODEL=/home/joshuawarren/.cache/huggingface/hub/models--mlx-community--Qwen2.5-0.5B-Instruct-4bit/snapshots
MODEL=$(ls -d $MODEL/*/ | head -1)
WHEEL=/var/tmp/TermAJW16/mlx_omarchy-0.32.2.dev202609161852+2e252962-cp314-cp314-linux_aarch64.whl
PY=/var/tmp/TermAJW16/venv/bin/python
flock -w 900 /tmp/m1-gpu.lock timeout 1800 $PY /var/tmp/termA-driver-ab.py \
  --bench /var/tmp/decode-trio/scripts/bench_decode.py \
  --model "$MODEL" \
  --short-text "$(cat $W/prompt-short.txt)" \
  --ctx-text "$(cat $W/prompt-ctx1024.txt)" \
  --wheel "$WHEEL" \
  --arm "old=VK_DRIVER_FILES=$W/oldmesa/old-icd.json" \
  --arm "new=VK_DRIVER_FILES=UNSET" \
  --rounds 12 --out $W/packaged-jw16-ab.json
echo "== suite on the packaged new driver =="
flock -w 900 /tmp/m1-gpu.lock timeout 900 /home/joshuawarren/src/mlx-omarchy/.work/build/tests/omarchy/omarchy_runtime_tests \
  > "$W/suite-packaged.log" 2>&1
echo "suite rc=$?"
grep -E "test cases|assertions|Status" "$W/suite-packaged.log" | tail -3
echo "== restart llm-inference =="
sudo -n systemctl start llm-inference.service
sleep 3
systemctl is-active llm-inference.service
