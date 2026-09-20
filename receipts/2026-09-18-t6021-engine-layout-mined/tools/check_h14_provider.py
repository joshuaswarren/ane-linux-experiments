#!/usr/bin/env python3
"""Verify saved macOS H14 provider identity and pinned KC branch anchors; no hardware."""
import gzip
import hashlib
import json
import plistlib
import struct
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
capture = root / "receipts/2026-09-18-jw14m2-macos27-capture/ioreg-ioservice.plist.gz"
raw = capture.read_bytes()
assert hashlib.sha256(raw).hexdigest() == "e4688fa51b1750e71ee9602dda9e4478a750302053320764b127b74fdd749f37"
node = plistlib.loads(gzip.decompress(raw))
for name in ("J414cAP", "AppleARMPE", "arm-io", "AppleT602xIO", "ane0"):
    matches = [c for c in node["IORegistryEntryChildren"] if c["IORegistryEntryName"] == name]
    assert len(matches) == 1, name
    node = matches[0]
assert node["IOObjectClass"] == "AppleARMIODevice"
assert node["ane-type"] == bytes.fromhex("a0000000")
assert node["ane-subtype"] == bytes(4)
children = node["IORegistryEntryChildren"]
assert len(children) == 1
assert children[0]["IORegistryEntryName"] == "H11ANE"
assert children[0]["IOObjectClass"] == "H11ANEIn"
assert children[0]["IOProviderClass"] == "AppleARMIODevice"

data = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kernelcache.mac14j.raw").read_bytes()
assert hashlib.sha256(data).hexdigest() == "8304156fe05849a45f1c15807432e82cb0e8ac8cb9c883541889bf51287340fa"
base = 0x7004000
anchors = {
    0x9600120: 0x34000480,  # RTBuddyService prefix match -> RTBuddy initializer
    0x9600144: 0x34000720,  # ane prefix match -> legacy provider cast
    0x960023C: 0xF9040A80,  # save provider at device+0x810
    0x9600240: 0xB4000420,  # reject failed cast
    0x9600244: 0x52800036,  # success
    0x9600248: 0x14000038,  # skip RTBuddy flag store
    0x9600288: 0x391E0296,  # RTBuddy success sets device+0x780
    0x9613368: 0xB9408288,  # load config ane-type
    0x961336C: 0x7102FD1F,
    0x9613370: 0x54000E6D,
    0x961353C: 0x71017D1F,
    0x9613540: 0x540006AC,
    0x9613614: 0x71023D1F,
    0x9613618: 0x54000F4C,
    0x9613808: 0x7102811F,  # compare ane-type 0xa0
    0x961380C: 0x54003DE0,  # equal -> 0x9613fc8
    0x9613FC8: 0x52801008,  # normalized config type 0x80
    0x9613FCC: 0xB9007E88,
    0x9613FD8: 0xD0FEF588,
    0x9613FDC: 0x911A5908,  # string h14g
}
for address, word in anchors.items():
    assert struct.unpack_from("<I", data, address - base)[0] == word, hex(address)
for address, text in ((0x74C48F6, b"RTBuddyService"), (0x74C4905, b"ane"), (0x74C5696, b"h14g")):
    offset = address - base
    assert data[offset:offset + len(text) + 1] == text + bytes(1)
print(json.dumps({"status": "PASS", "capture_provider": "ane0/H11ANE", "ane_type": 160,
                  "ane_subtype": 0, "configuration": "h14g", "instruction_anchors": len(anchors),
                  "scope": "saved macOS 27 capture and static KC; not live Linux boot qualification"}))
