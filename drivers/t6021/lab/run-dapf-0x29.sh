#!/bin/bash
# Runs ON the M2. Fresh boot only. Load with DAPF, PS read, 0x29, PS read. No TM/engine reads.
set -u
cd /var/tmp/dart-walk
printf 'obj-m := dart_psonly.o\nKDIR := /lib/modules/%s/build\nall:\n\t$(MAKE) -C $(KDIR) M=$(PWD) modules\n' "$(uname -r)" > Makefile
make 2>&1 | grep -E 'error' || true
echo BOOT=$(cat /proc/sys/kernel/random/boot_id)
sudo -n insmod /var/tmp/m2-primitive-driver/t6021-v2/ane_t6021_rtclient.ko \
  fw_diag_retention=0 fw_extra_ram=0x200000 fw_load=1 fw_diag_marker=0 fw_start=1 \
  fw_start_stop_after=0 fw_start_table_mode=2 fw_start_rtb_mode=0 fw_alias_reserved=1 \
  fw_start_venc_gates=0 fw_start_mpm_off=0 fw_start_state_report=0 \
  fw_start_dart_single_stream=0 fw_start_mbox_ctrl_bit19=0 fw_start_core1_run=0 \
  fw_start_wrapper_b80_unmask=0 fw_start_dapf=1 patch_timer_freq=0 scratch3_ack=1 \
  legacy_only=1 legacy_query=1 legacy_load=0 legacy_seq=1 legacy_resource=0 \
  legacy_silent=0 legacy_notify_ack=1 legacy_fast_poll=1 csne_ping=0 poll_rx=1 \
  hello_wait_ms=1000 fw_load_stamp_base=0 boot_prevent_nap=1
echo INS=$?
sudo -n insmod dart_psonly.ko; sudo -n dmesg | grep 'pso:' | tail -1 | cut -c16-120
sudo -n rmmod dart_psonly
sudo -n dmesg -C >/dev/null 2>&1
sudo -n cp /var/tmp/dart-walk/pmu.bin /lib/firmware/apple/ane/seq/04.bin && sync
timeout 40 sudo -n python3 -c 'import os; os.write(os.open("/sys/kernel/debug/ane_t6021_seq/run", os.O_WRONLY), b"1"); print("SEND=0")'
echo RC=$?
sleep 3
sudo -n rm -f /lib/firmware/apple/ane/seq/04.bin
sudo -n insmod dart_psonly.ko; sudo -n dmesg | grep -E 'pso:|SEQ 4|NO PTE|ASSERT' | cut -c16-140 | tail -5
