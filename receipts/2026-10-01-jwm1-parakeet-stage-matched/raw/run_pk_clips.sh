#!/bin/bash
# Product-path Parakeet stage medians per corpus clip (n=11 in-process each, run 1 excluded). Runs on jwm1.
set -u
V=$HOME/.local/share/mlx-omarchy/venv
mkdir -p /var/tmp/pk-audio
sed -e 's/audio=None, out=out/audio=args.audio, out=out/' \
    -e 's/ap.add_argument("--label", default="")/ap.add_argument("--label", default="")\n    ap.add_argument("--audio", default=None)/' \
    /var/tmp/pk-sess-driver.py | tee /var/tmp/pk-sess-driver-audio.py > /dev/null
exec 9>/tmp/m1-gpu.lock
flock -w 1200 9 || exit 3
for clip in fixture_v03 fixture_v1 fixture_v5 fixture_v10; do
  rm -rf /var/tmp/pk118-$clip
  $V/bin/python /var/tmp/pk-sess-driver-audio.py --venv $V --out-root /var/tmp/pk118-$clip --runs 11 --label $clip --audio /var/tmp/pk-audio/$clip.flac > /var/tmp/pk118-$clip.log 2>&1
  echo "$clip rc=$?"
done
flock -u 9
echo PKC-DONE
