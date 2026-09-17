#!/bin/bash
# run-roundtrip-e2e.sh — one fused_e2e pass against the CURRENT module/map_mode.
# Usage: run-roundtrip-e2e.sh <tag> [launch|resident-batch]
# Mirrors the isolation production pass: E2E296-era runner (fold-regression
# numeric signature — TIMING-ONLY certification), island-reexport bundles,
# strict libane, resident-batch by default. Records every artifact identity.
set -uo pipefail
TAG=${1:?tag required}
MODE=${2:-resident-batch}
RUN=/var/tmp/ParakeetE2EJw16
PY=/home/joshuawarren/venv-agxgen/bin/python
E2E=/var/tmp/E2E296
export PYTHONPATH=/var/tmp/TdtLoopDefault/pkg:$E2E/site:/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ
export ANE_ISLAND_MODE=$MODE
export MLX_OMARCHY_PLACED=ABC
OUTDIR=/var/tmp/ane-submit-probe/roundtrip-e2e/$TAG
mkdir -p "$OUTDIR"

{
  echo "tag=$TAG mode=$MODE date=$(date -Is)"
  echo "module: $(grep '^ane ' /proc/modules)"
  echo "map_mode: $(cat /sys/module/ane/parameters/map_mode 2>/dev/null || echo 'n/a (original module)')"
  echo "runner:   $(sha256sum $E2E/overlay/tools/coreml/vulkan_encoder.py)"
  echo "worker:   $(sha256sum /var/tmp/E2E296-battery/worker/mlx-omarchy-ane-worker)"
  echo "libane:   $(sha256sum /var/tmp/island-reexport/libane-strict.so)"
  echo "bundles:  $(ls /var/tmp/island-reexport/bundles)"
  echo "mlxcore:  $(ls $E2E/site/mlx/core*.so)"
} > "$OUTDIR/identity.txt"
cat "$OUTDIR/identity.txt"

# Lock discipline: the CALLER wraps this script in `flock /tmp/m1-gpu.lock`
# (single acquisition point; an inner flock deadlocks on the inherited fd).
$PY $RUN/fused_e2e.py \
  --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
  --golden /var/tmp/EncoderParityAne/capture \
  --model /home/joshuawarren/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018 \
  --pkg /var/tmp/TdtLoopDefault/pkg \
  --encoder-runner $E2E/overlay/tools/coreml/vulkan_encoder.py \
  --source /var/tmp/EncoderParityAne/encoder-source \
  --bundles /var/tmp/island-reexport/bundles \
  --worker /var/tmp/E2E296-battery/worker/mlx-omarchy-ane-worker \
  --libane /var/tmp/island-reexport/libane-strict.so \
  --scratch $OUTDIR/scratch \
  --out $OUTDIR \
  --deadline-ms 20000
RC=$?

python3 - "$OUTDIR" "$TAG" "$MODE" "$RC" <<'PY'
import json, sys
d, tag, mode, rc = sys.argv[1:5]
try:
    r = json.load(open(d + "/e2e-report.json"))
except Exception as e:
    print(tag, mode, "rc", rc, "NO REPORT:", e); sys.exit(0)
st = {s.get("stage"): s.get("wall_ms") for s in r.get("stages", [])}
an = r.get("ane", {})
rounds = an.get("log", [])
sums = {}
for rec in rounds:
    k = rec.get("bundle", "?")
    sums[k] = sums.get(k, 0) + rec.get("elapsed_ns", 0) / 1e6
print(tag, mode,
      "status:", r.get("status"),
      "cpu_tensor_events:", r.get("execution", {}).get("cpu_tensor_events"),
      "subs:", an.get("submissions"),
      "ane_exec_ms:", an.get("exec_ms"),
      "encoder_wall_ms:", st.get("encoder_ane"),
      "total_ms:", r.get("timing", {}).get("total_pipeline_ms"))
import hashlib
for f in ("encoder_hidden.npy", "transcript.txt", "token_ids.json"):
    try:
        h = hashlib.sha256(open(d + "/" + f, "rb").read()).hexdigest()
        print(f"  sha256 {f}: {h}")
    except OSError:
        print(f"  sha256 {f}: MISSING")
for k, v in sorted(sums.items()):
    n = sum(1 for x in rounds if x.get("bundle") == k)
    print(f"  island-sum {k}: {v:.1f} ms over {n} rounds")
PY
