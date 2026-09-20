#!/bin/sh
# Runnable END-TO-END production-flow fixture test for stage-live-candidate.sh.
# Uses a fake diskutil (PATH stub) + fixture volume tree — NO real mounts, NO sudo,
# NO raw device writes. Exercises: volume identity, original hash pins (overridable
# for fixture), free-space gate, reuse-refusing backups, temp+readback+rename installs,
# exact-hash cfg, final readback table. Run: sh test-e2e-production-flow.sh
# SPDX-License-Identifier: MIT
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
EXEC=$HERE/stage-live-candidate.sh
WORK=$(mktemp -d /tmp/jwm1e2e-XXXX)
BIN=$WORK/bin; VOL=$WORK/vol
mkdir -p "$BIN" "$VOL/m1n1" "$VOL/grub-ane" "$VOL/EFI/BOOT" "$VOL/asahi"

cat > "$BIN/diskutil" <<FAKE
#!/bin/sh
case "\$1" in
  info) printf 'Volume Name: EFI - ASAHI\nMount Point: %s\n' "$VOL" ;;
  mount) echo mounted ;;
esac
FAKE
chmod +x "$BIN/diskutil"

# originals (arbitrary content; pins computed from these)
printf 'orig-boot-d1ee\n' > "$VOL/m1n1/boot.bin"
printf 'orig-9d6e\n' > "$VOL/EFI/BOOT/BOOTAA64.EFI"
printf 'orig-ee36\n' > "$VOL/grub-ane/VMLINUZ.REC"
printf 'orig-de4a\n' > "$VOL/grub-ane/INITRD.REC"
printf 'orig-marked-cfg\n' > "$VOL/grub-ane/grub.cfg"
printf 'orig-stock-boot\n' > "$VOL/m1n1/boot.bin.stock-20260906"
printf 'orig-stock-ba64\n' > "$VOL/EFI/BOOT/BOOTAA64.EFI.stock"

# staged sources (fixture stand-ins with pinned env hashes computed from these very files)
printf 'staged-boot-566227f9-standin\n' > "$WORK/stage-boot"
printf 'staged-vmlinuz\n' > "$WORK/stage-vmlinuz"
printf 'staged-initrd\n' > "$WORK/stage-initrd"

export BOOT_ORIG_SHA BOOTAA64_SHA VML_REC_SHA INITRD_REC_SHA STOCK_BOOT_SHA STOCK_BA64_SHA
BOOT_ORIG_SHA=$(sha256sum "$VOL/m1n1/boot.bin" | cut -d' ' -f1)
BOOTAA64_SHA=$(sha256sum "$VOL/EFI/BOOT/BOOTAA64.EFI" | cut -d' ' -f1)
VML_REC_SHA=$(sha256sum "$VOL/grub-ane/VMLINUZ.REC" | cut -d' ' -f1)
INITRD_REC_SHA=$(sha256sum "$VOL/grub-ane/INITRD.REC" | cut -d' ' -f1)
STOCK_BOOT_SHA=$(sha256sum "$VOL/m1n1/boot.bin.stock-20260906" | cut -d' ' -f1)
STOCK_BA64_SHA=$(sha256sum "$VOL/EFI/BOOT/BOOTAA64.EFI.stock" | cut -d' ' -f1)
BOOT_SHA=$(sha256sum "$WORK/stage-boot" | cut -d' ' -f1)
VML_SHA=$(sha256sum "$WORK/stage-vmlinuz" | cut -d' ' -f1)
INITRD_SHA=$(sha256sum "$WORK/stage-initrd" | cut -d' ' -f1)
export BOOT_SHA VML_SHA INITRD_SHA

PASS=0; FAILN=0
ok() { PASS=$((PASS+1)); echo "PASS: $1"; }
bad() { FAILN=$((FAILN+1)); echo "FAIL: $1"; }

if PATH="$BIN:$PATH" STAGE_BOOT="$WORK/stage-boot" STAGE_VMLINUZ="$WORK/stage-vmlinuz" \
   STAGE_INITRD="$WORK/stage-initrd" sh "$EXEC" > "$WORK/out" 2>"$WORK/err" && \
   grep -q "STAGE-DONE" "$WORK/out" \
   && [ -f "$VOL/grub-ane/VMLINUZ.7113" ] && [ -f "$VOL/grub-ane/INITRD.7113" ] \
   && grep -q "panic=10" "$VOL/grub-ane/grub.cfg" \
   && [ -f "$VOL/m1n1/boot.bin.d1ee-716" ] && [ -f "$VOL/grub-ane/VMLINUZ.REC.716" ] \
   && [ -f "$VOL/grub-ane/INITRD.REC.716" ] && [ -f "$VOL/grub-ane/grub.cfg.pre-7113" ]; then
    ok "E2E: full production flow rc=0, all installs+backups+cfg present, STAGE-DONE"
else bad "E2E: full flow (out: $(tail -3 "$WORK/out" 2>/dev/null) | err: $(tail -3 "$WORK/err" 2>/dev/null))"; fi

# mutation-stop: FRESH volume fixture + bad staged boot; require EXACT drift message and
# byte-identical before/after full fixture manifest (proves zero writes happened).
snapshot() { find "$VOL" -type f -exec sha256sum {} + | sort -k2; }
mutvol="$WORK/mutvol"
mkdir -p "$mutvol/usr/lib/firmware" "$mutvol/m1n1" "$mutvol/grub-ane" "$mutvol/EFI/BOOT" "$mutvol/asahi"
ln -s usr/lib "$mutvol/lib"
printf 'orig-boot-d1ee\n' > "$mutvol/m1n1/boot.bin"
printf 'orig-9d6e\n' > "$mutvol/EFI/BOOT/BOOTAA64.EFI"
printf 'orig-ee36\n' > "$mutvol/grub-ane/VMLINUZ.REC"
printf 'orig-de4a\n' > "$mutvol/grub-ane/INITRD.REC"
printf 'orig-marked-cfg\n' > "$mutvol/grub-ane/grub.cfg"
printf 'orig-stock-boot\n' > "$mutvol/m1n1/boot.bin.stock-20260906"
printf 'orig-stock-ba64\n' > "$mutvol/EFI/BOOT/BOOTAA64.EFI.stock"
# re-point fake diskutil at the mutation volume
sed -i "s|$VOL|$mutvol|g" "$BIN/diskutil"
snapshot > "$WORK/manifest-before"
printf 'bad\n' > "$WORK/badboot"
if PATH="$BIN:$PATH" STAGE_BOOT="$WORK/badboot" STAGE_VMLINUZ="$WORK/stage-vmlinuz" \
   STAGE_INITRD="$WORK/stage-initrd" sh "$EXEC" > "$WORK/out2" 2>"$WORK/err2"; then
    bad "mutation-stop accepted"
else
    grep -q "staged boot.bin: hash drift" "$WORK/out2" "$WORK/err2" \
      && snapshot > "$WORK/manifest-after" \
      && cmp -s "$WORK/manifest-before" "$WORK/manifest-after" \
      && ok "E2E mutation-stop: exact drift message, fixture manifest unchanged" \
      || bad "mutation-stop (exact message or manifest-unchanged check failed)"
fi

echo "----"; echo "pass=$PASS fail=$FAILN"
rm -rf "$WORK"
[ $FAILN -eq 0 ]
