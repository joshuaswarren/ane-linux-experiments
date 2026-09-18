#!/bin/bash
# F1 drift forensics window on jw16: one flock window.
# Phase A: capture real conv-module boundary tensors (GPU, --no-ane).
# Phase B: 28 decode-only probe runs (GPU, --no-ane, hidden from file).
# Phase C: in-situ island checks + adversarial matched-K cases (ANE).
# Everything stdout-to-file; e2e transcript/prefix per probe parsed at the end.
set -uo pipefail
RUN=/var/tmp/ParakeetE2EJw16
D=/var/tmp/f1-drift
B=/var/tmp/jw16-conv-place/bundles-conv
PY=/home/joshuawarren/venv-agxgen/bin/python
export PYTHONPATH=$RUN/site:/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE || true
mkdir -p $D/probe-logs $D/cap

COMMON="--audio /var/tmp/ParakeetE2E/audio/fixture.flac
  --golden /var/tmp/EncoderParityAne/capture
  --model $HOME/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
  --pkg /var/tmp/TdtLoopDefault/pkg
  --source /var/tmp/EncoderParityAne/encoder-source
  --no-ane"

# --- Phase A: capture (one run) -------------------------------------------
echo "--- capture $(date -Iseconds) ---"
F1_CAP_DIR=$D/cap $PY $RUN/fused_e2e.py $COMMON \
  --encoder-runner /tmp/conv-lane/f1_capture.py \
  --scratch $D/scratch-cap --out $D/out-cap \
  > $D/logs-capture.log 2>&1 || { echo "CAPTURE FAILED"; tail -20 $D/logs-capture.log; }
echo "capture tensors: $(ls $D/cap | wc -l) files (expect 144)"

# --- Phase B: decode-only probes ------------------------------------------
run_probe () { # name
  local name=$1
  rm -rf $D/out-$name $D/scratch-$name
  mkdir -p $D/out-$name $D/scratch-$name
  F1_HIDDEN=$D/probes/$name.npy $PY $RUN/fused_e2e.py $COMMON \
    --encoder-runner /tmp/conv-lane/f1_hprobe.py \
    --scratch $D/scratch-$name --out $D/out-$name \
    > $D/probe-logs/$name.log 2>&1
  local rc=$?
  python3 - "$name" "$rc" "$D/out-$name" <<'PY'
import hashlib, json, sys
name, rc, out = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    r = json.load(open(out + "/e2e-report.json"))
    seq = r["layers"]["layer_6_decoder_sequence"]
    trs = hashlib.sha256(open(out + "/transcript.txt", "rb").read()).hexdigest()[:16]
    row = {"probe": name, "rc": rc, "prefix": seq["matching_prefix_length"],
           "tokens_match": seq["tokens_match"], "transcript": trs,
           "first_div": (seq.get("first_divergence") or {}).get("actual", {}).get("token_id")}
except Exception as e:
    row = {"probe": name, "rc": rc, "error": str(e)[:200]}
print(json.dumps(row, separators=(",", ":")), flush=True)
PY
}
export -f run_probe
export RUN D PY PYTHONPATH MLX_OMARCHY_SPIRV_CACHE COMMON
echo "--- probes $(date -Iseconds) ---"
for p in probe-abc probe-j probe-jkh probe-jkhi \
         sfj-1 sfj-2 sfj-3 sfj-4 sfj-5 sfj-6 sfj-7 sfj-8 \
         sfjkhi-1 sfjkhi-2 sfjkhi-3 sfjkhi-4 sfjkhi-5 sfjkhi-6 sfjkhi-7 sfjkhi-8 \
         sfj-t05-1 sfj-t05-2 sfj-t05-3 sfj-t05-4 \
         sfj-t2-1 sfj-t2-2 sfj-t2-3 sfj-t2-4; do
  run_probe "$p"
done | tee $D/probes.jsonl

# --- Phase C: in-situ ANE checks -------------------------------------------
echo "--- in-situ $(date -Iseconds) ---"
$PY /tmp/conv-lane/f1_inprobe.py > $D/logs-insitu.log 2>&1 || { echo "INPROBE FAILED"; tail -20 $D/logs-insitu.log; }
tail -6 $D/logs-insitu.log
echo "--- F1 WINDOW DONE $(date -Iseconds) ---"
