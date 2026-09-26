#!/bin/bash
# ANE clock/counter snapshots on T6001 (ane_ctr_probe.ko, SET-gated, read-only):
# two snapshots 1 s apart while idle, then two 1 s apart while a 16-iteration
# whole-encoder run keeps the engine busy. Rates = delta / delta-t.
# Usage: jw16-ctr.sh <label>
set -uo pipefail
label=${1:?label}
KO=$HOME/ane-clk-probe/ane_ctr_probe.ko
W=/var/tmp/encoder-whole/build/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
IN=/tmp/aneclock-ab
snap() {
	sudo -n dmesg -C
	sudo -n insmod "$KO" base=0x284000000 ps_phys=0x28e08c000 tag="$1" || return 1
	sudo -n rmmod ane_ctr_probe
	sudo -n dmesg | grep -E "ane_ctr_probe: $1 (CLK|CTR)" >> "$IN/ctr-$label.txt"
}
: > "$IN/ctr-$label.txt"
snap idle0 && sleep 1 && snap idle1 || exit 1
"$W" --bundle /var/tmp/encoder-whole/bundle --libane /var/tmp/encoder-whole/libane-strict.so \
	--deadline-ms 60000 --iterations 16 \
	--input input_features="$IN/in_features.f16" --input attention_mask="$IN/in_mask.f16" \
	--save encoder_hidden="$IN/hidden-ctr.f16" >> "$IN/worker-ctr-$label.log" 2>&1 &
wpid=$!
sleep 3
snap busy0 && sleep 1 && snap busy1
wait "$wpid"
echo "worker rc=$?"
/var/tmp/v072-venv-fused/bin/python3 - "$IN/ctr-$label.txt" <<'PY'
import re, sys
rows = {}
for tag, name, t, v in re.findall(r"ane_ctr_probe: (\w+) (\w+) t=(\d+) val=(0x[0-9a-f]+|0)", open(sys.argv[1]).read()):
    rows[(tag, name)] = (int(t), int(v, 16))
for a, b in (("idle0", "idle1"), ("busy0", "busy1")):
    for name in ("CLK0", "CTR0", "CLK1", "CTR1", "CLK2", "CTR2", "CLK3", "CTR3"):
        if (a, name) not in rows or (b, name) not in rows:
            continue
        (t0, v0), (t1, v1) = rows[(a, name)], rows[(b, name)]
        dv = (v1 - v0) & 0xffffffff
        print(f"{a}->{b} {name} {v0:#010x}->{v1:#010x} d={dv:>11d} dt_ms={(t1-t0)/1e6:9.3f} MHz={dv / (t1 - t0) * 1e3:10.3f}")
PY
