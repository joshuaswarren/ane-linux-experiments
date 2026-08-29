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

    def test_submission_pad_encodes_explicit_queue(self):
        self.assertEqual(MODULE.submission_pad(None), 0)
        self.assertEqual(MODULE.submission_pad(1), 0x81)

    def test_parse_int_accepts_hexadecimal_geometry(self):
        self.assertEqual(MODULE.parse_int("0x200"), 0x200)

    def test_task_bases_follow_descriptor_slots(self):
        data = bytearray(0x700)
        struct.pack_into("<I", data, 0x28, 0xF401F800)
        struct.pack_into("<I", data, 0x328, 0xF401F800)
        self.assertEqual(MODULE.task_bases(data, 0, len(data)), (0, 0x300))

    def test_bootstrap_packs_and_remaps_non_contiguous_slots(self):
        data = bytearray(0x700)
        struct.pack_into("<I", data, 0x28, 0xF401F800)
        struct.pack_into("<I", data, 0x428, 0xF401F800)
        data[0x40:0x44] = b"ABCD"
        data[0x440:0x444] = b"WXYZ"
        struct.pack_into("<I", data, 0x1C, 0x400)
        struct.pack_into("<I", data, 0x41C, 0x600)
        bootstrap = MODULE.build_bootstrap(data, 0, len(data), (0, 0x400), 0x274, 2)
        self.assertEqual(len(bootstrap), 0x574)
        self.assertEqual(bootstrap[0x40:0x44], b"ABCD")
        self.assertEqual(bootstrap[0x340:0x344], b"WXYZ")
        self.assertEqual(struct.unpack_from("<I", bootstrap, 0x1C)[0], 0x300)
        self.assertEqual(struct.unpack_from("<I", bootstrap, 0x31C)[0], 0)
        one = MODULE.build_bootstrap(data, 0, len(data), (0, 0x400), 0x274, 1)
        self.assertEqual(struct.unpack_from("<I", one, 0x1C)[0], 0)

    def test_bootstrap_rebases_ids_and_terminates_last_task(self):
        data = bytearray(0x700)
        struct.pack_into("<I", data, 0, 7)
        struct.pack_into("<H", data, 6, 0x9C)
        struct.pack_into("<I", data, 0x1C, 0x400)
        struct.pack_into("<I", data, 0x400, 9)
        struct.pack_into("<H", data, 0x406, 0x9C)
        bootstrap = MODULE.build_bootstrap(data, 0, len(data), (0, 0x400), 0x274, 2)
        self.assertEqual(struct.unpack_from("<H", bootstrap, 0)[0], 0)
        self.assertEqual(struct.unpack_from("<H", bootstrap, 0x300)[0], 1)
        self.assertEqual(bootstrap[0x303] & 0x3, 0x3)
        self.assertEqual(struct.unpack_from("<H", bootstrap, 0x306)[0] & 0x1FF, 0)

    def test_bootstrap_zero_pads_short_terminal_descriptor(self):
        data = bytearray(0x700)
        data[0x600:0x680] = b"\xA5" * 0x80
        struct.pack_into("<I", data, 0x61C, 0)
        bootstrap = MODULE.build_bootstrap(data, 0, 0x680, (0x600,), 0x274, 1)
        self.assertEqual(bootstrap[8:0x80], data[0x608:0x680])
        self.assertEqual(bootstrap[0x80:], b"\0" * (0x274 - 0x80))


if __name__ == "__main__":
    unittest.main()
