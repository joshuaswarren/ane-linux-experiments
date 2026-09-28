#!/bin/bash
set -euo pipefail
expected_boot=${1:?expected boot UUID required}
[[ $expected_boot =~ ^[0-9a-f-]{36}$ ]]
STAGE=/var/tmp/m2-primitive-driver
exec 9>/var/tmp/m2-fetch-capture/invocation.lock
flock -n 9
[[ $(uname -r) == 7.1.13-ARCH-polltx ]]
[[ $(cat /proc/sys/kernel/random/boot_id) == "$expected_boot" ]]
[[ ! -d /sys/module/ane_t6021_rtclient && ! -d /sys/module/ane_t6021 ]]
MODULE=$STAGE/t6021-v2/ane_t6021_rtclient.ko
printf '%s  %s\n' d4d51583e9f2af7eb923f72c95f3569c73df82209cd2cd0f3d39eac41b8ab9d9 "$MODULE" | sha256sum -c -
printf '%s  %s\n' a9c4b771294a6b115624d9480a6248d0899a1681a575e865070b87a3248427bc /lib/firmware/apple/ane/t602x_ane0_fw_selene_rc4x.macho | sha256sum -c -
[[ $(modinfo -F vermagic "$MODULE") == 7.1.13-ARCH-polltx* ]]
OUT=$STAGE/load-$expected_boot
mkdir "$OUT"
cp "$0" "$OUT/invocation.sh"
cat /proc/sys/kernel/random/boot_id > "$OUT/boot-id"
uname -a > "$OUT/uname.txt"
sha256sum /lib/firmware/apple/ane/h14conv/*.bin > "$OUT/payloads.sha256"
dmesg > "$OUT/dmesg-before.log"
sudo -n /var/tmp/m2-heap-test/read-scratch > "$OUT/scratch-before.txt"
args=(fw_diag_retention=0 fw_extra_ram=0x200000 fw_load=1 fw_diag_marker=0 fw_start=1 fw_start_stop_after=0 fw_start_table_mode=2 fw_start_rtb_mode=0 fw_alias_reserved=1 fw_start_venc_gates=0 fw_start_mpm_off=0 fw_start_state_report=0 fw_start_dart_single_stream=0 fw_start_mbox_ctrl_bit19=0 fw_start_core1_run=0 fw_start_wrapper_b80_unmask=0 fw_start_dapf=0 patch_timer_freq=0 scratch3_ack=1 legacy_only=1 legacy_query=1 legacy_load=0 legacy_seq=1 legacy_resource=0 legacy_silent=0 legacy_notify_ack=1 legacy_fast_poll=1 csne_ping=0 poll_rx=1 hello_wait_ms=1000 fw_load_stamp_base=0 boot_prevent_nap=1)
printf '%s\n' "${args[@]}" > "$OUT/parameters-requested.txt"
printf 'CONTEXT-BEGIN %s\n' "$OUT"
sudo -n timeout -k 2 50 python3 /var/tmp/m2-transition-observer.py --boot "$expected_boot" --seconds 45 > "$OUT/transitions.jsonl" 2> "$OUT/observer.err" &
observer_pid=$!
trap 'kill "$observer_pid" 2>/dev/null || true' EXIT
for attempt in {1..20}; do
    [[ -s "$OUT/transitions.jsonl" ]] && break
    sleep 0.1
done
[[ -s "$OUT/transitions.jsonl" ]]
set +e
timeout -k 5 90 sudo -n insmod "$MODULE" "${args[@]}" > "$OUT/insmod.log" 2>&1
rc=$?
wait "$observer_pid"
observer_rc=$?
trap - EXIT
printf '%s\n' "$observer_rc" > "$OUT/observer-exit"
set -e
printf '%s\n' "$rc" > "$OUT/insmod-exit"
dmesg > "$OUT/dmesg-after.log"
sudo -n /var/tmp/m2-heap-test/read-scratch > "$OUT/scratch-after.txt"
for p in /sys/module/ane_t6021_rtclient/parameters/*; do
    [[ -f $p ]] || continue
    printf '%s=' "${p##*/}"
    cat "$p"
done > "$OUT/parameters-actual.txt"
printf 'CONTEXT-END rc=%s output=%s\n' "$rc" "$OUT"
cat "$OUT/insmod.log" "$OUT/scratch-after.txt"
exit "$rc"
