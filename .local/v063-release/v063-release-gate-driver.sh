#!/bin/bash
# v0.6.3 release gate on jwm1 — corrected driver.
# Gates the UPLOADED release bytes: wheel downloaded from the GitHub
# release URL, sha256-asserted, then (1) clean-install packaging gate
# (3x transcribe, pins checked by the gate itself), (2) pinned ctx1024
# decode leg in a dedicated venv (never ambient python).
# Corrected per 2026-09-17-v063-gate-failure.md:
#   - stdout always to a FILE (SIGPIPE killed the old driver post-run)
#   - /tmp cleaned + >=3G asserted BEFORE gating
#   - trap cleans gate scratch so a killed run orphans nothing
#   - decode leg uses dedicated V063REL venv + HF_HUB_OFFLINE=1
set -u
URL="https://github.com/joshuaswarren/mlx-omarchy/releases/download/v0.6.3/mlx_omarchy-0.32.2.dev202609171159+1ed1dab-cp314-cp314-linux_aarch64.whl"
EXPECT_SHA="dcb84f7b196bf70c61c420d72f8fcf001bdbac92716b039f0cd6c8fcd08fe23d"
EXPECT_DECODE="7da83f06ec9f001d"
GATE=/var/tmp/v062-wt/receipts/2026-09-16-parakeet-wheel-packaging/gate-jwm1.sh
MATRIX=/var/tmp/v062-wt/scripts/bench_matrix.py
OUT=/var/tmp/v063-release-gate
STATUS=/var/tmp/v063-release.status
VENV=/var/tmp/V063REL-venv
SNAP="$HOME/.cache/huggingface/hub/models--mlx-community--Qwen2.5-0.5B-Instruct-4bit/snapshots/a5339a4131f135d0fdc6a5c8b5bbed2753bbe0f3"

mkdir -p "$OUT"; : > "$STATUS"
WORK=""
cleanup() { if [[ -n "$WORK" && -d "$WORK" ]]; then rm -rf "$WORK"; fi; }
trap cleanup EXIT
note() { echo "$* $(date -Iseconds)" >> "$STATUS"; }

fatal() { note "FATAL: $*"; exit 9; }

# --- preflight: no live gate, /tmp clean and >=3G -----------------------
pgrep -f "mlx-omarchy-parakeet|gate-jwm1|bench_matrix" >/dev/null \
  && fatal "a gate/decode process is already live"
rm -rf /tmp/parakeet-gate.*
avail=$(df --output=avail -BG /tmp | tail -1 | tr -dc 0-9)
note "tmp avail ${avail}G after cleanup"
(( avail >= 3 )) || fatal "/tmp below 3G after cleanup"
[[ -d "$SNAP" ]] || fatal "pinned 0.5B-4bit snapshot missing"

# --- 1. fetch the UPLOADED release bytes and assert sha256 --------------
curl -fsSL --retry 3 --max-time 600 -o "$OUT/mlx_omarchy-0.32.2.dev202609171159+1ed1dab-cp314-cp314-linux_aarch64.whl" "$URL" || fatal "release download failed"
sha=$(sha256sum "$OUT/mlx_omarchy-0.32.2.dev202609171159+1ed1dab-cp314-cp314-linux_aarch64.whl" | cut -d' ' -f1)
note "downloaded sha256 $sha"
[[ "$sha" == "$EXPECT_SHA" ]] || fatal "uploaded bytes hash mismatch"

# --- 2. clean-install packaging gate (3x transcribe) --------------------
WORK=$(mktemp -d /tmp/parakeet-gate.release.XXXXXX)
bash "$GATE" "$OUT/mlx_omarchy-0.32.2.dev202609171159+1ed1dab-cp314-cp314-linux_aarch64.whl" "$OUT/packaging" > "$OUT/packaging.log" 2>&1
gate_rc=$?
note "gate-exit=$gate_rc"
WORK=""
[[ $gate_rc == 0 ]] || { note "GATE RED (packaging)"; exit 1; }

# --- 3. pinned ctx1024 decode leg, dedicated venv ------------------------
if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV" || fatal "venv create failed"
  "$VENV/bin/pip" install --quiet mlx-lm==0.31.3 || fatal "mlx-lm install failed"
fi
"$VENV/bin/pip" install --quiet --no-deps --force-reinstall "$OUT/mlx_omarchy-0.32.2.dev202609171159+1ed1dab-cp314-cp314-linux_aarch64.whl" || fatal "wheel install failed"
flock -w 900 /tmp/m1-gpu.lock env HF_HUB_OFFLINE=1 MLX_DISABLE_COMPILE=1 \
  "$VENV/bin/python" "$MATRIX" --mode run --select longctx-1024-decode-32 \
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
