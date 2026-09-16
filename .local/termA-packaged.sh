#!/usr/bin/env bash
# Install the packaged mesa bump, verify, then packaged-driver A/B + suite.
set -uo pipefail
W=/var/tmp/TermASplit
PKG=/home/joshuawarren/src/mesa-pkg-20260908/mesa-honeykrisp-omarchy-26.3.0.devel.hk7397476-2-aarch64.pkg.tar.xz
sudo -n pacman -U --noconfirm "$PKG" 2>&1 | tail -3
echo "== driver version =="
exp=$'VK_DRIVER_FILES unset\nvulkaninfo'
glxinfo -B 2>/dev/null | grep -i -m1 "OpenGL version" || true
python3 - <<'EOF'
import subprocess
out = subprocess.run(["vulkaninfo", "--summary"], capture_output=True, text=True).stdout
for line in out.splitlines():
    if "driverName" in line or "driverVersion" in line or "apiVersion" in line:
        print(line.strip())
EOF
echo "== packaged confirm battery: old-behavior (worktree sink) vs new package, 6 rounds =="
export VK_DRIVER_FILES=/home/joshuawarren/src/mesa-wt-dispatchfloor/dispatchfloor-icd.json
MODEL=/home/joshuawarren/models/Qwen2.5-0.5B-Instruct-4bit-mlx
WHEEL=/var/tmp/V060-rel/mlx_omarchy-0.32.2.dev202609161852+2e252962-cp314-cp314-linux_aarch64.whl
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=$W/spirv
# newpkg arm clears the ICD override so it loads the installed package
/var/tmp/V060PIN-venv2/bin/python /var/tmp/termA-driver-ab.py \
  --bench /var/tmp/Jwm1AneAccelSmoke2-a9f14124/scripts/bench_decode.py \
  --model "$MODEL" \
  --short-text "$(cat $W/prompt-short.txt)" \
  --ctx-text "$(cat $W/prompt-ctx1024.txt)" \
  --wheel "$WHEEL" \
  --arm "oldpkg=VK_DRIVER_FILES=/home/joshuawarren/src/mesa-wt-dispatchfloor/dispatchfloor-icd.json" \
  --arm "newpkg=VK_DRIVER_FILES=UNSET" \
  --rounds 6 --out $W/packaged-ab.json
echo "== suite on the packaged driver =="
timeout 900 /home/joshuawarren/src/mlx-omarchy/.work/build/tests/omarchy/omarchy_runtime_tests \
  > "$W/suite-packaged.log" 2>&1
echo "suite rc=$?"
tail -4 "$W/suite-packaged.log"
