#!/bin/bash
# Install a built honeykrisp .so as the SYSTEM Vulkan ICD with a backup of the previous ICD json.
# usage: install_icd.sh BUILT_SO TAG     (rollback: cp the printed .bak over the ICD json)
set -euo pipefail
SO="${1:?built .so}"; TAG="${2:?tag}"
ICD=/usr/share/vulkan/icd.d/asahi_icd.aarch64.json
DEST="/usr/local/lib/libvulkan_asahi.so.$TAG"
BAK="/var/tmp/asahi_icd.aarch64.json.pre-$TAG.bak"
[ -e "$BAK" ] && { echo "backup exists: $BAK"; exit 1; }
cp "$ICD" "$BAK"
sudo install -m 0755 "$SO" "$DEST"
sudo sha256sum "$DEST"
printf '{\n  "ICD": {\n    "api_version": "1.4.359",\n    "library_arch": "64",\n    "library_path": "%s"\n  },\n  "file_format_version": "1.0.1"\n}\n' "$DEST" | sudo tee "$ICD" > /dev/null
echo "installed ICD -> $DEST"; cat "$ICD"
echo "rollback: sudo cp $BAK $ICD"
