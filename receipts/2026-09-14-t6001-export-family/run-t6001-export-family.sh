#!/usr/bin/env bash
# Three guarded single-shot ANE executes on jw16mbp1-linux (T6001) for the
# fixed export family, reproducing the T8103 run recorded in
# receipts/2026-09-14-1x896-export-fix.json from byte-identical artifacts.
#
#   1. 64-element add-mul control -- the device-qualified class, whose derived
#      role-to-channel map equals the positional one, so it is a no-op check
#      on the derived-channel libane.
#   2. 1x512 re-export  -- derived map src=4 dst=5, the reverse of positional.
#   3. 1x896 re-export  -- same, the program the whole chain was found on.
#
# One iteration each, 5000 ms deadline, no loop, no retry, no reboot, no module
# unload, no GPU lock, no SET write. Stops before the next program on any
# failure.
#
# Differences from the jwm1 runner, all because these are jwm1-local
# conventions rather than anything the worker creates:
#   * /run/lock/mlx-omarchy-ane/{device.lock,quarantine} does not exist here.
#     Nothing in the mlx-omarchy runtime sources creates or reads it, so it is
#     an agent convention on jwm1. Its absence is recorded, not manufactured.
#   * /sys/module/ane/version does not exist on this module build; the module
#     is identified by its sysfs binding and parameter set instead.
#   * runtime_status lives at /sys/devices/platform/soc/285c04000.ane, not
#     under a /sys/devices/platform/ane* glob.
#   * SET0 is read before and after through a PROT_READ /dev/mem map. The
#     worker's device open resumes the domain via genpd; this never writes SET.
set -uo pipefail

W=${1:-/var/tmp/T6001ExportFamily-20260914}
TOOL=/var/tmp/jw16-tiny-linear/mlx-omarchy-ane-worker
CTRL=$W/control
LIB=$W/libane-polarity.so
LIVENESS=$W/ane_worker_liveness.py
SET0=$W/set0-read.py
ANE_SYSFS=/sys/devices/platform/soc/285c04000.ane
DEADLINE=5000

say() { printf '%s\n' "$*"; }

say "host=$(hostname)"
say "started=$(date -Is)"
say "kernel=$(uname -r)"
say "machine=$(uname -m)"
say "soc_compatible=$(tr '\0' ' ' < /proc/device-tree/compatible)"
say "boot_id=$(cat /proc/sys/kernel/random/boot_id)"
say "uptime_start=$(uptime -s)"
say "device_before=$(stat -c %F /dev/accel/accel0)"
say "device_node=$(stat -c '%A %U:%G %t,%T' /dev/accel/accel0)"
say "module_before=$(lsmod | awk '/^ane /{print $1" refs="$3}')"
say "module_version_file=$( [ -r /sys/module/ane/version ] && cat /sys/module/ane/version || echo absent )"
say "module_params=$(ls /sys/module/ane/parameters | tr '\n' ',')"
say "ane_binding=$(cat $ANE_SYSFS/uevent 2>/dev/null | awk -F= '/^OF_FULLNAME/{print $2}')"
say "runtime_status_before=$(cat $ANE_SYSFS/power/runtime_status 2>/dev/null || echo unknown)"
say "runtime_control=$(cat $ANE_SYSFS/power/control 2>/dev/null || echo unknown)"
say "jwm1_lock_convention=$( [ -d /run/lock/mlx-omarchy-ane ] && echo present || echo absent_on_this_host )"
# Reported, never acquired. QmmOccupancyTileM holds this for GPU medians.
if flock -n /tmp/m1-gpu.lock -c true 2>/dev/null; then
  say "gpu_lock=free_not_acquired"
else
  say "gpu_lock=held_by_another_agent_not_acquired"
fi
say "set0_before=$(sudo -n python3 "$SET0")"

liveness_before=$(python3 "$LIVENESS")
say "worker_liveness_before=$liveness_before"
if [ "$(printf '%s' "$liveness_before" | python3 -c 'import json,sys; print(json.load(sys.stdin)["worker_count"])')" != "0" ]; then
  say "worker_clearance_before=false"; exit 1
fi
say "worker_clearance_before=true"
dmesg_before=$(dmesg | wc -l)

say ""
say "--- artifact identity ---"
sha256sum "$TOOL" "$LIB" \
  "$CTRL/bundle/manifest.json" "$CTRL/bundle/program-0.anec" "$CTRL/bundle/program-1.anec" \
  "$CTRL/a.bin" "$CTRL/b.bin" "$CTRL/y.bin" \
  "$W/staged/ane-add-fp16-1x512/manifest.json" "$W/staged/ane-add-fp16-1x512/model.anec" \
  "$W/staged/ane-add-fp16-1x896/manifest.json" "$W/staged/ane-add-fp16-1x896/model.anec" \
  "$W/t1_1x512.bin" "$W/t2_1x512_expected.bin" \
  "$W/t1_1x896.bin" "$W/t2_1x896_expected.bin"
# ane_bind_init and the whole derivation are `static inline` in ane_bind.h, so
# they are NOT exported symbols and no nm check can distinguish this build
# from a positional one. The library is pinned by the digests of the sources it
# was compiled from, and the derived binding is proven by the value check: with
# a positional-binding libane the exported family completes and returns a wrong
# element 0 rather than an error (jwm1, 2026-09-14).
sha256sum "$W/libane-src/libane/ane.c" "$W/libane-src/libane/ane_bind.h" \
          "$W/libane-src/libane/ane.h"

say ""
say "--- submitted headers ---"
python3 - "$CTRL/bundle/program-0.anec" "$W/staged/ane-add-fp16-1x512/model.anec" \
         "$W/staged/ane-add-fp16-1x896/model.anec" <<'PY'
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
  echo "ANE-T6001-EXPORTFAMILY $label BEGIN $(date -Is)" | sudo -n tee /dev/kmsg >/dev/null
  local t0 t1 status
  t0=$(date +%s%N)
  timeout --signal=TERM --kill-after=5s 25s \
    "$TOOL" --bundle "$bundle" --libane "$LIB" \
    --deadline-ms "$DEADLINE" --iterations 1 "$@" 2>&1
  status=$?
  t1=$(date +%s%N)
  echo "ANE-T6001-EXPORTFAMILY $label END status=$status $(date -Is)" | sudo -n tee /dev/kmsg >/dev/null
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
  run_once reexport-1x512 "$W/staged/ane-add-fp16-1x512" \
    --input t1="$W/t1_1x512.bin" --expect t2="$W/t2_1x512_expected.bin"
  fix512_status=$?
  if [ "$fix512_status" -ne 0 ]; then
    say "1x512 failed; refusing to submit 1x896"
  else
    run_once reexport-1x896 "$W/staged/ane-add-fp16-1x896" \
      --input t1="$W/t1_1x896.bin" --expect t2="$W/t2_1x896_expected.bin"
    fix896_status=$?
  fi
fi

say ""
say "--- post-state ---"
say "worker_liveness_after=$(python3 "$LIVENESS")"
say "set0_after=$(sudo -n python3 "$SET0")"
say "device_after=$(stat -c %F /dev/accel/accel0)"
say "module_after=$(lsmod | awk '/^ane /{print $1" refs="$3}')"
say "runtime_status_after=$(cat $ANE_SYSFS/power/runtime_status 2>/dev/null || echo unknown)"
say "boot_id_after=$(cat /proc/sys/kernel/random/boot_id)"
say "uptime_start_after=$(uptime -s)"
say "errno110_this_boot=$(dmesg | grep -ciE 'tm execution failed|errno[ =-]*110')"
if flock -n /tmp/m1-gpu.lock -c true 2>/dev/null; then
  say "gpu_lock_after=free_never_acquired"
else
  say "gpu_lock_after=held_by_another_agent_never_acquired"
fi
say "--- dmesg tail since marker ---"
dmesg | tail -n "$(( $(dmesg | wc -l) - dmesg_before + 2 ))"
say "finished=$(date -Is)"
say "control_exit=$control_status reexport_512_exit=$fix512_status reexport_896_exit=$fix896_status"
