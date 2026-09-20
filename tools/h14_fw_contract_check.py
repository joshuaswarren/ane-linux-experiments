#!/usr/bin/env python3
"""H14 W13 offline firmware/contract checker. No device contact.

Validates the staged t6021 ANE firmware artifact chain and re-derives the
mined boot-contract constants straight from the extracted binaries, so a
loader implementation can be checked offline before any device write.

Usage: python3 tools/h14_fw_contract_check.py [--fw-dir /opt/ane/fw]
Exit 0 = all checks pass.
"""
import argparse
import hashlib
import struct
import sys

EXPECT_IM4P_SHA256 = "ad9151af4e732575a67ce007d385413b3d55a8eecffc562085678daa5bac151a"
EXPECT_MACHO_SHA256 = "9f7915c431d288a2bdc2132c399db8cf5574716a3b1e94af76be6a291c2e665b"
PAYLOAD_SIZE = 0x1A4000
ENTRY_PC = 0x0
TEXT_VA, TEXT_SZ = 0x0, 0xE8000
DATA_VA, DATA_VMSZ = 0xE8000, 0x284000
FWINFO_MAGIC = 0x1DEAFBABE
TUNABLES_HDR = 0x00240301
MH_PRELOAD = 5
RVBAR_OFF = 0x1050000
ROM_ENTRY = 0x0081000000000001
ENTRY_MASK = 0xFF7EFFFFFFFFFFF8
POSTBOOT_POLL_CONST = 0x08042006
RVBAR_COMPOSE_MASK = 0xFF7EFFFFFFFFF800
RVBAR_OR_BITS = 0x0081000000000001


def check_rvbar_compose():
    """RVBAR entry is a COMPOSITION: (obj18 & mask) | OR_BITS — verified
    bit semantics (integer bitops; mask 0xFF7EFFFFFFFFF800 clears obj18
    bits 0-10, 48, 55; preserves 11-47, 49-54, 56-63; OR forces 0, 48,
    55; bits 1-10 always 0 in the result)."""
    ok = True
    for obj18 in (0, 1, 0x08042006, 0x1234567890abcdef, 0xffffffffffffffff):
        rvbar = (obj18 & RVBAR_COMPOSE_MASK) | RVBAR_OR_BITS
        # bits 1-10 must always be 0 in the result (cleared, not ORed)
        if any((rvbar >> b) & 1 for b in range(1, 11)):
            ok = False
        # bit0, 48, 55 always forced
        if not ((rvbar >> 0) & 1 and (rvbar >> 48) & 1 and (rvbar >> 55) & 1):
            ok = False
        # obj18 bits 11-47 survive verbatim
        for b in list(range(11, 48)):
            if ((rvbar >> b) & 1) != ((obj18 >> b) & 1):
                ok = False
    print(f"[{'PASS' if ok else 'FAIL'}] RVBAR compose bit semantics "
          f"(mask {RVBAR_COMPOSE_MASK:#x}, OR {RVBAR_OR_BITS:#x})")
    return ok


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{': ' + detail if detail else ''}")
    return ok


def parse_der_im4p(data):
    """Return (fourcc_list, payload) from the DER SEQUENCE im4p."""
    assert data[0] == 0x30, "not a DER SEQUENCE"
    l = data[1]
    off = 2
    if l & 0x80:
        n = l & 0x7F
        l = int.from_bytes(data[2:2 + n], "big")
        off = 2 + n
    strings, octet = [], None
    p = off
    while p < len(data):
        tag = data[p]
        ln = data[p + 1]
        q = p + 2
        if ln & 0x80:
            n = ln & 0x7F
            ln = int.from_bytes(data[q:q + n], "big")
            q += n
        val = data[q:q + ln]
        if tag == 0x16:
            strings.append(val)
        elif tag == 0x04:
            octet = val
        p = q + ln
    return strings, octet


def macho_summary(payload):
    magic, cputype, cpusub, ftype, ncmds, sizeofcmds, flags = struct.unpack_from(
        "<IiiIIII", payload, 0)
    assert magic == 0xFEEDFACF, "not MH_MAGIC_64"
    segs, entry = [], None
    off = 32
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from("<II", payload, off)
        if cmd == 0x19:
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from(
                "<QQQQ", payload, off + 24)
            name = payload[off + 8:off + 24].rstrip(b"\0").decode()
            segs.append((name, vmaddr, vmsize, fileoff, filesize))
        elif cmd == 0x5:
            p = off + 8
            while p < off + cmdsize:
                flavor, count = struct.unpack_from("<II", payload, p)
                if flavor == 6:
                    entry = struct.unpack_from("<33Q", payload, p + 8)[32]
                p += 8 + count * 4
        off += cmdsize
    return ftype, segs, entry


def read_vm(payload, vmaddr, size):
    """__TEXT fileoff 0x4000 @vm0; __DATA fileoff 0xec000 @vm0xe8000."""
    if vmaddr < 0xE8000:
        return payload[0x4000 + vmaddr:0x4000 + vmaddr + size]
    return payload[0xEC000 + (vmaddr - 0xE8000):0xEC000 + (vmaddr - 0xE8000) + size]


def scan_contract_constants(kext_path):
    """Re-derive RVBAR contract bytes from a kext binary (K14 or K13).

    Instruction-level scan: MOVK x?, #imm, lsl #hw and MOVZ w?, #0x105, lsl #16.
    """
    d = open(kext_path, "rb").read()
    found = {"rvbar_off": False, "entry_hi": 0, "mask_hi": 0}
    n = len(d) - 4
    for off in range(0, n, 4):
        w = struct.unpack_from("<I", d, off)[0]
        top = w >> 23
        hw = (w >> 21) & 3
        imm = (w >> 5) & 0xFFFF
        # MOVK 64-bit: sf=1 opc=11 100101 => bits31-23 == 0b111100101
        if top == 0x1E5:
            if hw == 3 and imm == 0x81:
                found["entry_hi"] += 1
            if hw == 3 and imm == 0xFF7E:
                found["mask_hi"] += 1
        # MOVZ 32-bit: sf=0 opc=10 100101 => bits31-23 == 0b010100101
        if top == 0xA5 and hw == 1 and imm == 0x105:
            found["rvbar_off"] = True
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fw-dir", default="/opt/ane/fw")
    ap.add_argument("--kext14", default=None)
    ap.add_argument("--kext13", default=None)
    args = ap.parse_args()

    ok = True
    import os
    im4p_p = os.path.join(args.fw_dir, "t602x_ane0_fw_selene_rc4x.im4p")
    macho_p = os.path.join(args.fw_dir, "t602x_ane0_fw_selene_rc4x.macho")
    if not check("staged files exist", os.path.exists(im4p_p) and os.path.exists(macho_p), args.fw_dir):
        return 1

    im4p = open(im4p_p, "rb").read()
    macho = open(macho_p, "rb").read()
    ok &= check("im4p sha256", hashlib.sha256(im4p).hexdigest() == EXPECT_IM4P_SHA256)
    ok &= check("macho sha256", hashlib.sha256(macho).hexdigest() == EXPECT_MACHO_SHA256)

    strings, payload = parse_der_im4p(im4p)
    ok &= check("DER wrapper strings", strings[:3] == [b"IM4P", b"anef", b"1"], str(strings[:3]))
    ok &= check("payload size", len(payload) == PAYLOAD_SIZE, f"{len(payload):#x}")
    ok &= check("payload == macho", payload == macho)
    ok &= check("no IM4M in payload container", b"IM4M" not in im4p[:64])

    ftype, segs, entry = macho_summary(payload)
    ok &= check("MH_PRELOAD", ftype == MH_PRELOAD, str(ftype))
    ok &= check("entry pc == 0", entry == ENTRY_PC, hex(entry))
    text = next(s for s in segs if s[0] == "__TEXT")
    data = next(s for s in segs if s[0] == "__DATA")
    ok &= check("__TEXT vm/size", (text[1], text[2]) == (TEXT_VA, TEXT_SZ),
                f"vm={text[1]:#x} sz={text[2]:#x}")
    ok &= check("__DATA vm/vmsize", (data[1], data[2]) == (DATA_VA, DATA_VMSZ),
                f"vm={data[1]:#x} vmsz={data[2]:#x}")

    bl1 = read_vm(payload, 0x190100, 0x80)
    ok &= check("_rtk_boot_l1 zero (loader-populated)", not any(bl1))
    pt = read_vm(payload, 0x110000, 0x80000)
    ok &= check("_rtk_page_tables zero (loader-populated)", not any(pt))
    fwinfo = read_vm(payload, 0x190000, 0x40)
    ok &= check("_fwinfo magic", struct.unpack_from("<Q", fwinfo, 0)[0] == FWINFO_MAGIC)
    tun = read_vm(payload, 0x100590, 8)
    ok &= check("_rtk_tunables header", struct.unpack_from("<I", tun, 0)[0] == TUNABLES_HDR)

    ok &= check_rvbar_compose()

    for label, path in (("K14", args.kext14), ("K13", args.kext13)):
        if not path or not os.path.exists(path):
            continue
        f = scan_contract_constants(path)
        ok &= check(f"{label} RVBAR offset constant", f["rvbar_off"])
        ok &= check(f"{label} ROM entry movk #0x81 lsl#48", f["entry_hi"] >= 1)
        ok &= check(f"{label} entry mask movk #0xff7e lsl#48", f["mask_hi"] >= 1)

    print("\ncontract:", "ROM entry 0x0081_0000_0000_0001 @ RVBAR eng+0x1050000,"
          " gate bit0, SCRATCH7 cold boot, image+bootargs via DART-mapped surface")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
