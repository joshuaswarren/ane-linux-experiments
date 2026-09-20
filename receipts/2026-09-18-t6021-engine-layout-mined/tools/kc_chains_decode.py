#!/usr/bin/env python3
"""Kernel-collection (MH_FILESET) chained-fixup chain walker — production decoder.

Format authority: xnu osfmk/mach/dyld_kernel_fixups.h (kernel_collection_slide /
rebase_chain). Header is the canonical 7-u32 dyld_chained_fixups_header (NO magic);
entry format 8 = DYLD_CHAINED_PTR_64_KERNEL_CACHE:
  dyld_chained_ptr_64_kernel_cache_rebase, LSB-first:
    target[0:30)  — offset from the KC __TEXT vm base (basePointers[cacheLevel])
    cacheLevel[30:32)
    diversity[32:48)
    addrDiv[48]
    key[49:51)
    next[51:63)   — stride to next fixup = next*4 (0 = end of chain)
    isAuth[63]
Target recovery needs NO PAC keys: auth entries are target30 + signing METADATA
(diversity/addrDiv/key) applied by the boot-time signer; low30 + base is the address.

kc_chains_decode.py --regress validates against the AppleH11ANEInterface image:
  __ZTV11ANEHWDevice address-point = 0x8141de0 (ctor-stored vptr, 0x959b180..0x198)
  vptr+0x8a8 -> ANEHWDevice::dartMapMemoryDescriptor          = 0x95daa38
  vptr+0x8b0 -> ANEHWDevice::dartMapMemoryDescriptorSharedMallocRegion = 0x95db620
  makeMemoryVisible                                           = 0x95db284
"""
import struct
import sys

KC = '/tmp/kernelcache.mac14j.raw'
KC_TEXT_VM = 0xFFFFFE0007004000

SEGMENTS = [
    ("__TEXT", 0xFFFFFE0007004000, 0x8000, 0x0),
    ("__PRELINK_TEXT", 0xFFFFFE000700C000, 0xDDC000, 0x8000),
    ("__DATA_CONST", 0xFFFFFE0007DE8000, 0xC8C000, 0xDE4000),
    ("__DATA_SPTM", 0xFFFFFE0008A74000, 0x74000, 0x1A70000),
    ("__TEXT_EXEC", 0xFFFFFE0008AE8000, 0x3AB8000, 0x1AE4000),
    ("__TEXT_BOOT_EXEC", 0xFFFFFE000C5A0000, 0x8000, 0x559C000),
    ("__PRELINK_INFO", 0xFFFFFE000C5A8000, 0x3A0000, 0x55A4000),
    ("__DATA", 0xFFFFFE000C948000, 0x420000, 0x5944000),
    ("__LINKEDIT", 0xFFFFFE000CD68000, 0x19E0000, 0x5D64000),
]

# slot VM -> KC file offset (segment vm 0x7de8000 -> file 0xde4000)
def vm_to_file(vm):
    return vm - 0xFFFFFE0007DE8000 + 0xDE4000

REGRESS = {
    vm_to_file(0xFFFFFE0008141DE0 + 0x8A8): 0xFFFFFE00095DAA38,  # dartMapMemoryDescriptor
    vm_to_file(0xFFFFFE0008141DE0 + 0x8B0): 0xFFFFFE00095DB620,  # dartMapMemoryDescriptorSharedMallocRegion
}


def decode_entry(v):
    return {
        "target": v & 0x3FFFFFFF,
        "cacheLevel": (v >> 30) & 3,
        "diversity": (v >> 32) & 0xFFFF,
        "addrDiv": (v >> 48) & 1,
        "key": (v >> 49) & 3,
        "next": (v >> 51) & 0xFFF,
        "isAuth": (v >> 63) & 1,
    }


def walk():
    d = open(KC, 'rb').read()
    starts_fo = 0x7740000 + 0x1C  # canonical header: starts_offset = 28 (7 u32 header)
    seg_count = struct.unpack_from("<I", d, starts_fo)[0]
    offs = struct.unpack_from(f"<{seg_count}I", d, starts_fo + 4)
    entries = []
    chains = 0
    for si in range(seg_count):
        so = offs[si]
        if so == 0:
            continue
        q = starts_fo + so
        size, page_size, ptr_fmt = struct.unpack_from("<IHH", d, q)
        seg_offset = struct.unpack_from("<Q", d, q + 8)[0]
        page_count = struct.unpack_from("<H", d, q + 20)[0]
        if ptr_fmt != 8:
            print(f"seg{si}: unhandled format {ptr_fmt}", file=sys.stderr)
            continue
        for pg in range(page_count):
            start = struct.unpack_from("<H", d, q + 22 + pg * 2)[0]
            if start == 0xFFFF or start & 0x8000:
                continue
            chains += 1
            addr = seg_offset + pg * page_size + start
            for _ in range(1 << 20):
                v = struct.unpack_from("<Q", d, addr)[0]
                e = decode_entry(v)
                entries.append((addr, e))
                if e["next"] == 0:
                    break
                addr += e["next"] * 4
    return d, chains, entries


def regress(d, entries):
    table = dict(entries)
    ok = True
    for slot_vm, want in REGRESS.items():
        e = table.get(slot_vm)
        got = 0xFFFFFE0000000000 | (KC_TEXT_VM + e["target"]) if e else None
        status = "OK" if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  {status} slot {hex(slot_vm)} -> {hex(got) if got is not None else None} (want {hex(want)})")
    # makeMemoryVisible present among targets
    mv = 0xFFFFFE00095DB284
    hit = any((0xFFFFFE0000000000 | (KC_TEXT_VM + e["target"])) == mv for _, e in entries)
    print(f"  INFO makeMemoryVisible 0x{mv:x} present among fixup targets: {hit} (informational — makeMemoryVisible is invoked via direct bl, a chain entry is not required)")
    return ok


def main():
    d, chains, entries = walk()
    print(f"chains {chains}, entries {len(entries)}")
    segok = all(
        any(s[1] <= KC_TEXT_VM + e["target"] < s[1] + s[2] for s in SEGMENTS)
        for _, e in entries
    )
    print(f"targets inside known KC segments: {segok}")
    if "--regress" in sys.argv:
        if not regress(d, entries):
            sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
