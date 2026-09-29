#!/bin/bash
# Build the honeykrisp ICD (asahi Vulkan) from a shipped source tree; write an ICD json for VK_DRIVER_FILES.
# System ICD is never touched. usage: build_mesa_icd.sh SRC_DIR OUT_DIR
set -euo pipefail
SRC="${1:?mesa source dir}"; OUT="${2:?out dir}"
mkdir -p "$OUT"
cd "$SRC"
[ -d build ] || meson setup build --buildtype=release -Dvulkan-drivers=asahi -Dgallium-drivers= \
  -Dglx=disabled -Degl=disabled -Dplatforms= -Dvideo-codecs= -Dgbm=disabled -Dllvm=enabled > "$OUT/meson.log" 2>&1
ninja -C build src/asahi/vulkan/libvulkan_asahi.so 2>&1 | tail -2
cp build/src/asahi/vulkan/libvulkan_asahi.so "$OUT/libvulkan_asahi.so"
printf '{"ICD":{"api_version":"1.4.359","library_arch":"64","library_path":"%s/libvulkan_asahi.so"},"file_format_version":"1.0.1"}\n' "$OUT" > "$OUT/icd.json"
sha256sum "$OUT/libvulkan_asahi.so"
echo "ICD: $OUT/icd.json"
