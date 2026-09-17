#!/bin/bash
# v0.6.5 gate addition: pinned short-decode-32 leg on the downloaded bytes.
set -u
HOSTDIR="$1"; ROOT="$2"; VENV="$3"
cd "$ROOT"
flock -w 900 /tmp/m1-gpu.lock env HF_HUB_OFFLINE=1 MLX_DISABLE_COMPILE=1 \
  "$VENV/bin/python" "$ROOT/scripts/bench_matrix.py" \
  --mode run --select short-decode-32 \
  > "$HOSTDIR/decode-short.json" 2> "$HOSTDIR/decode-short.log"
echo "short-exit=$?"
python3 - "$HOSTDIR" <<'PY'
import json, sys
d = json.load(open(sys.argv[1] + "/decode-short.json"))
for leg in d["legs"]:
    if leg.get("measured"):
        m = leg["metrics"]
        print(leg["leg_id"], m["generated_ids_sha256_16"], m["decode_tok_s"])
PY
