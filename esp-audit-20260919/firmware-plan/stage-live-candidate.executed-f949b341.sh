#!/bin/sh
# jwm1 LIVE CANDIDATE staging executor -- v2 (Main review fixes applied)
# POSIX sh (macOS /bin/sh compatible): no process substitution, no bashisms,
# native shasum -a 256 (auto-fallback sha256sum for fixture runs on Linux),
# full 64-hex hash compares everywhere, backup REUSE REFUSAL on mismatch,
# free-space check, sync before every readback and after every rename,
# exact-hash checked cfg, final per-file readback table.
# --selftest runs an offline fixture test of the copy/backup/refusal logic.
# NO nextonly arm, NO reboot, NO raw FAT writes. Execution requires Main authorization.
# SPDX-License-Identifier: MIT
set -u

# ALL hash pins are test-overridable for fixture runs (production defaults = real on-device
# identities). Production runs MUST NOT set these env vars.
VUUID=919DE1C3-2EC7-3B75-ACA0-86DE382AD2F7
BOOT_SHA=${BOOT_SHA:-566227f96ea94bafac65ee6c997da0ba98be6f20479c3619ba1b8b739d156f33}
VML_SHA=${VML_SHA:-e339c992eef9bb879680513efee54aec68b39f14cba78f96b6db3a5c1d68533c}
INITRD_SHA=${INITRD_SHA:-b4a24461669358f82db63d78e3d5f5fe72b9160b8dd66301190d60506e0a2a6e}
BOOT_ORIG_SHA=${BOOT_ORIG_SHA:-d1ee639c160cdabdde206d8ef5b91ab7a58f132033b6fe91d92623bf028d3aa2}
BOOTAA64_SHA=${BOOTAA64_SHA:-9d6e751045e794733a672db7f6acf73a2b137e6488653c5eba93d013c45a1065}
VML_REC_SHA=${VML_REC_SHA:-ee36d989d62f2dd498b818e15c2044350c79d814a2017ffca61fdc2ad1aa95b6}
INITRD_REC_SHA=${INITRD_REC_SHA:-de4ae60473443e2b2184dce8b73be270ded13f21b704f7d568145bbb000d650c}

die() { echo "STAGE-STOP: $*" >&2; exit 1; }

detect_sha() {
    if command -v shasum >/dev/null 2>&1; then
        SHACMD="shasum -a 256"
    elif command -v sha256sum >/dev/null 2>&1; then
        SHACMD="sha256sum"
    else
        die "no sha256 tool available (need shasum or sha256sum)"
    fi
}

hash_file() {  # $1=file ; prints hash ; rc!=0 if missing/unreadable
    [ -f "$1" ] && [ -r "$1" ] || return 1
    $SHACMD "$1" 2>/dev/null | awk '{print $1}'
}

verify_hash() {  # $1=file $2=expected_full_sha $3=label ; EXITS the script on mismatch
    _vh_file=$1; _vh_want=$2; _vh_label=$3
    [ -f "$_vh_file" ] || { echo "STAGE-STOP: $_vh_label: missing ($_vh_file)" >&2; exit 1; }
    _vh_got=$(hash_file "$_vh_file") || { echo "STAGE-STOP: $_vh_label: unreadable" >&2; exit 1; }
    [ "$_vh_got" = "$_vh_want" ] || { echo "STAGE-STOP: $_vh_label: hash drift (got=$_vh_got want=$_vh_want)" >&2; exit 1; }
}

# backup_existing SRC DST EXPECTED LABEL
#  - dst exists: verify full hash == expected (reuse); mismatch = REFUSE (die)
#  - dst absent: copy src->dst, sync, readback full hash == expected
backup_existing() {
    _b_src=$1; _b_dst=$2; _b_want=$3; _b_label=$4
    if [ -e "$_b_dst" ]; then
        _b_got=$(hash_file "$_b_dst") || _b_got=""
        if [ -z "$_b_got" ]; then echo "STAGE-STOP: $_b_label: existing backup unreadable -- REFUSED" >&2; return 1; fi
        if [ "$_b_got" != "$_b_want" ]; then echo "STAGE-STOP: $_b_label: existing backup hash mismatch (got=$_b_got want=$_b_want) -- REUSE REFUSED" >&2; return 1; fi
        echo "  backup reused (verified): $_b_label"
        return 0
    fi
    cp -p "$_b_src" "$_b_dst" || { echo "STAGE-STOP: $_b_label: backup copy failed" >&2; return 1; }
    sync
    _b_got=$(hash_file "$_b_dst") || _b_got=""
    if [ -z "$_b_got" ]; then echo "STAGE-STOP: $_b_label: backup readback failed" >&2; return 1; fi
    if [ "$_b_got" != "$_b_want" ]; then echo "STAGE-STOP: $_b_label: backup readback MISMATCH" >&2; return 1; fi
    echo "  backup created (verified): $_b_label"
}

# install_verified SRC DST EXPECTED LABEL  (temp + sync + readback + rename + sync + re-readback)
install_verified() {
    _i_src=$1; _i_dst=$2; _i_want=$3; _i_label=$4
    _i_tmp="$_i_dst.new.$$"
    [ -e "$_i_tmp" ] && { echo "STAGE-STOP: $_i_label: stale temp exists ($_i_tmp)" >&2; return 1; }
    cp "$_i_src" "$_i_tmp" || { echo "STAGE-STOP: $_i_label: temp copy failed" >&2; return 1; }
    sync
    _i_got=$(hash_file "$_i_tmp") || _i_got=""
    if [ -z "$_i_got" ] || [ "$_i_got" != "$_i_want" ]; then
        rm -f "$_i_tmp"
        echo "STAGE-STOP: $_i_label: temp readback failed/mismatch (got=${_i_got:-none} want=$_i_want)" >&2
        return 1
    fi
    mv -f "$_i_tmp" "$_i_dst" || { echo "STAGE-STOP: $_i_label: rename failed" >&2; return 1; }
    sync
    _i_got=$(hash_file "$_i_dst") || _i_got=""
    if [ -z "$_i_got" ]; then echo "STAGE-STOP: $_i_label: final readback failed" >&2; return 1; fi
    if [ "$_i_got" != "$_i_want" ]; then echo "STAGE-STOP: $_i_label: final readback MISMATCH" >&2; return 1; fi
    echo "  installed (verified): $_i_label"
}

# ---------------- fixture test (offline, no mounts) ----------------
selftest() {
    detect_sha
    T=$(mktemp -d /tmp/jwm1stage-selftest-XXXX)
    P=0; F=0
    t_ok()  { P=$((P+1)); echo "PASS: $1"; }
    t_bad() { F=$((F+1)); echo "FAIL: $1"; }

    printf 'payload-A\n' > "$T/src-a"
    A_SHA=$(hash_file "$T/src-a")
    printf 'payload-B\n' > "$T/src-b"
    B_SHA=$(hash_file "$T/src-b")

    # F1 backup fresh
    backup_existing "$T/src-a" "$T/dst-a" "$A_SHA" "F1" && t_ok "F1 backup fresh created+verified" || t_bad "F1"

    # F2 backup reuse (dst exists, hash matches) -- must succeed without touching src
    printf 'CHANGED\n' > "$T/src-a"
    if backup_existing "$T/src-b" "$T/dst-a" "$A_SHA" "F2" 2>/dev/null; then t_ok "F2 backup reuse accepted"; else t_bad "F2"; fi

    # F3 backup reuse REFUSAL (dst exists, hash mismatches)
    printf 'other\n' > "$T/dst-b"
    if backup_existing "$T/src-b" "$T/dst-b" "$B_SHA" "F3" 2>/dev/null; then t_bad "F3 refusal"; else t_ok "F3 backup mismatch REFUSED"; fi

    # F4 install happy
    install_verified "$T/src-b" "$T/inst-b" "$B_SHA" "F4" && t_ok "F4 install verified" || t_bad "F4"

    # F5 install drift refusal (wrong expected hash)
    printf 'x\n' > "$T/src-c"
    C_SHA=$(hash_file "$T/src-c")
    if install_verified "$T/src-c" "$T/inst-c" "0000000000000000000000000000000000000000000000000000000000000000" "F5" 2>/dev/null; then t_bad "F5 drift"; else
        [ ! -e "$T/inst-c" ] && t_ok "F5 drift refused, no dst left" || t_bad "F5 leftover tmp/dst"
    fi

    # F6 install missing src
    if install_verified "$T/does-not-exist" "$T/inst-d" "00" "F6" 2>/dev/null; then t_bad "F6"; else t_ok "F6 missing src refused"; fi

    echo "----"
    echo "selftest pass=$P fail=$F"
    rm -rf "$T"
    [ $F -eq 0 ]
}

case "${1:-}" in
    --selftest) detect_sha; selftest; exit $? ;;
esac

# ---------------- production staging ----------------
detect_sha

echo "== [0] volume identity by UUID =="
VINFO=$(mktemp /tmp/jwm1stage-vinfo-XXXXXX)
diskutil info "$VUUID" > "$VINFO" 2>&1 || die "volume $VUUID not present (diskutil info failed)"
grep -q "EFI - ASAHI" "$VINFO" || die "volume name mismatch (expected EFI - ASAHI)"
MPOINT=$(sed -n 's/.*Mount Point:[[:space:]]*//p' "$VINFO" | head -1)
[ -n "$MPOINT" ] && [ -d "$MPOINT" ] || die "volume not mounted; mount by UUID first per plan"
echo "  mount point: $MPOINT"

echo "== [0b] staged sources required =="
: "${STAGE_BOOT:?set STAGE_BOOT (staged clean boot.bin path)}"
: "${STAGE_VMLINUZ:?set STAGE_VMLINUZ (staged 7.1.13 vmlinuz path)}"
: "${STAGE_INITRD:?set STAGE_INITRD (staged 7.1.13 initrd path)}"
verify_hash "$STAGE_BOOT" "$BOOT_SHA" "staged boot.bin"
verify_hash "$STAGE_VMLINUZ" "$VML_SHA" "staged vmlinuz"
verify_hash "$STAGE_INITRD" "$INITRD_SHA" "staged initrd"

echo "== [0c] free space =="
AVAIL_KB=$(df -k "$MPOINT" | awk 'NR==2{print $4}')
NEED_KB=$(((98014376 + 34114048 + 6212626 + 33917440 + 19414040 + 6092721 + 552 + 4096) / 1024 + 2048))
[ "${AVAIL_KB:-0}" -ge "$NEED_KB" ] || die "insufficient free space: avail=${AVAIL_KB}K need>=${NEED_KB}K"
echo "  avail=${AVAIL_KB}K need>=${NEED_KB}K (conservative: new artifacts + all backup copies + cfg, 2 MiB margin)"

echo "== [1] fresh original hashes (full compare) =="
verify_hash "$MPOINT/m1n1/boot.bin" "$BOOT_ORIG_SHA" "original boot.bin"
verify_hash "$MPOINT/EFI/BOOT/BOOTAA64.EFI" "$BOOTAA64_SHA" "original BOOTAA64.EFI"
verify_hash "$MPOINT/grub-ane/VMLINUZ.REC" "$VML_REC_SHA" "original VMLINUZ.REC"
verify_hash "$MPOINT/grub-ane/INITRD.REC" "$INITRD_REC_SHA" "original INITRD.REC"
CFG_SHA=$(hash_file "$MPOINT/grub-ane/grub.cfg") || die "grub.cfg unreadable"
echo "  originals verified; current grub.cfg sha=$CFG_SHA"

echo "== [2] preserve originals (reuse-refusing backups) =="
backup_existing "$MPOINT/m1n1/boot.bin"        "$MPOINT/m1n1/boot.bin.d1ee-716"    "$BOOT_ORIG_SHA"  "boot.bin.d1ee-716" || exit 1
backup_existing "$MPOINT/grub-ane/VMLINUZ.REC" "$MPOINT/grub-ane/VMLINUZ.REC.716"  "$VML_REC_SHA"    "VMLINUZ.REC.716" || exit 1
backup_existing "$MPOINT/grub-ane/INITRD.REC"  "$MPOINT/grub-ane/INITRD.REC.716"   "$INITRD_REC_SHA" "INITRD.REC.716" || exit 1
backup_existing "$MPOINT/grub-ane/grub.cfg"    "$MPOINT/grub-ane/grub.cfg.pre-7113" "$CFG_SHA"       "grub.cfg.pre-7113" || exit 1

echo "== [3] install kernel pair =="
install_verified "$STAGE_VMLINUZ" "$MPOINT/grub-ane/VMLINUZ.7113" "$VML_SHA"    "VMLINUZ.7113" || exit 1
install_verified "$STAGE_INITRD"  "$MPOINT/grub-ane/INITRD.7113"  "$INITRD_SHA" "INITRD.7113" || exit 1

echo "== [4] install clean boot.bin =="
install_verified "$STAGE_BOOT" "$MPOINT/m1n1/boot.bin" "$BOOT_SHA" "boot.bin(566227f9)" || exit 1

echo "== [5] temporary candidate-default grub.cfg =="
HOST_CFG=$(mktemp /tmp/jwm1stage-cfg-XXXXXX)
cat > "$HOST_CFG" <<'CFG' || { rm -f "$HOST_CFG"; echo "STAGE-STOP: cfg host write failed" >&2; exit 1; }
set timeout=10
set default=0
terminal_output console
echo "GRUB cfg loaded: probing ESP 6C79-DC47"
search --no-floppy --fs-uuid --set=root 6C79-DC47
menuentry "Omarchy Linux 7.1.13 netfix (candidate)" {
	linux /grub-ane/VMLINUZ.7113 root=UUID=725346d2-f127-47bc-b464-9dd46155e8d6 rw rootflags=subvol=@ loglevel=7 plymouth.enable=0 rd.plymouth=0 systemd.show_status=1 panic=10
	initrd /grub-ane/INITRD.7113
}
menuentry "Omarchy Linux recovery (7.1.6 kernel+initrd from ESP)" {
	linux /grub-ane/VMLINUZ.REC root=UUID=725346d2-f127-47bc-b464-9dd46155e8d6 rw rootflags=subvol=@ loglevel=7 plymouth.enable=0 rd.plymouth=0 systemd.show_status=1
	initrd /grub-ane/INITRD.REC
}
CFG
_sync_rc=$?
[ "$_sync_rc" = "0" ] || { rm -f "$HOST_CFG"; die "cfg host sync failed (rc=$_sync_rc)"; }
[ -s "$HOST_CFG" ] || { rm -f "$HOST_CFG"; die "cfg host write produced empty file"; }
CFG_SHA_EXPECT=$(hash_file "$HOST_CFG") || { rm -f "$HOST_CFG"; die "cfg host hash failed"; }
[ -n "$CFG_SHA_EXPECT" ] || { rm -f "$HOST_CFG"; die "cfg host hash empty"; }
CFG_TMP="$MPOINT/grub-ane/.grub.cfg.new.$$"
cp "$HOST_CFG" "$CFG_TMP" || { rm -f "$HOST_CFG"; die "cfg copy failed"; }
sync
CFG_GOT=$(hash_file "$CFG_TMP") || CFG_GOT=""
if [ "$CFG_GOT" != "$CFG_SHA_EXPECT" ]; then rm -f "$CFG_TMP" "$HOST_CFG"; die "cfg copy readback mismatch"; fi
grep -q "panic=10" "$CFG_TMP" || { rm -f "$CFG_TMP" "$HOST_CFG"; die "cfg missing panic=10"; }
mv -f "$CFG_TMP" "$MPOINT/grub-ane/grub.cfg" || { rm -f "$HOST_CFG"; die "cfg rename failed"; }
sync
verify_hash "$MPOINT/grub-ane/grub.cfg" "$CFG_SHA_EXPECT" "grub.cfg(final, exact staged content)"
rm -f "$HOST_CFG"
echo "  grub.cfg installed, exact-hash verified (sha=$CFG_SHA_EXPECT)"

echo "== [6] final readback table =="
FAILS=0
verify_hash "$MPOINT/m1n1/boot.bin"                    "$BOOT_SHA"      "final boot.bin"               || FAILS=$((FAILS+1))
verify_hash "$MPOINT/m1n1/boot.bin.d1ee-716"           "$BOOT_ORIG_SHA" "final boot.bin.d1ee-716"      || FAILS=$((FAILS+1))
STOCK_BOOT_SHA=${STOCK_BOOT_SHA:-3945ed51f83224c09f3a837fa8bcb746fdd7db23b02cfb6b4ac7718b174311d1}
STOCK_BA64_SHA=${STOCK_BA64_SHA:-d5765e2caadedcf19c30361903bd047dc4059c41b23be53fa1002cd9287d2847}
verify_hash "$MPOINT/m1n1/boot.bin.stock-20260906"     "$STOCK_BOOT_SHA" "final boot.bin.stock" || FAILS=$((FAILS+1))
verify_hash "$MPOINT/grub-ane/VMLINUZ.7113"            "$VML_SHA"       "final VMLINUZ.7113"           || FAILS=$((FAILS+1))
verify_hash "$MPOINT/grub-ane/INITRD.7113"             "$INITRD_SHA"    "final INITRD.7113"            || FAILS=$((FAILS+1))
verify_hash "$MPOINT/grub-ane/VMLINUZ.REC"             "$VML_REC_SHA"   "final VMLINUZ.REC"            || FAILS=$((FAILS+1))
verify_hash "$MPOINT/grub-ane/VMLINUZ.REC.716"         "$VML_REC_SHA"   "final VMLINUZ.REC.716"        || FAILS=$((FAILS+1))
verify_hash "$MPOINT/grub-ane/INITRD.REC"              "$INITRD_REC_SHA" "final INITRD.REC"            || FAILS=$((FAILS+1))
verify_hash "$MPOINT/grub-ane/INITRD.REC.716"          "$INITRD_REC_SHA" "final INITRD.REC.716"        || FAILS=$((FAILS+1))
verify_hash "$MPOINT/EFI/BOOT/BOOTAA64.EFI"            "$BOOTAA64_SHA"  "final BOOTAA64.EFI"           || FAILS=$((FAILS+1))
verify_hash "$MPOINT/EFI/BOOT/BOOTAA64.EFI.stock"      "$STOCK_BA64_SHA" "final BOOTAA64.stock" || FAILS=$((FAILS+1))
if [ $FAILS -ne 0 ]; then die "final readback: $FAILS file(s) failed"; fi
echo "STAGE-DONE (all final readbacks exact)"
