#!/bin/sh
# Regression for jwm1-modstage.sh. Runs the production script ONLY through
# "$BUSYBOX ash" and ONLY against mktemp fixture roots — never system paths,
# never a real /usr/lib/modules, never a real /sysroot. Every scenario
# asserts precise exit codes and filesystem outcomes, including that the
# 7.1.6 sentinel and any pre-existing target are byte-unchanged.
#
# Env:
#   JWM1_MODSTAGE_BUSYBOX   busybox binary to test with (default: busybox)
#   REAL_TREE=<dir>         also run a full-size deploy from this tree
#                           (read-only source; output still fixture-only)
#
# Exit: 0 all pass, 1 any failure.

set -u

BUSYBOX=${JWM1_MODSTAGE_BUSYBOX:-busybox}
SCRIPT=$(cd "$(dirname "$0")" && pwd)/jwm1-modstage.sh
PINNED=7.1.13-3-1-ARCH
PASS=0; FAIL=0

say()  { printf '%s\n' "$*"; }
ok()   { PASS=$((PASS + 1)); say "  PASS: $*"; }
bad()  { FAIL=$((FAIL + 1)); say "  FAIL: $*"; }
# assert_eq <what> <want> <got>
assert_eq() {
    if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (want '$2' got '$3')"; fi
}

# ---------- precheck: real busybox, ash applet, required applets ----------
[ -f "$SCRIPT" ] || { say "FATAL: $SCRIPT not found"; exit 1; }
command -v "$BUSYBOX" >/dev/null 2>&1 || { say "FATAL: busybox not found: $BUSYBOX"; exit 1; }
"$BUSYBOX" ash -c ':' 2>/dev/null || { say "FATAL: $BUSYBOX has no working ash applet"; exit 1; }
APL=$("$BUSYBOX" --list 2>/dev/null) || { say "FATAL: $BUSYBOX --list failed"; exit 1; }
# Applets the production script actually invokes; the candidate initramfs
# busybox has no find/cmp, so the script must not depend on them.
for a in mktemp sha256sum readlink df du cp mv rm tail sync; do
    echo "$APL" | grep -qx "$a" || { say "FATAL: busybox missing applet: $a"; exit 1; }
done

BASE=$(mktemp -d "${TMPDIR:-/tmp}/jwm1-sms-regress.XXXXXX") || exit 1
TMPDIR="$BASE/tmp"; export TMPDIR
mkdir -p "$TMPDIR"
trap 'rm -rf "$BASE"' EXIT

# Private bin dir of symlinks to the busybox applets, so the production
# script's PATH holds ONLY busybox applets (+ scenario mocks) and can never
# fall back to host GNU tools.
BUSYBOXBIN="$BASE/busybox-bin"
mkdir -p "$BUSYBOXBIN"
for a in $APL; do ln -s "$(command -v "$BUSYBOX")" "$BUSYBOXBIN/$a"; done
# Self-check: with this PATH alone the script's tools resolve, and df -kP
# parses (busybox df wraps long filesystem names in non-P format).
if ! PATH="$BUSYBOXBIN" "$BUSYBOX" ash -c 'command -v df >/dev/null && df -kP / >/dev/null 2>&1'; then
    say "FATAL: busybox applet PATH (df -kP) not usable: $BUSYBOXBIN"
    exit 1
fi

# ---------- fixture builders (all paths under $BASE) ----------
# build_source <dir>: synthetic tree with the pinned version name.
build_source() {
    mkdir -p "$1/$PINNED/kernel/fs/btrfs" \
             "$1/$PINNED/kernel/crypto/krb5" \
             "$1/$PINNED/dtbs/all-empty" \
             "$1/$PINNED"
    printf 'btrfs-bytes-\001\002\003' > "$1/$PINNED/kernel/fs/btrfs/btrfs.ko"
    printf 'ccm-bytes' > "$1/$PINNED/kernel/crypto/ccm.ko"
    printf 'krb5-bytes' > "$1/$PINNED/kernel/crypto/krb5/krb5.ko"
    : > "$1/$PINNED/kernel/fs/btrfs/empty.ko"
    yes X | head -c 8192 > "$1/$PINNED/kernel/bigblob.ko"
    printf 'dtb-t8103' > "$1/$PINNED/dtbs/t8103-j293.dtb"
    ln -s krb5/krb5.ko "$1/$PINNED/kernel/crypto/krb5-link.ko"
}

# build_root <dir>: fixture sysroot with a 7.1.6 sentinel tree.
build_root() {
    mkdir -p "$1/usr/lib/modules/7.1.6-1-1-ARCH/kernel"
    printf 'sentinel-7.1.6-do-not-touch' > "$1/usr/lib/modules/7.1.6-1-1-ARCH/kernel/sentinel.ko"
}

# check_sentinel <root>: 7.1.6 sentinel byte-unchanged and alone.
check_sentinel() {
    [ "$(cat "$1/usr/lib/modules/7.1.6-1-1-ARCH/kernel/sentinel.ko")" = 'sentinel-7.1.6-do-not-touch' ] \
        && [ "$(find "$1/usr/lib/modules/7.1.6-1-1-ARCH" -type f | wc -l)" = 1 ]
}

# no_leftover_stage <root>: no .jwm1-modstage.* entries remain in modules/.
no_leftover_stage() {
    find "$1/usr/lib/modules" -maxdepth 1 -name '.jwm1-modstage.*' | grep -q . && return 1
    return 0
}

# run_stage <root> <srcdir> <manifest> [mockbindir] -> prints status only.
# Production PATH = optional mock dir + busybox applet links ONLY.
run_stage() {
    _rs_path="$BUSYBOXBIN"
    [ -n "${4:-}" ] && _rs_path="$4:$BUSYBOXBIN"
    ( cd "$BASE" && PATH="$_rs_path" "$BUSYBOX" ash "$SCRIPT" stage "$1" "$2" "$3" \
        >"$BASE/last.out" 2>"$BASE/last.err" )
    echo $?
}

# gen_manifest <srcdir> <outfile> [cwd] -> returns real status; log on stderr
gen_manifest() {
    ( cd "${3:-$BASE}" && "$BUSYBOX" ash "$SCRIPT" manifest "$1" > "$2" )
}

# scenario scaffolding: fresh root+src per scenario
new_case() {
    rm -rf "$BASE/case"
    mkdir -p "$BASE/case"
    build_root "$BASE/case/root"
    build_source "$BASE/case/src"
    gen_manifest "$BASE/case/src/$PINNED" "$BASE/case/src.manifest" \
        || { say "FATAL: fixture manifest generation failed"; exit 1; }
}

# =====================================================================
say "== S0 manifest shape, determinism, cwd independence =="
new_case
rc1=0; gen_manifest "$BASE/case/src/$PINNED" "$BASE/case/m1" "$BASE" || rc1=$?
rc2=0; gen_manifest "$BASE/case/src/$PINNED" "$BASE/case/m2" "/" || rc2=$?
assert_eq "manifest rc from fixture cwd" 0 "$rc1"
assert_eq "manifest rc from / cwd" 0 "$rc2"
if cmp -s "$BASE/case/m1" "$BASE/case/m2"; then ok "manifest identical from different cwds"; else bad "manifest differs across cwds"; fi
if grep -qx 'd \.' "$BASE/case/m1"; then bad "manifest contains the tree root as an entry"; else ok "no tree-root entry"; fi
if grep -q '^#' "$BASE/case/m1"; then bad "manifest contains comment/footer lines"; else ok "no footer/comment lines"; fi
# Manifest order is a DFS (deterministic, reproduced by the same code at
# run time). Completeness is checked as a SET against an independent host
# find walk: every entry present exactly once, nothing extra.
( cd "$BASE/case/src/$PINNED" && find . -mindepth 1 | sed 's|^\./||' | LC_ALL=C sort ) > "$BASE/case/ref.paths"
LC_ALL=C awk '{ if ($1 == "f") print $3; else print $2 }' "$BASE/case/m1" | LC_ALL=C sort > "$BASE/case/got.paths"
if cmp -s "$BASE/case/ref.paths" "$BASE/case/got.paths"; then
    ok "manifest covers exactly the host-find entry set"
else
    bad "manifest entry set differs from host find walk"
fi
if grep -q "^f [0-9a-f]\{64\} dtbs/t8103-j293.dtb$" "$BASE/case/m1" \
   && grep -q "^l kernel/crypto/krb5-link.ko -> krb5/krb5.ko$" "$BASE/case/m1" \
   && grep -q "^d dtbs/all-empty$" "$BASE/case/m1"; then
    ok "manifest has hash, symlink, and empty-dir entries"
else
    bad "manifest missing expected entry forms"
fi

# =====================================================================
say "== S1 happy deploy: absent target =="
new_case
rc=$(run_stage "$BASE/case/root" "$BASE/case/src/$PINNED" "$BASE/case/src.manifest")
assert_eq "stage rc" 0 "$rc"
[ -d "$BASE/case/root/usr/lib/modules/$PINNED" ] && ok "target dir created" || bad "target dir missing"
"$BUSYBOX" ash "$SCRIPT" manifest "$BASE/case/root/usr/lib/modules/$PINNED" > "$BASE/case/deployed.manifest" 2>/dev/null
if cmp -s "$BASE/case/deployed.manifest" "$BASE/case/src.manifest"; then ok "deployed tree byte-verifies against manifest"; else bad "deployed tree differs from manifest"; fi
if diff -r "$BASE/case/src/$PINNED" "$BASE/case/root/usr/lib/modules/$PINNED" > "$BASE/case/diff.out" 2>&1; then ok "deployed tree == source (diff -r)"; else bad "deployed tree != source: $(head -c 300 "$BASE/case/diff.out")"; fi
assert_eq "no leftover stage dirs" "" "$(find "$BASE/case/root/usr/lib/modules" -maxdepth 1 -name '.jwm1-modstage.*')"
check_sentinel "$BASE/case/root" && ok "7.1.6 sentinel intact" || bad "7.1.6 sentinel damaged"

# =====================================================================
say "== S2 idempotent: existing exact target left untouched =="
new_case
run_stage "$BASE/case/root" "$BASE/case/src/$PINNED" "$BASE/case/src.manifest" >/dev/null
before=$(stat -c '%i %Y' "$BASE/case/root/usr/lib/modules/$PINNED")
rc=$(run_stage "$BASE/case/root" "$BASE/case/src/$PINNED" "$BASE/case/src.manifest")
assert_eq "second stage rc" 0 "$rc"
after=$(stat -c '%i %Y' "$BASE/case/root/usr/lib/modules/$PINNED")
assert_eq "target inode+mtime unchanged (untouched)" "$before" "$after"
no_leftover_stage "$BASE/case/root" && ok "no leftover stage dirs" || bad "leftover stage dirs"
check_sentinel "$BASE/case/root" && ok "7.1.6 sentinel intact" || bad "7.1.6 sentinel damaged"

# =====================================================================
say "== S3 existing differing target: abort, untouched =="
new_case
run_stage "$BASE/case/root" "$BASE/case/src/$PINNED" "$BASE/case/src.manifest" >/dev/null
printf 'TAMPERED' > "$BASE/case/root/usr/lib/modules/$PINNED/kernel/crypto/ccm.ko"
rc=$(run_stage "$BASE/case/root" "$BASE/case/src/$PINNED" "$BASE/case/src.manifest")
assert_eq "stage rc on differing target" 15 "$rc"
assert_eq "tampered target byte preserved" "TAMPERED" "$(cat "$BASE/case/root/usr/lib/modules/$PINNED/kernel/crypto/ccm.ko")"
no_leftover_stage "$BASE/case/root" && ok "no leftover stage dirs" || bad "leftover stage dirs"
check_sentinel "$BASE/case/root" && ok "7.1.6 sentinel intact" || bad "7.1.6 sentinel damaged"

# =====================================================================
say "== S4 missing source =="
new_case
rm -rf "$BASE/case/src/$PINNED"
rc=$(run_stage "$BASE/case/root" "$BASE/case/src/$PINNED" "$BASE/case/src.manifest")
assert_eq "stage rc missing source" 11 "$rc"
[ -e "$BASE/case/root/usr/lib/modules/$PINNED" ] && bad "target created despite missing source" || ok "no target created"
no_leftover_stage "$BASE/case/root" && ok "no leftover stage dirs" || bad "leftover stage dirs"

# =====================================================================
say "== S5 corrupt (truncated) manifest =="
new_case
head -n 2 "$BASE/case/src.manifest" > "$BASE/case/bad.manifest"
rc=$(run_stage "$BASE/case/root" "$BASE/case/src/$PINNED" "$BASE/case/bad.manifest")
assert_eq "stage rc corrupt manifest" 12 "$rc"
[ -e "$BASE/case/root/usr/lib/modules/$PINNED" ] && bad "target created despite corrupt manifest" || ok "no target created"
no_leftover_stage "$BASE/case/root" && ok "no leftover stage dirs" || bad "leftover stage dirs"

# =====================================================================
say "== S6 unexpected entry type (fifo) in source =="
new_case
mkfifo "$BASE/case/src/$PINNED/kernel/fs/btrfs/fifo.ko"
rc=$(run_stage "$BASE/case/root" "$BASE/case/src/$PINNED" "$BASE/case/src.manifest")
assert_eq "stage rc unexpected entry" 12 "$rc"
[ -e "$BASE/case/root/usr/lib/modules/$PINNED" ] && bad "target created despite unexpected entry" || ok "no target created"
no_leftover_stage "$BASE/case/root" && ok "no leftover stage dirs" || bad "leftover stage dirs"

# =====================================================================
say "== S7 symlink ancestor under sysroot refused =="
new_case
mkdir -p "$BASE/case/decoy/usr/lib/modules"
printf 'decoy-sentinel' > "$BASE/case/decoy/usr/lib/modules/marker"
mv "$BASE/case/root/usr/lib" "$BASE/case/root/real-lib"
ln -s "$BASE/case/decoy/usr/lib" "$BASE/case/root/usr/lib"
rc=$(run_stage "$BASE/case/root" "$BASE/case/src/$PINNED" "$BASE/case/src.manifest")
assert_eq "stage rc symlink ancestor" 11 "$rc"
assert_eq "decoy untouched" "decoy-sentinel" "$(cat "$BASE/case/decoy/usr/lib/modules/marker")"
[ -e "$BASE/case/decoy/usr/lib/modules/$PINNED" ] && bad "wrote through symlink ancestor" || ok "nothing written through symlink"
[ -L "$BASE/case/root/usr/lib" ] && ok "symlink ancestor preserved" || bad "symlink ancestor altered"

# =====================================================================
say "== S8 target exists as symlink: refused, symlink kept =="
new_case
ln -s /nonexistent-jwm1 "$BASE/case/root/usr/lib/modules/$PINNED"
rc=$(run_stage "$BASE/case/root" "$BASE/case/src/$PINNED" "$BASE/case/src.manifest")
assert_eq "stage rc symlink target" 11 "$rc"
[ -L "$BASE/case/root/usr/lib/modules/$PINNED" ] && ok "target symlink preserved" || bad "target symlink altered"
check_sentinel "$BASE/case/root" && ok "7.1.6 sentinel intact" || bad "7.1.6 sentinel damaged"

# =====================================================================
say "== S9 wrong version basename: pinned constant refuses =="
new_case
mv "$BASE/case/src/$PINNED" "$BASE/case/src/7.1.6-1-1-ARCH"
rc=$(run_stage "$BASE/case/root" "$BASE/case/src/7.1.6-1-1-ARCH" "$BASE/case/src.manifest")
assert_eq "stage rc wrong basename" 11 "$rc"
[ -e "$BASE/case/root/usr/lib/modules/7.1.6-1-1-ARCH" ] || bad "7.1.6 dir vanished?!"
check_sentinel "$BASE/case/root" && ok "7.1.6 sentinel intact (nothing staged into it)" || bad "7.1.6 sentinel damaged"

# =====================================================================
say "== S10 failed copy (real: ulimit -f), rc14, stage dir cleaned =="
new_case
rc=$( ( ulimit -f 2 2>/dev/null
        cd "$BASE" && PATH="$BUSYBOXBIN" "$BUSYBOX" ash "$SCRIPT" stage \
            "$BASE/case/root" "$BASE/case/src/$PINNED" "$BASE/case/src.manifest" \
            >"$BASE/last.out" 2>"$BASE/last.err"
      ) ; echo $? )
assert_eq "stage rc failed copy" 14 "$rc"
no_leftover_stage "$BASE/case/root" && ok "failed-copy stage dir cleaned" || bad "stage dir left after copy failure"
[ -e "$BASE/case/root/usr/lib/modules/$PINNED" ] && bad "target created despite copy failure" || ok "no target created"
gen_manifest "$BASE/case/src/$PINNED" "$BASE/case/src.after.manifest" \
    && cmp -s "$BASE/case/src.manifest" "$BASE/case/src.after.manifest" \
    && ok "source unchanged after failed copy" || bad "source altered by failed copy"
check_sentinel "$BASE/case/root" && ok "7.1.6 sentinel intact" || bad "7.1.6 sentinel damaged"

# =====================================================================
say "== S11 space-preflight abort (13): SKIPPED =="
say "  SKIP: cannot create a constrained filesystem without root, and busybox"
say "  ash resolves applet names before PATH (verified by probe), so df/cp"
say "  PATH-mocks never load. The 13 branch is one numeric compare; the real"
say "  df parse (the actual past failure) is exercised by every deploy scenario."

# =====================================================================

# =====================================================================
say "== S12 foreign stage-like dir is never deleted =="
new_case
mkdir -p "$BASE/case/root/usr/lib/modules/.jwm1-modstage.stale-data/kernel"
printf 'someone-elses-data' > "$BASE/case/root/usr/lib/modules/.jwm1-modstage.stale-data/kernel/x.ko"
rc=$(run_stage "$BASE/case/root" "$BASE/case/src/$PINNED" "$BASE/case/src.manifest")
assert_eq "deploy succeeds alongside foreign dir" 0 "$rc"
assert_eq "foreign stage-like dir preserved" "someone-elses-data" \
    "$(cat "$BASE/case/root/usr/lib/modules/.jwm1-modstage.stale-data/kernel/x.ko")"
check_sentinel "$BASE/case/root" && ok "7.1.6 sentinel intact" || bad "7.1.6 sentinel damaged"

# =====================================================================
say "== S13 real full-size tree (optional, REAL_TREE) =="
if [ -n "${REAL_TREE:-}" ] && [ -d "${REAL_TREE:-}" ]; then
    rm -rf "$BASE/real"
    mkdir -p "$BASE/real"
    build_root "$BASE/real/root"
    start=$(date +%s)
    gen_manifest "$REAL_TREE" "$BASE/real/manifest" >/dev/null
    mrc=$?
    mid=$(date +%s)
    assert_eq "real-tree manifest rc" 0 "$mrc"
    assert_eq "real-tree manifest lines" "$(find "$REAL_TREE" -mindepth 1 | wc -l)" "$(wc -l < "$BASE/real/manifest")"
    rc=$(run_stage "$BASE/real/root" "$REAL_TREE" "$BASE/real/manifest")
    end=$(date +%s)
    assert_eq "real-tree stage rc" 0 "$rc"
    "$BUSYBOX" ash "$SCRIPT" manifest "$BASE/real/root/usr/lib/modules/$PINNED" > "$BASE/real/deployed.manifest" 2>/dev/null
    if cmp -s "$BASE/real/deployed.manifest" "$BASE/real/manifest"; then ok "real deployed tree verifies"; else bad "real deployed tree mismatch"; fi
    say "  timing: manifest $((mid - start))s, stage $((end - mid))s, tree $(du -sk "$REAL_TREE" | cut -f1)KiB"
    check_sentinel "$BASE/real/root" && ok "7.1.6 sentinel intact" || bad "7.1.6 sentinel damaged"
else
    say "  skipped (set REAL_TREE=<dir> to enable)"
fi

# =====================================================================
say ""
say "======== RESULTS: PASS=$PASS FAIL=$FAIL ========"
[ "$FAIL" -eq 0 ]
