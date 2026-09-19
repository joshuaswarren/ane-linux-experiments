#!/usr/bin/env bash
# Prep the 5deac1c8-rebuilt-today arm into /var/tmp/MesaL2/pkg-s5de.
set -euo pipefail
pkg=/var/tmp/wb-base5de/mesa-honeykrisp-omarchy-26.3.0.devel.hk5deac1c-1-aarch64.pkg.tar.xz
D=/var/tmp/MesaL2/pkg-s5de
[ -f "$pkg" ] || { echo "missing $pkg" >&2; exit 1; }
mkdir -p "$D"
tar -xf "$pkg" -C "$D"
so=$(find "$D" -name "libvulkan_asahi.so*" | head -1)
[ -n "$so" ] || { echo "no libvulkan_asahi in $pkg" >&2; exit 1; }
cat > "$D/icd.json" <<EOF
{
    "ICD": {
        "api_version": "1.4.359",
        "library_arch": "64",
        "library_path": "$so"
    },
    "file_format_version": "1.0.1"
}
EOF
echo "prepared: $so"
sha256sum "$so"
