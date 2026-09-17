#!/bin/bash
# jw16 fused-FFN chain E2E matrix: {ABC, ABCG} x {launch, resident-batch}.
# Runner: vk_chain.py (origin/main 23fc9a9a runner bytes + additive G hunks,
# sha 06e5f338; 63c1d3cf NOT an ancestor). Bundles: bundles-chain
# (= bundles-ffn select-fixed A/B/C set + 48 fused chain bundles
# island-ffn-L{LL}-f{m}). Lock /tmp/m1-gpu.lock: flock -w 900, never steal.
set -euo pipefail
RUN=/var/tmp/ParakeetE2EJw16
B=/var/tmp/jw16-ep-bisect
PY=/home/joshuawarren/venv-agxgen/bin/python
export PYTHONPATH=/var/tmp/E2EREV/site:/var/tmp/MelFrontendPerf/venv-cache/lib/python3.14/site-packages
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE || true
run_arm () { # name placed mode
  local name=$1 placed=$2 mode=$3
  local outdir=$B/out-chain-$name scratch=$B/scratch-chain-$name
  echo "--- arm $name PLACED=$placed MODE=$mode $(date -Iseconds) ---"
  rm -rf $outdir $scratch; mkdir -p $outdir $scratch
  MLX_OMARCHY_PLACED=$placed ANE_ISLAND_MODE=$mode $PY $RUN/fused_e2e.py \
    --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
    --golden /var/tmp/EncoderParityAne/capture \
    --model ~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018 \
    --pkg /var/tmp/TdtLoopDefault/pkg \
    --encoder-runner $RUN/vk_chain.py \
    --source /var/tmp/EncoderParityAne/encoder-source \
    --bundles $B/bundles-chain \
    --worker /var/tmp/jw16-oproj-place/mlx-omarchy-ane-worker \
    --libane /var/tmp/jw16-oproj-place/libane-strict-fill.so \
    --scratch $scratch \
    --out $outdir \
    --deadline-ms 20000 > $B/chain-$name.log 2>&1 || { echo "ARM $name FAILED"; tail -5 $B/chain-$name.log; return 1; }
  $PY - "$outdir" "$name" <<'PY'
import hashlib, json, sys
out, name = sys.argv[1], sys.argv[2]
r = json.load(open(out + "/e2e-report.json"))
hid = hashlib.sha256(open(out + "/encoder_hidden.npy", "rb").read()).hexdigest()
trs = hashlib.sha256(open(out + "/transcript.txt", "rb").read()).hexdigest()
seq = r["layers"]["layer_6_decoder_sequence"]
enc = next((s for s in r["stages"] if isinstance(s, dict) and s.get("name") == "encoder_ane"), {})
print(json.dumps({
    "arm": name, "status": r["status"],
    "subs": r["ane"]["submissions"], "mode": r["ane"].get("mode"),
    "prefix": seq.get("matching_prefix_length"),
    "bounds": r["layers"]["layer_5_encoder"]["all_bounds_pass"],
    "cpu_tensor_events": r["execution"]["cpu_tensor_events"],
    "gpu_ops": r["execution"]["encoder_gpu_ops"],
    "ane_ops": r["execution"]["encoder_ane_ops"],
    "encoder_wall_ms": enc.get("wall_ms"),
    "ane_exec_ms": r["ane"].get("exec_ms"),
    "timeouts": r["ane"].get("timeouts"),
    "hidden": hid, "transcript": trs,
}))
PY
}
run_arm abc-launch ABC launch
run_arm abc-resident ABC resident-batch
run_arm abcg-launch ABCG launch
run_arm abcg-resident ABCG resident-batch
