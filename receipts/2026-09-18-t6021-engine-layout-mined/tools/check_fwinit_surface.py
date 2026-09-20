#!/usr/bin/env python3
"""Check exact KC anchors for RTBuddy FW_INIT surface; never touches hardware."""
import hashlib
import json
import struct
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kernelcache.mac14j.raw")
data = path.read_bytes()
assert hashlib.sha256(data).hexdigest() == "8304156fe05849a45f1c15807432e82cb0e8ac8cb9c883541889bf51287340fa"
base = 0x7004000
anchors = {
    0x95FE46C: 0xF9401C37,  # ldr x23, [x1,#0x38]: CPU surface base
    0x95FE470: 0xB90086E8,  # str w8, [x23,#0x84]
    0x95FE47C: 0x3C888F00,  # str q0,[x24,#0x88]!: x24 becomes surface+0x88
    0x95FE4FC: 0x3D800300,  # str q0,[x24]: first template vector
    0x95FE4D0: 0xAD075F16,  # stp q22,q23,[x24,#0xe0]: final 32 template bytes
    0x95FE890: 0x39408368,  # endpoint table flag at +0x20
    0x95FE8A0: 0x97FFFEE8,  # bl SetupFWInitBootArgs
    0x95FE8A8: 0xF9000F28,  # params -> endpoint record+0x18
    0x95FE8E4: 0xB3541D2A,  # bfi size-page count at bits44..51
    0x95FE8E8: 0xB340AD0A,  # low44 bits of Params+0x18
    0x95FF968: 0x928000B5,  # endpoint loop starts -6; index = counter+7
    0x95FF9A8: 0x54FFFE43,  # continue through endpoint6
    0x9612B84: 0xF904CE60,  # template allocation -> device+0x998
}
for vm, expected in anchors.items():
    assert struct.unpack_from("<I", data, vm - base)[0] == expected, hex(vm)
expected = [
    (1, 0x10000, 0x494E4954, "FW_INIT", 1),
    (2, 0x40000, 0x54324643, "T2F_CMD", 0),
    (3, 0x40000, 0x54324648, "T2F_HIPRI", 0),
    (4, 0x10000, 0x54324853, "T2H_SHMEM", 0),
    (5, 0x20000, 0x54324843, "T2H_CMD", 0),
    (6, 0x10000, 0x54324854, "T2H_TERM", 0),
]
for index, size, tag, name, flag in expected:
    entry = struct.unpack_from("<5Q", data, 0x814E520 + index * 40 - base)
    assert entry[:3] == (index, size, tag) and entry[4] == flag
    # DYLD_CHAINED_PTR_64_KERNEL_CACHE: target30 offset from outer __TEXT.
    assert (entry[3] >> 30) & 3 == 0
    offset = entry[3] & 0x3FFFFFFF
    assert data[offset:data.index(bytes([0]), offset)].decode() == name
# x24 writeback changes the base before all template stores.
assert 0x88 + 0xE0 + 32 == 0x188
assert 0x5C0 + 1 * 0x40 + 0x18 == 0x618
print(json.dumps({"status": "PASS", "instruction_anchors": len(anchors),
                  "endpoints": expected, "template_surface_range": [0x88, 0x188],
                  "fw_init_params_device_offset": 0x618}))
