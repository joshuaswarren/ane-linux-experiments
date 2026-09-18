#!/bin/bash
# F1 drift forensics, phase B2: 16 extra signflip draws (seeds 9-16).
set -u
RUN=/var/tmp/ParakeetE2EJw16
D=/var/tmp/f1-drift
PY=/home/joshuawarren/venv-agxgen/bin/python
export PYTHONPATH=$RUN/site:/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE || true
mkdir -p $D/probe-logs
COMMON="--audio /var/tmp/ParakeetE2E/audio/fixture.flac
  --golden /var/tmp/EncoderParityAne/capture
  --model $HOME/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
  --pkg /var/tmp/TdtLoopDefault/pkg
  --source /var/tmp/EncoderParityAne/encoder-source
  --no-ane"
run_probe () {
  local name=$1
  rm -rf $D/out-$name $D/scratch-$name
  mkdir -p $D/out-$name $D/scratch-$name
  F1_HIDDEN=$D/probes/$name.npy $PY $RUN/fused_e2e.py $COMMON \
    --encoder-runner /tmp/conv-lane/f1_hprobe.py \
    --scratch $D/scratch-$name --out $D/out-$name \
    > $D/probe-logs/$name.log 2>&1
  local rc=$?
  $PY - "$name" "$rc" "$D/out-$name" <<'PY'
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
echo "--- probes B2 $(date -Iseconds) ---"
for p in sfj-9 sfj-10 sfj-11 sfj-12 sfj-13 sfj-14 sfj-15 sfj-16 \
         sfjkhi-9 sfjkhi-10 sfjkhi-11 sfjkhi-12 sfjkhi-13 sfjkhi-14 sfjkhi-15 sfjkhi-16; do
  run_probe "$p"
done | tee -a $D/probes.jsonl
echo "--- probes B2 done $(date -Iseconds) ---"
