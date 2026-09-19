#!/bin/bash
# v0.7.0 both-host arm runner — stages the t6001-test-host-proven gate kit onto
# m1-test-host-linux and runs scripts/v070-m1-test-host-gate.sh there. One command, safe to
# re-run; the gate keeps running on m1-test-host-linux if this script is interrupted
# (--attach re-polls). Run from any fleet orchestration box AFTER m1-test-host-linux
# returns (Asahi 1TR repair complete).
#
#   scripts/v070-m1-test-host-arm.sh            # wait for host, stage, run, poll
#   scripts/v070-m1-test-host-arm.sh --wait 3600
#   scripts/v070-m1-test-host-arm.sh --stage-only
#   scripts/v070-m1-test-host-arm.sh --attach   # re-poll a running gate
#
# Gate table enforced on m1-test-host-linux (pins identical to t6001-test-host V070Recert):
#   packaging 3x transcript-exact db501a8c...; E2E serve/launch/AC/ACO pins
#   (38c73261 / ef6afd13); decode legs 7fd25a86 / 7da83f06; primitive 103/103,
#   runtime 41/41, capsim 6/6, tape 12/12; wheel sha 2def345c provenance;
#   venv guard, hwcap, KATs.
set -u
m1-test-host_HOST="${m1-test-host_HOST:-m1-test-host}"          # ssh alias / [redacted-ip]
t6001-test-host_HOST="${t6001-test-host_HOST:-t6001-test-host}"       # wheel + kit source (gate ran green here)
MLX_REPO="${MLX_REPO:-$HOME/src/mlx-omarchy}"
# Wheel provenance pin: the PUBLISHED v0.7.1 aarch64 wheel (50eeb290 build,
# shipped 2026-09-19; x86_64 is 11747f46...). Override via env only if
# a future lane re-stages and re-publishes.
EXPECT_WHEEL_SHA="${EXPECT_WHEEL_SHA:-e536056bcb23d8d93121edc662cebb0c4b14b8670233c8f018ad54150b9b8d49}"
ROOT_DEST=/var/tmp/v070-m1-test-host
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
  until ssh_ok "$m1-test-host_HOST"; do
    [ "$WAIT" -gt 0 ] || die "m1-test-host-linux ($m1-test-host_HOST) not reachable. The Asahi 1TR repair has not brought Linux back yet. Run with --wait N to poll."
    WAIT=$((WAIT - 15)); sleep 15
  done
  [ "$(ssh -o BatchMode=yes "$m1-test-host_HOST" uname -m)" = "aarch64" ] || die "$m1-test-host_HOST is not aarch64 — wrong host?"

  WORK=$(mktemp -d /tmp/v070-m1-test-host-kit.XXXXXX)
  trap 'rm -rf "$WORK"' EXIT
  mkdir -p "$WORK/kit" "$WORK/oproj" "$WORK/wheel"

  note "collecting kit from $t6001-test-host_HOST (wheel, oproj islands, probes, e2e harness)"
  WHLNAME=$(ssh -o BatchMode=yes "$t6001-test-host_HOST" \
    'ls /var/tmp/v070-t6001-test-host/dist/mlx_omarchy-0.32.3.dev*+*-cp314-cp314-linux_aarch64.whl 2>/dev/null | head -1')
  [ -n "$WHLNAME" ] || die "candidate wheel not found on $t6001-test-host_HOST (/var/tmp/v070-t6001-test-host/dist/)"
  scp -q -o BatchMode=yes "$t6001-test-host_HOST:$WHLNAME" "$WORK/wheel/" \
    || die "wheel copy failed from $t6001-test-host_HOST:$WHLNAME"
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
  scp -q -o BatchMode=yes "$t6001-test-host_HOST:/var/tmp/v067-gate/hwcap_probe.c" "$t6001-test-host_HOST:/var/tmp/v067-gate/kat_probe.cpp" "$WORK/kit/" \
    || die "hwcap/kat probe sources not found on $t6001-test-host_HOST (/var/tmp/v067-gate/)"
  scp -q -o BatchMode=yes "$t6001-test-host_HOST:/var/tmp/ParakeetE2Et6001-test-host/fused_e2e.py" "$WORK/kit/" \
    || die "fused_e2e.py not found on $t6001-test-host_HOST (/var/tmp/ParakeetE2Et6001-test-host/)"
  scp -q -o BatchMode=yes "$t6001-test-host_HOST:/var/tmp/v063-t6001-test-host/scripts/venv-identity-guard.py" \
    "$t6001-test-host_HOST:/var/tmp/v063-t6001-test-host/scripts/certified-libmlx-identities.txt" "$WORK/kit/" \
    || die "venv-identity-guard.py / certified-libmlx-identities.txt not found on $t6001-test-host_HOST (/var/tmp/v063-t6001-test-host/scripts/)"
  scp -q -o BatchMode=yes "$t6001-test-host_HOST:/var/tmp/t6001-test-host-encoder-islands/bundles/island-oproj-L*" "$WORK/oproj/" \
    || die "island-oproj-L* bundles not found on $t6001-test-host_HOST (/var/tmp/t6001-test-host-encoder-islands/bundles/)"
  [ -d "$WORK/oproj/island-oproj-L00" ] || die "oproj staging incomplete (no island-oproj-L00)"

  note "collecting repo-side gate pieces from $MLX_REPO"
  for f in receipts/2026-09-16-parakeet-wheel-packaging/gate-m1-test-host.sh \
           scripts/bench_matrix.py; do
    [ -f "$MLX_REPO/$f" ] || die "missing in $MLX_REPO: $f"
  done
  cp "$MLX_REPO/receipts/2026-09-16-parakeet-wheel-packaging/gate-m1-test-host.sh" "$WORK/kit/"
  cp "$MLX_REPO/scripts/bench_matrix.py" "$WORK/kit/"
  cp "$(dirname "$0")/v070-m1-test-host-gate.sh" "$WORK/gate.sh"

  note "pushing kit to $m1-test-host_HOST:$ROOT_DEST"
  ssh -o BatchMode=yes "$m1-test-host_HOST" "mkdir -p $ROOT_DEST"
  rsync -a -e "ssh -o BatchMode=yes" "$WORK/wheel" "$WORK/kit" "$WORK/oproj" "$WORK/gate.sh" "$m1-test-host_HOST:$ROOT_DEST/"
  ssh -o BatchMode=yes "$m1-test-host_HOST" "test -f $ROOT_DEST/gate.sh && test -d $ROOT_DEST/oproj && ls $ROOT_DEST/oproj/island-oproj-L* >/dev/null && sha256sum $ROOT_DEST/wheel/*.whl" | grep -q "$got" \
    || die "staged kit verification on $m1-test-host_HOST failed"

  # E2E inputs: use m1-test-host-local copies when present (2026-09-16 both-host E2E
  # staged them there), else push from t6001-test-host and pin the env overrides.
  E2E_ENV=""
  missing=$(ssh -o BatchMode=yes "$m1-test-host_HOST" '
    for f in /var/tmp/ParakeetE2E/audio/fixture.flac /var/tmp/EncoderParityAne/capture \
             /var/tmp/EncoderParityAne/encoder-source /var/tmp/EncoderParityAne/capture/encoder_hidden.npy; do
      [ -e "$f" ] || echo "$f"
    done')
  if [ -n "$missing" ]; then
    note "staging E2E inputs from $t6001-test-host_HOST (missing on m1-test-host: $(echo $missing | tr '\n' ' '))"
    ssh -o BatchMode=yes "$m1-test-host_HOST" "mkdir -p $ROOT_DEST/e2e-inputs"
    for f in /var/tmp/ParakeetE2E/audio/fixture.flac \
             /var/tmp/EncoderParityAne/capture \
             /var/tmp/EncoderParityAne/encoder-source \
             /var/tmp/EncoderParityAne/capture/encoder_hidden.npy; do
      rel=${f#/var/tmp/}
      mkdir -p "$WORK/e2e/$(dirname "$rel")"
      scp -q -r -o BatchMode=yes "$t6001-test-host_HOST:$f" "$WORK/e2e/$rel" \
        || die "E2E input not found on $t6001-test-host_HOST: $f"
    done
    rsync -a -e "ssh -o BatchMode=yes" "$WORK/e2e/" "$m1-test-host_HOST:$ROOT_DEST/e2e-inputs/"
    E2E_ENV="E2E_AUDIO=$ROOT_DEST/e2e-inputs/ParakeetE2E/audio/fixture.flac E2E_GOLDEN=$ROOT_DEST/e2e-inputs/EncoderParityAne/capture E2E_SOURCE=$ROOT_DEST/e2e-inputs/EncoderParityAne/encoder-source E2E_ANEREF=$ROOT_DEST/e2e-inputs/EncoderParityAne/capture/encoder_hidden.npy"
  fi

  hf=$(ssh -o BatchMode=yes "$m1-test-host_HOST" 'ls ~/.cache/huggingface/hub 2>/dev/null | grep -ci "qwen2.5-0.5b" || true')
  [ "$hf" -ge 1 ] || note "WARN: no Qwen2.5-0.5B HF cache on $m1-test-host_HOST — decode legs will fail (they run HF_HUB_OFFLINE=1)"

  note "launching gate on $m1-test-host_HOST (detached; logs: $ROOT_DEST/v070-m1-test-host.status)"
  PINENV=""; [ -n "$EXPECT_WHEEL_SHA" ] && PINENV="EXPECT_WHEEL_SHA=$EXPECT_WHEEL_SHA"
  ssh -o BatchMode=yes "$m1-test-host_HOST" \
    "pgrep -f 'v070-m1-test-host/gate.sh' >/dev/null && echo GATE-ALREADY-RUNNING || (nohup env $PINENV $E2E_ENV bash $ROOT_DEST/gate.sh > $ROOT_DEST/gate-console.log 2>&1 & echo GATE-LAUNCHED)"
  [ "$MODE" = "stage" ] && { note "stage-only: gate launched; re-run with --attach to poll."; exit 0; }
fi

# --- poll -------------------------------------------------------------------
note "polling $m1-test-host_HOST:$ROOT_DEST/v070-m1-test-host.status (Ctrl-C safe; gate keeps running)"
seen=0
while :; do
  out=$(ssh -o ConnectTimeout=10 -o BatchMode=yes "$m1-test-host_HOST" "wc -l < $ROOT_DEST/v070-m1-test-host.status 2>/dev/null; cat $ROOT_DEST/v070-m1-test-host.status 2>/dev/null" 2>/dev/null)
  [ -n "$out" ] || { echo "[arm] (no status yet — host unreachable or gate not started; retrying)"; sleep 60; continue; }
  n=$(echo "$out" | head -1)
  body=$(echo "$out" | tail -n +2)
  if [ "$n" -gt "$seen" ]; then
    echo "$body" | tail -n $((n - seen))
    seen=$n
  fi
  if echo "$body" | grep -q "GATE GREEN"; then
    echo
    echo "== m1-test-host-linux arm: GATE GREEN — both-host v0.7.0 recert complete =="
    exit 0
  fi
  if echo "$body" | grep -qE "GATE RED|FATAL:"; then
    echo
    echo "== m1-test-host-linux arm: GATE RED — inspect $m1-test-host_HOST:$ROOT_DEST/ (gate-console.log, $ROOT_DEST/gate-out/ logs) =="
    exit 1
  fi
  sleep 60
done
