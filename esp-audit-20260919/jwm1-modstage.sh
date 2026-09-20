#!/bin/sh
# jwm1-modstage: install the full 7.1.13-3-1-ARCH module tree into the real
# root from the initramfs copy, before switch_root. POSIX sh (busybox ash).
#
# Usage:
#   jwm1-modstage.sh manifest <tree-dir>
#       Emit the tree manifest on stdout. The exact same code path
#       re-verifies at run time, so the verifier cannot drift from the
#       generator. May be run from any working directory.
#   jwm1-modstage.sh stage <sysroot> <srcdir> <manifest-file>
#       Deploy <srcdir> (the initramfs-embedded tree) to
#       <sysroot>/usr/lib/modules/7.1.13-3-1-ARCH.
#
# Policy:
#   - The target version is pinned: srcdir basename must be 7.1.13-3-1-ARCH
#     and the target is <sysroot>/usr/lib/modules/<that name>. No other
#     target can ever be constructed; 7.1.6-1-1-ARCH is unreachable.
#   - Every path component under <sysroot> (usr, usr/lib, usr/lib/modules)
#     and srcdir/manifest themselves must be real, never symlinks.
#   - The manifest is a fixed, deterministic inventory: one line per entry,
#     "d <dir>" / "f <sha256> <file>" / "l <link> -> <target>", in a
#     deterministic LC_ALL=C glob-DFS order, emitted from inside a subshell
#     that cd-ed into the tree. Stage recomputes it and requires equality:
#     source, staged copy, and an existing target are all judged by the
#     same compare.
#   - Existing target identical -> left untouched, rc 0. Different -> abort
#     untouched, rc 15. Never overwrite. Nothing pre-existing is ever
#     deleted (including leftover stage dirs from crashed runs; they only
#     reduce free space, the space check aborts, a human decides).
#   - Space preflight: du -sk of the verified source plus a 2x margin,
#     compared against df -k available on the target filesystem. Both are
#     KiB by definition, so the units cannot be mixed. A copy that still
#     hits ENOSPC aborts via the copy's exit status and the post-copy
#     manifest verify.
#   - The copy goes to a unique mktemp -d dir on the SAME filesystem as the
#     target (mode 0700, unpredictable name), is fully verified, then one
#     rename. All scratch files live in a private mktemp -d workdir.
#   - No raw device or filesystem writes; no mount, no modprobe, no boot.
#
# Exit codes: 0 ok; 10 usage; 11 environment guard (bad path, symlink where
# a dir is required, missing mktemp); 12 source tree/manifest invalid;
# 13 insufficient space; 14 copy or copy-verification failure;
# 15 existing target differs (left untouched); 16 rename/finish failure.

readonly PINNED_VERSION='7.1.13-3-1-ARCH'
# Deterministic glob ordering and tool output; set before any expansion.
export LC_ALL=C

err() { echo "jwm1-modstage: ERROR: $*" >&2; }
usage() { err "usage: $0 manifest <tree-dir> | stage <sysroot> <srcdir> <manifest>"; exit 10; }

WORK=''; STAGE_TN=''; STAGE_CREATED=0
finish() {
    [ "$STAGE_CREATED" -eq 1 ] && rm -rf "$STAGE_TN"
    [ -n "$WORK" ] && [ -d "$WORK" ] && rm -rf "$WORK"
    exit "${1:-0}"
}
trap 'finish $?' EXIT

# emit_manifest <tree-dir>: inventory on stdout, rc 0 iff the tree could be
# walked and hashed completely. The whole walk runs inside one subshell that
# has cd-ed into the tree, so output never depends on the caller's cwd.
# The walk is a recursive glob DFS under LC_ALL=C: the candidate initramfs
# busybox (v1.36.1, 147 applets) has no `find`, and glob expansion inside
# ash is collate-sorted, so the order is deterministic across machines.
# An entry that is none of dir/file/symlink is rejected outright (rc 12): a
# valid manifest therefore only ever contains d/f/l lines.
emit_manifest() {
    [ -d "$1" ] && [ ! -L "$1" ] || { err "manifest: not a directory: $1"; return 11; }
    (
        cd "$1" || exit 11
        # $1 = directory relative to the tree root ("." at the root).
        walk_emit() {
            # Unmatched globs stay literal; [ -e ]/[ -L ] filters them out.
            for p in "$1"/* "$1"/.[!.]* "$1"/..?*; do
                [ -e "$p" ] || [ -L "$p" ] || continue
                rel=${p#./}
                if [ -L "$rel" ]; then
                    t=$(readlink "$rel") || exit 12
                    printf 'l %s -> %s\n' "$rel" "$t" || exit 12
                elif [ -f "$rel" ]; then
                    h=$(sha256sum "$rel") || exit 12
                    printf 'f %s %s\n' "${h%% *}" "$rel" || exit 12
                elif [ -d "$rel" ]; then
                    printf 'd %s\n' "$rel" || exit 12
                    walk_emit "$rel"
                else
                    err "unexpected entry (not dir/file/symlink): $rel"
                    exit 12
                fi
            done
        }
        walk_emit "."
    )
}

# verify_tree <tree-dir> <manifest-file>: rc 0 iff the recomputed inventory
# equals the manifest. The candidate busybox has no `cmp`; the private
# workdir files are compared by sha256 instead.
verify_tree() {
    emit_manifest "$1" > "$WORK/got" || return 12
    _vh=$(sha256sum "$WORK/got") || return 12
    _wh=$(sha256sum "$2") || return 12
    [ "${_vh%% *}" = "${_wh%% *}" ]
}

# kib_free <dir>: available KiB on the filesystem holding <dir>, or empty.
# df -kP is required: without -P both busybox and GNU df wrap long
# filesystem names onto their own line, which shifts every column.
kib_free() {
    set -- $(df -kP "$1" | tail -n 1)
    case "$4" in ''|*[!0-9]*) return 1 ;; esac
    printf '%s\n' "$4"
}

# real_dir_under <base> <comp...>: every component must exist as a real
# directory under <base>; a symlink, file, or absence anywhere fails.
real_dir_under() {
    _rd="$1"; shift
    for _rd_c in "$@"; do
        _rd="$_rd/$_rd_c"
        if [ ! -d "$_rd" ] || [ -L "$_rd" ]; then
            err "required dir missing or symlink: $_rd"
            return 1
        fi
    done
    return 0
}

cmd_stage() {
    _sysroot="$1"; _src="$2"; _mf="$3"

    command -v mktemp >/dev/null || { err "mktemp applet missing"; exit 11; }

    [ -d "$_sysroot" ] && [ ! -L "$_sysroot" ] || { err "bad sysroot: $_sysroot"; exit 11; }
    real_dir_under "$_sysroot" usr lib modules || exit 11
    MODS="$_sysroot/usr/lib/modules"

    [ -d "$_src" ] && [ ! -L "$_src" ] || { err "bad source tree: $_src"; exit 11; }
    [ -f "$_mf" ] && [ ! -L "$_mf" ] || { err "bad manifest: $_mf"; exit 11; }

    _src=${_src%/}
    VERSION=${_src##*/}
    [ "$VERSION" = "$PINNED_VERSION" ] || { err "source basename is not $PINNED_VERSION: $VERSION"; exit 11; }
    TARGET="$MODS/$PINNED_VERSION"

    # An existing target must match exactly (leave untouched) or we abort.
    if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
        [ -d "$TARGET" ] && [ ! -L "$TARGET" ] || { err "target exists but is not a real dir: $TARGET"; exit 11; }
        verify_tree "$TARGET" "$_mf" || { err "target exists with different content; left untouched: $TARGET"; exit 15; }
        echo "jwm1-modstage: $PINNED_VERSION already installed and valid; left untouched"
        exit 0
    fi

    # Source must match the manifest exactly before anything is written.
    verify_tree "$_src" "$_mf" || { err "source tree fails manifest verification"; exit 12; }

    # Space preflight in KiB end to end: df -k available vs 2x the du -sk of
    # the verified source plus 1MiB headroom.
    set -- $(du -sk "$_src") || { err "cannot measure source size"; exit 12; }
    src_kib=$1
    case "$src_kib" in ''|*[!0-9]*) err "bad du output"; exit 12 ;; esac
    avail_kib=$(kib_free "$MODS") || { err "cannot read free space"; exit 13; }
    need_kib=$(( src_kib * 2 + 1024 ))
    [ "$avail_kib" -ge "$need_kib" ] || { err "insufficient space: need ${need_kib}KiB, have ${avail_kib}KiB"; exit 13; }

    # Stage into a unique temp dir on the same filesystem, then one rename.
    STAGE_TN=$(mktemp -d "$MODS/.jwm1-modstage.XXXXXX") || { err "cannot create stage dir in $MODS"; exit 14; }
    STAGE_CREATED=1
    [ -d "$STAGE_TN" ] && [ ! -L "$STAGE_TN" ] || { err "stage dir not a real dir"; exit 14; }

    cp -a "$_src"/. "$STAGE_TN"/ || { err "copy failed"; exit 14; }
    [ -d "$STAGE_TN" ] && [ ! -L "$STAGE_TN" ] || { err "stage dir damaged during copy"; exit 14; }
    verify_tree "$STAGE_TN" "$_mf" || { err "staged copy fails manifest verification"; exit 14; }

    mv "$STAGE_TN" "$TARGET" || { err "rename failed"; exit 16; }
    STAGE_CREATED=0
    [ -d "$TARGET" ] || { err "target missing after rename"; exit 16; }
    sync
    echo "jwm1-modstage: installed $PINNED_VERSION into $TARGET"
    exit 0
}

[ $# -ge 2 ] || usage
WORK=$(mktemp -d "${TMPDIR:-/tmp}/jwm1-modstage-work.XXXXXX") || { err "cannot create workdir"; exit 11; }
case "$1" in
    manifest) [ $# -eq 2 ] || usage; emit_manifest "$2" || exit $? ;;
    stage)    [ $# -eq 4 ] || usage; cmd_stage "$2" "$3" "$4" ;;
    *)        usage ;;
esac
