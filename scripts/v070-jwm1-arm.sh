#!/bin/bash
# v0.7.0 both-host arm runner — stages the jw16-proven gate kit onto
# jwm1-linux and runs scripts/v070-jwm1-gate.sh there. One command, safe to
# re-run; the gate keeps running on jwm1-linux if this script is interrupted
# (--attach re-polls). Run from any fleet orchestration box AFTER jwm1-linux
# returns (Asahi 1TR repair complete).
#
#   scripts/v070-jwm1-arm.sh            # wait for host, stage, run, poll
#   scripts/v070-jwm1-arm.sh --wait 3600
#   scripts/v070-jwm1-arm.sh --stage-only
#   scripts/v070-jwm1-arm.sh --attach   # re-poll a running gate
#
# Gate table enforced on jwm1-linux (pins identical to jw16 V070Recert):
#   packaging 3x transcript-exact db501a8c...; E2E serve/launch/AC/ACO pins
#   (38c73261 / ef6afd13); decode legs 7fd25a86 / 7da83f06; primitive 103/103,
#   runtime 41/41, capsim 6/6, tape 12/12; wheel sha 2def345c provenance;
#   venv guard, hwcap, KATs.
set -u
JWM1_HOST="${JWM1_HOST:-jwm1}"          # ssh alias / 100.84.184.102
JW16_HOST="${JW16_HOST:-16m1mbp}"       # wheel + kit source (gate ran green here)
MLX_REPO="${MLX_REPO:-$HOME/src/mlx-omarchy}"
# Wheel provenance pin: the PUBLISHED v0.7.1 aarch64 wheel (50eeb290 build,
# shipped 2026-09-19; x86_64 is 11747f46...). Override via env only if
# a future lane re-stages and re-publishes.
EXPECT_WHEEL_SHA="${EXPECT_WHEEL_SHA:-e536056bcb23d8d93121edc662cebb0c4b14b8670233c8f018ad54150b9b8d49}"
ROOT_DEST=/var/tmp/v070-jwm1
MODE=run; WAIT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --stage-only) MODE=stage ;;
    --attach) MODE=attach ;;
    --wait) [ $# -ge 2 ] || { echo "--wait needs a value"; exit 2; }; WAIT=$2; shift ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
  shift
done

die() { echo "FATAL: $*" >&2; exit 9; }
note() { echo "[arm] $*"; }

ssh_ok() { ssh -o ConnectTimeout=6 -o BatchMode=yes "$1" true 2>/dev/null; }

# --attach: skip staging, just poll an existing gate.
if [ "$MODE" != "attach" ]; then
  until ssh_ok "$JWM1_HOST"; do
    [ "$WAIT" -gt 0 ] || die "jwm1-linux ($JWM1_HOST) not reachable. The Asahi 1TR repair has not brought Linux back yet. Run with --wait N to poll."
    WAIT=$((WAIT - 15)); sleep 15
  done
  [ "$(ssh -o BatchMode=yes "$JWM1_HOST" uname -m)" = "aarch64" ] || die "$JWM1_HOST is not aarch64 — wrong host?"

  WORK=$(mktemp -d /tmp/v070-jwm1-kit.XXXXXX)
  trap 'rm -rf "$WORK"' EXIT
  mkdir -p "$WORK/kit" "$WORK/oproj" "$WORK/wheel"

  note "collecting kit from $JW16_HOST (wheel, oproj islands, probes, e2e harness)"
  WHLNAME=$(ssh -o BatchMode=yes "$JW16_HOST" \
    'ls /var/tmp/v070-jw16/dist/mlx_omarchy-0.32.3.dev*+*-cp314-cp314-linux_aarch64.whl 2>/dev/null | head -1')
  [ -n "$WHLNAME" ] || die "candidate wheel not found on $JW16_HOST (/var/tmp/v070-jw16/dist/)"
  scp -q -o BatchMode=yes "$JW16_HOST:$WHLNAME" "$WORK/wheel/" \
    || die "wheel copy failed from $JW16_HOST:$WHLNAME"
  WHLF=$(ls "$WORK"/wheel/*.whl)
  got=$(sha256sum "$WHLF" | cut -d' ' -f1)
  if [ -n "$EXPECT_WHEEL_SHA" ]; then
    [ "$got" = "$EXPECT_WHEEL_SHA" ] || die "wheel sha mismatch: $got != pinned $EXPECT_WHEEL_SHA"
    note "wheel staged, sha256 verified: $EXPECT_WHEEL_SHA"
  else
    note "wheel staged UNPINNED — sha256 $got (set EXPECT_WHEEL_SHA to assert provenance)"
  fi

  # Overlay runner bytes must come from the SAME commit as the wheel.
  WHLCOMMIT=$(basename "$WHLNAME" | sed -E 's/.*\+([0-9a-f]+)-cp314.*/\1/')
  curl -fsSL "https://raw.githubusercontent.com/joshuaswarren/mlx-omarchy/$WHLCOMMIT/overlay/tools/coreml/vulkan_encoder.py" \
    -o "$WORK/kit/overlay-vulkan_encoder.py" \
    || die "overlay vulkan_encoder.py fetch at $WHLCOMMIT failed (no network to raw.githubusercontent.com?)"
  [ "$(wc -c < "$WORK/kit/overlay-vulkan_encoder.py")" -gt 1000 ] || die "overlay fetch suspiciously small"
  scp -q -o BatchMode=yes "$JW16_HOST:/var/tmp/v067-gate/hwcap_probe.c" "$JW16_HOST:/var/tmp/v067-gate/kat_probe.cpp" "$WORK/kit/" \
    || die "hwcap/kat probe sources not found on $JW16_HOST (/var/tmp/v067-gate/)"
  scp -q -o BatchMode=yes "$JW16_HOST:/var/tmp/ParakeetE2EJw16/fused_e2e.py" "$WORK/kit/" \
    || die "fused_e2e.py not found on $JW16_HOST (/var/tmp/ParakeetE2EJw16/)"
  scp -q -o BatchMode=yes "$JW16_HOST:/var/tmp/v063-jw16/scripts/venv-identity-guard.py" \
    "$JW16_HOST:/var/tmp/v063-jw16/scripts/certified-libmlx-identities.txt" "$WORK/kit/" \
    || die "venv-identity-guard.py / certified-libmlx-identities.txt not found on $JW16_HOST (/var/tmp/v063-jw16/scripts/)"
  scp -q -o BatchMode=yes "$JW16_HOST:/var/tmp/jw16-encoder-islands/bundles/island-oproj-L*" "$WORK/oproj/" \
    || die "island-oproj-L* bundles not found on $JW16_HOST (/var/tmp/jw16-encoder-islands/bundles/)"
  [ -d "$WORK/oproj/island-oproj-L00" ] || die "oproj staging incomplete (no island-oproj-L00)"

  note "collecting repo-side gate pieces from $MLX_REPO"
  for f in receipts/2026-09-16-parakeet-wheel-packaging/gate-jwm1.sh \
           scripts/bench_matrix.py; do
    [ -f "$MLX_REPO/$f" ] || die "missing in $MLX_REPO: $f"
  done
  cp "$MLX_REPO/receipts/2026-09-16-parakeet-wheel-packaging/gate-jwm1.sh" "$WORK/kit/"
  cp "$MLX_REPO/scripts/bench_matrix.py" "$WORK/kit/"
  cp "$(dirname "$0")/v070-jwm1-gate.sh" "$WORK/gate.sh"

  note "pushing kit to $JWM1_HOST:$ROOT_DEST"
  ssh -o BatchMode=yes "$JWM1_HOST" "mkdir -p $ROOT_DEST"
  rsync -a -e "ssh -o BatchMode=yes" "$WORK/wheel" "$WORK/kit" "$WORK/oproj" "$WORK/gate.sh" "$JWM1_HOST:$ROOT_DEST/"
  ssh -o BatchMode=yes "$JWM1_HOST" "test -f $ROOT_DEST/gate.sh && test -d $ROOT_DEST/oproj && ls $ROOT_DEST/oproj/island-oproj-L* >/dev/null && sha256sum $ROOT_DEST/wheel/*.whl" | grep -q "$got" \
    || die "staged kit verification on $JWM1_HOST failed"

  # E2E inputs: use jwm1-local copies when present (2026-09-16 both-host E2E
  # staged them there), else push from jw16 and pin the env overrides.
  E2E_ENV=""
  missing=$(ssh -o BatchMode=yes "$JWM1_HOST" '
    for f in /var/tmp/ParakeetE2E/audio/fixture.flac /var/tmp/EncoderParityAne/capture \
             /var/tmp/EncoderParityAne/encoder-source /var/tmp/EncoderParityAne/capture/encoder_hidden.npy; do
      [ -e "$f" ] || echo "$f"
    done')
  if [ -n "$missing" ]; then
    note "staging E2E inputs from $JW16_HOST (missing on jwm1: $(echo $missing | tr '\n' ' '))"
    ssh -o BatchMode=yes "$JWM1_HOST" "mkdir -p $ROOT_DEST/e2e-inputs"
    for f in /var/tmp/ParakeetE2E/audio/fixture.flac \
             /var/tmp/EncoderParityAne/capture \
             /var/tmp/EncoderParityAne/encoder-source \
             /var/tmp/EncoderParityAne/capture/encoder_hidden.npy; do
      rel=${f#/var/tmp/}
      mkdir -p "$WORK/e2e/$(dirname "$rel")"
      scp -q -r -o BatchMode=yes "$JW16_HOST:$f" "$WORK/e2e/$rel" \
        || die "E2E input not found on $JW16_HOST: $f"
    done
    rsync -a -e "ssh -o BatchMode=yes" "$WORK/e2e/" "$JWM1_HOST:$ROOT_DEST/e2e-inputs/"
    E2E_ENV="E2E_AUDIO=$ROOT_DEST/e2e-inputs/ParakeetE2E/audio/fixture.flac E2E_GOLDEN=$ROOT_DEST/e2e-inputs/EncoderParityAne/capture E2E_SOURCE=$ROOT_DEST/e2e-inputs/EncoderParityAne/encoder-source E2E_ANEREF=$ROOT_DEST/e2e-inputs/EncoderParityAne/capture/encoder_hidden.npy"
  fi

  hf=$(ssh -o BatchMode=yes "$JWM1_HOST" 'ls ~/.cache/huggingface/hub 2>/dev/null | grep -ci "qwen2.5-0.5b" || true')
  [ "$hf" -ge 1 ] || note "WARN: no Qwen2.5-0.5B HF cache on $JWM1_HOST — decode legs will fail (they run HF_HUB_OFFLINE=1)"

  note "launching gate on $JWM1_HOST (detached; logs: $ROOT_DEST/v070-jwm1.status)"
  PINENV=""; [ -n "$EXPECT_WHEEL_SHA" ] && PINENV="EXPECT_WHEEL_SHA=$EXPECT_WHEEL_SHA"
  ssh -o BatchMode=yes "$JWM1_HOST" \
    "pgrep -f 'v070-jwm1/gate.sh' >/dev/null && echo GATE-ALREADY-RUNNING || (nohup env $PINENV $E2E_ENV bash $ROOT_DEST/gate.sh > $ROOT_DEST/gate-console.log 2>&1 & echo GATE-LAUNCHED)"
  [ "$MODE" = "stage" ] && { note "stage-only: gate launched; re-run with --attach to poll."; exit 0; }
fi

# --- poll -------------------------------------------------------------------
note "polling $JWM1_HOST:$ROOT_DEST/v070-jwm1.status (Ctrl-C safe; gate keeps running)"
seen=0
while :; do
  out=$(ssh -o ConnectTimeout=10 -o BatchMode=yes "$JWM1_HOST" "wc -l < $ROOT_DEST/v070-jwm1.status 2>/dev/null; cat $ROOT_DEST/v070-jwm1.status 2>/dev/null" 2>/dev/null)
  [ -n "$out" ] || { echo "[arm] (no status yet — host unreachable or gate not started; retrying)"; sleep 60; continue; }
  n=$(echo "$out" | head -1)
  body=$(echo "$out" | tail -n +2)
  if [ "$n" -gt "$seen" ]; then
    echo "$body" | tail -n $((n - seen))
    seen=$n
  fi
  if echo "$body" | grep -q "GATE GREEN"; then
    echo
    echo "== jwm1-linux arm: GATE GREEN — both-host v0.7.0 recert complete =="
    exit 0
  fi
  if echo "$body" | grep -qE "GATE RED|FATAL:"; then
    echo
    echo "== jwm1-linux arm: GATE RED — inspect $JWM1_HOST:$ROOT_DEST/ (gate-console.log, $ROOT_DEST/gate-out/ logs) =="
    exit 1
  fi
  sleep 60
done
