#!/usr/bin/env python3
"""Shared helpers: AppleH11ANEInterface-9.512.0 kext slice mapping + arm64e disasm."""
import struct, re

KEXT = ('~/src/ane-linux-experiments/receipts/'
        '2026-09-18-t6021-engine-layout-mined/kext-h13/'
        'AppleH11ANEInterface-9.512.0-macstudio-25G83')

D = open(KEXT, 'rb').read()

# (vmaddr, fileoff, filesize, name) from LC_SEGMENT_64 walk
SEGS = []
def _load_segs():
    nc = struct.unpack_from('<I', D, 16)[0]
    off = 32
    for _ in range(nc):
        cmd, csz = struct.unpack_from('<II', D, off)
        if cmd == 0x19:
            name = D[off+8:off+24].rstrip(b'\0').decode()
            vm, vmsz, fa, fsz = struct.unpack_from('<QQQQ', D, off+24)
            SEGS.append((name, vm, vmsz, fa, fsz))
        off += csz
_load_segs()

def vm_to_file(vm):
    for name, v, vs, f, fs in SEGS:
        if v <= vm < v + vs:
            fo = vm - v + f
            if fo < f + fs or fs == 0:
                return fo, name
    return None, None

def file_to_vm(fo):
    for name, v, vs, f, fs in SEGS:
        if f <= fo < f + fs:
            return v + (fo - f), name
    return None, None

SECTION = {}
def _load_sects():
    nc = struct.unpack_from('<I', D, 16)[0]
    off = 32
    for _ in range(nc):
        cmd, csz = struct.unpack_from('<II', D, off)
        if cmd == 0x19:
            nsects = struct.unpack_from('<I', D, off+64)[0]
            so = off + 72
            for s in range(nsects):
                sname = D[so:so+16].rstrip(b'\0').decode()
                sgm = D[so+16:so+32].rstrip(b'\0').decode()
                addr, sz = struct.unpack_from('<QQ', D, so+32)
                ofs = struct.unpack_from('<I', D, so+48)[0]
                SECTION[f'{sgm},{sname}'] = (addr, sz, ofs)
                so += 80
        off += csz
_load_sects()

TEXT_EXEC = SECTION['__TEXT_EXEC,__text']   # (addr, size, fileoff)
CSTRING   = SECTION['__TEXT,__cstring']
OSLOG     = SECTION['__TEXT,__os_log']
CONST     = SECTION['__DATA_CONST,__const']
DATA      = SECTION['__DATA,__data']

def strings(seg, minlen=4):
    addr, size, fo = seg
    b = D[fo:fo+size]
    out = {}
    cur = b''; start = 0
    for i, ch in enumerate(b):
        if 32 <= ch < 127:
            if not cur:
                start = i
            cur += bytes([ch])
        else:
            if len(cur) >= minlen and cur.decode() not in out:
                out[cur.decode()] = addr + start
            cur = b''
    return out  # string -> vma (first occurrence)

# PAC/branch-target helper: kernel arm64e addresses carry pac bits in high bits
def strip_pac(v):
    return v & 0x0000FFFFFFFFFFFF
