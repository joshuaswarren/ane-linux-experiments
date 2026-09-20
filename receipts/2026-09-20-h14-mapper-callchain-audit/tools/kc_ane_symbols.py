#!/usr/bin/env python3
"""Independent AppleH11ANEInterface symbol extractor from the pinned KC.

Walks the container's LC_FILESET_ENTRY commands, finds the ANE kext's nested
Mach-O, reads ITS OWN LC_SYMTAB (nsyms/symoff/stroff), and writes a sorted
`vmaddr name` table. Ground truth: names come from the KC's own string table,
addresses from the KC's own nlist records. No adjacency inference anywhere.

Also --vtable: dumps the __ZTV11ANEHWDevice vtable slots by walking the
DYLD_CHAINED_PTR_64_KERNEL_CACHE fixup chains on-disk (osfmk/mach/
dyld_kernel_fixups.h), decoding each 8-byte entry:
  target[0:30) = offset from KC __TEXT vm base; [30:32) cacheLevel;
  [32:48) diversity; [48) addrDiv; [49:51) key; [51:63) next (x4 bytes);
  [63) isAuth. Auth entries carry signing metadata only; target recovery
  is low30 + __TEXT vm base.

Run: python3 kc_ane_symbols.py [--vtable [count]]
"""
import struct, sys

KC = '/tmp/kernelcache.mac14j.raw'
LC_SEGMENT_64 = 0x19
LC_SYMTAB = 0x2
LC_FILESET_ENTRY = 0x80000035


def container_segments(d):
    ncmds, = struct.unpack_from('<I', d, 16)
    off = 32
    segs = []
    for _ in range(ncmds):
        cmd, cs = struct.unpack_from('<II', d, off)
        if cmd == LC_SEGMENT_64:
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from('<QQQQ', d, off + 24)
            segs.append((vmaddr, vmsize, fileoff, filesize))
        off += cs
    return segs


def find_kext(d, bundle_substr):
    ncmds, = struct.unpack_from('<I', d, 16)
    off = 32
    for _ in range(ncmds):
        cmd, cs = struct.unpack_from('<II', d, off)
        if cmd == LC_FILESET_ENTRY:
            eo, eid = struct.unpack_from('<QQ', d, off + 8)
            name = d[off + 32:off + cs].split(b'\x00')[0].decode()
            if bundle_substr in name:
                return name, eo, eid
        off += cs
    return None


def kext_symtab(d, kext_file_off):
    ncmds, = struct.unpack_from('<I', d, kext_file_off + 16)
    off = kext_file_off + 32
    for _ in range(ncmds):
        cmd, cs = struct.unpack_from('<II', d, off)
        if cmd == LC_SYMTAB:
            return struct.unpack_from('<IIII', d, off + 8)
        off += cs
    return None


def symbols(d, symoff, nsyms, stroff):
    out = []
    for i in range(nsyms):
        strx, ntype, nsect, ndesc = struct.unpack_from('<IBBH', d, symoff + 16 * i)
        val, = struct.unpack_from('<Q', d, symoff + 16 * i + 8)
        o = stroff + strx
        name = d[o:d.find(b'\x00', o)].decode(errors='replace')
        out.append((val, name, ntype))
    return out


def vm_to_file(segs, vm):
    for vmaddr, vmsize, fileoff, filesize in segs:
        if vmaddr <= vm < vmaddr + vmsize:
            return fileoff + (vm - vmaddr)
    raise ValueError(f'vm {vm:#x} not in any segment')


def decode_fixup(v):
    return {
        'target30': v & 0x3FFFFFFF,
        'cacheLevel': (v >> 30) & 3,
        'diversity': (v >> 32) & 0xFFFF,
        'addrDiv': (v >> 48) & 1,
        'key': (v >> 49) & 3,
        'next4': (v >> 51) & 0xFFF,
        'isAuth': (v >> 63) & 1,
    }


def dump_vtable(d, segs, text_vm, by_name, by_addr, count, start_vm=None):
    ap = start_vm if start_vm else by_name['__ZTV11ANEHWDevice'] + 16  # address point
    fo0 = vm_to_file(segs, ap)
    print(f'vtable address point: {ap:#x} (file {fo0:#x}); __ZTV hdr {ap-16:#x}')
    v, = struct.unpack_from('<Q', d, fo0)
    pos = 0
    while pos < count:
        vm = ap + pos
        e = decode_fixup(v)
        tgt = text_vm + e['target30']
        nm = by_addr.get(tgt, '??')
        fo = vm_to_file(segs, vm)
        print(f'  +{pos:#05x} vm {vm:#x} file {fo:#x} raw {v:#018x} -> tgt {tgt:#x} auth={e["isAuth"]} key={e["key"]} lvl={e["cacheLevel"]} next={e["next4"]} {nm}')
        step = 8 * e['next4'] if e['next4'] else 8
        pos += step
        if pos < count:
            v, = struct.unpack_from('<Q', d, fo0 + pos)
    return ap


def main():
    d = open(KC, 'rb').read()
    segs = container_segments(d)
    text_vm = segs[0][0]
    name, eo, eid = find_kext(d, 'AppleH11ANEInterface')
    symoff, nsyms, stroff, strsize = kext_symtab(d, eid)
    syms = symbols(d, symoff, nsyms, stroff)
    by_name, by_addr = {}, {}
    for val, nm, _t in syms:
        if nm and val:
            by_name.setdefault(nm, val)
            by_addr.setdefault(val, nm)
    with open(__file__.rsplit('/', 1)[0] + '/../ane_kext.syms', 'w') as f:
        for val, nm, _t in sorted(set(syms)):
            if nm and val:
                f.write(f'{val:#016x} {nm}\n')
    print(f'{name}: {nsyms} syms, symoff {symoff:#x}, stroff {stroff:#x}')
    if '--vtable' in sys.argv:
        cnt = int(sys.argv[sys.argv.index('--vtable') + 1], 0) if len(sys.argv) > sys.argv.index('--vtable') + 1 else 0x40 // 4
        dump_vtable(d, segs, text_vm, by_name, by_addr, cnt)


if __name__ == '__main__':
    main()
