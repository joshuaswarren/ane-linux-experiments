#!/usr/bin/env python3
# Root-tree staging step of build-initrd.sh (build-initrd.sh step 2).
import os, shutil

asm = os.path.dirname(os.path.abspath(__file__))
audit = os.path.dirname(asm)   # asm/ -> esp-audit-20260919
work = os.environ.get('JWM1_ASM_WORK', os.path.join(audit, '.work', 'assemble'))
base_root = os.path.join(work, 'base-extract', 'root')
tree_src = os.path.join(work, 'usr', 'lib', 'modules', '7.1.13-3-1-ARCH')
root = os.path.join(work, 'root2')

if os.path.exists(root):
    shutil.rmtree(root)   # builder-owned staging path; recreated from pristine inputs below

# base tree without the partial module dir (full package tree replaces it)
shutil.copytree(base_root, root,
                ignore=shutil.ignore_patterns('7.1.13-3-1-ARCH'),
                symlinks=True)
shutil.copytree(tree_src, os.path.join(root, 'usr/lib/modules/7.1.13-3-1-ARCH'), symlinks=True)

os.makedirs(os.path.join(root, 'usr/local/bin'), exist_ok=True)
shutil.copy2(os.path.join(audit, 'jwm1-modstage.sh'), os.path.join(root, 'usr/local/bin/jwm1-modstage.sh'))
shutil.copy2(os.path.join(audit, 'firmware-plan/asahi-firmware-late.sh'),
             os.path.join(root, 'usr/local/bin/jwm1-firmware-late'))
shutil.copy2(os.path.join(audit, 'hook-jwm1-modstage'), os.path.join(root, 'hooks/jwm1-modstage'))
shutil.copy2(os.path.join(work, 'modules.manifest'), os.path.join(root, 'etc/jwm1-modules.manifest'))
for p in ['usr/local/bin/jwm1-modstage.sh', 'usr/local/bin/jwm1-firmware-late', 'hooks/jwm1-modstage']:
    os.chmod(os.path.join(root, p), 0o755)
os.chmod(os.path.join(root, 'etc/jwm1-modules.manifest'), 0o644)

cfg = os.path.join(root, 'config')
s = open(cfg).read()
assert s.count('LATEHOOKS=""') == 1
open(cfg, 'w').write(s.replace('LATEHOOKS=""', 'LATEHOOKS="jwm1-modstage"'))

init = os.path.join(root, 'init')
s = open(init).read()
anchor = '"$mount_handler" /sysroot\n'
assert s.count(anchor) == 1
block = '''
# jwm1 vendorfw: persist Apple firmware into the real root from the embedded
# verbatim vendorfw cpio. Nonzero stops boot here with the upstream fatal
# pattern plus a terminal exit fallback: control can never reach switch_root.
if ! /usr/local/bin/jwm1-firmware-late /sysroot; then
    err "jwm1 vendorfw: persistence FAILED - stopping before switch_root"
    launch_interactive_shell --exec
    exit 1
fi
'''
open(init, 'w').write(s.replace(anchor, anchor + block, 1))

# normalize mtimes (cpio --reproducible zeroes inos but keeps mtimes; fresh
# dirs carry build-time mtimes). epoch 0 everywhere, deepest first.
targets = []
for dp, dn, fn in os.walk(root):
    for n in fn + dn:
        targets.append(os.path.join(dp, n))
    targets.append(dp)
for p in targets:
    os.utime(p, (0, 0), follow_symlinks=False)
print('root2 staged:', sum(len(f) for _, _, f in os.walk(root)), 'files, mtimes normalized')
