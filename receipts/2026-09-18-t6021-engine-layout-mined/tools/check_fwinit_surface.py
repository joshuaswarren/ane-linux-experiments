#!/usr/bin/env python3
"""Check pinned legacy and RTBuddy init surfaces; never touches hardware."""
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
    0x9612B60: 0x52802000,  # allocation size 0x100
    0x9612B64: 0x52800081,  # allocation flags 4 (Z_ZERO)
    0x9612B68: 0x9400E618,  # bl _kalloc_data auth stub
    0x964C3C8: 0xF0FF58B1,  # stub GOT page 0x8163000
    0x964C3CC: 0x91228231,  # GOT offset 0x8a0
    0xBC4DD20: 0x33000822,  # kalloc_data preserves flags bits0..2
    0x9612A60: 0x91043016,  # x22 = config+0x10c
    0x9612B48: 0xB0FEF788,  # constant page 0x7503000
    0x9612B4C: 0xFD46AD00,  # d0 = constant8 at0x7503d58
    0x9612B50: 0xFD0066C0,  # d0 -> config+[0x1d4,0x1dc)
    0x9612B70: 0xB941DA89,  # load config+0x1d8
    0x9612B74: 0xB9000009,  # store template word0
    0x95EA710: 0xF944B660,  # offset allocator at device+0x968
    0x95EA714: 0x52802E81,  # request 0x174 bytes
    0x95EA718: 0x97FE73FA,
    0x95EA720: 0xB9096260,  # save offset at device+0x960
    0x95EA730: 0xF944C268,  # pool Params at device+0x980
    0x95EA734: 0xF9401D09,  # pool CPU base
    0x95EA738: 0x8B20C139,  # x25 = CPU base + signed offset
    0x95EA908: 0x3C86CEC0,  # x22 writeback to x25+0x6c
    0x95EA90C: 0x52800808,  # 64 words
    0x95EA910: 0xB81FC2C8,  # count at x25+0x68
    0x95EA934: 0xF944CE68,  # template source device+0x998
    0x95EA958: 0xAD075ED6,  # last 32 template bytes
    0x95EA97C: 0xAD0006C0,  # first 32 template bytes
    0x95EAA90: 0xD5033E9F,  # dsb st before publication
    0x95EAA98: 0xB9443A61,  # low publication register offset
    0x95EAA9C: 0xF944C268,
    0x95EAAA0: 0xB9401909,  # DMA base low32
    0x95EAAA4: 0xB9403908,  # CPU base low32
    0x95EAAA8: 0x0B190129,
    0x95EAAAC: 0x4B080122,  # low32(DMA base+x25-CPU base)
    0x95EAAD0: 0xB9443E61,  # high publication register offset
    0x95EAAD8: 0xF9400D09,
    0x95EAADC: 0xF9401D08,
    0x95EAAE0: 0x8B190129,
    0x95EAAE4: 0xCB080128,
    0x95EAAE8: 0xD360FD02,  # high32(DMA base+x25-CPU base)
    0x9622770: 0x913E0210,  # ANERegisterControl vtable address
    0x9622774: 0x91004210,  # address point +0x10
    0x9622784: 0xF9000010,
    0x9622D48: 0xF9400C08,  # mapped register base
    0x9622D4C: 0xB8214902,  # write32, not write64
}
for vm, expected in anchors.items():
    assert struct.unpack_from("<I", data, vm - base)[0] == expected, hex(vm)
assert struct.unpack_from("<Q", data, 0x81638A0 - base)[0] == 0x8011000004C49D10
assert 0x10C + 0xC8 == 0x1D4
assert struct.unpack_from("<2I", data, 0x7503D58 - base) == (128, 0)
assert struct.unpack_from("<Q", data, 0x814FFA8 - base)[0] == 0x801113440261ED44
assert (0x801113440261ED44 & 0x3FFFFFFF) + base == 0x9622D44
assert struct.unpack_from("<8I", data, 0x7503A40 - base) == tuple(range(0x1840048, 0x1840068, 4))
assert 0x6C + 0xE0 + 32 == 0x16C < 0x174
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
