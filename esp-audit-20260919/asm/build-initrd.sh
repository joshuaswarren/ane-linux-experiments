#!/bin/bash
# Reproducible builder for initrd-7113-clean-modstage.img (jwm1 recovery initrd).
# Rebuilds the artifact from content-addressed inputs. Builds to a temp file,
# verifies segment integrity, then atomically renames into place. A previous
# artifact with a different hash is preserved as <OUT>.superseded-<sha>.
# Byte-reproducible: python newc writers fix inode/mtime/nlink; gzip has no
# timestamp; walk order is LC_ALL=C sorted.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
AUDIT=$(cd "$HERE/.." && pwd)
WORK="${JWM1_ASM_WORK:-$AUDIT/.work/assemble}"

BASE_IMG="$WORK/base.img"
MANIFEST="$WORK/modules.manifest"
SCRIPT="$AUDIT/jwm1-modstage.sh"
HOOK="$AUDIT/hook-jwm1-modstage"
FWSNIPPET="$AUDIT/firmware-plan/asahi-firmware-late.sh"
FWCPIO="$AUDIT/content-store/b1e15f13af97732732fe19a4b699551fc29dfac5de53b8400814d1422963b2be/firmware.cpio"
OUT="$AUDIT/initrd-7113-clean-modstage.img"
TEMP="$WORK/initrd-build.tmp.img"
ROOT="$WORK/root2"

for f in "$BASE_IMG" "$MANIFEST" "$SCRIPT" "$HOOK" "$FWSNIPPET" "$FWCPIO" \
         "$WORK/base-extract/early.cpio" "$FWCPIO"; do
    [ -f "$f" ] || { echo "input missing: $f" >&2; exit 1; }
done
[ -d "$WORK/usr/lib/modules/7.1.13-3-1-ARCH" ] || { echo "module tree pull missing" >&2; exit 1; }

# 1. early segment: first 10240 bytes of the canonical base (verbatim).
dd if="$BASE_IMG" of="$WORK/base-extract/early.cpio" bs=10240 count=1 2>/dev/null

# 2. root tree staging (builder owns and recreates root2).
python3 "$HERE/build-root.py"

# 3. main segment: native GNU cpio --reproducible (zeroes inode numbers;
# mtime is normalized separately by build-root.py) + gzip -n (no timestamp).
# pipefail makes any cpio failure abort the build.
( cd "$ROOT" && find . -print0 | LC_ALL=C sort -z \
    | cpio --null -o -H newc --reproducible -R 0:0 2>"$WORK/cpio.err" \
    | gzip -n ) > "$WORK/main-new.cpio.gz"
[ -s "$WORK/main-new.cpio.gz" ] || { echo "main segment empty" >&2; cat "$WORK/cpio.err" >&2; exit 1; }
GZLEN=$(wc -c < "$WORK/main-new.cpio.gz")

# 4. e2 segment: deterministic newc.
python3 "$HERE/build-e2.py"

# 5. concatenate; segment starts must be 4-byte aligned: the kernel parser
# (init/initramfs.c unpack_to_rootfs) only parses a raw cpio when
# (*buf == '0' && !(this_header & 3)) — an unaligned segment start errors
# out as "invalid magic" and the segment is silently skipped. Zero padding
# is skipped by the parser's zero-consumer, never a 512 block.
EARLY_BYTES=10240
pad=$(( (4 - (EARLY_BYTES + GZLEN) % 4) % 4 ))
head -c "$pad" /dev/zero > "$WORK/segpad"
cat "$WORK/base-extract/early.cpio" "$WORK/main-new.cpio.gz" "$WORK/segpad" "$FWCPIO" "$WORK/e2.cpio" \
    > "$TEMP"

# 6. verify the temp artifact before it becomes the deliverable.
FWOFF=$((EARLY_BYTES + GZLEN + pad))
FWBYTES=$(wc -c < "$FWCPIO")
E2BYTES=$(wc -c < "$WORK/e2.cpio")
TOTAL=$(wc -c < "$TEMP")
[ "$TOTAL" -eq $((FWOFF + FWBYTES + E2BYTES)) ] \
    || { echo "VERIFY FAIL: size mismatch" >&2; exit 1; }
readseg() { python3 -c "
import sys
f = open(sys.argv[1], 'rb'); f.seek(int(sys.argv[2]))
sys.stdout.buffer.write(f.read(int(sys.argv[3])))
" "$TEMP" "$1" "$2"; }
SEEN_FW=$(readseg "$FWOFF" "$FWBYTES" | sha256sum | cut -d' ' -f1)
[ "$SEEN_FW" = "b1e15f13af97732732fe19a4b699551fc29dfac5de53b8400814d1422963b2be" ] \
    || { echo "VERIFY FAIL: firmware segment sha $SEEN_FW" >&2; exit 1; }
SEEN_E2=$(readseg "$((FWOFF + FWBYTES))" "$E2BYTES" | sha256sum | cut -d' ' -f1)
SEEN_E2_REF=$(sha256sum "$WORK/e2.cpio" | cut -d' ' -f1)
[ "$SEEN_E2" = "$SEEN_E2_REF" ] || { echo "VERIFY FAIL: e2 segment" >&2; exit 1; }
gzip -t < <(readseg "$EARLY_BYTES" "$GZLEN")

# 7. atomic placement; preserve a superseded artifact under its own hash.
if [ -f "$OUT" ]; then
    OLD=$(sha256sum "$OUT" | cut -d' ' -f1)
    NEW=$(sha256sum "$TEMP" | cut -d' ' -f1)
    if [ "$OLD" != "$NEW" ]; then
        mv "$OUT" "$OUT.superseded-$OLD"
        echo "preserved previous artifact as $OUT.superseded-$OLD"
    fi
fi
mv "$TEMP" "$OUT"
echo "built: $OUT"
sha256sum "$OUT"
