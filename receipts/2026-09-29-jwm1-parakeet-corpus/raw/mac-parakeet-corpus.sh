#!/bin/bash
# macOS Parakeet per-clip stage timings (ane arm), same clips as the Linux corpus_gate run.
# usage: mac-parakeet-corpus.sh <audio_dir> <outdir>
set -u
A=$1; O=$2; mkdir -p "$O"
B=$HOME/mac-reference-bundle
P=$B/bin/parakeet
MODELS=$B/models
for f in fixture_v03.flac fixture_v1.flac fixture_v5.flac fixture_v10.flac fixture.flac 1089-134686-0000.wav; do
  c=${f%.*}
  for i in cold w1 w2 w3 r1 r2 r3 r4 r5 r6 r7 r8 r9 r10; do
    "$P" transcribe "$A/$f" --models "$MODELS" --show-timing --compute-units ane > "$O/$c.$i.out" 2> "$O/$c.$i.err"
    echo "$c $i rc=$?"
  done
done
echo CORPUS-DONE
