"""Convert a fresh macOS 26 HWX (Mach-O) into a Linux .anec for libane.

Layout discovered by diffing fresh compiles against retained working graphs:
  payload tile starts at 0x4000; TD at payload+0x28; command buffer is
  BASE+0 with size from the descriptor at 0xd0; kernel region starts at
  BASE+<kernel address word> (0x2f0 descriptor) with size = file end.

Usage: hwxv2-to-anec.py IN.hwx OUT.anec SRC_CH DST_CH
"""
import struct
import sys
from pathlib import Path

src_path, dst_path, in_ch, out_ch = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
data = Path(src_path).read_bytes()
words = struct.unpack(f'<{len(data) // 4}I', data)

magic_hits = [i * 4 for i, w in enumerate(words) if w == 0xF401F800]
assert len(magic_hits) == 1, f'expected one TD, got {magic_hits}'
td_file_off = magic_hits[0]
payload_start = td_file_off & ~0xFFF
base_hits = [i * 4 for i, w in enumerate(words) if w == 0x30000000]
td_size = 0x274
kernel_off = 0x280
kernel_size = 0x40000
cmd_size = words[base_hits[1] // 4 + 2]

content = data[payload_start:]
td_size = 0x274
size = len(content)
tiles = [0] * 32
tiles[0] = size // 0x4000 + (1 if size % 0x4000 else 0)

nchw = [0] * (32 * 6)


def put_nchw(slot, n, c, h, w, plane_stride, row_stride):
    nchw[slot * 6:slot * 6 + 6] = [n, c, h, w, plane_stride, row_stride]


put_nchw(4, 1, out_ch, 1, 1, 0x40, 0x40)
src_plane = (in_ch * 2 + 63) & -64
src_row = src_plane
put_nchw(5, 1, in_ch, 1, 1, src_plane, src_row)
src_bytes = in_ch * src_plane
tiles[5] = max(1, (src_bytes + 0x3FFF) // 0x4000)
tiles[4] = max(1, (out_ch * 0x40 + 0x3FFF) // 0x4000)
header = struct.pack(
    '<QIIQQII32I192Q',
    size, td_size, 1, td_size, kernel_size, 1, 1, *tiles, *nchw,
)

header += b'\x00' * (0x1000 - len(header))
Path(dst_path).write_bytes(header + content)
print(
    f'wrote={dst_path} content={hex(size)} td@{hex(td_file_off)} '
    f'cmd={hex(cmd_size)} kernel@content+{hex(kernel_off)} ({hex(kernel_size)}B) '
    f'src_stride={hex(src_row)}'
)
