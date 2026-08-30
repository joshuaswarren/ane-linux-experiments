import importlib.util
import struct
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "hwxv2_to_anec", Path(__file__).with_name("hwxv2-to-anec.py")
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OldFormatHWXParserTests(unittest.TestCase):
    def test_accepts_non_file_backed_virtual_buffer_sections(self):
        data = bytearray(Path(__file__).with_name("fresh-w4.hwx.sample").read_bytes())
        command_offset = 32
        for _ in range(struct.unpack_from("<I", data, 16)[0]):
            command, command_size = struct.unpack_from("<II", data, command_offset)
            if command == MODULE.LC_SEGMENT_64:
                segment = struct.unpack_from("<16s", data, command_offset + 8)[0]
                file_size = struct.unpack_from("<Q", data, command_offset + 48)[0]
                section_count = struct.unpack_from("<I", data, command_offset + 64)[0]
                if (
                    segment.rstrip(b"\0") == b"__FVMLIB"
                    and file_size == 0
                    and section_count
                ):
                    section_offset = command_offset + 72
                    struct.pack_into("<Q", data, section_offset + 40, len(data) + 1)
                    break
            command_offset += command_size
        else:
            self.fail("fixture has no virtual buffer section")

        image = MODULE.parse_hwx(data)

        self.assertGreater(image.input_size, len(data))


if __name__ == "__main__":
    unittest.main()
