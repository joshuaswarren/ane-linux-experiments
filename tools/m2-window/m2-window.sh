#!/usr/bin/env bash
# One-shot M2 Max (T6021) GPU + Parakeet window kit.
#
# Fills two matrix cells on m2-host (Apple M2 Max, Mac14,5, Omarchy/Asahi
# Linux) in a single short window:
#   1. Qwen3.8-2B GPU contract   (benchmarks/qwen38-2b-contract.json protocol:
#      greedy, 32 new tokens, 3 warmups, 10 passes x 10 prompts, pure-prefill
#      512 leg) on the staged mlx-omarchy main wheel -> qwen-contract.json.
#   2. Parakeet full-audio contract (golden fixture, pinned transcript) via
#      mlx-omarchy-parakeet -> parakeet.json. Requires the Linux ANE; when the
#      ANE is absent the leg emits an honest "blocked-ane-unavailable" receipt
#      and the GPU cell still lands.
#
# usage: m2-window.sh [--stage DIR] [--out DIR] [--repo DIR] [--keep-venv]
#                     [--skip-parakeet] [--selfcheck]
#   --stage DIR   kit stage dir (wheel + mlx-lm patches); default: alongside
#                 this script /stage. Needs stage/mlx_omarchy-*.whl and
#                 stage/mlx-lm-patches/ (produce with stage-main-wheel.sh).
#   --repo DIR    ane-linux-experiments checkout for the bench scripts
#                 (benchmarks/); default: this script's repo root.
#   --keep-venv   keep the fresh venv under /var/tmp after the window
#                 (default: removed; state restore).
#
# Every mutation is listed in mutations.json; nothing outside the output dir,
# the fresh venv, and the HF cache is touched. No system installs, no ICD
# changes. Host identity is the neutral label "m2-host"; no serials, no IPs.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
STAGE_DIR="$(cd "$HERE" && pwd)/stage"
REPO_DIR="$(cd "$HERE/../.." && pwd)"
OUT_DIR=""
KEEP_VENV=0
SKIP_PARAKEET=0
SELFCHECK=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --stage) STAGE_DIR="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --repo) REPO_DIR="$2"; shift 2 ;;
    --keep-venv) KEEP_VENV=1; shift ;;
    --skip-parakeet) SKIP_PARAKEET=1; shift ;;
    --selfcheck) SELFCHECK=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

HOST_LABEL="m2-host"
T0=$(date +%s)
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT_DIR="${OUT_DIR:-$PWD/m2-window-$TS}"
VENV=""
mkdir -p "$OUT_DIR"
MUTATIONS="$OUT_DIR/mutations.json"
echo '{"mutations": [], "notes": []}' > "$MUTATIONS"

note_mutation() { # json object string
  python3 - "$MUTATIONS" "$1" <<'PY'
import json, sys
path, obj = sys.argv[1], json.loads(sys.argv[2])
d = json.load(open(path))
d["mutations"].append(obj)
json.dump(d, open(path, "w"), indent=1)
PY
}
note() {
  python3 - "$MUTATIONS" "$1" <<'PY'
import json, sys
path, msg = sys.argv[1], sys.argv[2]
d = json.load(open(path))
d["notes"].append(msg)
json.dump(d, open(path, "w"), indent=1)
PY
}
elapsed_s() { echo $(( $(date +%s) - T0 )); }

sha256_of() { sha256sum "$1" | cut -d' ' -f1; }
sha_prefix_ok() { # value prefix
  [[ "${1#"$2"}" != "$1" ]]
}

fail() { echo "M2-WINDOW FAIL: $*" >&2; exit 1; }

cleanup() {
  local rc=$?
  if [[ -n "$VENV" && -d "$VENV" && "$KEEP_VENV" != 1 ]]; then
    rm -rf "$VENV"
    note_mutation "{\"action\": \"removed\", \"path\": \"$VENV\", \"reason\": \"state restore (default)\"}"
  fi
  python3 - "$OUT_DIR" "$rc" "$(elapsed_s)" <<'PY'
import hashlib, json, os, subprocess, sys
out, rc, el = sys.argv[1], sys.argv[2], sys.argv[3]
d = {"host_label": "m2-host", "exit_code": int(rc), "elapsed_s": int(el),
     "kind": "m2-window", "final": True}
json.dump(d, open(os.path.join(out, "window.json"), "w"), indent=1)
os.chdir(out)
sums = []
for f in sorted(os.listdir(".")):
    if f.endswith((".json", ".txt", ".log", ".sums")) or f in ("SHA256SUMS",):
        if os.path.isfile(f):
            sums.append(f"{hashlib.sha256(open(f,'rb').read()).hexdigest()}  {f}")
open("SHA256SUMS", "w").write("\n".join(sums) + "\n")
PY
  echo "M2-WINDOW DONE rc=$rc elapsed=$(elapsed_s)s out=$OUT_DIR"
}
trap cleanup EXIT

# ---------------------------------------------------------------- selfcheck
if [[ "$SELFCHECK" == 1 ]]; then
  echo "== selfcheck: stage contents + pin table + receipt plumbing =="
  for f in "$STAGE_DIR"/mlx_omarchy-*.whl; do
    [[ -e "$f" ]] || { echo "selfcheck: no staged wheel in $STAGE_DIR (allowed; see stage-main-wheel.sh)"; break; }
    echo "wheel: $(basename "$f") sha256=$(sha256_of "$f")"
  done
  [[ -f "$STAGE_DIR/mlx-lm-patches/apply-mlx-lm-patches.sh" ]] \
    || echo "selfcheck: missing stage/mlx-lm-patches/ (stage-main-wheel.sh --export-patches only)"
  python3 - "$OUT_DIR" <<'PY'
import hashlib, json, os, sys
out = sys.argv[1]
json.dump({"host_label": "m2-host", "selfcheck": True,
           "pin_table": {
             "qwen_records": "dbf704971617fdfcf693c4287b9f0403ee24a2b2c5d3a9fb4d2a032d613c9596",
             "parakeet_transcript": "db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790",
             "parakeet_fixture": "30885601173f96b0d8ddd020dc959b055c6c1582b85a33e3fcab8c4b08ed94c2",
             "corpus": "9299a3b2fc136a4c0c355f9ad3e211be81823a5fb9eeadbc2e6608fb3e5718a0"}},
          open(os.path.join(out, "selfcheck.json"), "w"), indent=1)
PY
  note "selfcheck ok"
  exit 0
fi

# ---------------------------------------------------------------- preflight
echo "== preflight =="
[[ "$(uname -m)" == "aarch64" ]] || fail "this kit runs on the M2 host (aarch64); got $(uname -m)"
[[ -r /proc/device-tree/compatible ]] \
  && tr '\0' ' ' </proc/device-tree/compatible | grep -q "apple,t6021" \
  || fail "device-tree does not identify apple,t6021"
PY314="$(command -v python3.14 || command -v python3)"
"$PY314" -c 'import sys; sys.exit(sys.version_info[:2] != (3,14))' \
  || fail "python 3.14 required (M2 host convention); got $("$PY314" --version)"

WHEEL="$(ls "$STAGE_DIR"/mlx_omarchy-*-cp314-cp314-linux_aarch64.whl 2>/dev/null | head -n 1 || true)"
[[ -n "$WHEEL" ]] || fail "no staged wheel in $STAGE_DIR — run stage-main-wheel.sh first (needs the parakeet-encoder-whole bundle; see the script header)"
[[ -f "$STAGE_DIR/mlx-lm-patches/apply-mlx-lm-patches.sh" ]] || fail "stage/mlx-lm-patches/ missing"
[[ -f "$REPO_DIR/benchmarks/qwen38-mlx-bench.py" ]] || fail "benchmarks/ not found under --repo $REPO_DIR"
CORPUS="$REPO_DIR/benchmarks/qwen38-2b-prompts.jsonl"
[[ "$(sha256_of "$CORPUS")" == 9299a3b2fc136a4c0c355f9ad3e211be81823a5fb9eeadbc2e6608fb3e5718a0 ]] \
  || fail "prompt corpus sha mismatch"

MODEL_SNAP="$(ls -d "$HOME"/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/ 2>/dev/null | head -n 1 || true)"
[[ -n "$MODEL_SNAP" && -f "$MODEL_SNAP/model.safetensors" ]] \
  || fail "pinned Qwen3.8-2B snapshot not in the HF cache"
MODEL_SHA="$(sha256_of "$MODEL_SNAP/model.safetensors")"
sha_prefix_ok "$MODEL_SHA" "b0d5de68" || fail "model.safetensors sha $MODEL_SHA does not match pin b0d5de68…"

# Vulkan identity: per-device JSON check (text summary greps lie via llvmpipe).
VK_JSON="$OUT_DIR/vulkaninfo.json"
if command -v vulkaninfo >/dev/null 2>&1; then
  vulkaninfo --json > "$VK_JSON" 2>"$OUT_DIR/vulkaninfo.err" || true
else
  echo "vulkaninfo absent" > "$VK_JSON"
fi
VULKAN_ID="$(python3 - "$VK_JSON" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as e:
    print(json.dumps({"check": "inconclusive", "reason": str(e)})); raise SystemExit
rows = []
def emit(dev):
    name = dev.get("deviceName", "")
    ext = dev.get("supportedExtensions", {}) or {}
    rows.append({"device": name,
                 "driver": (dev.get("driverInfo", "") or {}).get("driverName", dev.get("driverName", "")),
                 "driver_ver": (dev.get("driverInfo", "") or {}).get("driverInfo", ""),
                 "cooperative_matrix": ext.get("VK_KHR_cooperative_matrix", {}).get("specVersion") if isinstance(ext.get("VK_KHR_cooperative_matrix"), dict) else ext.get("VK_KHR_cooperative_matrix")})
for dev in d.get("devices", []) or []:
    emit(dev)
apple_ok = any("Apple" in r["device"] and r["cooperative_matrix"] for r in rows)
print(json.dumps({"check": "ok" if apple_ok else "MISSING",
                  "devices": rows,
                  "note": "llvmpipe exposes coopmat but is not an Apple device; verdict is per-device"}))
PY
)"
echo "vulkan identity: $VULKAN_ID"

ICD_INFO="{}"
ICD_JSON="/usr/share/vulkan/icd.d/asahi_icd.json"
if [[ -f "$ICD_JSON" ]]; then
  ICD_INFO="$(python3 - "$ICD_JSON" <<'PY'
import hashlib, json, os, sys
p = sys.argv[1]
d = json.load(open(p))
lib = d.get("ICD", {}).get("library_path", "")
if lib and not os.path.isabs(lib):
    lib = os.path.join(os.path.dirname(p), lib)
h = hashlib.sha256(open(lib, "rb").read()).hexdigest() if os.path.isfile(lib) else None
print(json.dumps({"icd": p, "library_path": lib, "sha256": h, "api_version": d.get("ICD", {}).get("api_version")}))
PY
)"
fi
echo "icd: $ICD_INFO"

# ANE capability (gates only the parakeet leg; honest blocked receipt otherwise).
ANE_NODES="$(ls /dev/dri/renderD* 2>/dev/null | tr '\n' ' ' || true)"
ANE_LOADED=0; [[ -d /sys/module/ane ]] && ANE_LOADED=1
PARAKEET_VIABLE=0
if [[ "$ANE_LOADED" == 1 && -n "${ANE_NODES// }" ]]; then PARAKEET_VIABLE=1; fi
echo "ane: loaded=$ANE_LOADED nodes=${ANE_NODES:-none} parakeet_viable=$PARAKEET_VIABLE"

python3 - "$OUT_DIR" "$HOST_LABEL" "$WHEEL" "$MODEL_SNAP" "$MODEL_SHA" "$ICD_INFO" "$VULKAN_ID" "$ANE_LOADED" "$ANE_NODES" "$PARAKEET_VIABLE" <<'PY'
import hashlib, json, os, platform, sys
out = sys.argv[1]
env = {
 "host_label": "m2-host",
 "kind": "m2-window-env",
 "uname": platform.release(), "machine": platform.machine(),
 "python": platform.python_version(),
 "model_soc": open("/proc/device-tree/model").read().strip("\x00\n") if os.path.exists("/proc/device-tree/model") else None,
 "compatible": open("/proc/device-tree/compatible").read().replace("\x00", " ").strip() if os.path.exists("/proc/device-tree/compatible") else None,
 "wheel": {"path": os.path.basename(sys.argv[3]),
           "sha256": hashlib.sha256(open(sys.argv[3], "rb").read()).hexdigest()},
 "model_snapshot": {"dir": os.path.basename(sys.argv[4].rstrip("/")),
                    "safetensors_sha256": sys.argv[5]},
 "vulkan_icd": json.loads(sys.argv[6]),
 "vulkan_identity": json.loads(sys.argv[7]),
 "ane": {"module_loaded": bool(int(sys.argv[8])), "render_nodes": sys.argv[9].split(),
         "parakeet_viable": bool(int(sys.argv[10]))},
 "thermal_c": [round(int(open(f"/sys/class/thermal/{z}/temp").read())/1000.0, 1)
               for z in sorted(os.listdir("/sys/class/thermal")) if z.startswith("thermal_zone")]
 if os.path.isdir("/sys/class/thermal") else [],
 "loadavg_start": round(os.getloadavg()[0], 2),
}
json.dump(env, open(os.path.join(out, "env.json"), "w"), indent=1)
PY

# ------------------------------------------------------- fresh venv + stack
echo "== venv =="
VENV="/var/tmp/m2-window-venv-$TS"
"$PY314" -m venv --copies "$VENV"
note_mutation "{\"action\": \"created\", \"path\": \"$VENV\"}"
PIP="$VENV/bin/pip"
"$PIP" install --no-cache-dir "$WHEEL" mlx-lm==0.31.3 --no-deps 2>&1 | tail -2
"$PIP" install --no-cache-dir "transformers==5.16.1" numpy protobuf pyyaml jinja2 huggingface_hub 2>&1 | tail -2
"$VENV/bin/pip" freeze > "$OUT_DIR/pip-freeze.txt"

echo "== mlx-lm patches (GDN fast + raw route, greedy prune) =="
bash "$STAGE_DIR/mlx-lm-patches/apply-mlx-lm-patches.sh" "$VENV" 2>&1 | tee "$OUT_DIR/mlx-lm-patches.log"
SITE="$(dirname "$(ls -d "$VENV"/lib/python3.*/site-packages/mlx_lm | head -n 1)")"
RAW_COUNT="$(grep -rc "gated_delta_update_raw" "$SITE" 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')"
[[ "${RAW_COUNT:-0}" -ge 1 ]] || fail "raw-route patch not present after apply (count=$RAW_COUNT)"
echo "raw-route marker count: $RAW_COUNT"

# ----------------------------------------------------------- qwen contract
echo "== qwen GPU contract =="
WHEEL_COMMIT="$(basename "$WHEEL" .whl | awk -F'+' '{print $NF}' | cut -d- -f1)"
"$VENV/bin/python" "$HERE/stage/run_with_rss.py" \
  "$VENV/bin/python" "$REPO_DIR/benchmarks/qwen38-mlx-bench.py" \
    --model "$MODEL_SNAP" --prompts "$CORPUS" \
    --warmup 3 --passes 10 --new-tokens 32 --prefill-tokens 512 \
    --label "m2-t6021-gpu-main-${WHEEL_COMMIT:-unknown}" \
    --out "$OUT_DIR/qwen-contract.json" \
    2> "$OUT_DIR/qwen-bench.err"
tail -3 "$OUT_DIR/qwen-bench.err" || true

python3 - "$OUT_DIR" <<'PY'
import hashlib, json, os, random, statistics, sys
out = sys.argv[1]
d = json.load(open(os.path.join(out, "qwen-contract.json")))
recs = d["per_prompt"]
e2e = [round(r["ttft_s"] + r["decode_s"], 4) for r in recs]

# paired bootstrap 95% CI over the 10 repetitions (contract measurement
# block), 10k resamples, seed 0 — same methodology as the Sep-23 cells
by_rep = {}
for r in recs:
    by_rep.setdefault(r["pass"], []).append(r["decode_tok_rate"])
reps = [v for _, v in sorted(by_rep.items())]
rnd = random.Random(0)
boot = []
for _ in range(10000):
    sample = [reps[i] for i in (rnd.randrange(len(reps)) for _ in range(len(reps)))]
    flat = [x for rep in sample for x in rep]
    boot.append(round(statistics.median(flat), 2))
boot.sort()

peak = None
for line in open(os.path.join(out, "qwen-bench.err")):
    if line.startswith("PEAK_RSS_KB"):
        peak = int(line.split()[1])
PIN = "dbf704971617fdfcf693c4287b9f0403ee24a2b2c5d3a9fb4d2a032d613c9596"
digest = d["ordered_records_sha256"]
derived = {
  "kind": "qwen-derived",
  "decode_tok_rate_median": d["decode_tok_rate"]["median"],
  "decode_tok_rate_paired_bootstrap_ci95": [boot[249], boot[9749]],
  "ttft_tok_rate_median": d["ttft_tok_rate"]["median"],
  "pure_prefill": d.get("pure_prefill"),
  "e2e_s": {"median": round(statistics.median(e2e), 4),
            "min": min(e2e), "max": max(e2e), "n": len(e2e),
            "definition": "ttft_s + decode_s per record (n=100)"},
  "peak_rss_kb": peak,
  "records_digest": digest,
  "digest_gate": "match" if digest == PIN else "DIVERGES-from-dbf70497 (ship, do not install)",
}
json.dump(derived, open(os.path.join(out, "qwen-derived.json"), "w"), indent=1)
print(json.dumps({k: derived[k] for k in ("decode_tok_rate_median", "records_digest", "digest_gate")}))
PY

# -------------------------------------------------------- parakeet contract
if [[ "$SKIP_PARAKEET" != 1 ]]; then
  echo "== parakeet full-audio contract =="
  PKJSON="$OUT_DIR/parakeet.json"
  if [[ "$PARAKEET_VIABLE" != 1 ]]; then
    python3 - "$PKJSON" "$ANE_NODES" <<'PY'
import json, sys
json.dump({"kind": "parakeet", "status": "blocked-ane-unavailable",
           "cell": "parakeet-full-audio",
           "reason": "Linux ANE not up on this host (/sys/module/ane absent or no render node); "
                     "the ANE lane owns T6021 bring-up. Re-run the kit in a window after the ANE lands.",
           "render_nodes": sys.argv[2].split()},
          open(sys.argv[1], "w"), indent=1)
PY
    echo "parakeet: blocked-ane-unavailable (receipt written)"
  else
    "$VENV/bin/mlx-omarchy-parakeet" download --json > "$OUT_DIR/parakeet-download.json" 2>"$OUT_DIR/parakeet-download.err" \
      || echo "parakeet download rc=$? (continuing; transcribe will verify)" || true
    if "$VENV/bin/mlx-omarchy-parakeet" transcribe --repeat 6 -o "$OUT_DIR/parakeet-runs" \
         > "$OUT_DIR/parakeet-transcribe.log" 2>&1; then
      python3 - "$OUT_DIR" <<'PY'
import glob, hashlib, json, os, sys
out = sys.argv[1]
runs = os.path.join(out, "parakeet-runs")
reports = sorted(glob.glob(os.path.join(runs, "**", "transcribe-report.json"), recursive=True))
statuses, emissions, tshas = [], [], []
for rp in reports:
    r = json.load(open(rp))
    statuses.append(r.get("status"))
    checks = r.get("checks", {}) or {}
    em = (checks.get("emissions", {}) or {}).get("actual")
    if em is not None: emissions.append(em)
    t = (checks.get("transcript", {}) or {}).get("actual_sha256")
    if t: tshas.append(t)
for tf in glob.glob(os.path.join(runs, "**", "transcript.txt"), recursive=True):
    tshas.append(hashlib.sha256(open(tf, "rb").read()).hexdigest())
PIN = "db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
ok = bool(statuses) and all(s == "match" for s in statuses)
verdict = {
  "kind": "parakeet", "cell": "parakeet-full-audio",
  "status": "ok" if ok else "mismatch",
  "runs": len(reports), "statuses": statuses, "emissions": emissions,
  "transcript_sha256s": sorted(set(tshas)),
  "transcript_gate": "match" if any(t.startswith("db501a8c") for t in tshas) else "MISMATCH",
  "fixture_pin": "30885601173f96b0d8ddd020dc959b055c6c1582b85a33e3fcab8c4b08ed94c2",
}
json.dump(verdict, open(os.path.join(out, "parakeet.json"), "w"), indent=1)
print(json.dumps({k: verdict[k] for k in ("status", "runs", "transcript_gate")}))
PY
    else
      rc=$?
      python3 - "$PKJSON" "$rc" <<'PY'
import json, sys
json.dump({"kind": "parakeet", "cell": "parakeet-full-audio",
           "status": "failed", "exit_code": int(sys.argv[2]),
           "note": "transcribe failed; see parakeet-transcribe.log"},
          open(sys.argv[1], "w"), indent=1)
PY
      echo "parakeet: transcribe rc=$rc (receipt written)"
    fi
  fi
fi

echo "== receipts + state restore =="
note "window completed with wheel $(basename "$WHEEL")"
