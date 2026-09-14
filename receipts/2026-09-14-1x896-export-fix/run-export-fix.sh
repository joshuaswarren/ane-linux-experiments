#!/usr/bin/env bash
# Three guarded single-shot ANE executes on jwm1 for the export-path fix.
#
#   1. 64-element add-mul control  -- the device-qualified class. Its geometry
#      is unchanged by the fix (one DMA run per channel, so the padded plane
#      layout still holds), and it must stay exact.
#   2. 1x512 re-export             -- converter run over the retained macOS 26
#      object, blob payload relocated, dense geometry derived.
#   3. 1x896 re-export             -- same converter run, the program the two
#      residuals were found on.
#
# One iteration each, 5000 ms deadline, no loop, no retry, no reboot, no
# module unload, no GPU lock. Stops before 896 if the control or 512 fails.
set -uo pipefail

W=/var/tmp/ExportGeometryFix-20260914
TOOL=/var/tmp/AneWorkerValidation-c05ba1df/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
CTRL=/var/tmp/AneWorkerValidation-c05ba1df/receipts/2026-09-13-ane-worker-validation
LIB=/var/tmp/AneChannelPolarity-20260914/libane-polarity.so
LIVENESS=$W/ane_worker_liveness.py
DEADLINE=5000

say() { printf '%s\n' "$*"; }

say "host=$(hostname)"
say "started=$(date -Is)"
say "kernel=$(uname -r)"
say "boot_id=$(cat /proc/sys/kernel/random/boot_id)"
say "uptime_start=$(uptime -s)"
say "device_before=$(stat -c %F /dev/accel/accel0)"
say "module_version=$(cat /sys/module/ane/version)"
say "runtime_status=$(cat /sys/devices/platform/ane*/power/runtime_status 2>/dev/null || echo unknown)"
say "quarantine_before_bytes=$(stat -c %s /run/lock/mlx-omarchy-ane/quarantine)"
say "gpu_lock=not_acquired"
# Worker liveness by argv[0] basename plus accel-device fd holders. pgrep -af
# matches the naming shell itself and would refuse to start on a clean box.
liveness_before=$(python3 "$LIVENESS")
say "worker_liveness_before=$liveness_before"
if [ "$(printf '%s' "$liveness_before" | python3 -c 'import json,sys; print(json.load(sys.stdin)["worker_count"])')" != "0" ]; then
  say "worker_clearance_before=false"; exit 1
fi
say "worker_clearance_before=true"
if ! flock -n /run/lock/mlx-omarchy-ane/device.lock -c true; then
  say "ane_lock_free_before=false"; exit 1
fi
say "ane_lock_free_before=true"
dmesg_before=$(dmesg | wc -l)

say ""
say "--- artifact identity ---"
sha256sum "$TOOL" "$LIB" \
  "$CTRL/bundle/manifest.json" "$CTRL/bundle/program-0.anec" "$CTRL/bundle/program-1.anec" \
  "$W/ane-add-fp16-1x512/manifest.json" "$W/ane-add-fp16-1x512/model.anec" \
  "$W/ane-add-fp16-1x896/manifest.json" "$W/ane-add-fp16-1x896/model.anec" \
  "$W/t1_1x512.bin" "$W/t2_1x512_expected.bin" \
  "$W/t1_1x896.bin" "$W/t2_1x896_expected.bin"

say ""
say "--- submitted headers ---"
python3 - "$CTRL/bundle/program-0.anec" "$W/ane-add-fp16-1x512/model.anec" \
         "$W/ane-add-fp16-1x896/model.anec" <<'PY'
import pathlib, struct, sys
for path in sys.argv[1:]:
    raw = pathlib.Path(path).read_bytes()
    td, tsk, krn = (struct.unpack_from('<I', raw, 8)[0],
                    struct.unpack_from('<Q', raw, 16)[0],
                    struct.unpack_from('<Q', raw, 24)[0])
    tiles = struct.unpack_from('<32I', raw, 40)
    nchw = [struct.unpack_from('<6Q', raw, 168 + c * 48) for c in (4, 5)]
    print(f"{pathlib.Path(path).parent.name}/{pathlib.Path(path).name}: "
          f"td_size={td:#x} tsk_size={tsk:#x} krn_size={krn:#x} "
          f"tiles[4,5]={tiles[4], tiles[5]} nchw[4]={nchw[0]} nchw[5]={nchw[1]}")
PY

run_once() {
  local label=$1 bundle=$2; shift 2
  say ""
  say "=== $label ==="
  echo "ANE-EXPORTFIX $label BEGIN $(date -Is)" | sudo tee /dev/kmsg >/dev/null
  local t0 t1 status
  t0=$(date +%s%N)
  timeout --signal=TERM --kill-after=5s 25s \
    "$TOOL" --bundle "$bundle" --libane "$LIB" \
    --deadline-ms "$DEADLINE" --iterations 1 "$@" 2>&1
  status=$?
  t1=$(date +%s%N)
  echo "ANE-EXPORTFIX $label END status=$status $(date -Is)" | sudo tee /dev/kmsg >/dev/null
  say "${label}_exit=$status wall_ms=$(( (t1 - t0) / 1000000 ))"
  return $status
}

run_once control-64el "$CTRL/bundle" \
  --input a="$CTRL/a.bin" --input b="$CTRL/b.bin" --expect y="$CTRL/y.bin"
control_status=$?

fix512_status=skipped
fix896_status=skipped
if [ "$control_status" -ne 0 ]; then
  say "control failed; refusing to submit either re-export"
else
  run_once reexport-1x512 "$W/ane-add-fp16-1x512" \
    --input t1="$W/t1_1x512.bin" --expect t2="$W/t2_1x512_expected.bin"
  fix512_status=$?
  if [ "$fix512_status" -ne 0 ]; then
    say "1x512 failed; refusing to submit 1x896"
  else
    run_once reexport-1x896 "$W/ane-add-fp16-1x896" \
      --input t1="$W/t1_1x896.bin" --expect t2="$W/t2_1x896_expected.bin"
    fix896_status=$?
  fi
fi

say ""
say "--- post-state ---"
say "worker_liveness_after=$(python3 "$LIVENESS")"
flock -n /run/lock/mlx-omarchy-ane/device.lock -c 'echo ane_lock_reacquire=PASS' \
  || say "ane_lock_reacquire=FAIL"
say "quarantine_after_bytes=$(stat -c %s /run/lock/mlx-omarchy-ane/quarantine)"
say "device_after=$(stat -c %F /dev/accel/accel0)"
say "module_loaded_after=$(lsmod | awk '/^ane /{print $1" refs="$3}')"
say "runtime_status_after=$(cat /sys/devices/platform/ane*/power/runtime_status 2>/dev/null || echo unknown)"
say "boot_id_after=$(cat /proc/sys/kernel/random/boot_id)"
say "uptime_start_after=$(uptime -s)"
say "errno110_this_boot=$(dmesg | grep -ciE 'tm execution failed|errno[ =-]*110')"
say "--- dmesg tail since marker ---"
dmesg | tail -n "$(( $(dmesg | wc -l) - dmesg_before + 2 ))"
say "finished=$(date -Is)"
say "control_exit=$control_status reexport_512_exit=$fix512_status reexport_896_exit=$fix896_status"
