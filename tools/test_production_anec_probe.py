import hashlib
import importlib.util
import struct
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

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

    def test_original_prefix_preserves_spacing_and_terminates_selected_task(self):
        data = bytearray(0x700)
        struct.pack_into("<H", data, 6, 0x9C)
        struct.pack_into("<I", data, 0x1C, 0x400)
        data[0x280:0x284] = b"SIDE"
        prefix = MODULE.build_original_prefix(data, 0, len(data), (0, 0x400), 1)
        self.assertEqual(len(prefix), len(data))
        self.assertEqual(prefix[0x280:0x284], b"SIDE")
        self.assertEqual(prefix[3] & 0x3, 0x3)
        self.assertEqual(struct.unpack_from("<H", prefix, 6)[0] & 0x1FF, 0)
        self.assertEqual(struct.unpack_from("<I", prefix, 0x1C)[0], 0)

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

    def test_stage_geometry_decodes_production_buffer_roles(self):
        tiles = [0] * 32
        tiles[0] = 1
        tiles[3] = 0x66
        tiles[4] = 5
        tiles[5] = 6
        nchw = [0] * 192
        nchw[24:30] = [1, 2048, 1, 1, 64, 64]
        nchw[30:36] = [1, 2048, 1, 1, 64, 64]
        header = MODULE.ANEC_HEADER.pack(
            0x59238000, 0x274, 3, 0xEA2F8, 0x40, 1, 1, *tiles, *nchw
        )
        stage = MODULE.stage_geometry(MODULE.ANEC_HEADER.unpack(header))
        self.assertEqual(stage["workspace_size"], 0x66 * MODULE.TILE_SIZE)
        self.assertEqual(stage["output_size"], 5 * MODULE.TILE_SIZE)
        self.assertEqual(stage["source_size"], 6 * MODULE.TILE_SIZE)
        self.assertEqual(stage["output_nchw"], (1, 2048, 1, 1, 64, 64))
        self.assertEqual(stage["source_nchw"], (1, 2048, 1, 1, 64, 64))
        self.assertEqual(stage["td_count"], 3)
        self.assertEqual(stage["src_count"], 1)
        self.assertEqual(stage["dst_count"], 1)

    def test_file_sha256_matches_hashlib_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.anec"
            path.write_bytes(b"production-artifact")
            self.assertEqual(
                MODULE.file_sha256(path),
                hashlib.sha256(b"production-artifact").hexdigest(),
            )

    def test_validate_expected_hash_rejects_mismatch_before_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.anec"
            path.write_bytes(b"production-artifact")
            digest = MODULE.file_sha256(path)
            self.assertEqual(MODULE.validate_expected_hash(path, digest), digest)
            with self.assertRaises(ValueError):
                MODULE.validate_expected_hash(path, "0" * 64)

    def test_validate_handoff_accepts_matching_contract(self):
        head = {
            "output_nchw": (1, 2048, 1, 1, 64, 64),
            "output_size": 0x90C000,
            "workspace_size": 0x68000,
        }
        tail = {
            "source_nchw": (1, 2048, 1, 1, 64, 64),
            "source_size": 0x730000,
            "workspace_size": 0x68000,
        }
        MODULE.validate_handoff(head, tail)

    def test_validate_handoff_rejects_shape_mismatch(self):
        head = {
            "output_nchw": (1, 2048, 1, 1, 64, 64),
            "output_size": 0x90C000,
            "workspace_size": 0x68000,
        }
        tail = {
            "source_nchw": (1, 1024, 1, 1, 64, 64),
            "source_size": 0x730000,
            "workspace_size": 0x68000,
        }
        with self.assertRaises(ValueError):
            MODULE.validate_handoff(head, tail)

    def test_validate_handoff_rejects_tail_source_beyond_saved_output(self):
        head = {
            "output_nchw": (1, 2048, 1, 1, 64, 64),
            "output_size": 0x1000,
            "workspace_size": 0x68000,
        }
        tail = {
            "source_nchw": (1, 2048, 1, 1, 64, 64),
            "source_size": 0x730000,
            "workspace_size": 0x68000,
        }
        with self.assertRaises(ValueError):
            MODULE.validate_handoff(head, tail)

    def test_validate_handoff_rejects_missing_workspace(self):
        head = {
            "output_nchw": (1, 2048, 1, 1, 64, 64),
            "output_size": 0x90C000,
            "workspace_size": 0,
        }
        tail = {
            "source_nchw": (1, 2048, 1, 1, 64, 64),
            "source_size": 0x730000,
            "workspace_size": 0x68000,
        }
        with self.assertRaises(ValueError):
            MODULE.validate_handoff(head, tail)

    def test_parse_args_exposes_task_zero_envelope_option(self):
        with mock.patch(
            "sys.argv",
            ["probe", "target.anec", "--task-zero-envelope", "control.anec"],
        ):
            args = MODULE.parse_args()
        self.assertEqual(args.task_zero_envelope, Path("control.anec"))

    def test_parse_args_exposes_task_zero_descriptor_option(self):
        with mock.patch(
            "sys.argv",
            ["probe", "target.anec", "--task-zero-descriptor", "control.anec"],
        ):
            args = MODULE.parse_args()
        self.assertEqual(args.task_zero_descriptor, Path("control.anec"))

    def test_parse_args_rejects_envelope_with_descriptor(self):
        with mock.patch(
            "sys.argv",
            [
                "probe",
                "target.anec",
                "--task-zero-envelope",
                "control.anec",
                "--task-zero-descriptor",
                "other.anec",
            ],
        ):
            with self.assertRaises(SystemExit):
                MODULE.parse_args()

    def test_splice_replaces_exactly_ten_envelope_words(self):
        target = bytearray(range(0x80))
        control = bytearray((i * 7 + 3) & 0xFF for i in range(0x80))
        struct.pack_into("<I", target, 0, 0x00400005)
        struct.pack_into("<I", control, 0, 0x00400000)
        struct.pack_into("<I", target, MODULE.NEXT_POINTER_OFFSET, 0x200)
        struct.pack_into("<I", control, MODULE.NEXT_POINTER_OFFSET, 0x300)
        patched = MODULE.splice_task_zero_envelope(bytes(target), bytes(control))
        self.assertEqual(struct.unpack_from("<I", patched, 0)[0], 0x00400005)
        for offset in range(4, MODULE.TEN_WORD_ENVELOPE_SIZE, 4):
            if offset == MODULE.NEXT_POINTER_OFFSET:
                self.assertEqual(
                    struct.unpack_from("<I", patched, offset)[0], 0x200
                )
            else:
                self.assertEqual(
                    struct.unpack_from("<I", patched, offset)[0],
                    struct.unpack_from("<I", control, offset)[0],
                )

    def test_splice_preserves_qwen_body_and_link_bytes(self):
        target = bytearray(range(0x100))
        control = bytearray((i * 7 + 3) & 0xFF for i in range(0x100))
        struct.pack_into("<I", target, 0x40, 0x00400007)
        struct.pack_into("<I", target, 0x5C, 0x200)
        struct.pack_into("<I", control, 0xC0, 0x00400002)
        struct.pack_into("<I", control, 0xDC, 0x400)
        patched = MODULE.splice_task_zero_envelope(
            bytes(target), bytes(control), target_base=0x40, control_base=0xC0
        )
        self.assertEqual(patched[:0x40], bytes(target[:0x40]))
        self.assertEqual(patched[0x68:], bytes(target[0x68:]))
        self.assertEqual(struct.unpack_from("<I", patched, 0x40)[0], 0x00400007)
        self.assertEqual(struct.unpack_from("<I", patched, 0x5C)[0], 0x200)

    def test_splice_rejects_truncated_control(self):
        with self.assertRaises(ValueError):
            MODULE.splice_task_zero_envelope(
                bytes(0x80), bytes(MODULE.TEN_WORD_ENVELOPE_SIZE - 1)
            )

    def test_splice_rejects_truncated_target(self):
        with self.assertRaises(ValueError):
            MODULE.splice_task_zero_envelope(
                bytes(MODULE.TEN_WORD_ENVELOPE_SIZE - 1), bytes(0x80)
            )

    def test_splice_rejects_base_beyond_the_task_stream(self):
        with self.assertRaises(ValueError):
            MODULE.splice_task_zero_envelope(
                bytes(0x80), bytes(0x80), control_base=0x80
            )

    def test_descriptor_splice_transplants_exactly_td_size_bytes(self):
        target = bytearray(i & 0xFF for i in range(0x300))
        control = bytearray((i * 5 + 1) & 0xFF for i in range(0x300))
        struct.pack_into("<I", target, 0, 0x00400005)
        struct.pack_into("<I", control, 0, 0x00A90000)
        struct.pack_into("<I", target, MODULE.NEXT_POINTER_OFFSET, 0x200)
        struct.pack_into("<I", control, MODULE.NEXT_POINTER_OFFSET, 0x900)
        patched = MODULE.splice_task_zero_descriptor(bytes(target), bytes(control))
        self.assertEqual(len(patched), len(target))
        self.assertEqual(struct.unpack_from("<I", patched, 0)[0], 0x00A90005)
        for offset in range(4, MODULE.TD_SIZE, 4):
            if offset == MODULE.NEXT_POINTER_OFFSET:
                self.assertEqual(
                    struct.unpack_from("<I", patched, offset)[0], 0x200
                )
            else:
                self.assertEqual(
                    struct.unpack_from("<I", patched, offset)[0],
                    struct.unpack_from("<I", control, offset)[0],
                )
        self.assertEqual(patched[MODULE.TD_SIZE:], bytes(target[MODULE.TD_SIZE:]))

    def test_descriptor_splice_preserves_stream_outside_descriptor(self):
        target = bytearray(i & 0xFF for i in range(0x400))
        control = bytearray((i * 11 + 2) & 0xFF for i in range(0x400))
        struct.pack_into("<I", target, 0x40, 0x00400007)
        struct.pack_into("<I", target, 0x5C, 0x200)
        struct.pack_into("<I", control, 0xC0, 0x00B80000)
        struct.pack_into("<I", control, 0xDC, 0x500)
        patched = MODULE.splice_task_zero_descriptor(
            bytes(target), bytes(control), target_base=0x40, control_base=0xC0
        )
        self.assertEqual(patched[:0x40], bytes(target[:0x40]))
        self.assertEqual(patched[0x2B4:], bytes(target[0x2B4:]))
        self.assertEqual(struct.unpack_from("<I", patched, 0x40)[0], 0x00B80007)
        self.assertEqual(struct.unpack_from("<I", patched, 0x5C)[0], 0x200)
        for offset in range(0x44, 0x2B4, 4):
            if offset == 0x5C:
                self.assertEqual(
                    struct.unpack_from("<I", patched, offset)[0], 0x200
                )
            else:
                self.assertEqual(
                    struct.unpack_from("<I", patched, offset)[0],
                    struct.unpack_from("<I", control, offset - 0x40 + 0xC0)[0],
                )

    def test_descriptor_splice_rejects_truncated_control(self):
        with self.assertRaises(ValueError):
            MODULE.splice_task_zero_descriptor(
                bytes(0x300), bytes(MODULE.TD_SIZE - 1)
            )

    def test_descriptor_splice_rejects_truncated_target(self):
        with self.assertRaises(ValueError):
            MODULE.splice_task_zero_descriptor(
                bytes(MODULE.TD_SIZE - 1), bytes(0x300)
            )

    def test_validate_splice_geometry_rejects_short_descriptor(self):
        stage = {"td_size": 0x20, "task_stream_size": 0x274}
        with self.assertRaises(ValueError):
            MODULE.validate_splice_geometry(stage, 0x2000, stage, 0x2000)

    def test_validate_splice_geometry_rejects_truncated_artifact(self):
        stage = {"td_size": 0x274, "task_stream_size": 0x274}
        with self.assertRaises(ValueError):
            MODULE.validate_splice_geometry(
                stage, MODULE.HEADER_SIZE + 0x100, stage, 0x2000
            )

    def test_validate_splice_geometry_rejects_task_stream_below_descriptor(self):
        stage = {"td_size": 0x274, "task_stream_size": 0x100}
        with self.assertRaises(ValueError):
            MODULE.validate_splice_geometry(stage, 0x2000, stage, 0x2000)

    def test_validate_splice_geometry_accepts_descriptor_sized_td(self):
        stage = {"td_size": MODULE.TD_SIZE, "task_stream_size": MODULE.TD_SIZE}
        MODULE.validate_splice_geometry(
            stage,
            MODULE.HEADER_SIZE + MODULE.TD_SIZE,
            stage,
            MODULE.HEADER_SIZE + MODULE.TD_SIZE,
            min_td=MODULE.TD_SIZE,
        )

    def test_validate_splice_geometry_descriptor_mode_rejects_envelope_td(self):
        stage = {
            "td_size": MODULE.TEN_WORD_ENVELOPE_SIZE,
            "task_stream_size": MODULE.TD_SIZE,
        }
        with self.assertRaises(ValueError):
            MODULE.validate_splice_geometry(
                stage, 0x2000, stage, 0x2000, min_td=MODULE.TD_SIZE
            )


if __name__ == "__main__":
    unittest.main()
