#!/bin/bash
# Runs ON the M2 on boot 8f468602 (steps 00-04 done). Runs steps 05..07 one at a time, verifies each.
cd /var/tmp/dart-walk || exit 1
echo BOOT="$(cat /proc/sys/kernel/random/boot_id)"
for S in 05 06 07; do
  sudo -n dmesg -C >/dev/null 2>&1
  sudo -n cp "/var/tmp/faseq8/$S.bin" "/lib/firmware/apple/ane/seq/$S.bin" && sync
  timeout 40 sudo -n python3 /var/tmp/dart-walk/run_step.py
  sleep 5
  sudo -n rm -f "/lib/firmware/apple/ane/seq/$S.bin"
  sudo -n dmesg | grep -E "SEQ ${S#0} (send|result)|NO PTE|ASSERT|translation" | cut -c16-110
  N="ps$S"
  sed "s/pso4/$N/g" dart_pso4.c > "dart_$N.c"
  printf 'obj-m := dart_%s.o\nKDIR := /lib/modules/%s/build\nall:\n\t$(MAKE) -C $(KDIR) M=$(PWD) modules\n' "$N" "$(uname -r)" > Makefile
  make 2>&1 | grep -E 'error'
  sudo -n insmod "dart_$N.ko"
  PS=$(sudo -n dmesg | grep "$N:" | tail -1)
  echo "$PS" | cut -c16-120
  if echo "$PS" | grep -q "00=0x3ff 08=0x3ff 10=0x3ff 18=0x3ff 20=0x3ff 28=0x3ff 30=0x3ff"; then
    sed "s/tqst/tq$S/g" dart_tqst.c > "dart_tq$S.c"
    printf 'obj-m := dart_tq%s.o\nKDIR := /lib/modules/%s/build\nall:\n\t$(MAKE) -C $(KDIR) M=$(PWD) modules\n' "$S" "$(uname -r)" > Makefile
    make 2>&1 | grep -E 'error'
    sudo -n insmod "dart_tq$S.ko"
    sudo -n dmesg | grep "tq$S:" | cut -c16-110
  else
    echo "PS not all on: TM not read"
  fi
  sed "s/s04b/s${S}b/g;s/step-04/step-$S/g" verify_y.py > "verify_$S.py"
  sudo -n python3 "verify_$S.py" | grep -E "bit-exact|sentinel|VERDICT|y\[:6\]|expect"
done
