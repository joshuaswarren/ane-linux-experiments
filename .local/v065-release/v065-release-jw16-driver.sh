#!/bin/bash
# v0.6.5 release gate on jw16 (M1 Max) — corrected driver.
# Gates the UPLOADED release bytes. Stops llm-inference.service to release
# /tmp/m1-gpu.lock (ExecStart flock --nonblock exec); ALWAYS restarts the
# service on exit and confirms active. Never steals the lock.
# Corrected per 2026-09-17-v063-gate-failure.md: file stdout, /tmp guard
# + trap cleanup, dedicated venv, HF_HUB_OFFLINE=1.
set -u
URL="https://github.com/joshuaswarren/mlx-omarchy/releases/download/v0.6.5/mlx_omarchy-0.32.2.dev202609171729+7b05e93-cp314-cp314-linux_aarch64.whl"
EXPECT_SHA="83434ca5a46f3b7aaedd75711b5ac089641a0f2ff936cd5c91dbf79fe70daec0"
EXPECT_DECODE="7da83f06ec9f001d"
ROOT=/var/tmp/v063-jw16
GATE=$ROOT/receipts/2026-09-16-parakeet-wheel-packaging/gate-jwm1.sh
WHLF=$ROOT/mlx_omarchy-0.32.2.dev202609171729+7b05e93-cp314-cp314-linux_aarch64.whl
OUT=/var/tmp/v065-release-gate-jw16
STATUS=/var/tmp/v065-release-jw16.status
VENV=/var/tmp/V064REL-venv

mkdir -p "$OUT"; : > "$STATUS"
note() { echo "$* $(date -Iseconds)" >> "$STATUS"; }
fatal() { note "FATAL: $*"; exit 9; }
restore_service() {
  sudo -n systemctl start llm-inference.service
  note "service=$(systemctl is-active llm-inference.service) after restart"
}
trap restore_service EXIT

# preflight
pgrep -f "mlx-omarchy-parakeet|gate-jwm1|bench_matrix" >/dev/null \
  && fatal "a gate/decode process is already live"
rm -rf /tmp/parakeet-gate.*
avail=$(df --output=avail -BG /tmp | tail -1 | tr -dc 0-9)
note "tmp avail ${avail}G after cleanup"
(( avail >= 3 )) || fatal "/tmp below 3G"
note "module=$(cat /sys/module/ane/version) map_mode=$(cat /sys/module/ane/parameters/map_mode)"

# uploaded bytes
curl -fsSL --retry 3 --max-time 600 -o "$WHLF" "$URL" || fatal "release download failed"
sha=$(sha256sum "$WHLF" | cut -d' ' -f1)
note "downloaded sha256 $sha"
[[ "$sha" == "$EXPECT_SHA" ]] || fatal "uploaded bytes hash mismatch"

# release the GPU lock by design: stop llm-inference
sudo -n systemctl stop llm-inference.service
note "service=$(systemctl is-active llm-inference.service) stopped"
locked=1
for i in $(seq 1 10); do
  if flock -n /tmp/m1-gpu.lock true; then locked=0; break; fi
  sleep 1
done
(( locked == 0 )) || fatal "lock still held after service stop"
note "lock-free"

# packaging gate: 3x clean-HOME transcribe
bash "$GATE" "$WHLF" "$OUT/packaging" > "$OUT/packaging.log" 2>&1
gate_rc=$?
note "gate-exit=$gate_rc"
[[ $gate_rc == 0 ]] || { note "GATE RED (packaging)"; exit 1; }

# pinned ctx1024 decode leg, dedicated venv
if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV" || fatal "venv create failed"
  "$VENV/bin/pip" install --quiet mlx-lm==0.31.3 || fatal "mlx-lm install failed"
fi
"$VENV/bin/pip" install --quiet --no-deps --force-reinstall "$WHLF" || fatal "wheel install failed"
cd "$ROOT"
flock -w 900 /tmp/m1-gpu.lock env HF_HUB_OFFLINE=1 MLX_DISABLE_COMPILE=1 \
  "$VENV/bin/python" scripts/bench_matrix.py \
  --mode run --select longctx-1024-decode-32 \
  > "$OUT/decode.json" 2> "$OUT/decode.log"
dec_rc=$?
note "decode-exit=$dec_rc"
[[ $dec_rc == 0 ]] || { note "GATE RED (decode run)"; exit 1; }

digest=$(python3 -c "
import json
d=json.load(open('$OUT/decode.json'))
for leg in d['legs']:
    if leg['leg_id']=='qwen25-0.5b-4bit:longctx-1024-decode-32' and leg.get('measured'):
        m=leg['metrics']; print(m['generated_ids_sha256_16'], m['decode_tok_s'])
")
note "decode leg: $digest"
echo "$digest" | grep -q "^$EXPECT_DECODE" || { note "GATE RED (decode digest)"; exit 1; }
note "GATE GREEN"
exit 0
