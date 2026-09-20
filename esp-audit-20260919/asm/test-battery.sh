#!/bin/ash
# T3/T4 battery for the assembled initrd, run on jw14m2-linux with the
# candidate initramfs busybox (51572718...). Fixtures only, no real root.
# $1 = directory containing: busybox, initrd-7113-clean-modstage.img
# Harness copies of hooks differ from the embedded hook ONLY in the three
# absolute path constants (script, /sysroot, manifest), sed-replaced to
# fixture paths; everything else, including init_functions, is the real
# artifact content.
set -u
D="$1"; BB="$D/busybox"; ART="$D/initrd-7113-clean-modstage.img"
PASS=0; FAIL=0
ok() { PASS=$((PASS+1)); echo "  PASS: $*"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL: $*"; }

echo "== split artifact segments =="
rm -rf "$D/x"
mkdir -p "$D/x/main" "$D/x/fw" "$D/x/e2"
tail -c +10241 "$ART" | gzip -dc > "$D/x/main.cpio" 2>"$D/x/gz.err"
grep -q 'trailing garbage' "$D/x/gz.err" && ok "gzip stream ends inside artifact (firmware/e2 segments follow)" || bad "gzip tail behavior unexpected: $(cat "$D/x/gz.err")"
( cd "$D/x/main" && cpio -idm --quiet < "$D/x/main.cpio" 2>/dev/null )
FWOFF=$((10240 + $(wc -c < "$D/x/main.cpio" 2>/dev/null || echo 0)))
# main.cpio is decompressed; compute fw offset from compressed length instead:
GZLEN=$(python3 -c "
import zlib
f=open('$ART','rb'); f.seek(10240)
d=zlib.decompressobj(16+zlib.MAX_WBITS)
while not d.eof:
    c=f.read(1<<20)
    if not c: break
    d.decompress(c)
print(f.tell()-len(d.unused_data))
" 2>/dev/null || echo "")
if [ -n "$GZLEN" ]; then
    # GZLEN is the absolute end offset of the gzip stream; the builder pads
    # with zeros to the next 4-byte boundary before the firmware cpio.
    PAD=$(( (4 - GZLEN % 4) % 4 ))
    FWOFF=$((GZLEN + PAD))
    tail -c +"$((FWOFF+1))" "$ART" > "$D/x/tail.cpio"
    head -c 32513468 "$D/x/tail.cpio" > "$D/x/fw.cpio"
    tail -c +32513469 "$D/x/tail.cpio" > "$D/x/e2.cpio"
    S1=$(sha256sum "$D/x/fw.cpio" | cut -d' ' -f1)
    S2=$(sha256sum "$D/x/e2.cpio" | cut -d' ' -f1)
    S2REF=$(sha256sum "$D/e2.cpio.ref" 2>/dev/null | cut -d' ' -f1)
    [ "$S1" = "b1e15f13af97732732fe19a4b699551fc29dfac5de53b8400814d1422963b2be" ] && ok "T1 firmware segment sha (verbatim append)" || bad "T1 fw segment sha $S1"
    [ -n "$S2REF" ] && [ "$S2" = "$S2REF" ] && ok "T1 e2 segment sha matches builder reference" || bad "T1 e2 segment sha $S2 vs builder reference $S2REF"
    ( cd "$D/x/fw" && cpio -idm --quiet < "$D/x/fw.cpio" 2>/dev/null ); FWRC=$?
    ( cd "$D/x/e2" && cpio -idm --quiet < "$D/x/e2.cpio" 2>/dev/null ); E2RC=$?
    [ "$FWRC" -eq 0 ] && [ "$E2RC" -eq 0 ] && ok "fw/e2 cpio extraction rc=0" || bad "fw/e2 extraction rc: fw=$FWRC e2=$E2RC"
else
    bad "could not compute gzip length (python3 missing?)"
fi

echo "== T3 syntax with candidate ash =="
for f in init init_functions hooks/jwm1-modstage usr/local/bin/jwm1-modstage.sh usr/local/bin/jwm1-firmware-late; do
    if "$BB" ash -n "$D/x/main/$f" 2>"$D/x/syn.err"; then ok "ash -n $f"; else bad "ash -n $f: $(cat "$D/x/syn.err")"; fi
done

echo "== fw caller insertion position =="
MOUNTLINE=$("$BB" grep -n '"\$mount_handler" /sysroot' "$D/x/main/init" | head -n1 | cut -d: -f1)
FWLINE=$("$BB" grep -n 'jwm1-firmware-late /sysroot' "$D/x/main/init" | head -n1 | cut -d: -f1)
LATELINE=$("$BB" grep -n "run_hookfunctions 'run_latehook'" "$D/x/main/init" | head -n1 | cut -d: -f1)
SWLINE=$("$BB" grep -n '/usr/bin/switch_root' "$D/x/main/init" | head -n1 | cut -d: -f1)
EXITFB=$("$BB" grep -c '^[[:space:]]*exit 1$' "$D/x/main/init")
if [ -n "$MOUNTLINE" ] && [ -n "$FWLINE" ] && [ "$MOUNTLINE" -lt "$FWLINE" ] && [ "$FWLINE" -lt "$LATELINE" ] && [ "$LATELINE" -lt "$SWLINE" ]; then
    ok "order mount($MOUNTLINE) < fw($FWLINE) < latehooks($LATELINE) < switch_root($SWLINE)"
else
    bad "ordering: mount=$MOUNTLINE fw=$FWLINE late=$LATELINE sw=$SWLINE"
fi
[ "$EXITFB" -ge 1 ] && ok "explicit exit fallback in init" || bad "exit fallback missing"

echo "== firmware first-boot resolution + checked copy =="
[ "$("$BB" readlink "$D/x/e2/lib/firmware/vendor" 2>/dev/null)" = "/vendorfw" ] && ok "e2 symlink lib/firmware/vendor -> /vendorfw" || bad "e2 symlink"
# merge e2 dotfiles into the fw vendorfw tree (one unpacked root in the real image)
cp "$D/x/e2/vendorfw/.vendorfw.sha256" "$D/x/e2/vendorfw/.vendorfw.manifest" "$D/x/fw/vendorfw/" 2>/dev/null
if [ -f "$D/x/fw/vendorfw/brcm/brcmfmac4364b2-pcie.apple,ekans.bin" ]; then
    ok "ekans firmware present under /vendorfw/brcm"
else
    find "$D/x/fw/vendorfw/brcm" -name 'brcmfmac4364b2-pcie.apple,ekans*' 2>/dev/null | grep -q . && ok "ekans firmware present under /vendorfw/brcm (find)" || bad "ekans firmware missing"
fi
HCOUNT=$(find "$D/x/fw/vendorfw" -type f 2>/dev/null | wc -l)
[ "$HCOUNT" -gt 100 ] && ok "firmware tree extracted: $HCOUNT files" || bad "firmware tree too small: $HCOUNT"
( cd "$D/x/fw/vendorfw" && "$BB" sha256sum -c .vendorfw.sha256 2>/dev/null ) > "$D/x/chk.out"
BADLINES=$(grep -cv ': OK$' "$D/x/chk.out")
BADLINES=${BADLINES:-0}
TOTLINES=$(wc -l < "$D/x/chk.out")
[ "$TOTLINES" -ge 200 ] && [ "$BADLINES" -eq 0 ] && ok "busybox sha256sum -c: $TOTLINES/217 entries OK" || bad "sha256sum -c: $TOTLINES lines, $BADLINES bad"

echo "== T4 hook contract: failure can never reach switch_root =="
FIX="$D/x/t4"; mkdir -p "$FIX/sysroot" "$FIX/root"
cp "$D/x/main/usr/local/bin/jwm1-modstage.sh" "$FIX/jwm1-modstage.sh"
# failure harness: /sysroot constant replaced by a nonexistent fixture path
sed -e "s|/usr/local/bin/jwm1-modstage.sh|$FIX/jwm1-modstage.sh|" \
    -e 's|/sysroot|/nonexistent-sysroot|g' \
    -e "s|/usr/lib/modules/7.1.13-3-1-ARCH|$D/x/main/usr/lib/modules/7.1.13-3-1-ARCH|" \
    -e "s|/etc/jwm1-modules.manifest|$D/x/main/etc/jwm1-modules.manifest|" \
    "$D/x/main/hooks/jwm1-modstage" > "$FIX/hook-fail"
: > "$FIX/log"
cat > "$FIX/h1" <<HEOF
. '$D/x/main/init_functions'
launch_interactive_shell() { echo "RESCUE-SHELL-INVOKED \$*" >> '$FIX/log'; exit 42; }
. '$FIX/hook-fail'
run_latehook
echo "REACHED-SWITCH-ROOT-POSITION" >> '$FIX/log'
HEOF
"$BB" ash "$FIX/h1" >/dev/null 2>&1
R1=$?
if grep -q RESCUE-SHELL-INVOKED "$FIX/log" && ! grep -q "REACHED-SWITCH-ROOT-POSITION" "$FIX/log"; then
    ok "failure path: rescue invoked, switch_root position never reached (harness rc=$R1)"
else
    bad "failure path: rc=$R1 log=$(cat "$FIX/log")"
fi
# success harness: sysroot/manifest constants replaced by fixture paths
rm -rf "$FIX/sysroot/usr/lib/modules/7.1.13-3-1-ARCH"
mkdir -p "$FIX/sysroot/usr/lib/modules"
sed -e "s|/usr/local/bin/jwm1-modstage.sh|$FIX/jwm1-modstage.sh|" \
    -e "s|/sysroot|$FIX/sysroot|g" \
    -e "s|/usr/lib/modules/7.1.13-3-1-ARCH|$D/x/main/usr/lib/modules/7.1.13-3-1-ARCH|" \
    -e "s|/etc/jwm1-modules.manifest|$D/x/main/etc/jwm1-modules.manifest|" \
    "$D/x/main/hooks/jwm1-modstage" > "$FIX/hook-ok"
: > "$FIX/log2"
cat > "$FIX/h2" <<HEOF
. '$D/x/main/init_functions'
. '$FIX/hook-ok'
run_latehook
echo "REACHED-SWITCH-ROOT-POSITION" >> '$FIX/log2'
HEOF
"$BB" ash "$FIX/h2" >"$FIX/h2.out" 2>"$FIX/h2.err"
R2=$?
if grep -q "REACHED-SWITCH-ROOT-POSITION" "$FIX/log2" && [ "$R2" -eq 0 ]; then
    ok "success path: run_latehook rc=0, boot continues"
else
    bad "success path: rc=$R2 err=$(head -c 200 "$FIX/h2.err") out=$(head -c 100 "$FIX/h2.out")"
fi

echo "== embedded module stage end-to-end (artifact's own files) =="
"$BB" ash "$FIX/jwm1-modstage.sh" manifest "$D/x/main/usr/lib/modules/7.1.13-3-1-ARCH" > "$FIX/m2" 2>/dev/null
cmp -s "$FIX/m2" "$D/x/main/etc/jwm1-modules.manifest" && ok "artifact tree manifest == embedded manifest" || bad "manifest mismatch"
"$BB" ash "$FIX/jwm1-modstage.sh" stage "$FIX/sysroot" "$D/x/main/usr/lib/modules/7.1.13-3-1-ARCH" "$D/x/main/etc/jwm1-modules.manifest" >/dev/null 2>&1
R3=$?
[ "$R3" -eq 0 ] && ok "artifact module stage rc=0 into fixture sysroot" || bad "artifact module stage rc=$R3"
# idempotent second call leaves target untouched, rc 0
"$BB" ash "$FIX/jwm1-modstage.sh" stage "$FIX/sysroot" "$D/x/main/usr/lib/modules/7.1.13-3-1-ARCH" "$D/x/main/etc/jwm1-modules.manifest" >/dev/null 2>&1
R4=$?
[ "$R4" -eq 0 ] && ok "second stage rc=0 (already-exact untouched)" || bad "second stage rc=$R4"

echo ""
echo "======== BATTERY: PASS=$PASS FAIL=$FAIL ========"
[ "$FAIL" -eq 0 ]
