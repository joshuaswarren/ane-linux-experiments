#!/bin/bash
# Read-only T8103 ANE tunable readback on jwm1 (no writes anywhere).
# Uses the unchanged one-word reader ane_clk_probe.ko (omarchy-ane clock
# worktree 85c6012): it reads the ANE_SYS SET word first and refuses the
# target read unless ACTUAL == 0xf, then does one readl and logs it.
# Usage: tunable-readback.sh <label>   (run once per state: boot, reload)
set -euo pipefail

label=${1:?label}
ko=${KO:-$HOME/ane-clk-probe/ane_clk_probe.ko}
ps_phys=0x23b70c000
out=$HOME/ane-tunable-readback-$label.txt

# m1n1 t8103_ane_tunables entries: PA mask expected (applied iff val&mask == expected)
targets=(
	"0x26a000738 0x1ff01ff 0x200020"
	"0x26a000900 0x101 0x101"
	"0x26b8f003c 0x262 0x262"
	"0x26b8f4028 0x6b7 0x6b7"
	"0x26b908008 0xf8aff 0xf8a96"
)

lsmod | grep -q '^ane ' || { echo "ane not loaded: ANE may be unpowered, refusing" >&2; exit 1; }
if lsmod | grep -q '^ane_clk_probe '; then
	echo "ane_clk_probe already loaded, refusing" >&2
	exit 1
fi

: > "$out"
for t in "${targets[@]}"; do
	read -r pa mask want <<< "$t"
	sudo -n dmesg -C
	sudo -n insmod "$ko" phys="$pa" ps_phys="$ps_phys"
	sudo -n rmmod ane_clk_probe
	line=$(sudo -n dmesg | grep -F "ane_clk_probe: $pa = " || true)
	[ -n "$line" ] || { echo "no readback for $pa" >&2; sudo -n dmesg | grep ane_clk_probe >&2; exit 1; }
	val=${line##* = }
	if (( (val & mask) == want )); then verdict=applied; else verdict=NOT-applied; fi
	printf '%s %s val=%s mask=%s want=%s %s\n' "$label" "$pa" "$val" "$mask" "$want" "$verdict" | tee -a "$out"
done
echo "wrote $out"
