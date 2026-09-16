#!/usr/bin/env bash
# Recreate the vanished worktree ICD json, then quick-verify the fixup build.
set -uo pipefail
ICD=/home/joshuawarren/src/mesa-wt-dispatchfloor/dispatchfloor-icd.json
cat > "$ICD" <<'EOF'
{
    "ICD": {
        "api_version": "1.4.359",
        "library_arch": "64",
        "library_path": "/home/joshuawarren/src/mesa-wt-dispatchfloor/build3/src/asahi/vulkan/libvulkan_asahi.so"
    },
    "file_format_version": "1.0.1"
}
EOF
echo icd-recreated
flock -w 30 /tmp/m1-gpu.lock timeout 300 /var/tmp/termA-fixup-check.sh
