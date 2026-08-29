import importlib.util
import struct
import unittest
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "production_anec_probe", Path(__file__).with_name("production-anec-probe.py")
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProductionProbeTests(unittest.TestCase):
    def test_copy_content_uses_offset_and_size(self):
        data = bytes(range(256)) * 2
        destination = BytesIO()
        MODULE.copy_content(data, 17, 100, destination)
        self.assertEqual(destination.getvalue(), data[17:117])

    def test_copy_task_stream_preserves_variable_spacing(self):
        data = bytes(range(256)) * 2
        self.assertEqual(MODULE.copy_task_stream(data, 17, 100), data[17:117])

    def test_task_bases_follow_descriptor_slots(self):
        data = bytearray(0x700)
        struct.pack_into("<I", data, 0x28, 0xF401F800)
        struct.pack_into("<I", data, 0x328, 0xF401F800)
        self.assertEqual(MODULE.task_bases(data, 0, len(data)), (0, 0x300))

    def test_bootstrap_packs_and_remaps_non_contiguous_slots(self):
        data = bytearray(0x700)
        struct.pack_into("<I", data, 0x28, 0xF401F800)
        struct.pack_into("<I", data, 0x428, 0xF401F800)
        data[0:4] = b"ABCD"
        data[0x400:0x404] = b"WXYZ"
        struct.pack_into("<I", data, 0x1C, 0x400)
        struct.pack_into("<I", data, 0x41C, 0x600)
        bootstrap = MODULE.build_bootstrap(data, 0, len(data), (0, 0x400), 0x274, 2)
        self.assertEqual(len(bootstrap), 0x574)
        self.assertEqual(bootstrap[:4], b"ABCD")
        self.assertEqual(bootstrap[0x300:0x304], b"WXYZ")
        self.assertEqual(struct.unpack_from("<I", bootstrap, 0x1C)[0], 0x300)
        self.assertEqual(struct.unpack_from("<I", bootstrap, 0x31C)[0], 0)
        one = MODULE.build_bootstrap(data, 0, len(data), (0, 0x400), 0x274, 1)
        self.assertEqual(struct.unpack_from("<I", one, 0x1C)[0], 0)

    def test_bootstrap_zero_pads_short_terminal_descriptor(self):
        data = bytearray(0x700)
        data[0x600:0x680] = b"\xA5" * 0x80
        struct.pack_into("<I", data, 0x61C, 0)
        bootstrap = MODULE.build_bootstrap(data, 0, 0x680, (0x600,), 0x274, 1)
        self.assertEqual(bootstrap[:0x80], data[0x600:0x680])
        self.assertEqual(bootstrap[0x80:], b"\0" * (0x274 - 0x80))


if __name__ == "__main__":
    unittest.main()
