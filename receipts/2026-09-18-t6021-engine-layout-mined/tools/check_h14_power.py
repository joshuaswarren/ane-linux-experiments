#!/usr/bin/env python3
"""Pinned H14 constructor, pre-CPU table and power branch checks; no hardware."""
import hashlib
import struct
import sys
from pathlib import Path

data = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kernelcache.mac14j.raw").read_bytes()
assert hashlib.sha256(data).hexdigest() == "8304156fe05849a45f1c15807432e82cb0e8ac8cb9c883541889bf51287340fa"
base = 0x7004000
anchors = {
    0x959B174: 0x9123A016,  # x22=device+0x8e8
    0x959B264: 0xB907827F,  # zero four flag bytes at0x780
    0x959B268: 0x391E127F,  # zero flag byte0x784
    0x959B290: 0xA9007EDF,  # zero16 bytes at0x8e8
    0x95D0A94: 0xB9407D09,  # normalized type, not raw ane-type
    0x95D0A98: 0x5100C129,
    0x95D0A9C: 0x13891130,
    0x95D0AB8: 0xB8B07A30,  # relative signed jump table
    0x95D0DD0: 0xB9408508,  # subtype0 or1
    0x95D0DE8: 0x39400108,
    0x95D0DEC: 0x370820C8,  # device+0x3ea0 bit1 selects alternative
    0x95D0E08: 0x52805C01,  # PMGR offset0x2e0
    0x95D0E0C: 0x528001E2,  # plain branch writes0xf
    0x95D1240: 0x12027402,  # alternative clears bits28..29
    0x95D1250: 0xD73F0930,
    0x95D1290: 0x5103C122,  # alternative value0x1000000f
    0x95D1294: 0x52805C01,
    0x9615008: 0xF001AAA8,  # pre-CPU table address
    0x961500C: 0x91062108,
    0x9615010: 0xF9005288,
    0x961503C: 0xFD46C500,  # table count3
    0x95D2054: 0xB9400922,  # write value from record+8
    0x95D205C: 0x54000160,  # skip sentinel -1
    0x95D2064: 0xB9400121,  # offset from record+0
    0x95D2080: 0xD73F0910,  # write32 accessor
    0x9612BFC: 0x52800068,  # default power selector3
    0x9612C00: 0xB93EA268,  # device+0x3ea0
    0x9615E24: 0xD503245F,  # parseANEBootArgs is bti/ret in this KC
    0x9615E28: 0xD65F03C0,
}
for address, word in anchors.items():
    assert struct.unpack_from("<I", data, address - base)[0] == word, hex(address)
assert struct.unpack_from("<i", data, 0x95D16B4 + 5 * 4 - base)[0] + 0x95D0ABC == 0x95D0DCC
assert struct.unpack_from("<2I", data, 0x7503D88 - base) == (3, 128)
for index, offset in enumerate((0xB38, 0xB98, 0xBF8)):
    assert struct.unpack_from("<5I", data, 0xCB6C188 + index * 20 - base) == (
        offset, offset + 4, 0x1FF01FF, 0, 0xFFFF)
print(f"PASS: {len(anchors)} anchors, H14 CPU branch and three pre-CPU records; runtime flags unqualified")
