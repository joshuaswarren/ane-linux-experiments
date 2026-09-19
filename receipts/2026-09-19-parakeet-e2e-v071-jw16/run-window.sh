#!/bin/bash
# ParakeetPerf: Parakeet E2E wall time on jw16, v0.7.1 runtime (50eeb29 wheel).
# .ane  arm: MLX_OMARCHY_PLACED=AC (runner default), ANE_ISLAND_MODE=resident-batch
# .all  arm: MLX_OMARCHY_PLACED="" (pure-GPU control; Linux analog of CoreML .all)
# Protocol per macOS divisor receipt 2026-09-16-parakeet-macos-timing-m1ultra:
# warm-up run, then 10 measured runs per arm; median of all 10 and of runs 2-10.
# Caller has stopped llm-inference.service and holds /tmp/m1-gpu.lock.
set -uo pipefail
W=/var/tmp/parakeet-timing-v071
RUN=/var/tmp/ParakeetE2EJw16
PY=/var/tmp/V071REL-venv/bin/python
RUNNER=/var/tmp/encwall-v071/base/vulkan_encoder.py
MODEL=~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018
mkdir -p "$W"
unset PYTHONPATH
export MLX_OMARCHY_SPIRV_CACHE=/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ
unset HK_PERF HK_PERFTEST MLX_OMARCHY_GATED_BARRIERS MLX_OMARCHY_GPU_PROFILE ANE_OP_WALL || true

# guards BEFORE any run (fail fast)
$PY /var/tmp/v063-jw16/scripts/venv-identity-guard.py --expect df3d4e74c597956c /var/tmp/V071REL-venv || exit 4
echo "runner sha: $(sha256sum "$RUNNER" | cut -d' ' -f1)"
echo "venv dist:  $($PY -c 'import importlib.metadata as M; print(M.version("mlx-omarchy"))')"

run_one () { # name placed
  local name=$1 placed=$2
  local out=$W/out-$name scratch=$W/scratch-$name
  rm -rf "$out" "$scratch"; mkdir -p "$out" "$scratch"
  MLX_OMARCHY_PLACED="$placed" ANE_ISLAND_MODE=resident-batch \
  $PY $RUN/fused_e2e.py \
    --audio /var/tmp/ParakeetE2E/audio/fixture.flac \
    --golden /var/tmp/EncoderParityAne/capture \
    --model "$MODEL" \
    --pkg /var/tmp/TdtLoopDefault/pkg \
    --encoder-runner "$RUNNER" \
    --source /var/tmp/EncoderParityAne/encoder-source \
    --ane-reference /var/tmp/EncoderParityAne/capture/encoder_hidden.npy \
    --bundles /var/tmp/jw16-conv-place/bundles-conv \
    --worker /var/tmp/jw16-oproj-place/mlx-omarchy-ane-worker \
    --libane /var/tmp/jw16-oproj-place/libane-strict-fill.so \
    --scratch "$scratch" --out "$out" \
    --deadline-ms 20000 > "$W/log-$name.txt" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then echo "RUN-FAILED $name rc=$rc"; tail -8 "$W/log-$name.txt"; exit 3; fi
  echo "run $name done $(date -Iseconds)"
}

run_one ane-warm AC
for i in $(seq 1 10); do run_one "ane-$i" AC; done
run_one all-warm ""
for i in $(seq 1 10); do run_one "all-$i" ""; done

python3 - "$W" <<'PYEOF'
import hashlib, json, statistics, sys
W = sys.argv[1]
TRANSCRIPT = "db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
HIDDEN_AC  = "38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
MEL        = "5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
STAGES = ["audio_load", "mel_frontend", "encoder_ane", "decoder_load", "tdt_decode", "detokenize"]

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

def collect(arm, n):
    rows = []
    for i in range(1, n + 1):
        out = f"{W}/out-{arm}-{i}"
        r = json.load(open(f"{out}/e2e-report.json"))
        st = {s["stage"]: s.get("wall_ms") for s in r["stages"] if isinstance(s, dict) and "stage" in s}
        ane = r.get("ane") or {}
        row = {
            "run": i,
            "status": r["status"],
            "prefix": r["layers"]["layer_6_decoder_sequence"].get("matching_prefix_length"),
            "bounds": r["layers"]["layer_5_encoder"]["all_bounds_pass"],
            "cpu_ev": r["execution"]["cpu_tensor_events"],
            "timeouts": ane.get("timeouts"),
            "submissions": ane.get("submissions"),
            "ane_exec_ms": round(ane.get("exec_ms", 0.0), 1),
            "transcript_sha": sha(f"{out}/transcript.txt"),
            "hidden_sha": sha(f"{out}/encoder_hidden.npy"),
            "mel_sha": sha(f"{out}/mel.npy"),
            "total_ms": r["timing"]["total_pipeline_ms"],
            "stages": {k: st.get(k) for k in STAGES},
        }
        rows.append(row)
    return rows

def gate_ane(rows):
    for row in rows:
        bad = []
        if row["status"] != "match": bad.append(f"status={row['status']}")
        if row["prefix"] != 104: bad.append(f"prefix={row['prefix']}")
        if row["transcript_sha"] != TRANSCRIPT: bad.append("transcript")
        if row["hidden_sha"] != HIDDEN_AC: bad.append("hidden")
        if row["mel_sha"] != MEL: bad.append("mel")
        if not row["bounds"]: bad.append("bounds")
        if row["cpu_ev"] != 0: bad.append(f"cpu_ev={row['cpu_ev']}")
        if row["timeouts"] != 0: bad.append(f"timeouts={row['timeouts']}")
        if bad:
            print(f"GATE-FAIL ane-{row['run']}: {', '.join(bad)}")
            sys.exit(2)
    print(f"ane gate: 10/10 pins-EXACT")

def summarize(rows):
    def med(key, subset):
        vals = [r[key] for r in rows][subset]
        return round(statistics.median(vals), 1)
    tot = [r["total_ms"] for r in rows]
    s2_10 = tot[1:]
    return {
        "median_all10_ms": round(statistics.median(tot), 1),
        "median_runs2_10_ms": round(statistics.median(s2_10), 1),
        "min_ms": round(min(tot), 1),
        "max_ms": round(max(tot), 1),
        "per_run_total_ms": [round(t, 1) for t in tot],
        "stage_medians_ms": {k: med_stage(k, rows) for k in STAGES},
        "like_for_like_ms": round(statistics.median(tot[1:]) - statistics.median([r["stages"]["audio_load"] for r in rows][1:]), 1),
    }

def med_stage(k, rows):
    vals = [r["stages"][k] for r in rows]
    return round(statistics.median(vals), 1)

summary = {"arm_ane": {}, "arm_all": {}}
ane_rows = collect("ane", 10)
gate_ane(ane_rows)
summary["arm_ane"]["rows"] = ane_rows
summary["arm_ane"]["summary"] = summarize(ane_rows)

all_rows = collect("all", 10)
tok_statuses = {r["status"] for r in all_rows}
tok_prefixes = {r["prefix"] for r in all_rows}
print(f"all arm (control): statuses={sorted(tok_statuses)} prefixes={sorted(tok_prefixes)}")
summary["arm_all"]["rows"] = all_rows
summary["arm_all"]["summary"] = summarize(all_rows)

json.dump(summary, open(f"{W}/summary.json", "w"), indent=2)
print(json.dumps({"ane": summary["arm_ane"]["summary"], "all": summary["arm_all"]["summary"]}, indent=2))
print("PARAKEET-TIMING DONE $(date -Iseconds)" if False else "PARAKEET-TIMING DONE")
PYEOF
