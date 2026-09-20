#!/usr/bin/env python3
# e2 segment builder (build-initrd.sh step 4): deterministic newc archive.
# Entries: dir vendorfw; symlink lib/firmware/vendor -> /vendorfw;
# vendorfw/.vendorfw.sha256; vendorfw/.vendorfw.manifest.
# usr/lib/firmware exists in the base main cpio, so no lib/firmware dir entry.
import hashlib, os

import sys
asm = os.path.dirname(os.path.abspath(__file__))
audit = os.path.dirname(asm)   # asm/ -> esp-audit-20260919
work = os.environ.get('JWM1_ASM_WORK', os.path.join(audit, '.work', 'assemble'))
store = os.path.join(audit, 'content-store',
                     'b1e15f13af97732732fe19a4b699551fc29dfac5de53b8400814d1422963b2be')

def hdr(name, mode, size):
    nb = name.encode() + b'\0'
    nums = [0, mode, 0, 0, 1, 0, size, 0, 0, 0, 0, len(nb), 0]
    h = b'070701' + b''.join(b'%08X' % f for f in nums)
    pad = (4 - (110 + len(nb)) % 4) % 4          # header+name multiple of 4 (newc rule)
    return h + nb + b'\0' * pad

def entry_file(name, data, mode=0o100644):
    return hdr(name, mode, len(data)) + data + b'\0' * ((4 - len(data) % 4) % 4)

def entry_dir(name):
    return hdr(name, 0o40755, 0)

def entry_sym(name, target):
    return hdr(name, 0o120777, len(target)) + target.encode() + b'\0' * ((4 - len(target) % 4) % 4)

e2 = entry_dir('vendorfw')
e2 += entry_sym('lib/firmware/vendor', '/vendorfw')
e2 += entry_file('vendorfw/.vendorfw.sha256',
                 open(os.path.join(audit, 'firmware-plan/vendorfw.sha256'), 'rb').read())
e2 += entry_file('vendorfw/.vendorfw.manifest',
                 open(os.path.join(store, 'manifest.txt'), 'rb').read())
e2 += hdr('TRAILER!!!', 0, 0)          # hdr already appends the canonical name padding

out = os.path.join(work, 'e2.cpio')
open(out, 'wb').write(e2)
print('e2.cpio bytes:', len(e2), 'sha256:', hashlib.sha256(e2).hexdigest())
