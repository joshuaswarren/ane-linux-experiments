#!/bin/sh
# jwm1 firmware persistence v4 — adapted from asahi-scripts initcpio/hooks/asahi run_latehook.
# Root mountpoint is passed EXPLICITLY by the init caller (production: /sysroot for artifact
# 63e39dd8f3316c8d39c75caf9854fcf04eddd14b4f5e8378c43c8847b269b75b; verified init:65-66,109).
# v4 changes (per Main v3 close + hook review):
#   - ROOT itself, plus /usr and /usr/lib (merged-usr branch), must be REAL DIRS (not symlinks),
#     matching module-hook expectations; previously only FWDIR was checked.
#   - cleanup() records per-step results (UMOUNT_RES, RMDIR_RES) and failc() reports them
#     honestly: on a failed cleanup, say "cannot verify root firmware tree untouched" instead
#     of claiming it's untouched/revealed unconditionally.
#   - Existing caller-loop guard (`if ! /usr/bin/jwm1-firmware-late /sysroot; then ...`) prevents
#     switch_root fallthrough on a nonzero snippet exit; init-caller-integration.txt documents it.
# Every operation guarded; on ANY failure: exit 1 and the caller MUST NOT switch_root.
# Test seams (production defaults in parentheses): JWM1_MOUNTS (/proc/mounts),
# JWM1_VENDORFW (/vendorfw).
# SPDX-License-Identifier: MIT
set -u

ROOT=${1:?jwm1 vendorfw: root mountpoint argument required (production caller passes /sysroot)}
MOUNTS=${JWM1_MOUNTS:-/proc/mounts}
VFW=${JWM1_VENDORFW:-/vendorfw}

fail() {
    echo "jwm1 vendorfw: FAIL: $*" >&2
    exit 1
}

UMOUNT_RES=
RMDIR_RES=

cleanup() {
    if [ "${mounted:-0}" = 1 ]; then
        if umount "$DEST" 2>/dev/null; then UMOUNT_RES=ok; else UMOUNT_RES=failed; fi
    fi
    if [ "${created:-0}" = 1 ]; then
        if rmdir "$DEST" 2>/dev/null; then RMDIR_RES=ok; else RMDIR_RES=failed; fi
    fi
}

failc() {
    cleanup
    local msg="jwm1 vendorfw: FAIL: $*"
    msg="$msg  cleanup: umount=${UMOUNT_RES:-(not-requested)} rmdir=${RMDIR_RES:-(not-requested)}"
    if [ "$UMOUNT_RES" = failed ] || [ "$RMDIR_RES" = failed ]; then
        msg="$msg - cannot verify root firmware tree untouched; caller MUST stop before switch_root"
    else
        msg="$msg - real-root firmware tree either untouched or revealed intact per tmpfs reveal semantics"
    fi
    echo "$msg" >&2
    exit 1
}

# --- inputs ---------------------------------------------------------------
[ -d "$VFW" ] || failc "$VFW missing in initramfs"
[ -f "$VFW/.vendorfw.sha256" ] || failc "$VFW/.vendorfw.sha256 missing"
[ -f "$VFW/.vendorfw.manifest" ] || failc "$VFW/.vendorfw.manifest missing"

# --- mounts source readability first -------------------------------------
[ -r "$MOUNTS" ] || failc "mounts file $MOUNTS not readable"

# --- ROOT must be a real dir ------------------------------------------------
[ -d "$ROOT" ] || failc "$ROOT missing"
[ ! -L "$ROOT" ] || failc "$ROOT is a symlink (target confusion; real-dir expected)"

# --- canonical firmware dir (reject unexpected symlink ancestors) --------
created=0
mounted=0
if [ -L "$ROOT/lib" ]; then
    _t=$(readlink "$ROOT/lib")
    [ "$_t" = "usr/lib" ] || failc "unexpected /lib symlink target: $_t"
    FWDIR=$ROOT/usr/lib/firmware
    # merged-usr: /usr and /usr/lib must also be real dirs (matching module-hook expectations)
    [ -d "$ROOT/usr" ] && [ ! -L "$ROOT/usr" ] || failc "$ROOT/usr missing or a symlink"
    [ -d "$ROOT/usr/lib" ] && [ ! -L "$ROOT/usr/lib" ] || failc "$ROOT/usr/lib missing or a symlink"
else
    [ -d "$ROOT/lib" ] || failc "$ROOT/lib missing and not a symlink"
    FWDIR=$ROOT/lib/firmware
fi
[ ! -L "$FWDIR" ] || failc "$FWDIR itself is a symlink (target confusion)"
[ -d "$FWDIR" ] || failc "$FWDIR missing or not a directory"
DEST=$FWDIR/vendor
ALIAS=$ROOT/lib/firmware/vendor

# --- pre-write guards -----------------------------------------------------
# reject ANY pre-existing mount at destination, in canonical OR alias form
if grep -F " $DEST " "$MOUNTS" >/dev/null 2>&1; then
    failc "unexpected existing mount at $DEST"
fi
if [ "$ALIAS" != "$DEST" ] && grep -F " $ALIAS " "$MOUNTS" >/dev/null 2>&1; then
    failc "unexpected existing mount at alias $ALIAS"
fi
# destination state: existing dir = normal Asahi install (mount over, keep underneath);
# broken-or-real symlink and regular file = reject explicitly
if [ -L "$DEST" ]; then
    failc "symlink at $DEST (rejected even if broken)"
elif [ -f "$DEST" ]; then
    failc "regular file at $DEST"
elif [ -d "$DEST" ]; then
    created=0
else
    mkdir "$DEST" || failc "mkdir $DEST"
    created=1
fi

# --- mount, assert ownership, checked copy --------------------------------
mounted=1
mount -t tmpfs -o mode=0755,nosuid vendorfw "$DEST" || {
    mounted=0
    failc "tmpfs mount at $DEST"
}
grep -F "vendorfw $DEST tmpfs " "$MOUNTS" >/dev/null 2>&1 || {
    failc "mount assertion failed: $DEST is not our tmpfs"
}

cp -r "$VFW/." "$DEST/" || {
    failc "copy into tmpfs (root firmware tree state per cleanup line)"
}
CHECK=$(cd "$DEST" && sha256sum -c "$VFW/.vendorfw.sha256" 2>&1) || {
    printf '%s\n' "$CHECK" | grep -v ': OK$' >&2
    failc "checked copy mismatch (tmpfs unmounted per cleanup line)"
}

OKCOUNT=$(printf '%s\n' "$CHECK" | grep -c ': OK$')
echo "jwm1 vendorfw: persistent copy verified (${OKCOUNT}/217) dest=$DEST created_dir=${created:-0}"
exit 0
