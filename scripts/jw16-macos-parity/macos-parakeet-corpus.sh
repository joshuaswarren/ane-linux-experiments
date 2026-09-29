#!/bin/bash
# macOS reference: run the pinned Parakeet CLI (CoreML) over the corpus, arms ane and gpu, 3 reps per clip
# (first rep includes any compile/cache effects; reps 2-3 are warm). Stdout = transcript; stderr = timing block.
# usage (on jw16 macOS): bash macos-parakeet-corpus.sh CORPUS_DIR OUT_DIR
set -u
CORPUS="${1:?corpus dir}"; OUT="${2:?out dir}"
B="$HOME/jw16-macos-window/mac-reference-bundle"
mkdir -p "$OUT"
( cd "$CORPUS" && shasum -a 256 -c SHA256SUMS > "$OUT/corpus-sha-check.txt" 2>&1 )
{ date -u; sw_vers; pmset -g batt | head -1; pmset -g | grep -i powermode; pmset -g therm | tail -2; } > "$OUT/env.txt" 2>&1
for arm in ane gpu; do
  for f in "$CORPUS"/*.flac; do
    n=$(basename "$f" .flac)
    for rep in 1 2 3; do
      "$B/bin/parakeet" transcribe "$f" --models "$B/models" --show-timing --compute-units "$arm" \
        > "$OUT/$arm-$n-r$rep.txt" 2> "$OUT/$arm-$n-r$rep.err"
    done
  done
done
( cd "$OUT" && shasum -a 256 ./*.txt > SHA256SUMS )
echo MACOS-PARAKEET-CORPUS-DONE
