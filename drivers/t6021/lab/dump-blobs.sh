#!/bin/bash
# Copy the sequencer's read-only debugfs blobs to <out dir> with a tag suffix.
# Usage: dump-blobs.sh <out dir> <tag> [blob ...]   (default: heap pool fwbuf)
set -euo pipefail
out=${1:?out dir}; tag=${2:?tag}; shift 2
blobs=("$@"); [[ ${#blobs[@]} -gt 0 ]] || blobs=(heap pool fwbuf)
mkdir -p "$out"
for b in "${blobs[@]}"; do
    sudo -n cat "/sys/kernel/debug/ane_t6021_seq/$b" > "$out/$b.$tag.bin"
done
cd "$out" && sha256sum ./*."$tag".bin
