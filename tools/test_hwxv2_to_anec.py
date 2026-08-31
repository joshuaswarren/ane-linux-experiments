import importlib.util
import struct
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    'hwxv2_to_anec', Path(__file__).with_name('hwxv2-to-anec.py')
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
RUNTIME_SPEC = importlib.util.spec_from_file_location(
    'ane_runtime', ROOT / 'ane-runtime.py'
)
assert RUNTIME_SPEC is not None
assert RUNTIME_SPEC.loader is not None
RUNTIME = importlib.util.module_from_spec(RUNTIME_SPEC)
RUNTIME_SPEC.loader.exec_module(RUNTIME)


class FreshHWXParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = (ROOT / 'tools/fresh-w4.hwx.sample').read_bytes()
        cls.image = MODULE.parse_hwx(cls.data)


    def test_real_macos26_fixture(self):
        data = (ROOT / 'tools/fresh-64.hwx.sample').read_bytes()
        image = MODULE.parse_hwx(data)
        self.assertEqual(image.content_offset, 0x4000)
        self.assertEqual(image.content_size, 0x4000)
        self.assertEqual(image.td_size, 0x274)
        self.assertEqual(image.kernel_offset, 0x280)
        self.assertEqual(image.kernel_size, 0x2000)
        self.assertEqual(
            [i for i, enabled in enumerate(image.kdma.enabled) if enabled],
            list(range(16)),
        )
        self.assertEqual(image.kdma.base_addresses, tuple(range(0, 128, 8)))
        self.assertEqual(image.kdma.buffer_sizes, (8,) * 16)
        self.assertEqual(image.workspace_size, 0)
        self.assertEqual(image.input_size, 0x1000)
        self.assertEqual(image.output_size, 0x1000)

    def test_macho_sections_are_parsed(self):
        text = self.image.sections[('__TEXT', '__text')]
        kernel = self.image.sections[('__TEXT', '__const')]
        self.assertEqual(text.file_offset, 0x4000)
        self.assertEqual(text.size, 0x274)
        self.assertEqual(kernel.file_offset, 0x4280)
        self.assertEqual(kernel.size, 0x80)

    def test_real_macho_magic_is_accepted(self):
        data = bytearray(self.data)
        struct.pack_into('<I', data, 0, MODULE.MACHO_MAGIC_64)
        self.assertEqual(MODULE.parse_hwx(bytes(data)).td_size, 0x274)

    def test_task_descriptor_offsets_follow_noncompute_links(self):
        data = bytearray(0x680)
        struct.pack_into('<I', data, 0x28, MODULE.TD_MAGIC)
        struct.pack_into('<I', data, 0x1C, 0x300)
        struct.pack_into('<I', data, 0x328, 0x4401F800)
        struct.pack_into('<I', data, 0x31C, 0x600)
        self.assertEqual(
            MODULE.find_task_offsets(bytes(data), 0, len(data)),
            (0, 0x300, 0x600),
        )

    def test_invalid_headers_are_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.parse_hwx(b'\0' * 32)
        with self.assertRaises(ValueError):
            MODULE.parse_hwx(self.data[:40])


    def test_content_and_descriptor_geometry(self):
        self.assertEqual(self.image.content_offset, 0x4000)
        self.assertEqual(self.image.content_size, 0x4000)
        self.assertEqual(self.image.td_offset, 0)
        self.assertEqual(self.image.td_size, 0x274)
        self.assertEqual(self.image.kernel_offset, 0x280)
        self.assertEqual(self.image.kernel_size, 0x80)

    def test_buffer_spans_come_from_sections(self):
        self.assertEqual(self.image.workspace_size, 0)
        self.assertEqual(self.image.input_size, 0xC0)
        self.assertEqual(self.image.output_size, 0x80)

    def test_fresh_kdma_registers_are_decoded(self):
        kdma = self.image.kdma
        self.assertEqual(
            [i for i, enabled in enumerate(kdma.enabled) if enabled], [0, 1]
        )
        self.assertEqual(kdma.base_addresses[:2], (0, 1))
        self.assertEqual(kdma.base_addresses[2:], (0,) * 14)
        self.assertEqual(kdma.buffer_sizes, (1,) * 16)

    def test_converted_header_matches_payload(self):
        result = MODULE.convert_hwx(self.data, 4, 4)
        fields = struct.unpack_from('<QIIQQII', result, 0)
        self.assertEqual(fields[:5], (0x4000, 0x274, 1, 0x274, 0x80))
        self.assertEqual(result[0x1000:0x1000 + 0x4000], self.data[0x4000:0x8000])

    def test_header_tiles_cover_virtual_buffer_spans(self):
        image = replace(
            self.image,
            workspace_size=0x4001,
            input_size=0x8001,
            output_size=0xC001,
        )
        header = struct.unpack_from(
            '<QIIQQII32I192Q',
            MODULE._build_header(image, (1, 4, 1, 1), (1, 4, 1, 1)),
        )
        tiles = header[7:39]
        self.assertEqual(tiles[3], 2)
        self.assertEqual(tiles[5], 3)
        self.assertEqual(tiles[4], 4)

    def test_multiport_header_maps_sections_to_distinct_tiles(self):
        image = replace(
            self.image,
            input_sections=((0, 0x1000), (0, 0x8001)),
            output_sections=((0, 0x3000), (0, 0x4001)),
        )
        header = struct.unpack_from(
            '<QIIQQII32I192Q',
            MODULE._build_header(image, (1, 4, 1, 1), (1, 4, 1, 1)),
        )
        self.assertEqual(header[5:7], (2, 2))
        self.assertEqual(header[7 + 4:7 + 8], (1, 2, 1, 3))

    def test_multiport_tiles_cover_nchw_padding(self):
        image = replace(
            self.image,
            input_sections=((0, 0x1000), (0, 0x80000), (0, 0x60000)),
            output_sections=((0, 0x80000), (0, 0x1000), (0, 0x60000)),
        )
        header = struct.unpack_from(
            '<QIIQQII32I192Q',
            MODULE._build_header(image, (1, 2048, 1, 1), (1, 2048, 1, 1)),
        )
        self.assertEqual(header[7 + 4:7 + 10], (32, 8, 24, 8, 32, 24))

    def test_packers_reuse_output_buffers(self):
        matrix_256 = np.arange(512 * 256, dtype=np.float16).reshape(512, 256)
        expected_256 = RUNTIME.pack_weights(matrix_256)
        output_256 = np.empty_like(expected_256)
        self.assertIs(RUNTIME.pack_weights(matrix_256, output_256), output_256)
        np.testing.assert_array_equal(output_256, expected_256)

        matrix_512 = np.arange(512 * 512, dtype=np.float16).reshape(512, 512)
        expected_512 = RUNTIME.pack_weights_512(matrix_512)
        output_512 = np.empty_like(expected_512)
        self.assertIs(RUNTIME.pack_weights_512(matrix_512, output_512), output_512)
        np.testing.assert_array_equal(output_512, expected_512)


if __name__ == '__main__':
    unittest.main()
