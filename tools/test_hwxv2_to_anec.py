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

    def test_td_size_follows_the_real_task_stream(self):
        # A hardcoded 0x274 over-fetched past a 0x1f8 task and decoded the
        # weight blob as register writes, so TM never went idle (-110).
        for name in ('tools/fresh-64.hwx.sample', 'tools/fresh-w4.hwx.sample'):
            image = MODULE.parse_hwx((ROOT / name).read_bytes())
            text = image.sections[('__TEXT', '__text')]
            self.assertEqual(image.td_size, text.size, name)

    def test_task_record_ignores_the_record_word_count(self):
        # macOS builds differ in the header's top byte: 0xf401f800 and
        # 0x4401f800 are the same 0x01f800 register write.
        self.assertTrue(MODULE.is_task_record(0xF401F800))
        self.assertTrue(MODULE.is_task_record(0x4401F800))
        self.assertFalse(MODULE.is_task_record(0x4401F804))


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
        # Current ABI (post 10d7c1f9 td clamp + 7e55943c tile units):
        # content tiles in 0x4000-B units, td_size clamped to 0x1f8.
        self.assertEqual(fields[:5], (0x4000, 504, 1, 628, 0x80))
        # Task-0's header word carries the re-encoded tile count; compare
        # the payload past it.
        self.assertEqual(
            result[0x1000 + 0x40:0x1000 + 0x4000],
            self.data[0x4000 + 0x40:0x8000],
        )

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


class DerivedKernelSectionTests(unittest.TestCase):
    """The kernel section must hold coefficients, not the blob's own header."""

    KERNEL_SIZE = 0x80
    PAYLOAD = struct.pack('<64H', *([0x3400] * 64))

    @classmethod
    def blob(cls, payload_offset=0x80, declared=None, records=1):
        head = struct.pack('<II', records, 2) + bytes(0x38)
        body = b''
        for index in range(records):
            body += struct.pack(
                '<IIQQQ',
                MODULE.BLOB_SENTINEL,
                1,
                declared if declared is not None else cls.KERNEL_SIZE,
                0,
                payload_offset + index * len(cls.PAYLOAD),
            ) + bytes(0x20)
        blob = bytearray(head + body)
        blob += bytes(payload_offset - len(blob))
        blob += cls.PAYLOAD * records
        return bytes(blob)

    @classmethod
    def hwx_with_blob_kernel(cls):
        """fresh-w4 with a weight blob file embedded from byte 0 of __const."""
        data = bytearray((ROOT / 'tools/fresh-w4.hwx.sample').read_bytes())
        kernel = MODULE.parse_hwx(bytes(data)).sections[('__TEXT', '__const')]
        start = kernel.file_offset
        data[start:start + cls.KERNEL_SIZE] = cls.blob()[:cls.KERNEL_SIZE]
        return bytes(data)

    def test_payload_offset_is_read_out_of_the_blob_record(self):
        # MIL says BLOBFILE(offset = 64) and the writer adds a 0x40 record, so
        # the payload offset is stated by the blob, never a constant.
        self.assertEqual(MODULE.blob_payload_offset(self.blob(), 0x80), 0x80)
        self.assertEqual(
            MODULE.blob_payload_offset(self.blob(payload_offset=0x200), 0x80),
            0x200,
        )

    def test_an_unaccounted_blob_is_refused(self):
        with self.assertRaises(ValueError):
            MODULE.blob_payload_offset(self.blob(declared=0x40), 0x80)
        with self.assertRaises(ValueError):
            MODULE.blob_payload_offset(self.blob(records=2), 0x80)
        with self.assertRaises(ValueError):
            MODULE.blob_payload_offset(self.blob(payload_offset=0x10), 0x80)

    def test_blob_kernel_is_detected_and_relocated(self):
        data = self.hwx_with_blob_kernel()
        image = MODULE.parse_hwx(data)
        self.assertTrue(image.kernel_is_blob)
        result = MODULE.convert_hwx(data, 4, 4, blob=self.blob())
        start = MODULE.ANEC_HEADER_SIZE + image.kernel_offset
        # Copying __const through would put 64 header words where the first 64
        # coefficients belong and truncate the real tail.
        self.assertEqual(result[start:start + self.KERNEL_SIZE], self.PAYLOAD)
        self.assertNotEqual(
            result[start:start + self.KERNEL_SIZE],
            data[image.content_offset + image.kernel_offset:][:self.KERNEL_SIZE],
        )

    def test_blob_kernel_without_the_blob_is_refused(self):
        # Emitting the truncated, header-prefixed coefficient stream is the
        # defect; refusing names the missing input instead.
        with self.assertRaises(ValueError):
            MODULE.convert_hwx(self.hwx_with_blob_kernel(), 4, 4)

    def test_a_plain_kernel_section_is_copied_verbatim(self):
        for name, channels in (('fresh-64', 64), ('fresh-w4', 4)):
            data = (ROOT / f'tools/{name}.hwx.sample').read_bytes()
            image = MODULE.parse_hwx(data)
            self.assertFalse(image.kernel_is_blob, name)
            result = MODULE.convert_hwx(data, channels, channels)
            # The task stream legitimately carries the current ABI's
            # re-encoded tile counts (10d7c1f9 td clamp, 7e55943c tile
            # units); the kernel COEFFICIENTS must still be verbatim.
            self.assertEqual(
                result[MODULE.ANEC_HEADER_SIZE + image.kernel_offset:
                       MODULE.ANEC_HEADER_SIZE + image.kernel_offset
                       + image.kernel_size],
                data[image.content_offset + image.kernel_offset:
                     image.content_offset + image.kernel_offset
                     + image.kernel_size],
                name,
            )

    def test_a_kernel_section_off_align16_is_refused(self):
        # libane reads the kernel at 0x1000 + align16(tsk_size); a section
        # anywhere else is read from the wrong bytes whatever it holds.
        data = bytearray((ROOT / 'tools/fresh-w4.hwx.sample').read_bytes())
        section = 0x230  # __TEXT,__const section_64 record
        moved = struct.unpack_from('<I', data, section + 48)[0] + 0x40
        struct.pack_into('<I', data, section + 48, moved)
        with self.assertRaises(ValueError):
            MODULE.parse_hwx(bytes(data))


class DerivedGeometryTests(unittest.TestCase):
    """nchw plane and row bytes are per-program and the task states them."""

    def test_tile_dma_counts_are_decoded_from_the_task(self):
        for name, expected in (
            ('fresh-64', (64, 4096, 64, 4096)),
            ('fresh-w4', (64, 192, 64, 128)),
        ):
            image = MODULE.parse_hwx(
                (ROOT / f'tools/{name}.hwx.sample').read_bytes()
            )
            self.assertEqual(
                (
                    image.tile_dma.source_run,
                    image.tile_dma.source_total,
                    image.tile_dma.dest_run,
                    image.tile_dma.dest_total,
                ),
                expected,
                name,
            )

    def test_one_run_per_channel_is_the_padded_plane_layout(self):
        # The proven mil-hwxc 64-element program: 0x13810 = 64 with
        # 0x13814 = 4096, which is exactly its (1,64,1,1,64,64) header.
        self.assertEqual(MODULE.derive_strides((1, 64, 1, 1), 4096, 64), (64, 64))

    def test_a_single_run_is_a_dense_surface(self):
        # The exported 1x896 add: every tile-DMA count reads 1792 = 896 * 2,
        # so the engine moves one contiguous run and the plane stride is 2.
        self.assertEqual(MODULE.derive_strides((1, 896, 1, 1), 1792, 1792), (2, 2))
        self.assertEqual(MODULE.derive_strides((1, 512, 1, 1), 1024, 1024), (2, 2))

    def test_counts_the_task_does_not_account_for_fall_back(self):
        # fresh-w4 moves 3 runs of 64 against 4 declared channels: neither the
        # padded nor the dense reading holds, so the convention stands.
        self.assertEqual(MODULE.derive_strides((1, 4, 1, 1), 192, 64), (64, 64))
        self.assertEqual(MODULE.derive_strides((1, 4, 1, 1), 0, 0), (64, 64))
        self.assertEqual(MODULE.derive_strides((1, 4, 1, 1), 100, 7), (64, 64))

    def test_a_dense_task_moves_the_header_off_the_padding_convention(self):
        image = MODULE.parse_hwx((ROOT / 'tools/fresh-64.hwx.sample').read_bytes())
        dense = replace(
            image, tile_dma=MODULE.TileDMA(0x1000, 0x1000, 0x1000, 0x1000)
        )
        header = struct.unpack_from(
            '<QIIQQII32I192Q',
            MODULE._build_header(dense, (1, 2048, 1, 1), (1, 2048, 1, 1)),
        )
        nchw = header[39:]
        self.assertEqual(tuple(nchw[4 * 6:4 * 6 + 6]), (1, 2048, 1, 1, 2, 2))
        self.assertEqual(tuple(nchw[5 * 6:5 * 6 + 6]), (1, 2048, 1, 1, 2, 2))
        self.assertEqual(header[7 + 4], 1)
        self.assertEqual(header[7 + 5], 1)

    def test_the_qualified_64_element_geometry_is_unchanged(self):
        # The regression bar: the device-qualified 64-element class must keep
        # (1,64,1,1,64,64) and its one-tile surfaces.
        data = (ROOT / 'tools/fresh-64.hwx.sample').read_bytes()
        header = struct.unpack_from(
            '<QIIQQII32I192Q', MODULE.convert_hwx(data, 64, 64), 0
        )
        nchw = header[39:]
        self.assertEqual(tuple(nchw[4 * 6:4 * 6 + 6]), (1, 64, 1, 1, 64, 64))
        self.assertEqual(tuple(nchw[5 * 6:5 * 6 + 6]), (1, 64, 1, 1, 64, 64))
        self.assertEqual(header[7 + 4], 1)
        self.assertEqual(header[7 + 5], 1)

    def test_a_record_running_past_the_descriptor_is_rejected(self):
        # This over-run is the -110 defect class: the walk must not decode
        # bytes the task does not own.
        td = bytearray(0x40)
        struct.pack_into('<I', td, 0x28, (0x3F << 26) | 0x13800)
        with self.assertRaises(ValueError):
            MODULE.walk_registers(bytes(td))

    def test_an_extra_header_word_is_not_a_register_record(self):
        # header[9] & 0x3 == 0x3: one extra word at 0x28, first record at 0x2c.
        td = bytearray(0x38)
        struct.pack_into('<I', td, 36, 0x23)
        struct.pack_into('<I', td, 40, 0)
        struct.pack_into('<I', td, 44, MODULE.TILE_DMA_SOURCE_RUN)
        struct.pack_into('<I', td, 48, 1792)
        self.assertEqual(MODULE.walk_registers(bytes(td)), {0x13810: 1792})

    def test_header_bit1_alone_does_not_skip_a_word(self):
        # 0x26 has bit 1 set and no extra word (corpus: H13 header[9]).
        td = bytearray(0x34)
        struct.pack_into('<I', td, 36, 0x26)
        struct.pack_into('<I', td, 40, MODULE.TILE_DMA_SOURCE_RUN)
        struct.pack_into('<I', td, 44, 4096)
        self.assertEqual(MODULE.walk_registers(bytes(td)), {0x13810: 4096})

    def test_predecessor_scan_reaches_a_short_last_task(self):
        # A 0x274 floor stopped before 0x200 when the section is 0x400.
        data = bytearray(0x400)
        struct.pack_into('<I', data, 0x328, MODULE.TD_MAGIC)
        struct.pack_into('<I', data, 0x200, 0x10)
        struct.pack_into('<I', data, 0x21C, 0x300)
        struct.pack_into('<I', data, 0x300, 0x11)
        self.assertEqual(
            MODULE.find_task_offsets(bytes(data), 0, len(data)),
            (0x200, 0x300),
        )



if __name__ == '__main__':
    unittest.main()
