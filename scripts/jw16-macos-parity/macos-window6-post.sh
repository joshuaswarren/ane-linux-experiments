#!/bin/bash
# macOS window 6 post-window: pull artifacts from jw16 macOS to omp-studio-local notebook path,
# then verify the SHA256SUMS line-by-line against the on-mac hashes.
# usage (on omp-studio-local): bash macos-window6-post.sh [REMOTE_USER] [REMOTE_HOST]
# Defaults: REMOTE_USER=joshuawarren, REMOTE_HOST=16m1mbp-macos
set -u
RU="${1:-joshuawarren}"; RH="${2:-16m1mbp-macos}"
DEST="$HOME/.local/share/apple-silicon-lab/artifacts/Jw16MacWin6/macos-window-6"
mkdir -p "$DEST"
ssh -o ConnectTimeout=8 "$RU@$RH" 'ls -la ~/jw16-macos-window/w6/out/' </dev/null > "$DEST/_mac-listing.txt" 2>&1 || true
# Skip the powermetrics txt (would be cut off by tmux); pull everything else.
rsync -a --info=stats2 "$RU@$RH:jw16-macos-window/w6/out/" "$DEST/" 2>&1 | tee "$DEST/_rsync.log"
( cd "$DEST" && find . -type f -name 'SHA256SUMS' -exec shasum -a 256 -c -- {} \; 2>&1 ) | tee "$DEST/_sha-verify.txt"
echo "post-done: $DEST"
