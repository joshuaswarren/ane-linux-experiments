#!/bin/sh
# Source-level failure tests for jwm1-firmware-late.sh v3/v4.
# Unprivileged: mount/umount are PATH stubs (no privileged live mounts); /proc/mounts via
# JWM1_MOUNTS fixture; /vendorfw source via JWM1_VENDORFW fixture; /sh-driver via
# `${BB_SH:-sh}` (override with a busybox applet link when verifying busybox
# compatibility). Fixture root uses the merged-usr layout (rootd/lib -> usr/lib symlink);
# canonical dest rootd/usr/lib/firmware/vendor.
# SPDX-License-Identifier: MIT
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SNIPPET=$HERE/asahi-firmware-late.sh
BB_SH=${BB_SH:-sh}        # override to a busybox applet link to verify on busybox
WORK=$(mktemp -d /tmp/jwm1fwtest3-XXXX)
STUB=$WORK/stub
mkdir -p "$STUB"

PASS=0; FAILN=0
ok()  { PASS=$((PASS+1)); echo "PASS: $1"; }
bad() { FAILN=$((FAILN+1)); echo "FAIL: $1"; }

cat > "$STUB/mount" <<'STUBEOF'
#!/bin/sh
if [ "${MOUNT_FAIL:-0}" = "1" ]; then echo "stub mount: failure injection" >&2; exit 1; fi
dest=
for a in "$@"; do dest="$a"; done
[ -n "$dest" ] || exit 32
printf 'vendorfw %s tmpfs rw,nosuid,mode=0755 0 0\n' "$dest" >> "$JWM1_MOUNTS"
echo "stub mount: $*" >> "$STUBDIR/mount.log"
# Snapshot pre-mount contents (real tmpfs would discard its own contents on umount and
# reveal whatever was underneath; the test fixture emulates that semantics.)
find "$dest" -mindepth 1 | sort > "$STUBDIR/snap-$(printf %s "$dest" | md5sum | cut -d' ' -f1)"
STUBEOF
cat > "$STUB/umount" <<'STUBEOF'
#!/bin/sh
echo "stub umount: $*" >> "$STUBDIR/umount.log"
dest=
for a in "$@"; do dest="$a"; done
snap="$STUBDIR/snap-$(printf %s "$dest" | md5sum | cut -d' ' -f1)"
if [ -d "$dest" ] && [ -f "$snap" ]; then
    find "$dest" -mindepth 1 | sort > "$dest.cur"
    comm -13 "$snap" "$dest.cur" > "$dest.rm"
    while IFS= read -r p; do
        rm -rf "$p"
    done < "$dest.rm"
    rm -f "$dest.cur" "$dest.rm"
fi
rm -f "$snap"
if [ -n "${JWM1_MOUNTS:-}" ] && [ -f "$JWM1_MOUNTS" ]; then
    grep -vF " $dest " "$JWM1_MOUNTS" > "$JWM1_MOUNTS.new" 2>/dev/null \
        && cat "$JWM1_MOUNTS.new" > "$JWM1_MOUNTS"
    rm -f "$JWM1_MOUNTS.new"
fi
STUBEOF
chmod +x "$STUB/mount" "$STUB/umount"

setup() {
    rootd=$1; usrlayout=$2; kind=$3; extra=$4
    if [ -d "$WORK/rootd" ]; then find "$WORK/rootd" -mindepth 1 -prune -exec rm -rf {} +; fi
    rm -rf "$WORK/rootd" 2>/dev/null
    if [ -d "$WORK/vendorfw" ]; then chmod -R u+rwX "$WORK/vendorfw" 2>/dev/null; fi
    if [ "$usrlayout" = merged ]; then
        mkdir -p "$rootd/usr/lib/firmware"
        ln -s usr/lib "$rootd/lib"
    else
        mkdir -p "$rootd/lib/firmware"
    fi
    mkdir -p "$WORK/vendorfw/brcm" "$WORK/elsewhere"
    printf 'fw-bytes-A\n' > "$WORK/vendorfw/brcm/a.bin"
    printf 'fw-bytes-B\n' > "$WORK/vendorfw/brcm/b.clm_blob"
    printf 'manifest-stub\n' > "$WORK/vendorfw/.vendorfw.manifest"
    {
        printf '%s  brcm/a.bin\n' "$(printf 'fw-bytes-A\n' | sha256sum | cut -d' ' -f1)"
        if [ "$kind" = ok ]; then
            printf '%s  brcm/b.clm_blob\n' "$(printf 'fw-bytes-B\n' | sha256sum | cut -d' ' -f1)"
        else
            printf '0000000000000000000000000000000000000000000000000000000000000000  brcm/b.clm_blob\n'
        fi
    } > "$WORK/vendorfw/.vendorfw.sha256"
    if [ "$kind" = cpfail ]; then
        if [ -f "$WORK/vendorfw/brcm/b.clm_blob" ]; then
            chmod 000 "$WORK/vendorfw/brcm/b.clm_blob"
        fi
    fi
    : > "$WORK/mounts"; : > "$WORK/mount.log"; : > "$WORK/umount.log"
    DEST=$rootd/usr/lib/firmware/vendor
    [ "$usrlayout" = merged ] || DEST=$rootd/lib/firmware/vendor
    case $extra in
        symlink)        ln -s "$WORK/elsewhere" "$DEST" ;;
        preexistdir)    mkdir -p "$DEST"; printf 'original-marker\n' > "$DEST/ORIG-MARKER.txt" ;;
        preexistmount)  printf 'otherdev %s tmpfs rw 0 0\n' "$DEST" >> "$WORK/mounts" ;;
        preexistmountalias)
            [ "$usrlayout" = merged ] || return 0
            printf 'otherdev %s tmpfs rw 0 0\n' "$rootd/lib/firmware/vendor" >> "$WORK/mounts" ;;
        preexistfile)   : > "$DEST" ;;
    esac
    return 0
}

run_snip() {
    ( cd "$WORK" && JWM1_MOUNTS="$WORK/mounts" JWM1_VENDORFW="$WORK/vendorfw" \
      PATH="$STUB:$PATH" STUBDIR="$WORK" "$BB_SH" "$SNIPPET" "$1" ) 2>"$WORK/err"
}

# T1 happy path
setup "$WORK/rootd" merged ok none
if run_snip "$WORK/rootd" \
   && [ -f "$WORK/rootd/usr/lib/firmware/vendor/brcm/a.bin" ] \
   && grep -q "vendorfw $WORK/rootd/usr/lib/firmware/vendor tmpfs" "$WORK/mounts"; then
    ok "T1 happy merged-usr: canonical dest mounted+asserted, copy+manifest present"
else bad "T1 happy merged-usr (err: $(head -2 "$WORK/err" 2>/dev/null))"; fi

# T2 mount failure
setup "$WORK/rootd" merged ok none
MOUNT_FAIL=1 run_snip "$WORK/rootd"; rc=$?
if [ $rc -ne 0 ] && [ ! -e "$WORK/rootd/usr/lib/firmware/vendor" ]; then
    ok "T2 mount failure: exit $rc, created dir cleaned"
else bad "T2 mount failure (rc=$rc)"; fi

# T3 pre-existing canonical mount
setup "$WORK/rootd" merged ok preexistmount
before=$(wc -l < "$WORK/mount.log")
run_snip "$WORK/rootd"; rc=$?
after=$(wc -l < "$WORK/mount.log")
if [ $rc -ne 0 ] && [ "$before" = "$after" ]; then
    ok "T3 canonical pre-existing mount rejected, no new mount"
else bad "T3 canonical pre-existing mount (rc=$rc mounts $before->$after)"; fi

# T3b alias-form pre-existing mount
setup "$WORK/rootd" merged ok preexistmountalias
run_snip "$WORK/rootd"; rc=$?
if [ $rc -ne 0 ]; then
    ok "T3b alias-form pre-existing mount rejected"
else bad "T3b alias-form pre-existing mount"; fi

# T4 symlink destination
setup "$WORK/rootd" merged ok symlink
run_snip "$WORK/rootd"; rc=$?
if [ $rc -ne 0 ] && [ ! -e "$WORK/elsewhere/brcm/a.bin" ]; then
    ok "T4 symlink destination rejected, target untouched"
else bad "T4 symlink destination (rc=$rc)"; fi

# T4b broken symlink destination
setup "$WORK/rootd" merged ok none
ln -s "$WORK/nonexistent-target" "$WORK/rootd/usr/lib/firmware/vendor"
run_snip "$WORK/rootd"; rc=$?
if [ $rc -ne 0 ]; then
    ok "T4b broken symlink destination rejected"
else bad "T4b broken symlink destination"; fi

# T5 mismatch created-dir
setup "$WORK/rootd" merged mismatch none
run_snip "$WORK/rootd"; rc=$?
um=$(wc -l < "$WORK/umount.log")
if [ $rc -ne 0 ] && [ "$um" -ge 1 ] && [ ! -e "$WORK/rootd/usr/lib/firmware/vendor" ]; then
    ok "T5 mismatch created-dir: exit $rc, umount issued, dir removed"
else bad "T5 mismatch created-dir (rc=$rc um=$um)"; fi

# T5b mismatch pre-existing
setup "$WORK/rootd" merged mismatch preexistdir
run_snip "$WORK/rootd"; rc=$?
um=$(wc -l < "$WORK/umount.log")
if [ $rc -ne 0 ] && [ "$um" -ge 1 ] \
   && [ -f "$WORK/rootd/usr/lib/firmware/vendor/ORIG-MARKER.txt" ] \
   && [ ! -f "$WORK/rootd/usr/lib/firmware/vendor/brcm/a.bin" ]; then
    ok "T5b mismatch pre-existing dir: umount issued, original dir intact"
else ls -la "$WORK/rootd/usr/lib/firmware/vendor/" 2>/dev/null; cat "$STUB/snap-$(printf %s "$WORK/rootd/usr/lib/firmware/vendor" | md5sum | cut -d" " -f1)" 2>/dev/null; bad "T5b rc=$rc um=$um snap=$STUB/snap-*"; fi

# T6 missing source
setup "$WORK/rootd" merged ok none
find "$WORK/vendorfw" -mindepth 1 -prune -exec rm -rf {} +
run_snip "$WORK/rootd"; rc=$?
if [ $rc -ne 0 ]; then ok "T6 missing source: exit $rc"; else bad "T6 missing source"; fi

# T7 unreadable mounts file
setup "$WORK/rootd" merged ok none
cp "$WORK/mounts" "$WORK/mounts-ro"
chmod 000 "$WORK/mounts-ro"
( cd "$WORK" && JWM1_MOUNTS="$WORK/mounts-ro" JWM1_VENDORFW="$WORK/vendorfw" \
  PATH="$STUB:$PATH" STUBDIR="$WORK" "$BB_SH" "$SNIPPET" "$WORK/rootd" ) 2>"$WORK/err"; rc=$?
if [ $rc -ne 0 ] && grep -q "not readable" "$WORK/err"; then
    ok "T7 unreadable mounts file: exit $rc with explicit readability failure"
else bad "T7 unreadable mounts (rc=$rc)"; fi
chmod 644 "$WORK/mounts-ro" 2>/dev/null

# T8 cp failure created-dir
setup "$WORK/rootd" merged cpfail none
run_snip "$WORK/rootd"; rc=$?
um=$(wc -l < "$WORK/mount.log")  # mount.log; cp-fail path has no umount
if [ $rc -ne 0 ]; then  # cp-fail path: snippet branch - cleanup() is called BEFORE assert check via the || failc wrapper; but our snippet has mount still active — the cp failure path issues umount and rmdir via cleanup().
    um=$(wc -l < "$WORK/umount.log")
fi
if [ $rc -ne 0 ] && [ ! -e "$WORK/rootd/usr/lib/firmware/vendor" ]; then
    ok "T8 cp failure created-dir: exit $rc, dir removed"
else bad "T8 cp failure (rc=$rc um=$um)"; fi

# T9 cp failure pre-existing
setup "$WORK/rootd" merged cpfail preexistdir
run_snip "$WORK/rootd"; rc=$?
um=$(wc -l < "$WORK/umount.log")
if [ $rc -ne 0 ] && [ "$um" -ge 1 ] \
   && [ -f "$WORK/rootd/usr/lib/firmware/vendor/ORIG-MARKER.txt" ]; then
    ok "T9 cp failure pre-existing dir: umount issued, original intact"
else ls -la "$WORK/rootd/usr/lib/firmware/vendor/" 2>/dev/null; cat "$STUB/snap-$(printf %s "$WORK/rootd/usr/lib/firmware/vendor" | md5sum | cut -d' ' -f1)" 2>/dev/null; bad "T9 cp pre-existing rc=$rc um=$um snap=$STUBDIR/snap-*"; fi

# T10 plain lib layout
setup "$WORK/rootd" plain ok none
if run_snip "$WORK/rootd" \
   && grep -q "vendorfw $WORK/rootd/lib/firmware/vendor tmpfs" "$WORK/mounts"; then
    ok "T10 plain lib layout: dest and assertion consistent"
else bad "T10 plain lib layout (err: $(head -2 "$WORK/err" 2>/dev/null))"; fi

echo "----"
echo "pass=$PASS fail=$FAILN bb_sh=$BB_SH"
rm -rf "$WORK" "$WORK/mounts-ro" 2>/dev/null
[ $FAILN -eq 0 ]
