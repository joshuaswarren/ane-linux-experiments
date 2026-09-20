#!/bin/sh
# Isolated candidate-ash fixture test for asahi-firmware-late.sh (production hook body
# UNMODIFIED). Shell FUNCTIONS mount/umount/cp are sourced BEFORE the hook body in a
# child candidate-busybox ash, so they precede the applet/builtin dispatch — proven by
# a preflight assertion that the child resolves mount/umount/cp to functions, and that
# a deliberately bad stub FAILS THE HOOK before any fixture side effect.
# No real mounts, no sudo. Run: sh test-busybox-ash-fixture.sh
# SPDX-License-Identifier: MIT
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SNIPPET=$HERE/asahi-firmware-late.sh
BB=$HERE/candidate-busybox/busybox          # canonical candidate busybox (aarch64 51572718...)
# EXACT-CANDIDATE DRIVER: the child shell must be the candidate aarch64 busybox ash itself.
# On aarch64 hosts BBHOST=BB runs the exact binary. On x86_64 hosts without qemu-aarch64
# user-mode emulation this suite CANNOT execute the exact candidate ash — it must be run on
# an aarch64 host (jw14m2-linux) or with qemu-aarch64. Set BBHOST explicitly in that case.
BBHOST=${BBHOST:-$BB}
[ -x "$BBHOST" ] || { echo "driver shell $BBHOST not executable" >&2; exit 70; }
if [ "$BBHOST" != "$BB" ]; then
    echo "NOTICE: BBHOST=$BBHOST is NOT the candidate binary (51572718...). Results are NOT candidate-proof." >&2
fi

PASS=0; FAILN=0
ok()  { PASS=$((PASS+1)); echo "PASS: $1"; }
bad() { FAILN=$((FAILN+1)); echo "FAIL: $1"; }

WORK=$(mktemp -d /tmp/jwm1ash-XXXX)
mkdir -p "$WORK/stub"

# ---- stub definitions file (sourced into the child BEFORE the hook body) ----
# Functions shadow PATH lookups in POSIX shells (incl. busybox ash): a function named
# mount/umount/cp is found before any builtin/applet of the same name.
cat > "$WORK/stub/stubs.sh" <<'STUBS'
MOUNT_CALLS=0; UMOUNT_CALLS=0; CP_CALLS=0; CP_FAIL=0; UMOUNT_FAIL=0
MOUNT_FAIL=${MOUNT_FAIL:-0}
mount() {
    MOUNT_CALLS=$((MOUNT_CALLS+1))
    [ "$MOUNT_FAIL" = "1" ] && return 1
    dest=
    for a in "$@"; do dest="$a"; done
    [ -n "$dest" ] || return 32
    printf 'vendorfw %s tmpfs rw,nosuid,mode=0755 0 0\n' "$dest" >> "$JWM1_MOUNTS"
    find "$dest" -mindepth 1 | sort > "$STUBDIR/snap-$(printf %s "$dest" | md5sum | cut -d' ' -f1)"
    return 0
}
umount() {
    UMOUNT_CALLS=$((UMOUNT_CALLS+1))
    [ "$UMOUNT_FAIL" = "1" ] && return 1
    dest=
    for a in "$@"; do dest="$a"; done
    snap="$STUBDIR/snap-$(printf %s "$dest" | md5sum | cut -d' ' -f1)"
    if [ -d "$dest" ] && [ -f "$snap" ]; then
        find "$dest" -mindepth 1 | sort > "$dest.cur"
        comm -13 "$snap" "$dest.cur" > "$dest.rm"
        while IFS= read -r p; do rm -rf "$p"; done < "$dest.rm"
        rm -f "$dest.cur" "$dest.rm"
    fi
    rm -f "$snap"
    if [ -n "${JWM1_MOUNTS:-}" ] && [ -f "$JWM1_MOUNTS" ]; then
        grep -vF " $dest " "$JWM1_MOUNTS" > "$JWM1_MOUNTS.new" 2>/dev/null \
            && cat "$JWM1_MOUNTS.new" > "$JWM1_MOUNTS"
        rm -f "$JWM1_MOUNTS.new"
    fi
    return 0
}
cp() {
    CP_CALLS=$((CP_CALLS+1))
    [ "$CP_FAIL" = "1" ] && return 1
    command cp -r "$@"
}
STUBS

# ---- child driver: source stubs, prove preflight, then run hook body ----
cat > "$WORK/driver.sh" <<'DRIVER'
# shellcheck shell=ash
. "$STUBS_FILE" || { echo "PREFLIGHT-FAIL: stubs source" >&2; exit 64; }
# PREFLIGHT PROOF (behavioral, version-independent): the sourced FUNCTIONS must intercept
# mount/umount/cp calls. Proven by invoking each on probe paths and requiring the stub
# call-counters to increment. No `type` text parsing (output format varies across busybox
# builds/versions and broke on the exact candidate binary).
mkdir -p "$PROBE_DIR" 2>/dev/null
mount "$PROBE_DIR/probe-mount" 2>/dev/null
umount "$PROBE_DIR/probe-mount" 2>/dev/null
cp "$PROBE_DIR/probe-cp-src" "$PROBE_DIR/probe-cp-dst" 2>/dev/null
[ "${MOUNT_CALLS:-0}" -ge 1 ] || { echo "PREFLIGHT-FAIL: mount not intercepted by stub function" >&2; exit 65; }
[ "${UMOUNT_CALLS:-0}" -ge 1 ] || { echo "PREFLIGHT-FAIL: umount not intercepted by stub function" >&2; exit 65; }
[ "${CP_CALLS:-0}" -ge 1 ] || { echo "PREFLIGHT-FAIL: cp not intercepted by stub function" >&2; exit 65; }
echo "PREFLIGHT-OK mount/umount/cp intercepted by sourced stub functions (calls: m=$MOUNT_CALLS u=$UMOUNT_CALLS c=$CP_CALLS)"
. "$SNIPPET_FILE"   # production hook body, UNMODIFIED — its mount/umount/cp calls hit the functions
exit $?
DRIVER

run_case() {  # $1=root ; env via MOUNT_FAIL/CP_FAIL/UMOUNT_FAIL exported by caller
    ( cd "$WORK" \
      && STUBS_FILE="$WORK/stub/stubs.sh" SNIPPET_FILE="$SNIPPET" \
         JWM1_MOUNTS="$WORK/mounts" JWM1_VENDORFW="$WORK/vendorfw" STUBDIR="$WORK/stub" \
         PROBE_DIR="$WORK/probe" MOUNT_FAIL="${MOUNT_FAIL:-0}" CP_FAIL="${CP_FAIL:-0}" \
         UMOUNT_FAIL="${UMOUNT_FAIL:-0}" \
         "$BBHOST" sh "$WORK/driver.sh" "$1" ) 2>"$WORK/err"
    echo $? > "$WORK/rc"
}

setup() {  # $1=USRLAYOUT $2=KIND $3=EXTRA  (reuses same conventions as test-firmware-late.sh)
    usrlayout=$1; kind=$2; extra=$3
    [ -d "$WORK/vendorfw" ] && chmod -R u+rwX "$WORK/vendorfw" 2>/dev/null
    find "$WORK/rootd" -mindepth 1 -prune -exec rm -rf {} + 2>/dev/null
    rm -rf "$WORK/vendorfw" 2>/dev/null
    mkdir -p "$WORK/rootd/usr/lib/firmware" "$WORK/vendorfw/brcm" "$WORK/elsewhere"
    ln -s usr/lib "$WORK/rootd/lib"
    printf 'fw-bytes-A\n' > "$WORK/vendorfw/brcm/a.bin"
    printf 'fw-bytes-B\n' > "$WORK/vendorfw/brcm/b.clm_blob"
    printf 'manifest-stub\n' > "$WORK/vendorfw/.vendorfw.manifest"
    {
        printf '%s  brcm/a.bin\n' "$(printf 'fw-bytes-A\n' | "$BBHOST" sha256sum | cut -d' ' -f1)"
        if [ "$kind" = ok ]; then
            printf '%s  brcm/b.clm_blob\n' "$(printf 'fw-bytes-B\n' | "$BBHOST" sha256sum | cut -d' ' -f1)"
        else
            printf '0000000000000000000000000000000000000000000000000000000000000000  brcm/b.clm_blob\n'
        fi
    } > "$WORK/vendorfw/.vendorfw.sha256"
    [ "$kind" = cpfail ] && chmod 000 "$WORK/vendorfw/brcm/b.clm_blob"
    : > "$WORK/mounts"; : > "$WORK/err"; : > "$WORK/log"
    DEST=$WORK/rootd/usr/lib/firmware/vendor
    case $extra in
        preexistdir) mkdir -p "$DEST"; printf 'original-marker\n' > "$DEST/ORIG-MARKER.txt" ;;
        preexistmount) printf 'otherdev %s tmpfs rw 0 0\n' "$DEST" >> "$WORK/mounts" ;;
    esac
    return 0
}

# ---- B0 preflight: bad stub must FAIL THE HOOK before any fixture effect ----
setup merged ok none
ln -s usr/lib "$WORK/rootd/lib" 2>/dev/null || true
cat > "$WORK/badstub" <<'BS'
mount() { return 0; }   # stub that lies: accepts everything, records nothing
BS
b0rc=$(cd "$WORK" && STUBS_FILE="$WORK/badstub" SNIPPET_FILE="$SNIPPET" \
     JWM1_MOUNTS="$WORK/mounts" JWM1_VENDORFW="$WORK/vendorfw" STUBDIR="$WORK/stub" \
     "$BBHOST" sh "$WORK/driver.sh" "$WORK/rootd" >/dev/null 2>"$WORK/err"; echo $?)
b0mounts=$(grep -c vendorfw "$WORK/mounts" 2>/dev/null); b0mounts=${b0mounts:-0}
b0prefl=$(grep -c "PREFLIGHT-OK" "$WORK/err" 2>/dev/null); b0prefl=${b0prefl:-0}
b0preflfail=$(grep -c "PREFLIGHT-FAIL" "$WORK/err" 2>/dev/null); b0preflfail=${b0preflfail:-0}
if [ "$b0rc" != "0" ] && [ "$b0mounts" = "0" ] && grep -q "PREFLIGHT-FAIL: mount not intercepted" "$WORK/err" && ! grep -q "PREFLIGHT-FAIL: stubs source" "$WORK/err"; then
    ok "B0 preflight: bad stub (no tmpfs recorded) fails hook before fixture effect"
else bad "B0 preflight rc=$b0rc mounts=$b0mounts preflight_ok=$b0prefl preflight_fail=$b0preflfail err=$(cat "$WORK/err" 2>/dev/null | head -1)"; fi

# ---- T1 happy path under candidate ash + function stubs ----
setup merged ok none
run_case "$WORK/rootd"
if [ "$(cat "$WORK/rc")" = "0" ] \
   && [ -f "$WORK/rootd/usr/lib/firmware/vendor/brcm/a.bin" ] \
   && grep -q "vendorfw $WORK/rootd/usr/lib/firmware/vendor tmpfs" "$WORK/mounts"; then
    ok "T1 happy: candidate ash, function stubs, canonical mount line present"
else bad "T1 happy (rc=$(cat "$WORK/rc") err=$(head -2 "$WORK/err"))"; fi

# ---- T2 mount function fails: hook exits nonzero, created dir cleaned ----
setup merged ok none
MOUNT_FAIL=1 run_case "$WORK/rootd"
if [ "$(cat "$WORK/rc")" != "0" ] && [ ! -e "$WORK/rootd/usr/lib/firmware/vendor" ]; then
    ok "T2 mount-fail: nonzero exit, created dir cleaned"
else bad "T2 mount-fail (rc=$(cat "$WORK/rc"))"; fi

# ---- T3 cp function fails (chmod 000 source): nonzero, umount cleanup runs ----
setup merged cpfail none
CP_FAIL=1 run_case "$WORK/rootd"
umc=$(grep -c 'u' "$WORK/log" 2>/dev/null); umc=${umc:-0}
if [ "$(cat "$WORK/rc")" != "0" ]; then
    ok "T3 cp-fail: nonzero exit (cleanup umount-line count $umc)"
else bad "T3 cp-fail"; fi

# ---- T4 checked-copy mismatch: nonzero exit; pre-existing dir revealed intact ----
setup merged mismatch preexistdir
run_case "$WORK/rootd"
if [ "$(cat "$WORK/rc")" != "0" ] \
   && [ -f "$WORK/rootd/usr/lib/firmware/vendor/ORIG-MARKER.txt" ] \
   && [ ! -e "$WORK/rootd/usr/lib/firmware/vendor/brcm" ]; then
    ok "T4 mismatch pre-existing: nonzero exit, original revealed intact"
else bad "T4 mismatch pre-existing (rc=$(cat "$WORK/rc"))"; fi

# ---- T5 unreadable mounts: failc readability-first under candidate ash ----
setup merged ok none
: > "$WORK/mounts-ro"; chmod 000 "$WORK/mounts-ro"
( cd "$WORK" \
  && STUBS_FILE="$WORK/stub/stubs.sh" SNIPPET_FILE="$SNIPPET" \
     JWM1_MOUNTS="$WORK/mounts-ro" JWM1_VENDORFW="$WORK/vendorfw" STUBDIR="$WORK/stub" \
     "$BBHOST" sh "$WORK/driver.sh" "$WORK/rootd" ) 2>"$WORK/err"
if [ "$(cat "$WORK/rc")" != "0" ] && grep -q "not readable" "$WORK/err"; then
    ok "T5 unreadable mounts: explicit readability failure"
else bad "T5 unreadable mounts (rc=$(cat "$WORK/rc"))"; fi
chmod 644 "$WORK/mounts-ro" 2>/dev/null

echo "----"
echo "pass=$PASS fail=$FAILN candidate_ash=$BB"
rm -rf "$WORK" 2>/dev/null
[ $FAILN -eq 0 ]
