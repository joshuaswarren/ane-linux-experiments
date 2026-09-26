#!/bin/bash
# Read DVFS_CMD / DVFS_ON through the SET-gated one-word reader while a
# 16-iteration whole-encoder run holds the boost (dvfs_ane=1 loaded).
set -uo pipefail
W=/var/tmp/encoder-whole/build/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
IN=/tmp/aneclock-ab
"$W" --bundle /var/tmp/encoder-whole/bundle --libane /var/tmp/encoder-whole/libane-strict.so \
	--deadline-ms 60000 --iterations 16 \
	--input input_features="$IN/in_features.f16" --input attention_mask="$IN/in_mask.f16" \
	--save encoder_hidden="$IN/hidden-probe.f16" >> "$IN/worker-probe.log" 2>&1 &
wpid=$!
sleep 3
for pa in 0x400004A00 0x400006000; do
	sudo -n dmesg -C
	sudo -n insmod "$HOME/ane-clk-probe/ane_clk_probe.ko" phys="$pa" ps_phys=0x28e08c000
	sudo -n rmmod ane_clk_probe
	sudo -n dmesg | grep -E "ane_clk_probe: 0x4"
done
wait "$wpid"
echo "worker rc=$?"
tail -2 "$IN/worker-probe.log"
