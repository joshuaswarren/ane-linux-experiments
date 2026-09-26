#!/bin/bash
# jw16 whole-encoder engine timing (Jw16Levers7's method): the ANE worker at
# --iterations 1 and 8, per-iter = (e8 - e1) / 7, bit-exact vs the reference.
# Usage: jw16-enc-ab.sh <label> [repeats]
set -euo pipefail
label=${1:?label}
reps=${2:-3}
PY=/var/tmp/v072-venv-fused/bin/python3
W=/var/tmp/encoder-whole/build/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
B=/var/tmp/encoder-whole/bundle
L=/var/tmp/encoder-whole/libane-strict.so
IN=/tmp/aneclock-ab
mkdir -p "$IN"
if [ ! -s "$IN/in_features.f16" ]; then
	"$PY" - "$IN" <<'PY'
import sys, numpy as np
d = sys.argv[1]
np.load("/var/tmp/parakeet-recover/capture/encoder_input_features.npy").astype(np.float16).tofile(f"{d}/in_features.f16")
np.load("/var/tmp/parakeet-recover/capture/encoder_input_mask.npy").astype(np.float16).tofile(f"{d}/in_mask.f16")
PY
fi
run() {
	local n=$1
	local out=$IN/hidden-$label-$n.f16
	local t0 t1
	t0=$(date +%s%N)
	"$W" --bundle "$B" --libane "$L" --deadline-ms 60000 --iterations "$n" \
		--input input_features="$IN/in_features.f16" --input attention_mask="$IN/in_mask.f16" \
		--save encoder_hidden="$out" > "$IN/worker-$label-$n.log" 2>&1
	t1=$(date +%s%N)
	echo $(( (t1 - t0) / 1000 ))
}
for r in $(seq 1 "$reps"); do
	e1=$(run 1)
	e8=$(run 8)
	gold=$("$PY" - "$IN/hidden-$label-8.f16" <<'PY'
import sys, hashlib, numpy as np
out = np.fromfile(sys.argv[1], dtype=np.uint16)
sha = hashlib.sha256(out.tobytes()).hexdigest()[:16]
print(f"sha16={sha} {'PIN-MATCH' if sha == 'fca96f1355485ec3' else 'PIN-MISMATCH'} words={out.size}")
PY
)
	awk -v l="$label" -v r="$r" -v a="$e1" -v b="$e8" -v g="$gold" \
		'BEGIN { printf "%s rep%d e1_ms=%.1f e8_ms=%.1f per_iter_ms=%.2f gold %s\n", l, r, a/1000, b/1000, (b-a)/7000, g }'
done
