#!/bin/bash
# Whole-encoder direct-worker bench (m1max-host harness from
# receipts/2026-09-22-encoder-m1max-anomaly §5). Usage: bench.sh LABEL N...
# Prints one line per N: label, iters, worker elapsed_ms, hidden/mask sha256.
set -euo pipefail
B=/var/tmp/encoder-whole
W=$B/build/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
label=$1; shift
out=/var/tmp/ane-clk/runs/$label
mkdir -p "$out"
for n in "$@"; do
	d=$out/n$n
	rm -rf "$d"; mkdir -p "$d"
	"$W" --bundle $B/bundle --libane $B/libane-strict.so --deadline-ms 60000 \
		--iterations "$n" \
		--input attention_mask=$B/smoke/in_attention_mask.bin \
		--input input_features=$B/smoke/in_input_features.bin \
		--save encoder_hidden="$d/h.bin" --save output_mask="$d/m.bin" \
		> "$d/worker.log" 2>&1
	ms=$(grep -o 'elapsed_ms=[0-9.]*' "$d/worker.log" | tail -1 | cut -d= -f2)
	hs=$(sha256sum "$d/h.bin" | cut -c1-16)
	msk=$(sha256sum "$d/m.bin" | cut -c1-16)
	echo "$label n=$n elapsed_ms=${ms:-?} hidden=$hs mask=$msk"
done
