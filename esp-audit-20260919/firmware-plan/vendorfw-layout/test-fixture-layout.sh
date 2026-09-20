#!/bin/sh
# Extra fixture-layout coverage for v4: ROOT real-dir guard, /usr + /usr/lib real-dir
# guards, non-/usr/lib symlink-target rejection, explicit cleanup messaging.
# SPDX-License-Identifier: MIT
set -u
HERE=$(cd "$(dirname "$0")/.." && pwd)
SNIPPET=$HERE/asahi-firmware-late.sh
WORK=$(mktemp -d /tmp/jwm1fwv4extra-XXXX)
STUB=$WORK/stub; mkdir -p "$STUB"
cat > "$STUB/mount" <<'STUBEOF'
#!/bin/sh
if [ "${MOUNT_FAIL:-0}" = "1" ]; then exit 1; fi
dest=
for a in "$@"; do dest="$a"; done
printf 'vendorfw %s tmpfs rw 0 0\n' "$dest" >> "$JWM1_MOUNTS"
STUBEOF
cat > "$STUB/umount" <<'STUBEOF'
#!/bin/sh
echo "u" >> "$STUBDIR/log"
exit 0
STUBEOF
chmod +x "$STUB/mount" "$STUB/umount"

# Always provide a valid vendorfw fixture
rm -rf "$WORK/vendorfw"; mkdir -p "$WORK/vendorfw/brcm"
printf 'x\n' > "$WORK/vendorfw/brcm/a.bin"
printf 'x\n' | sha256sum | cut -d' ' -f1 | awk '{printf "%s  brcm/a.bin\n",$1}' > "$WORK/vendorfw/.vendorfw.sha256"
printf 'm\n' > "$WORK/vendorfw/.vendorfw.manifest"

PASS=0; FAILN=0
ok() { PASS=$((PASS+1)); echo "PASS: $1"; }
bad() { FAILN=$((FAILN+1)); echo "FAIL: $1"; }

# E1 ROOT is a symlink -> reject
rm -rf "$WORK/rootl"; ln -s somewhere "$WORK/rootl"
if ( cd "$WORK" && : > "$WORK/mounts" && JWM1_MOUNTS="$WORK/mounts" \
     JWM1_VENDORFW="$WORK/vendorfw" PATH="$STUB:$PATH" STUBDIR="$WORK" \
     sh "$SNIPPET" "$WORK/rootl" ) 2>"$WORK/err"; then bad "E1"
elif grep -q "is a symlink" "$WORK/err"; then ok "E1 ROOT-as-symlink rejected"
else bad "E1 wrong reason: $(cat "$WORK/err")"; fi

# E2 /usr/lib is a symlink -> reject
rm -rf "$WORK/r2"; mkdir -p "$WORK/r2/usr/lib/firmware"
ln -s elsewhere "$WORK/r2/usr/lib"
if ( cd "$WORK" && : > "$WORK/mounts" && JWM1_MOUNTS="$WORK/mounts" \
     JWM1_VENDORFW="$WORK/vendorfw" PATH="$STUB:$PATH" STUBDIR="$WORK" \
     sh "$SNIPPET" "$WORK/r2" ) 2>"$WORK/err"; then bad "E2"
elif grep -q "/usr/lib missing or a symlink" "$WORK/err"; then ok "E2 /usr/lib-as-symlink rejected"
else bad "E2 wrong reason: $(cat "$WORK/err")"; fi

# E3 /lib points to non-/usr/lib
rm -rf "$WORK/r3"; mkdir -p "$WORK/r3/usr/lib/firmware"
ln -s elsewhere "$WORK/r3/lib"
if ( cd "$WORK" && : > "$WORK/mounts" && JWM1_MOUNTS="$WORK/mounts" \
     JWM1_VENDORFW="$WORK/vendorfw" PATH="$STUB:$PATH" STUBDIR="$WORK" \
     sh "$SNIPPET" "$WORK/r3" ) 2>"$WORK/err"; then bad "E3"
elif grep -q "unexpected /lib symlink target" "$WORK/err"; then ok "E3 /lib wrong-target rejected"
else bad "E3 wrong reason: $(cat "$WORK/err")"; fi

# E4 cleanup honest messaging (positive variant on a clean mount-fail path)
rm -rf "$WORK/r4"; mkdir -p "$WORK/r4/usr/lib/firmware"
MOUNT_FAIL=1
if ( cd "$WORK" && : > "$WORK/mounts" && MOUNT_FAIL=$MOUNT_FAIL \
     JWM1_MOUNTS="$WORK/mounts" JWM1_VENDORFW="$WORK/vendorfw" \
     PATH="$STUB:$PATH" STUBDIR="$WORK" sh "$SNIPPET" "$WORK/r4" ) 2>"$WORK/err"; then bad "E4"
elif grep -qE "real-root firmware tree (either untouched|or revealed intact per tmpfs)" "$WORK/err"; then
    ok "E4 mount-fail positive cleanup messaging present"
else bad "E4 wrong msg: $(cat "$WORK/err")"; fi

echo "----"; echo "pass=$PASS fail=$FAILN"
[ $FAILN -eq 0 ]
