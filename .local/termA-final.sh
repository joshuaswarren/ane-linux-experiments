#!/usr/bin/env bash
# Rebuild package from fixup commit, install, packaged A/B + suite.
set -uo pipefail
cd /home/joshuawarren/src/mesa-pkg-20260908
sed -i "s/^_commit=.*/_commit=f96e090b38212ca8c74def0f38331d2c2bba6d6a/" PKGBUILD
grep -E "^_commit|^pkgrel" PKGBUILD
bash m1-mesa-pkg-build.sh > /var/tmp/TermASplit/pkgbuild2.log 2>&1
rc=$?
echo "build rc=$rc"
tail -2 /home/joshuawarren/log/mesa-pkg-build.log
NEWPKG=$(ls -t mesa-honeykrisp-omarchy-*.pkg.tar.xz | head -1)
echo "package: $NEWPKG"
[ "$(basename "$NEWPKG")" = "mesa-honeykrisp-omarchy-26.3.0.devel.hkf96e090-2-aarch64.pkg.tar.xz" ] || { echo WRONG-PACKAGE; exit 1; }
sudo -n pacman -U --noconfirm "$NEWPKG" 2>&1 | tail -2
pacman -Q mesa-honeykrisp-omarchy
W=/var/tmp/TermASplit
export MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1
export MLX_OMARCHY_SPIRV_CACHE=$W/spirv
MODEL=/home/joshuawarren/models/Qwen2.5-0.5B-Instruct-4bit-mlx
WHEEL=/var/tmp/V060-rel/mlx_omarchy-0.32.2.dev202609161852+2e252962-cp314-cp314-linux_aarch64.whl
flock -w 60 /tmp/m1-gpu.lock timeout 900 /var/tmp/V060PIN-venv2/bin/python /var/tmp/termA-driver-ab.py \
  --bench /var/tmp/Jwm1AneAccelSmoke2-a9f14124/scripts/bench_decode.py \
  --model "$MODEL" \
  --short-text "$(cat $W/prompt-short.txt)" \
  --ctx-text "$(cat $W/prompt-ctx1024.txt)" \
  --wheel "$WHEEL" \
  --arm "old=VK_DRIVER_FILES=$W/oldmesa/old-icd.json" \
  --arm "new=VK_DRIVER_FILES=UNSET" \
  --rounds 6 --out $W/packaged-ab2.json
echo "== suite on the packaged fixup driver =="
flock -w 60 /tmp/m1-gpu.lock timeout 900 /home/joshuawarren/src/mlx-omarchy/.work/build/tests/omarchy/omarchy_runtime_tests \
  > "$W/suite-packaged.log" 2>&1
echo "suite rc=$?"
grep -E "test cases|assertions|Status" "$W/suite-packaged.log" | tail -3
