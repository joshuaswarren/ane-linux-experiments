#!/usr/bin/env bash
# ONE guarded execute of the td_size-corrected 1x896 bundle. No loop, no retry,
# no reboot, no module unload, no GPU lock. Stops on the first failure.
set -uo pipefail
ROOT=/var/tmp/Jwm1AneAccelSmoke2-a9f14124
WORK=/var/tmp/AnePlanJwm1-shape-aware
BUNDLE=/var/tmp/Ane1x896TdFix-20260914/ane-add-fp16-1x896
HARNESS="$WORK/ane-shape-aware-smoke"
LOG=/var/tmp/Ane1x896TdFix-20260914/execute-1x896-tdfix.log
DIAGNOSTIC=/tmp/AnePlanJwm1-shape-aware.diagnostic
MARK=ANE1X896-TDFIX

printf 'host='; hostname
printf 'mlx_source_commit='; git -C "$ROOT" rev-parse HEAD
printf 'boot_id='; cat /proc/sys/kernel/random/boot_id
printf 'uptime_start='; uptime -s
printf 'started='; date -Is
printf 'device_before='; stat -c %F /dev/accel/accel0
printf 'module_version='; cat /sys/module/ane/version
printf 'netconsole_loaded='; lsmod | awk '/^netconsole/{print "yes"}'
printf 'quarantine_before_bytes='; stat -c %s /run/lock/mlx-omarchy-ane/quarantine
printf 'gpu_lock=not_acquired\n'
if pgrep -af '^.*/mlx-omarchy-ane-worker([[:space:]]|$)'; then
  echo 'worker_clearance_before=false'; exit 1
fi
echo 'worker_clearance_before=true'
if ! flock -n /run/lock/mlx-omarchy-ane/device.lock -c true; then
  echo 'ane_lock_free_before=false'; exit 1
fi
echo 'ane_lock_free_before=true'

sha256sum "$BUNDLE/manifest.json" "$BUNDLE/model.anec" "$BUNDLE/weights.bin" \
          "$HARNESS" "$WORK/ane-shape-aware-smoke.cpp"
python3 -c 'import pathlib,struct,sys
data=pathlib.Path(sys.argv[1]).read_bytes()
values=struct.unpack("<896H",data[128:])
assert len(data)==1920 and set(values)=={0x3400}
print("weights_exact_fp16=PASS elements=896 bits=0x3400")' "$BUNDLE/weights.bin"
python3 -c 'import pathlib,struct,sys
raw=pathlib.Path(sys.argv[1]).read_bytes()
td,tsk=struct.unpack_from("<I",raw,8)[0],struct.unpack_from("<Q",raw,16)[0]
print(f"submitted_td_size={td:#x} submitted_tsk_size={tsk:#x} equal={td==tsk}")
assert td==tsk==0x1f8' "$BUNDLE/model.anec"

rm -f "$DIAGNOSTIC" "$LOG"
echo "$MARK-BEGIN $(date -Is)" | sudo tee /dev/kmsg >/dev/null
dmesg_before=$(dmesg | wc -l)
timeout --signal=TERM --kill-after=5s 25s "$HARNESS" "$BUNDLE" 0x3c00 0x3d00 5000 >"$LOG" 2>&1
status=$?
echo "$MARK-END status=$status $(date -Is)" | sudo tee /dev/kmsg >/dev/null
cat "$LOG"
printf 'execute_exit=%s\n' "$status"

if pgrep -af '^.*/mlx-omarchy-ane-worker([[:space:]]|$)'; then
  echo 'worker_clearance_after=false'; workers=1
else
  echo 'worker_clearance_after=true'; workers=0
fi
if flock -n /run/lock/mlx-omarchy-ane/device.lock -c 'echo ane_lock_reacquire=PASS'; then
  lock=0
else
  echo 'ane_lock_reacquire=FAIL'; lock=1
fi
printf 'quarantine_after_bytes='; stat -c %s /run/lock/mlx-omarchy-ane/quarantine
printf 'quarantine_after_text='; cat /run/lock/mlx-omarchy-ane/quarantine 2>/dev/null; echo
printf 'device_after='; stat -c %F /dev/accel/accel0
printf 'module_loaded_after='; lsmod | awk '/^ane /{print $1" refs="$3}'
if test -e "$DIAGNOSTIC"; then printf 'diagnostic='; cat "$DIAGNOSTIC"; echo
else echo 'diagnostic_absent=true'; fi
echo '--- dmesg tail since marker ---'
dmesg | tail -n "$(( $(dmesg | wc -l) - dmesg_before + 2 ))"
printf 'finished='; date -Is
printf 'uptime_after='; uptime -s
printf 'overall_exit=%s\n' "$status"
