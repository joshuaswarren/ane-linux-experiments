#!/usr/bin/env python3
"""Rebuild the 1x896 HWX from the shipped ANEC, and prove the rebuild is faithful.

The macOS 26 object for ane-add-fp16-1x896 exists only on the Mac exporter
host, which is unreachable (16m1mbp and jw14m2 time out; macstudio has no
export tree). Everything the converter reads, though, is retained: the ANEC
carries the __TEXT payload verbatim, and the section sizes are stated by the
header. So the object is rebuilt on the retained 1x512 Mach-O -- same exporter,
same compiler, same single-task add family, identical task stream size -- with
the 896 payload and the 896 section sizes written in.

The rebuild is only worth anything if it converts the way the real object
would, so this asserts that: the payload is byte-identical to the shipped
content, the parse reproduces every geometry field the shipped header states,
and the emitted ANEC differs from the shipped one in exactly the four fixed
fields -- td_size, tiles, nchw plane/row, and the kernel section.
"""
import importlib.util
import pathlib
import struct
import sys
from collections import Counter

FIXTURES = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(
    '/home/joshuawarren/src/mlx-omarchy/receipts/fixtures'
)
OUTPUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path(
    '/tmp/model-1x896-reconstructed.hwx'
)
ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'hwxv2_to_anec', ROOT / 'tools/hwxv2-to-anec.py'
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

# __FVMLIB,__const (input), __FVMLIB,__data (output) and __TEXT,__const
# section_64 records in the retained 1x512 object; the size field is at +40.
SECTIONS = (0xB0, 0x148, 0x230)
SECTION_SIZE_FIELD = 40

template = (FIXTURES / 'mil-oneop/model.hwx').read_bytes()
shipped = (FIXTURES / 'exported/ane-add-fp16-1x896/model.anec').read_bytes()
weights = (FIXTURES / 'exported/ane-add-fp16-1x896/weights.bin').read_bytes()
content_size, _td, td_count, tsk_size, krn_size, src, dst = struct.unpack_from(
    '<QIIQQII', shipped, 0
)
content = shipped[0x1000:0x1000 + content_size]

image = MODULE.parse_hwx(template)
rebuilt = bytearray(template)
rebuilt[image.content_offset:image.content_offset + content_size] = content
for section in SECTIONS:
    struct.pack_into('<Q', rebuilt, section + SECTION_SIZE_FIELD, krn_size)
rebuilt = bytes(rebuilt)
OUTPUT.write_bytes(rebuilt)

parsed = MODULE.parse_hwx(rebuilt)
assert rebuilt[parsed.content_offset:parsed.content_offset + parsed.content_size] \
    == content, 'the rebuilt payload is not the shipped content'
for label, got, want in (
    ('content_size', parsed.content_size, content_size),
    ('td_count', parsed.td_count, td_count),
    ('tsk_size', parsed.task_stream_size, tsk_size),
    ('krn_size', parsed.kernel_size, krn_size),
    ('source_count', 1, src),
    ('destination_count', 1, dst),
    ('input_size', parsed.input_size, krn_size),
    ('output_size', parsed.output_size, krn_size),
):
    assert got == want, f'{label}: rebuilt {got:#x} against shipped {want:#x}'

emitted = MODULE.convert_hwx(rebuilt, 896, 896, blob=weights)
kernel_at = 0x1000 + parsed.kernel_offset


def field(offset):
    if offset in (8, 9):
        return 'td_size'
    if 40 <= offset < 168:
        return f'tiles[{(offset - 40) // 4}]'
    if 168 <= offset < 168 + 32 * 48:
        return f'nchw[{(offset - 168) // 48}][{((offset - 168) % 48) // 8}]'
    if kernel_at <= offset < kernel_at + krn_size:
        return 'kernel-section'
    return f'UNEXPECTED@{offset:#x}'


differences = Counter(
    field(i) for i in range(len(emitted)) if emitted[i] != shipped[i]
)
expected = {
    'td_size', 'tiles[4]', 'tiles[5]', 'kernel-section',
    'nchw[4][4]', 'nchw[4][5]', 'nchw[5][4]', 'nchw[5][5]',
}
print(f'rebuilt   {OUTPUT} ({len(rebuilt)} bytes)')
print(f'parse     td_size={parsed.td_size:#x} krn@{parsed.kernel_offset:#x} '
      f'({parsed.kernel_size:#x}B) blob={parsed.kernel_is_blob} '
      f'tile_dma={parsed.tile_dma}')
print(f'emitted   differs from the shipped ANEC in: {dict(differences)}')
assert set(differences) == expected, set(differences) ^ expected
assert emitted[kernel_at:kernel_at + krn_size] == weights[0x80:0x80 + krn_size]
print('EQUIVALENCE: PASS -- only the four fixed fields differ, and the kernel '
      'section is the blob payload')
