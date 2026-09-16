#!/usr/bin/env bash
# Packaged A/B: old package (extracted hk6f6afc8-1) vs new package
# (installed hk7397476-2), 6 interleaved rounds, both legs, pins fatal.
set -uo pipefail
W=/var/tmp/TermASplit
mkdir -p $W/oldmesa
if [ ! -f $W/oldmesa/usr/lib/libvulkan_asahi.so ]; then
  cd $W/oldmesa && tar -xf ~/src/mesa-pkg-20260908/mesa-honeykrisp-omarchy-26.3.0.devel.hk6f6afc8-1-aarch64.pkg.tar.xz
fi
ls $W/oldmesa/usr/lib/libvulkan_asahi.so || exit 1
cat > $W/oldmesa/old-icd.json <<'EOF'
{
    "ICD": {
        "api_version": "1.4.359",
        "library_arch": "64",
        "library_path": "/var/tmp/TermASplit/oldmesa/usr/lib/libvulkan_asahi.so"
    },
    "file_format_version": "1.0.1"
}
EOF
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=$W/spirv
MODEL=/home/joshuawarren/models/Qwen2.5-0.5B-Instruct-4bit-mlx
WHEEL=/var/tmp/V060-rel/mlx_omarchy-0.32.2.dev202609161852+2e252962-cp314-cp314-linux_aarch64.whl
/var/tmp/V060PIN-venv2/bin/python /var/tmp/termA-driver-ab.py \
  --bench /var/tmp/Jwm1AneAccelSmoke2-a9f14124/scripts/bench_decode.py \
  --model "$MODEL" \
  --short-text "$(cat $W/prompt-short.txt)" \
  --ctx-text "$(cat $W/prompt-ctx1024.txt)" \
  --wheel "$WHEEL" \
  --arm "old=VK_DRIVER_FILES=$W/oldmesa/old-icd.json" \
  --arm "new=VK_DRIVER_FILES=UNSET" \
  --rounds 6 --out $W/packaged-ab.json
echo "== suite on the packaged (new) driver =="
timeout 900 /home/joshuawarren/src/mlx-omarchy/.work/build/tests/omarchy/omarchy_runtime_tests \
  > "$W/suite-packaged.log" 2>&1
echo "suite rc=$?"
grep -E "test cases|assertions|Status" "$W/suite-packaged.log" | tail -3
