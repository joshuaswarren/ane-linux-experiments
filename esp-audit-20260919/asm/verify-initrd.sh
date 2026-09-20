#!/usr/bin/env python3
# Unpack checker for initrd-7113-clean-modstate.img (jwm1 recovery initrd).
# Strict verification against content-addressed sources:
#   - segment layout incl. the 4-byte zero alignment pad after the gzip
#   - every newc header offset 4-aligned, in-bounds, exactly one TRAILER,
#     trailing bytes zero-only (per segment)
#   - normalized inventory ledger vs base: adds confined to approved
#     prefixes, zero deletions, content changes confined to the approved set
#   - FULL package .MTREE proof (1988/1988, not a sample)
#   - embedded scripts/manifest byte-identity with reviewed sources
#   - firmware: strict parse, hardlink group content consistency, and exact
#     reconciliation of vendorfw.sha256 (all listed paths matched, unique,
#     hashed correctly; the only cpio-not-listed path must be
#     vendorfw/.vendorfw.manifest)
# Exits nonzero on any failure. Usage: verify-initrd.sh [artifact]
import gzip, hashlib, os, stat, subprocess, sys

asm = os.path.dirname(os.path.abspath(__file__))
audit = os.path.dirname(asm)
work = os.environ.get('JWM1_ASM_WORK', os.path.join(audit, '.work', 'assemble'))
store = os.path.join(audit, 'content-store',
                     'b1e15f13af97732732fe19a4b699551fc29dfac5de53b8400814d1422963b2be')
art_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(audit, 'initrd-7113-clean-modstage.img')

fails = []
def check(ok, label, detail=''):
    print(('PASS: ' if ok else 'FAIL: ') + label + (('  :: ' + detail) if detail and not ok else ''))
    if not ok:
        fails.append(label)

def sha(b):
    return hashlib.sha256(b).hexdigest()

def parse_newc_strict(data, label):
    """Parse a newc archive; assert 4-aligned in-bounds headers and exactly
    one TRAILER; assert trailing bytes (if any) are zero. Return entries."""
    entries = []
    off = 0
    trailer_at = None
    while off < len(data):
        if (off % 4) != 0:
            fails.append(f'{label}: header offset {off} not 4-aligned')
            break
        if off + 110 > len(data):
            fails.append(f'{label}: truncated header at {off}')
            break
        magic = data[off:off + 6]
        if magic not in (b'070701', b'070702'):
            fails.append(f'{label}: bad magic {magic!r} at {off}')
            break
        f = [int(data[off + 6 + i * 8:off + 6 + (i + 1) * 8], 16) for i in range(13)]
        ns = f[11]
        name = data[off + 110:off + 110 + ns - 1].decode()
        if data[off + 110 + ns - 1:off + 110 + ns] != b'\0':
            fails.append(f'{label}: name not NUL-terminated at {off}')
            break
        off += 110 + ns + ((4 - (110 + ns) % 4) % 4)
        if off + f[6] > len(data):
            fails.append(f'{label}: data overruns archive at {off} ({name})')
            break
        d = data[off:off + f[6]]
        off += f[6] + ((4 - f[6] % 4) % 4)
        if name == 'TRAILER!!!':
            trailer_at = off
            break
        entries.append({'name': name, 'ino': f[0], 'mode': f[1],
                        'nlink': f[4], 'size': f[6], 'data': d})
    if trailer_at is None:
        fails.append(f'{label}: TRAILER!!! missing')
    else:
        check(all(b == 0 for b in data[trailer_at:]), f'{label}: trailing bytes zero-only')
    return entries

# ---- load artifact + reference segments ----
art = open(art_path, 'rb').read()
early = open(os.path.join(work, 'base-extract/early.cpio'), 'rb').read()
maingz = open(os.path.join(work, 'main-new.cpio.gz'), 'rb').read()
fw = open(os.path.join(store, 'firmware.cpio'), 'rb').read()
e2 = open(os.path.join(work, 'e2.cpio'), 'rb').read()

# ---- segment layout with alignment pad ----
EARLY = len(early)
gz_end = None
f = lambda: None
d = zlib = None
import zlib
dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
stream = art[EARLY:]
gzlen = None
pos = EARLY
dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
feed = art[EARLY:]
dec.decompress(feed)
gzlen = len(feed) - len(dec.unused_data)
pad_len = (4 - (EARLY + gzlen) % 4) % 4
pad = art[EARLY + gzlen:EARLY + gzlen + pad_len]
o = EARLY + gzlen + pad_len
seg_ok = (art[:EARLY] == early and art[EARLY:EARLY + gzlen] == maingz
          and all(b == 0 for b in pad)
          and art[o:o + len(fw)] == fw
          and art[o + len(fw):] == e2)
check(seg_ok, f'segment layout byte-exact incl. {pad_len}-byte zero alignment pad',
      f'early={EARLY} gz={gzlen} pad={pad_len} fw={len(fw)} e2={len(e2)} total={len(art)} expected={o + len(fw) + len(e2)}')

# ---- strict parse of every segment ----
main_cpio = gzip.decompress(art[EARLY:EARLY + gzlen])
main_entries = parse_newc_strict(main_cpio, 'main')
fw_entries = parse_newc_strict(fw, 'firmware')
e2_entries = parse_newc_strict(e2, 'e2')
early_entries = parse_newc_strict(early, 'early')
fn = {('' if e['name'] == '.' else e['name'].rstrip('/')) for e in main_entries}

# ---- full unpack (checked) ----
dst = os.path.join(work, 'verify-extract')
subprocess.run(['rm', '-rf', dst], check=True)
os.makedirs(dst)
r = subprocess.run(['cpio', '-idm', '--quiet'], input=main_cpio, cwd=dst, capture_output=True)
check(r.returncode == 0, f'main segment cpio extraction rc=0 ({len(fn)} entries)')

# ---- inventory ledger vs base ----
base_cpio = open(os.path.join(work, 'base-extract/main.cpio'), 'rb').read()
r = subprocess.run(['cpio', '-it'], input=base_cpio, capture_output=True, check=True)
bn = set()
for l in r.stdout.decode().splitlines():
    n = l.rstrip('/')
    bn.add('' if n == '.' else n)
added = sorted(fn - bn)
deleted = sorted(bn - fn)
APPROVED = ('usr/lib/modules/7.1.13-3-1-ARCH/', 'usr/local/bin/', 'usr/local/',
            'hooks/jwm1-modstage', 'etc/jwm1-modules.manifest')
stray = [a for a in added if not a.startswith(APPROVED) and a != '']
check(not deleted and not stray,
      f'inventory: added={len(added)} deleted={len(deleted)} stray={len(stray)}',
      f'deleted={deleted[:5]} stray={stray[:5]}')

changed = []
base_root = os.path.join(work, 'base-extract', 'root')
for n in sorted(bn & fn):
    p1, p2 = os.path.join(base_root, n), os.path.join(dst, n)
    if os.path.isfile(p1) and os.path.isfile(p2) and n != 'init':
        if sha(open(p1, 'rb').read()) != sha(open(p2, 'rb').read()):
            changed.append(n)
EXPECTED_CHANGED = {'config',
                    'usr/lib/modules/7.1.13-3-1-ARCH/modules.alias.bin',
                    'usr/lib/modules/7.1.13-3-1-ARCH/modules.dep.bin',
                    'usr/lib/modules/7.1.13-3-1-ARCH/modules.devname',
                    'usr/lib/modules/7.1.13-3-1-ARCH/modules.softdep',
                    'usr/lib/modules/7.1.13-3-1-ARCH/modules.symbols.bin'}
check(set(changed) <= EXPECTED_CHANGED,
      f'content changes confined to approved set ({len(changed)} changed)',
      f'unexpected: {sorted(set(changed) - EXPECTED_CHANGED)}')
init_changed = sha(open(os.path.join(dst, 'init'), 'rb').read()) != sha(open(os.path.join(base_root, 'init'), 'rb').read())
check(init_changed, 'init carries the hardened fw caller (expected change)')

# ---- FULL package .MTREE proof ----
prefix = 'usr/lib/modules/7.1.13-3-1-ARCH/'
expected = {}
for line in open(os.environ.get('JWM1_PKG_MTREE', os.path.join(audit, '.work', 'modstage', 'pkg.mtree'))):
    line = line.strip()
    if not line.startswith('./'):
        continue
    parts = line.split(' ')
    kv = dict(x.split('=', 1) for x in parts[1:] if '=' in x)
    if 'sha256digest' in kv and parts[0][2:].startswith(prefix):
        expected[parts[0][2:][len(prefix):]] = kv['sha256digest']
bad = 0
for rel, want in expected.items():
    p = os.path.join(dst, prefix, rel)
    if not os.path.isfile(p) or sha(open(p, 'rb').read()) != want:
        bad += 1
check(bad == 0 and len(expected) == 1988,
      f'FULL .MTREE proof: {len(expected) - bad}/{len(expected)} files match package')

# ---- embedded scripts + manifest identity ----
for rel, src in [('usr/local/bin/jwm1-modstage.sh', os.path.join(audit, 'jwm1-modstage.sh')),
                 ('usr/local/bin/jwm1-firmware-late', os.path.join(audit, 'firmware-plan/asahi-firmware-late.sh')),
                 ('etc/jwm1-modules.manifest', os.path.join(work, 'modules.manifest'))]:
    check(sha(open(os.path.join(dst, rel), 'rb').read()) == sha(open(src, 'rb').read()),
          f'embedded {rel} byte-identical to reviewed source')

# ---- firmware: hardlink decode + exact list reconciliation ----
regs = [e for e in fw_entries if (e['mode'] & 0o170000) == 0o100000]
carriers = [e for e in regs if e['size'] > 0]
zeros = [e for e in regs if e['size'] == 0]
groups = {}
for e in regs:
    groups.setdefault(e['ino'], []).append(e)
badlink = 0
for ino, g in groups.items():
    if len(g) > 1:
        payloads = {sha(m['data']) for m in g if m['size'] > 0}
        if len(payloads) > 1:
            badlink += 1
check(badlink == 0,
      f'firmware hardlink groups content-consistent ({sum(1 for g in groups.values() if len(g) > 1)} groups, '
      f'{len(carriers)} carriers, {len(zeros)} size-0 members)')

lst = open(os.path.join(audit, 'firmware-plan/vendorfw.sha256')).read().splitlines()
list_paths = [l.split('  ', 1)[1] for l in lst if '  ' in l]
check(len(list_paths) == len(lst), f'vendorfw.sha256 lines well-formed ({len(lst)})')
check(len(set(list_paths)) == len(list_paths), 'vendorfw.sha256 paths all unique')
name2entry = {e['name']: e for e in regs}
matched = 0
mism = 0
missing = []
for l in lst:
    h, p = l.split('  ', 1)
    p = 'vendorfw/' + p.strip()
    e = name2entry.get(p)
    if e is None:
        missing.append(p)
        continue
    payload = e['data'] if e['size'] > 0 else \
        next((c['data'] for c in groups.get(e['ino'], []) if c['size'] > 0), b'')
    matched += 1
    if sha(payload) != h:
        mism += 1
check(matched == len(lst) and not missing,
      f'vendorfw.sha256: all {len(lst)} listed paths present in cpio (missing={len(missing)})',
      f'missing={missing[:5]}')
check(mism == 0 and matched > 0,
      f'vendorfw.sha256: {matched}/{len(lst)} paths hash-verified, {mism} mismatched')
in_cpio_not_list = sorted(name2entry.keys() - {'vendorfw/' + p for p in list_paths})
check(in_cpio_not_list == ['vendorfw/.vendorfw.manifest'],
      'only cpio-not-listed path is vendorfw/.vendorfw.manifest (embedded by e2)',
      f'got {in_cpio_not_list}')

# ---- cross-segment ordering ----
e2_names = {e['name'] for e in e2_entries}
fw_names = {e['name'] for e in fw_entries}
coll = fn & (fw_names | e2_names)
check(not coll, f'no main-segment collisions with appended segments ({sorted(coll)})')
e2m = {e['name']: e['data'] for e in e2_entries if e['size'] > 0}
fwm = {e['name']: e['data'] for e in fw_entries if e['size'] > 0}
overlap = set(e2m) & set(fwm)
check(all(e2m[k] == fwm[k] for k in overlap),
      f'e2/fw overlapping file entries content-identical ({sorted(overlap)})')

# ---- bounded mode/link-type metadata comparison (base ∩ final) ----
meta_diffs = []
link_diffs = []
for n in sorted(bn & fn):
    if n == '':
        continue
    p1, p2 = os.path.join(base_root, n), os.path.join(dst, n)
    if os.path.islink(p1) or os.path.islink(p2):
        t1 = os.readlink(p1) if os.path.islink(p1) else None
        t2 = os.readlink(p2) if os.path.islink(p2) else None
        if t1 != t2:
            link_diffs.append((n, t1, t2))
        continue
    if os.path.isfile(p1) and os.path.isfile(p2):
        m1 = stat.S_IMODE(os.lstat(p1).st_mode)
        m2 = stat.S_IMODE(os.lstat(p2).st_mode)
        if m1 != m2:
            meta_diffs.append((n, oct(m1), oct(m2)))
check(not link_diffs, f'symlink targets identical for all base-carried symlinks ({len(link_diffs)} diff)',
      f'{link_diffs[:5]}')
check(not meta_diffs, f'modes identical for all base-carried files ({len(meta_diffs)} diff)',
      f'{meta_diffs[:5]}')
# added paths: modes sane (dirs 755, scripts 755, manifest 644)
add_modes = {'hooks/jwm1-modstage': '0o755', 'usr/local/bin/jwm1-modstage.sh': '0o755',
             'usr/local/bin/jwm1-firmware-late': '0o755', 'etc/jwm1-modules.manifest': '0o644'}
for rel, want in add_modes.items():
    got = oct(stat.S_IMODE(os.lstat(os.path.join(dst, rel)).st_mode))
    check(got == want, f'added {rel} mode {got} == {want}')

print('')
if fails:
    print(f'VERIFY: FAIL ({len(fails)}):')
    for x in fails:
        print('  -', x)
    sys.exit(1)
print('VERIFY: ALL PASS')
