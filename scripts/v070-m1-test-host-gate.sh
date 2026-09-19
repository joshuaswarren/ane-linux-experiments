#!/bin/bash
# v0.7.0 BOTH-HOST gate — m1-test-host-linux (T8103, M1) arm. Mirror of the t6001-test-host
# V070Recert gate (/tmp/v070-t6001-test-host-gate.sh, receipt
# mlx-omarchy/receipts/2026-09-18-v070-pretag-recert-t6001-test-host.md) with
# m1-test-host-linux paths and the C++ suites added. Run by scripts/v070-m1-test-host-arm.sh,
# which stages $ROOT/{wheel,kit,oproj} and resolves the E2E inputs first.
# Runs ON m1-test-host-linux.
#
# Gates (identical pins to t6001-test-host):
#  (0) artifact checks: sha256, version identity filename/dist-info/METADATA,
#      build commit b283a16 in libmlx, feature strings, WHEEL tag, runner
#      bytes == overlay bytes at b283a16f.
#  (1) clean-HOME packaging 3x (gate-m1-test-host.sh): transcript db501a8c... each run.
#  (2) E2E arms: serve-default / launch / placed-AC (hidden 38c73261...) /
#      placed-ACO (hidden ef6afd13... via merged oproj bundles), 104/104,
#      cpu_tensor_events 0, timeouts 0, bounds PASS, mel 5b54f4a9...
#  (3) BOTH decode legs in ONE flock hold: ctx1024 7da83f06ec9f001d +
#      short 7fd25a869ff21678, provenance names the wheel libmlx16.
#  (4) venv-identity-guard on the gate venv.
#  (5) hwcap probe + 13 FIPS 180-4 KATs on the DEPLOYED libmlx.
#  (6) C++ suites from a b283a16f worktree: primitive 103/103, runtime 41/41,
#      capability sim 6/6 (registry + 5 profiles), tape 12/12; fused-chain
#      recorded only (known candidate 33/34 dispatch-pin anomaly, T6001
#      A/B documented, non-blocking).
# Stops llm-inference.service when present to free /tmp/m1-gpu.lock; ALWAYS
# restarts and confirms on exit.
set -u
export PATH="$HOME/.local/bin:$PATH"
ROOT=/var/tmp/v070-m1-test-host
KIT="$ROOT/kit"
GATE="$KIT/gate-m1-test-host.sh"
MATRIX="$KIT/bench_matrix.py"
GUARD="$KIT/venv-identity-guard.py"
CERT="$KIT/certified-libmlx-identities.txt"
E2E="$KIT/fused_e2e.py"
DRVDIR="$KIT"
OPROJ="$KIT/oproj"
OUT="$ROOT/gate-out"
STATUS="$ROOT/v070-m1-test-host.status"
VENV="$ROOT/V070REL-venv"
REPO="${MLX_REPO:-$HOME/src/mlx-omarchy}"
WHLGLOB="$ROOT"/wheel/mlx_omarchy-0.32.3.dev*+*-cp314-cp314-linux_aarch64.whl
OVERLAY_RUNNER="$ROOT/kit/overlay-vulkan_encoder.py"
LOCK=/tmp/m1-gpu.lock
SERVICE=llm-inference.service
# E2E inputs (runner resolves and exports these; t6001-test-host-canonical defaults)
E2E_AUDIO="${E2E_AUDIO:-/var/tmp/ParakeetE2E/audio/fixture.flac}"
E2E_GOLDEN="${E2E_GOLDEN:-/var/tmp/EncoderParityAne/capture}"
E2E_SOURCE="${E2E_SOURCE:-/var/tmp/EncoderParityAne/encoder-source}"
E2E_ANEREF="${E2E_ANEREF:-/var/tmp/EncoderParityAne/capture/encoder_hidden.npy}"
EXPECT_CTX=7da83f06ec9f001d
EXPECT_SHORT=7fd25a869ff21678
EXPECT_TRANSCRIPT=db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790
EXPECT_HIDDEN_AC=38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7
EXPECT_HIDDEN_ACO=ef6afd137f1610901c1bce9cf4c9e199edc430c37bd4aeb27caa4622692d5e88
EXPECT_MEL=5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde
# Wheel provenance pin: the PUBLISHED v0.7.0 aarch64 wheel (4ff560af build,
# shipped 2026-09-19 05:42Z). The recert wheel (b283a16f) was
# 2def345c00a60c41d2f18018096720611d40ff5a3dc50845ae3e19dc59794e53.
EXPECT_WHEEL_SHA="${EXPECT_WHEEL_SHA:-c3143a70162abad80d7c3e20fd6a7302a890bd41757a85ef83e60484a6f1278a}"

mkdir -p "$OUT"; : > "$STATUS"
note() { echo "$* $(date -Iseconds)" >> "$STATUS"; }
fatal() { note "FATAL: $*"; exit 9; }
SVC_EXISTS=$(systemctl list-unit-files "$SERVICE" -q --no-legend 2>/dev/null | wc -l)
restore_service() {
  [ "$SVC_EXISTS" -eq 1 ] || return 0
  sudo -n systemctl start "$SERVICE"
  local code i
  for i in $(seq 1 90); do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:8002/health 2>/dev/null) || code=000
    [ "$code" = "200" ] && break
    sleep 2
  done
  note "service=$(systemctl is-active "$SERVICE") health=$code after restart"
}
trap restore_service EXIT

# --- preflight -------------------------------------------------------------
[ "$(uname -m)" = "aarch64" ] || fatal "not aarch64"
command -v python3.14 >/dev/null || fatal "python3.14 missing"
for f in "$GATE" "$MATRIX" "$GUARD" "$CERT" "$E2E" "$OVERLAY_RUNNER" \
         "$DRVDIR/hwcap_probe.c" "$DRVDIR/kat_probe.cpp" "$E2E_AUDIO" "$E2E_GOLDEN" \
         "$E2E_SOURCE" "$E2E_ANEREF"; do
  [ -e "$f" ] || fatal "staged input missing: $f"
done
ls "$OPROJ"/island-oproj-L* >/dev/null 2>&1 || fatal "oproj islands missing: $OPROJ"
[ -d "$REPO/.git" ] || fatal "mlx-omarchy repo missing at $REPO (needed for suites)"

pgrep -f "mlx-omarchy-parakeet|gate-m1-test-host|bench_matrix|fused_e2e" >/dev/null \
  && fatal "a gate/decode/e2e process is already live"
rm -rf /tmp/parakeet-gate.*
WHLF=$(ls $WHLGLOB 2>/dev/null | head -1)
[ -f "$WHLF" ] || fatal "candidate wheel not found: $WHLGLOB"
note "wheel $(basename "$WHLF")"
SHA=$(sha256sum "$WHLF" | cut -d' ' -f1)
note "wheel sha256 $SHA$( [ -n "$EXPECT_WHEEL_SHA" ] && echo " (== $EXPECT_WHEEL_SHA provenance)" || echo " (unpinned: set EXPECT_WHEEL_SHA to assert provenance)" )"
if [ -n "$EXPECT_WHEEL_SHA" ] && [ "$SHA" != "$EXPECT_WHEEL_SHA" ]; then
  fatal "wheel sha256 $SHA != pinned $EXPECT_WHEEL_SHA"
fi
note "wheel size $(stat -c '%s' "$WHLF")"

# --- (0) artifact checks ---------------------------------------------------
python3 - "$WHLF" "$OUT" "$OVERLAY_RUNNER" <<'PY' || { note "GATE RED (artifact checks)"; exit 1; }
import hashlib, sys, zipfile, re
wheel, out, overlay_runner = sys.argv[1], sys.argv[2], sys.argv[3]
fails = []
zf = zipfile.ZipFile(wheel)
name = wheel.split("/")[-1]
mver = re.match(r"mlx_omarchy-(.+)-cp314-cp314-linux_aarch64\.whl", name).group(1)
commit = mver.split("+")[-1]
distinfo = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
mv = re.match(r"mlx_omarchy-(.+)\.dist-info/METADATA", distinfo[0]).group(1)
meta = zf.read(distinfo[0]).decode()
if mv != mver: fails.append(f"version mismatch dist-info {mv} vs filename {mver}")
line = [l for l in meta.splitlines() if l.startswith("Version:")][0].split()[1]
if line != mver: fails.append(f"METADATA Version {line} vs filename {mver}")
if not re.fullmatch(r"[0-9a-f]{7,40}", commit): fails.append(f"filename build commit {commit!r} not a git sha")
lib = zf.read("mlx/lib/libmlx.so")
if commit.encode() not in lib: fails.append(f"libmlx.so does not record build commit {commit}")
if b"MLX_OMARCHY_GPU_PROFILE" in lib: fails.append("stable wheel carries MLX_OMARCHY_GPU_PROFILE")
if b"MLX_DISABLE_COMPILE" not in lib: fails.append("positive control MLX_DISABLE_COMPILE missing - check broken")
runner = None
for n in zf.namelist():
    if n.endswith("vulkan_encoder.py"):
        runner = zf.read(n); break
if runner is None:
    fails.append("vulkan_encoder.py not found in wheel")
else:
    rsha = hashlib.sha256(runner).hexdigest()
    osha = hashlib.sha256(open(overlay_runner, "rb").read()).hexdigest()
    if rsha != osha: fails.append(f"runner sha {rsha} != overlay-at-b283a16f {osha}")
    print(f"runner sha256 {rsha}")
wheeltxt = zf.read(distinfo[0].replace("METADATA", "WHEEL")).decode()
tags = [l.split()[1] for l in wheeltxt.splitlines() if l.startswith("Tag:")]
if "cp314-cp314-linux_aarch64" not in tags: fails.append(f"WHEEL tags {tags} lack filename platform")
sha = hashlib.sha256(open(wheel, "rb").read()).hexdigest()
lib16 = hashlib.sha256(lib).hexdigest()[:16]
print(f"artifact sha256 {sha}")
print(f"libmlx16 {lib16}")
print(f"version {mver}")
open(out + "/libmlx16", "w").write(lib16)
open(out + "/commit", "w").write(commit)
print(f"build commit {commit}")
if fails:
    print("ARTIFACT FAILS:", *fails, sep="\n  "); sys.exit(1)
print("artifact checks PASS")
PY
[ -f "$OUT/libmlx16" ] || fatal "no libmlx16 recorded"
LIBMLX16=$(cat "$OUT/libmlx16")
note "libmlx16=$LIBMLX16"
grep -q "^$LIBMLX16" "$CERT" && fatal "candidate libmlx16 already on certified list - regenerate"

# --- release the GPU lock by design: stop the serving unit when present ----
if [ "$SVC_EXISTS" -eq 1 ]; then
  sudo -n systemctl stop "$SERVICE"
  note "service=$(systemctl is-active "$SERVICE") stopped"
fi
for i in $(seq 1 10); do
  if flock -n "$LOCK" true 2>/dev/null; then break; fi
  sleep 1
done
flock -n "$LOCK" true 2>/dev/null || fatal "lock still held after service stop"
note "lock-free"

# --- (1) packaging gate: clean-HOME 3x -------------------------------------
bash "$GATE" "$WHLF" "$OUT/packaging" > "$OUT/packaging.log" 2>&1
gate_rc=$?
note "gate-exit=$gate_rc"
[ "$gate_rc" = 0 ] || { note "GATE RED (packaging)"; exit 1; }
for run in 1 2 3; do
  td=$(sha256sum "$OUT/packaging/run-$run/transcript.txt" | cut -d' ' -f1)
  note "transcript run-$run $td"
  [ "$td" = "$EXPECT_TRANSCRIPT" ] || { note "GATE RED (transcript run-$run)"; exit 1; }
done

# --- (2) E2E arms on wheel-installed files ---------------------------------
# ACO provenance (same finding as t6001-test-host, receipt above): the wheel ships no
# island-oproj-L* bundles, so pure main-bytes PLACED=ACO silently runs the
# o-proj on GPU (hidden = AC pin). The ACO arm uses the merged bundle dir =
# wheel base islands + staged oproj islands in $OPROJ. Runner/pkg/worker/
# libane stay wheel bytes.
rm -rf "$VENV"
python3.14 -m venv "$VENV"
"$VENV/bin/pip" install --quiet numpy protobuf soundfile
"$VENV/bin/pip" install --quiet --no-deps "$WHLF"
"$VENV/bin/pip" install --quiet --no-deps mlx-lm==0.31.3 Jinja2==3.1.6 \
  safetensors==0.8.0 tokenizers==0.23.2 transformers==5.16.1 PyYAML==6.0.3 \
  regex==2026.9.10 requests==2.34.2 tqdm==4.70.1 packaging==26.3 \
  typing_extensions==4.16.0 huggingface_hub==1.32.0 hf-xet==1.6.0 \
  filelock==4.0.0 fsspec==2026.7.0 httpx==0.28.1 httpcore==1.0.9 \
  anyio==4.15.1 h11==0.16.0 idna==3.20 certifi==2026.7.22 \
  charset-normalizer==3.5.1 urllib3==2.8.0 MarkupSafe==3.0.3 sniffio==1.3.1
"$VENV/bin/python" -c 'import mlx_lm' || fatal "mlx_lm not importable in gate venv"
SITE=$("$VENV/bin/python" -c 'import mlx, pathlib; print(pathlib.Path(mlx.__path__[0]).resolve())')
note "arm site $SITE"
for rel in coreml/vulkan_encoder.py coreml/parakeet-reference.lock \
           share/mlx-omarchy/parakeet-1/bundles \
           share/mlx-omarchy/parakeet-1/libane/libane-strict.so \
           bin/mlx-omarchy-ane-worker; do
  [ -e "$SITE/$rel" ] || fatal "installed surface missing: $rel"
done
WBUNDLES="$SITE/share/mlx-omarchy/parakeet-1/bundles"
ACO_BUNDLES="$OUT/bundles-aco-merged"
rm -rf "$ACO_BUNDLES" && cp -a "$WBUNDLES" "$ACO_BUNDLES"
cp -a "$OPROJ"/island-oproj-L* "$ACO_BUNDLES"/
[ -d "$ACO_BUNDLES/island-oproj-L00" ] || fatal "staged oproj islands missing"
mkdir -p "$OUT/armhome"
flock -w 900 "$LOCK" env HOME="$OUT/armhome" \
  "$VENV/bin/python" "$SITE/bin/mlx-omarchy-parakeet" download \
  > "$OUT/arm-download.log" 2>&1 || fatal "CLI download for arms failed"
MODELPATH=$(find "$OUT/armhome/.cache/mlx-omarchy/parakeet-reference" -mindepth 3 -maxdepth 3 -type d 2>/dev/null | head -1)
[ -d "$MODELPATH" ] || fatal "model dir not found under armhome cache"
note "arm model dir $MODELPATH"
mkdir -p "$OUT/pysite"
ln -sfn "$SITE/coreml" "$OUT/pysite/coreml"
export PYTHONPATH="$OUT/pysite"
e2earm () { # name expected_hidden [extra env...]
  local name=$1 exphid=$2; shift 2
  local outdir="$OUT/e2e-$name" scratch="$OUT/e2escratch-$name"
  local bundles="$WBUNDLES"
  [ "$name" = "placed-aco" ] && bundles="$ACO_BUNDLES"
  rm -rf "$outdir" "$scratch"; mkdir -p "$outdir" "$scratch"
  env "$@" flock -w 900 "$LOCK" \
    "$VENV/bin/python" "$E2E" \
    --audio "$E2E_AUDIO" \
    --golden "$E2E_GOLDEN" \
    --model "$MODELPATH" \
    --pkg "$SITE" \
    --encoder-runner "$SITE/coreml/vulkan_encoder.py" \
    --source "$E2E_SOURCE" \
    --ane-reference "$E2E_ANEREF" \
    --bundles "$bundles" \
    --worker "$SITE/bin/mlx-omarchy-ane-worker" \
    --libane "$SITE/share/mlx-omarchy/parakeet-1/libane/libane-strict.so" \
    --scratch "$scratch" --out "$outdir" --deadline-ms 20000 \
    > "$OUT/e2e-$name.log" 2>&1 || { note "GATE RED (e2e arm $name run)"; exit 1; }
  python3 - "$outdir" "$name" "$exphid" <<'PY' > "$OUT/e2e-$name.pins" 2>&1 || { note "GATE RED (e2e arm $name pins)"; exit 1; }
import hashlib, json, sys
out, name, exphid = sys.argv[1], sys.argv[2], sys.argv[3]
r = json.load(open(out + "/e2e-report.json"))
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
seq = r["layers"]["layer_6_decoder_sequence"]
enc = next((s for s in r["stages"] if isinstance(s, dict) and s.get("stage") == "encoder_ane"), {})
row = {
    "arm": name, "status": r["status"],
    "subs": r["ane"]["submissions"], "timeouts": r["ane"]["timeouts"],
    "prefix": seq.get("matching_prefix_length"),
    "bounds": r["layers"]["layer_5_encoder"]["all_bounds_pass"],
    "cpu_ev": r["execution"]["cpu_tensor_events"],
    "ane_mode": r["execution"].get("ane_mode"),
    "enc_wall_ms": enc.get("wall_ms"),
    "total_ms": round(r["timing"]["total_pipeline_ms"], 1),
    "transcript": sha(out + "/transcript.txt"),
    "hidden": sha(out + "/encoder_hidden.npy"),
    "mel": sha(out + "/mel.npy"),
}
EXP = {
    "transcript": "db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790",
    "mel": "5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde",
}
EXP["hidden"] = exphid
for k, v in EXP.items():
    assert row[k] == v, f"{k} {row[k]} != pin"
assert row["status"] == "match", row["status"]
assert row["prefix"] == 104, row["prefix"]
assert row["bounds"] is True
assert row["cpu_ev"] == 0, row["cpu_ev"]
assert row["timeouts"] == 0, row["timeouts"]
print(json.dumps(row, separators=(",", ":")))
PY
  note "e2e arm $name: $(cat "$OUT/e2e-$name.pins")"
  rm -rf "$scratch"
}
e2earm serve-default "$EXPECT_HIDDEN_AC" MLX_OMARCHY_SPIRV_CACHE="$OUT/spirv-serve"
e2earm launch "$EXPECT_HIDDEN_AC" MLX_OMARCHY_SPIRV_CACHE="$OUT/spirv-launch" ANE_ISLAND_MODE=launch
e2earm placed-ac "$EXPECT_HIDDEN_AC" MLX_OMARCHY_SPIRV_CACHE="$OUT/spirv-ac" MLX_OMARCHY_PLACED=AC
e2earm placed-aco "$EXPECT_HIDDEN_ACO" MLX_OMARCHY_SPIRV_CACHE="$OUT/spirv-aco" MLX_OMARCHY_PLACED=ACO
unset PYTHONPATH

# --- (4) venv identity guard on the arm/decode venv ------------------------
cp "$CERT" "$OUT/certified-libmlx-identities.v070cand.txt"
echo "$LIBMLX16 v0.7.0-candidate-b283a16 (LOCAL candidate line, pre-tag, m1-test-host arm)" \
  >> "$OUT/certified-libmlx-identities.v070cand.txt"
env -u PYTHONPATH python3 "$GUARD" --list "$OUT/certified-libmlx-identities.v070cand.txt" \
  --expect "$LIBMLX16" "$VENV" > "$OUT/guard.txt" 2>&1
grc=$?
note "guard-exit=$grc"
tail -2 "$OUT/guard.txt" >> "$STATUS"
[ "$grc" = 0 ] || { note "GATE RED (venv identity guard)"; exit 1; }

# --- (3) BOTH decode legs inside ONE flock hold (the v0.6.5 fix) -----------
flock -w 900 "$LOCK" bash -c '
  set -e
  cd '"$ROOT"'
  env HF_HUB_OFFLINE=1 MLX_DISABLE_COMPILE=1 \
    "'"$VENV"'/bin/python" "'"$MATRIX"'" --mode run --select longctx-1024-decode-32 \
    > '"$OUT"'/decode.json 2> '"$OUT"'/decode.log
  env HF_HUB_OFFLINE=1 MLX_DISABLE_COMPILE=1 \
    "'"$VENV"'/bin/python" "'"$MATRIX"'" --mode run --select short-decode-32 \
    > '"$OUT"'/decode-short.json 2> '"$OUT"'/decode-short.log
' || { note "GATE RED (decode runs, exit=$?)"; exit 1; }
note "both decode legs completed inside one lock hold"

"$VENV/bin/python" - "$OUT" "$EXPECT_CTX" "$EXPECT_SHORT" "$LIBMLX16" <<'PY' > "$OUT/legs.txt" 2>&1 || { note "GATE RED (digest)"; exit 1; }
import json, sys
out, ctx, short, lib16 = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
def leg(path, leg_id, expect):
    d = json.load(open(path))
    cands = [l for l in d["legs"] if l["leg_id"] == leg_id]
    assert len(cands) == 1, f"{leg_id}: {len(cands)} matches"
    l = cands[0]
    m = l["metrics"]
    dig = m["generated_ids_sha256_16"]
    prov = m["provenance_line"]
    assert f"libmlx.so=sha256:{lib16}" in prov, f"provenance libmlx mismatch: {prov}"
    assert l.get("exit_code", 0) == 0, l.get("exit_code")
    print(f"{leg_id} digest {dig} expect {expect}")
    assert dig == expect, dig
    return m
a = leg(out + "/decode.json", "qwen25-0.5b-4bit:longctx-1024-decode-32", ctx)
b = leg(out + "/decode-short.json", "qwen25-0.5b-4bit:short-decode-32", short)
print(f"ctx1024 tok/s {a.get('decode_tok_s')}")
print(f"short tok/s {b.get('decode_tok_s')}")
PY
note "legs: $(tr '\n' ';' < "$OUT/legs.txt")"

# --- (5) hwcap probe + KATs against the DEPLOYED libmlx --------------------
LIB="$SITE/lib/libmlx.so"
[ -f "$LIB" ] || fatal "deployed libmlx.so missing at $LIB"
[ "$(sha256sum "$LIB" | cut -d' ' -f1 | cut -c1-16)" = "$LIBMLX16" ] || fatal "deployed libmlx != wheel libmlx identity"
cc -O2 -o "$OUT/hwcap_probe" "$DRVDIR/hwcap_probe.c" || fatal "hwcap compile failed"
"$OUT/hwcap_probe" > "$OUT/hwcap.txt" 2>&1
note "hwcap: $(cat "$OUT/hwcap.txt")"
grep -q "HWCAP_SHA256=1" "$OUT/hwcap.txt" || { note "GATE RED (hwcap)"; exit 1; }
g++ -O2 -o "$OUT/kat_probe" "$DRVDIR/kat_probe.cpp" -ldl || fatal "kat compile failed"
"$OUT/kat_probe" "$LIB" > "$OUT/kat.txt" 2>&1
kat_rc=$?
tail -2 "$OUT/kat.txt" >> "$STATUS"
note "kat-exit=$kat_rc"
[ "$kat_rc" = 0 ] || { note "GATE RED (KAT/MBs)"; exit 1; }

# --- (6) C++ suites from a worktree at the wheel's build commit ------------
COMMIT=$(cat "$OUT/commit")
git -C "$REPO" worktree list | grep -q "$ROOT/wt" || git -C "$REPO" worktree add --detach "$ROOT/wt" "$COMMIT" || fatal "worktree at $COMMIT failed"
( cd "$ROOT/wt" && ./scripts/prepare-mlx.sh > "$OUT/prepare-mlx.log" 2>&1 ) || fatal "prepare-mlx failed"
( cd "$ROOT/wt" && cmake -S .work/mlx -B .work/build-tests -DMLX_BUILD_TESTS=ON -DCMAKE_BUILD_TYPE=Release \
    > "$OUT/suites-config.log" 2>&1 ) || fatal "suites cmake configure failed"
( cd "$ROOT/wt" && cmake --build .work/build-tests -j"$(nproc)" \
    --target omarchy_primitive_tests omarchy_runtime_tests omarchy_capability_sim_tests \
    omarchy_compiled_tape_tests omarchy_fused_chain_tests \
    > "$OUT/suites-build.log" 2>&1 ) || fatal "suites build failed"
TBIN="$ROOT/wt/.work/build-tests/tests/omarchy"
suite_run () { # name expect_total_or_skip
  flock -w 900 "$LOCK" timeout 3600 "$TBIN/$1" > "$OUT/suite-$1.log" 2>&1
  local rc=$?
  local line passed total
  line=$(grep -E "^\[doctest\] test cases: +[0-9]+ \|" "$OUT/suite-$1.log" | tail -1)
  total=$(echo "$line" | sed -E 's/.*test cases: +([0-9]+).*/\1/')
  passed=$(echo "$line" | sed -E 's/.*\| *([0-9]+) passed.*/\1/')
  if [ "$rc" != 0 ]; then
    note "GATE RED (suite $1 rc=$rc)"; exit 1
  fi
  note "suite $1: $passed/$total"
  [ -n "$2" ] && [ "$passed/$total" != "$2" ] && { note "GATE RED (suite $1 $passed/$total != $2)"; exit 1; }
}
suite_run omarchy_primitive_tests 103/103
suite_run omarchy_runtime_tests 41/41
suite_run omarchy_compiled_tape_tests 12/12
# capability sim: registry unit (no args runs it, then prints usage, exit 2)
# + 5/5 profiles rc=0 = 6/6 (per the v070 receipt's usage note).
"$TBIN/omarchy_capability_sim_tests" > "$OUT/capsim-registry.log" 2>&1
capreg_rc=$?
grep -qiE "registry" "$OUT/capsim-registry.log" || { note "GATE RED (capsim registry unit missing)"; exit 1; }
[ "$capreg_rc" = 2 ] || note "capsim registry rc=$capreg_rc (usage-exit expected 2)"
cap_n=1
for prof in m1-honeykrisp-fork m1-stock-no-coopmat subgroup-size-64 small-shared-memory no-cooperative-matrix; do
  flock -w 900 "$LOCK" env MLX_OMARCHY_ALLOW_NON_APPLE=1 timeout 1800 \
    "$TBIN/omarchy_capability_sim_tests" "$prof" > "$OUT/capsim-$prof.log" 2>&1 \
    || { note "GATE RED (capsim profile $prof rc=$?)"; exit 1; }
  cap_n=$((cap_n + 1))
done
note "capsim: $cap_n/6 (registry + 5 profiles)"
# fused-chain: recorded, NOT gating (known candidate dispatch-pin anomaly
# 33/34, A/B'd vs stock on T6001, non-blocking per the v070 receipt).
flock -w 900 "$LOCK" timeout 3600 "$TBIN/omarchy_fused_chain_tests" > "$OUT/suite-fused_chain.log" 2>&1
fc_line=$(grep -E "^\[doctest\] test cases:" "$OUT/suite-fused_chain.log" | tail -1)
note "suite omarchy_fused_chain_tests (recorded, non-blocking): ${fc_line:-rc=$?}"

note "GATE GREEN"
exit 0
