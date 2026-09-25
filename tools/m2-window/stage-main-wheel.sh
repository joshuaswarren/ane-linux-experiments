#!/usr/bin/env bash
# Stage the mlx-omarchy main wheel for the M2 window kit, off-box.
#
# Builds the cp314 linux_aarch64 wheel in the macstudio ALARM chroot
# (docker image dg-alarm-py314:sep23 — the fleet's standing aarch64 build
# path; no laptop ever compiles). Main-tip wheels require the pinned
# parakeet-encoder-whole bundle: build-wheel.sh refuses to produce a wheel
# that would silently fall back to the split-island path. The durable bundle
# copy lives at macstudio:~/src/ane-artifacts/encoder-whole/bundle/
# (manifest 08769793…, program-0.anec 13c74423…). This script verifies both
# shas against the runtime pin carried by the ref BEFORE the build, and
# build-wheel.sh re-verifies inside the chroot — a wrong bundle cannot ship.
#
# usage: stage-main-wheel.sh [--ref <mlx-omarchy git ref, default origin/main>]
#
# Outputs into tools/m2-window/stage/:
#   mlx_omarchy-<ver>-cp314-cp314-linux_aarch64.whl + SHA256SUMS
#   build-<commit>.log
#   mlx-lm-patches/{apply-mlx-lm-patches.sh,patches/*}  (from origin/main;
#                 patches target the venv's mlx-lm and are self-guarding)
set -euo pipefail

M2K_DIR="$(cd "$(dirname "$0")" && pwd)"
STAGE_DIR="$M2K_DIR/stage"
MLX_LOCAL="${MLX_OMARCHY_LOCAL_CHECKOUT:-$HOME/src/mlx-omarchy}"
MACSTUDIO="${M2K_MACSTUDIO:-macstudio}"
REMOTE_STAGE="m2-wheel-stage"
REF="origin/main"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref) REF="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[[ -d "$MLX_LOCAL/.git" ]] || { echo "mlx-omarchy checkout not found at $MLX_LOCAL" >&2; exit 2; }
COMMIT="$(git -C "$MLX_LOCAL" rev-parse --verify --short=7 "$REF")"
COMMIT_FULL="$(git -C "$MLX_LOCAL" rev-parse --verify "$REF")"
echo "== staging mlx-omarchy $REF @ $COMMIT =="
mkdir -p "$STAGE_DIR" /tmp/m2k
git -C "$MLX_LOCAL" archive --format=tar.gz -o /tmp/m2k/src.tgz "$COMMIT_FULL"

echo "== verifying bundle pin on $MACSTUDIO =="
read -r PIN_MANIFEST PIN_PROGRAM < <(git -C "$MLX_LOCAL" show "$COMMIT_FULL":overlay/tools/mlx-omarchy-parakeet/share/mlx-omarchy/parakeet-1/parakeet-runtime-pin.json \
  | python3 -c "import json,sys
b = json.load(sys.stdin)['assets']['bundles']['parakeet-encoder-whole']
print(b['manifest.json'], b['program-0.anec'])")
ssh "$MACSTUDIO" "shasum -a 256 \$HOME/src/ane-artifacts/encoder-whole/bundle/manifest.json \$HOME/src/ane-artifacts/encoder-whole/bundle/program-0.anec" \
  | while read -r sum path; do
      case "$path" in
        *manifest.json) [[ "$sum" == "$PIN_MANIFEST" ]] || { echo "FATAL manifest sha $sum != pin $PIN_MANIFEST" >&2; exit 1; }; echo "manifest OK $sum" ;;
        *program-0.anec) [[ "$sum" == "$PIN_PROGRAM" ]] || { echo "FATAL program sha $sum != pin $PIN_PROGRAM" >&2; exit 1; }; echo "program OK $sum" ;;
      esac
    done

echo "== exporting mlx-lm patch kit (from origin/main; patches target the venv's"
echo "   mlx-lm, are self-guarding, and stay compatible across wheel lineages) =="
PATCH_REF="$(git -C "$MLX_LOCAL" rev-parse --verify origin/main)"
rm -rf "$STAGE_DIR/mlx-lm-patches"
mkdir -p "$STAGE_DIR/mlx-lm-patches/patches"
git -C "$MLX_LOCAL" show "$PATCH_REF":scripts/apply-mlx-lm-patches.sh > "$STAGE_DIR/mlx-lm-patches/apply-mlx-lm-patches.sh"
chmod +x "$STAGE_DIR/mlx-lm-patches/apply-mlx-lm-patches.sh"
# the exact set scripts/apply-mlx-lm-patches.sh applies by default; the
# greedy-prune patch self-guards inert on wheels lacking the kernel
for p in mlx-lm-gated-delta-fast-route.patch mlx-lm-gated-delta-raw.patch mlx-lm-greedy-prune.patch; do
  git -C "$MLX_LOCAL" show "$PATCH_REF":patches/$p > "$STAGE_DIR/mlx-lm-patches/patches/$p"
done
echo "patch kit: $(ls "$STAGE_DIR/mlx-lm-patches/patches/" | tr '\n' ' ')"

echo "== shipping source to $MACSTUDIO =="
ssh "$MACSTUDIO" "mkdir -p \$HOME/$REMOTE_STAGE/$COMMIT"
scp -q /tmp/m2k/src.tgz "$MACSTUDIO:$REMOTE_STAGE/$COMMIT/src.tgz"
scp -q "$M2K_DIR/chroot-build.sh" "$MACSTUDIO:$REMOTE_STAGE/$COMMIT/chroot-build.sh"

echo "== chroot build (dg-alarm-py314:sep23) =="
ssh "$MACSTUDIO" "bash \$HOME/$REMOTE_STAGE/$COMMIT/chroot-build.sh $COMMIT" 2>&1 | tee "$STAGE_DIR/build-$COMMIT.log"

echo "== fetching artifacts =="
scp -q "$MACSTUDIO:$REMOTE_STAGE/$COMMIT"/*.whl "$STAGE_DIR/"
scp -q "$MACSTUDIO:$REMOTE_STAGE/$COMMIT/build.log" "$STAGE_DIR/build-$COMMIT.log"
( cd "$STAGE_DIR" && shasum -a 256 mlx_omarchy-*.whl > SHA256SUMS && cat SHA256SUMS )
echo "STAGED: $STAGE_DIR"
