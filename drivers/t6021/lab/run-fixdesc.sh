#!/bin/bash
# Runs ON the M2, fresh boot. faseq7/02.bin (260 B descriptor), DAPF load, bare call, guarded reads.
cd /var/tmp/dart-walk || exit 1
echo BOOT="$(cat /proc/sys/kernel/random/boot_id)"
sudo -n cp /var/tmp/faseq7/02.bin /lib/firmware/apple/ane/seq/02.bin && sync
sudo -n insmod /var/tmp/m2-primitive-driver/t6021-v2/ane_t6021_rtclient.ko \
  fw_diag_retention=0 fw_extra_ram=0x200000 fw_load=1 fw_diag_marker=0 fw_start=1 \
  fw_start_stop_after=0 fw_start_table_mode=2 fw_start_rtb_mode=0 fw_alias_reserved=1 \
  fw_start_venc_gates=0 fw_start_mpm_off=0 fw_start_state_report=0 \
  fw_start_dart_single_stream=0 fw_start_mbox_ctrl_bit19=0 fw_start_core1_run=0 \
  fw_start_wrapper_b80_unmask=0 fw_start_dapf=${DAPF:-1} patch_timer_freq=0 scratch3_ack=1 \
  legacy_only=1 legacy_query=1 legacy_load=0 legacy_seq=1 legacy_resource=0 \
  legacy_silent=0 legacy_notify_ack=1 legacy_fast_poll=1 csne_ping=0 poll_rx=1 \
  hello_wait_ms=1000 fw_load_stamp_base=0 boot_prevent_nap=1
echo INS=$?
sudo -n dmesg | grep -E "SEQ [0-3] result|SEQ done" | cut -c16-90
sudo -n dmesg -C >/dev/null 2>&1
sudo -n cp /var/tmp/seq-saved/04.bin /lib/firmware/apple/ane/seq/04.bin && sync
timeout 40 sudo -n python3 /var/tmp/dart-walk/run_step.py
sleep 6
sudo -n rm -f /lib/firmware/apple/ane/seq/04.bin
sudo -n dmesg | grep -E "SEQ 4 (send|result)|NO PTE|ASSERT|translation" | cut -c16-120
sed 's/pso4/psF/g' dart_pso4.c > dart_psF.c
printf 'obj-m := dart_psF.o\nKDIR := /lib/modules/%s/build\nall:\n\t$(MAKE) -C $(KDIR) M=$(PWD) modules\n' "$(uname -r)" > Makefile
make 2>&1 | grep -E 'error'
sudo -n insmod dart_psF.ko
PS=$(sudo -n dmesg | grep 'psF:' | tail -1)
echo "$PS" | cut -c16-120
if echo "$PS" | grep -q "00=0x3ff 08=0x3ff 10=0x3ff 18=0x3ff 20=0x3ff 28=0x3ff 30=0x3ff"; then
  sudo -n dmesg -C >/dev/null 2>&1
  sudo -n insmod dart_tqst.ko
  sudo -n dmesg | grep 'tqst:' | cut -c16-110
  sudo -n insmod dart_arm2.ko tag=post 2>/dev/null
  sudo -n dmesg | grep 'army post' | cut -c16-140
else
  echo "PS not all on: TM not read"
fi
sudo -n python3 /var/tmp/dart-walk/collect.py --check-y --step 04 2>&1 | tail -12
