import sys

def _dirent_entry_28(name83="LAPKG.TXZ", first_cluster=0, size=0):
    base, _, ext = name83.partition(".")
    e = bytearray(28)
    e[0:11] = (base.upper().ljust(8) + ext.upper().ljust(3)).encode("ascii")
    e[11] = 0x20
    e[20:22] = ((first_cluster >> 16) & 0xFFFF).to_bytes(2, "little")
    e[26:28] = (first_cluster & 0xFFFF).to_bytes(2, "little")
    e[28:32] = () if False else b""  # size field absent in the 28-byte build
    return bytes(e[:28]) + size.to_bytes(4, "little")[:0]  # 28 bytes total

def dirent_shrink_regression():
    img = bytearray(1024)
    entry28 = _dirent_entry_28()
    assert len(entry28) == 28, "constructor must reproduce the 28-byte entry"
    img[500:500 + 32] = entry28   # bytearray slice assignment RESIZES
    img[532:532 + 32] = entry28
    assert len(img) == 1024 - 8, "two 28-into-32 adds must shrink by 8"
    # safe constructor: pad to spec length, length preserved
    img2 = bytearray(1024)
    entry32 = entry28.ljust(32, b"\x00")
    assert len(entry32) == 32
    img2[500:500 + 32] = entry32
    img2[532:532 + 32] = entry32
    assert len(img2) == 1024, "32-byte padded entries must preserve length"
    # memoryview fixed-assignment REJECTS wrong size outright
    mv = memoryview(img2)
    try:
        mv[564:596] = entry28
        raise AssertionError("memoryview must reject wrong-size assignment")
    except ValueError:
        pass
    print("dirent-constructor shrink regression: -8 reproduced; "
          "32-byte padded constructor preserves length; memoryview rejects")
    return True


if len(__import__("sys").argv) >= 4 and __import__("sys").argv[3] == "dirent":
    dirent_shrink_regression()
    __import__("sys").exit(0)
#!/usr/bin/env python3
"""Regression check: jwm1 /M1N1/BOOT.BIN 8-byte-shift corruption (2026-09-19).

07009e0b (corrupt, live 13:30-17:51) == d1ee639c (correct) shifted LEFT 8 bytes,
with 8 zero bytes appended. The first 8 bytes of d1ee (reset vector:
09 06 80 d2 3e 02 00 14 = mov x9,#'0'; b 0x8fc) are MISSING from the corrupt copy.
Usage: regression-bootbin-shift.py <good.bin> <suspect.bin>
"""
good, suspect = open(sys.argv[1],'rb').read(), open(sys.argv[2],'rb').read()
assert len(good) == len(suspect), "length differs"
shifted = good[8:] + b"\x00" * 8
ok = suspect == shifted
print("8-byte-shift corruption present:", ok)
print("missing first 8 bytes:", good[:8].hex(), "(mov x9,#0x30; b 0x8fc reset vector)" if good[:8] == bytes.fromhex("090680d23e020014") else "")
sys.exit(0 if not ok else 1)

