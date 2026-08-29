import importlib.util
import struct
import unittest
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
        self.assertEqual([i for i, enabled in enumerate(image.kdma.enabled) if enabled], list(range(6)))
        self.assertEqual(image.kdma.base_addresses[:6], (80, 88, 96, 104, 112, 120))
        self.assertEqual(image.kdma.buffer_sizes[:6], (8, 8, 8, 8, 8, 8))

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
    def test_task_descriptor_offsets_are_counted(self):
        data = bytearray(0x800)
        struct.pack_into('<I', data, 0x28, MODULE.TD_MAGIC)
        struct.pack_into('<I', data, 0x328, MODULE.TD_MAGIC)
        self.assertEqual(MODULE.find_task_offsets(bytes(data), 0, len(data)), (0x28, 0x328))

    def test_invalid_headers_are_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.parse_hwx(b'\0' * 32)
        with self.assertRaises(ValueError):
            MODULE.parse_hwx(self.data[:40])


    def test_content_and_descriptor_geometry(self):
        self.assertEqual(self.image.content_offset, 0x4000)
        self.assertEqual(self.image.content_size, 0x4000)
        self.assertEqual(self.image.td_offset, 0x28)
        self.assertEqual(self.image.td_size, 0x274)
        self.assertEqual(self.image.kernel_offset, 0x280)
        self.assertEqual(self.image.kernel_size, 0x80)

    def test_command_window_size_comes_from_section(self):
        self.assertEqual(self.image.command_size, 0xC0)

    def test_fresh_kdma_registers_are_decoded(self):
        kdma = self.image.kdma
        self.assertEqual([i for i, enabled in enumerate(kdma.enabled) if enabled], [])
        self.assertEqual(kdma.base_addresses[:6], (0, 0, 0, 0, 0, 0))
        self.assertEqual(kdma.base_addresses[6:], (1,) * 10)
        self.assertEqual(kdma.buffer_sizes[:6], (1,) * 6)
        self.assertEqual(kdma.buffer_sizes[6:10], (2,) * 4)
        self.assertEqual(kdma.buffer_sizes[10:14], (0,) * 4)
        self.assertEqual(kdma.buffer_sizes[14:], (1, 1))

    def test_converted_header_matches_payload(self):
        result = MODULE.convert_hwx(self.data, 4, 4)
        fields = struct.unpack_from('<QIIQQII', result, 0)
        self.assertEqual(fields[:5], (0x4000, 0x274, 1, 0x274, 0x80))
        self.assertEqual(result[0x1000:0x1000 + 0x4000], self.data[0x4000:0x8000])

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
