import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "attention_runtime", Path(__file__).with_name("attention-runtime.py")
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeBuffer:
    next_handle = 1

    def __init__(self, size):
        self.map = bytearray(size)
        self.bo = SimpleNamespace(handle=FakeBuffer.next_handle)
        FakeBuffer.next_handle += 1

    def write(self, data):
        if len(data) > len(self.map):
            raise ValueError("buffer overflow")
        self.map[: len(data)] = data

    def close(self):
        pass


class FakeDevice:
    def __init__(self):
        self.fd = 7
        self.qid = 2
        self.buffers = []

    def buffer(self, size):
        buffer = FakeBuffer(size)
        self.buffers.append(buffer)
        return buffer


class MutableGemmTests(unittest.TestCase):
    def setUp(self):
        FakeBuffer.next_handle = 1
        self.device = FakeDevice()
        self.program = MODULE.MutableGemm(
            self.device,
            descriptor=bytes(MODULE.RUNTIME.TD_SIZE),
            output_rows=256,
            submit=lambda *_: None,
        )

    def tearDown(self):
        self.program.close()

    def test_write_row_updates_one_packed_output_channel(self):
        values = np.arange(256, dtype=np.float16)
        self.program.write_row(33, values)

        block = self.program.weights[1]
        np.testing.assert_array_equal(block[6 + 1 : 6 + 256 * 32 : 32], values)
        self.assertEqual(np.count_nonzero(self.program.weights[0]), 0)

    def test_write_column_updates_each_output_row(self):
        values = np.arange(256, dtype=np.float16)
        self.program.write_column(7, values)

        rows = np.arange(256)
        actual = self.program.weights[rows // 32, 6 + 7 * 32 + rows % 32]
        np.testing.assert_array_equal(actual, values)

    def test_rejects_out_of_range_updates(self):
        with self.assertRaisesRegex(ValueError, "row must be in"):
            self.program.write_row(256, np.zeros(256, dtype=np.float16))
        with self.assertRaisesRegex(ValueError, "column must be in"):
            self.program.write_column(256, np.zeros(256, dtype=np.float16))

    def test_run_uses_reserved_completion_lane(self):
        def submit(_fd, _request_code, _request):
            output = np.ndarray(
                MODULE.RUNTIME.OUT_BYTES // 2,
                dtype=np.float16,
                buffer=self.program.output.map,
            )
            output[: 256 * 32 : 32] = np.arange(256, dtype=np.float16)
            output[MODULE.COMPLETION_ROW * 32] = np.float16(0)

        self.program.submit = submit
        activation = np.arange(256, dtype=np.float16)
        actual = self.program.run(activation)

        source = np.ndarray(
            MODULE.RUNTIME.SRC_BYTES // 2,
            dtype=np.float16,
            buffer=self.program.source.map,
        )
        np.testing.assert_array_equal(source[: 256 * 32 : 32], activation)
        np.testing.assert_array_equal(actual, np.arange(256, dtype=np.float16))

    def test_close_is_idempotent_and_blocks_reuse(self):
        self.program.close()
        self.program.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            self.program.write_row(0, np.zeros(256, dtype=np.float16))


class AttentionGemmStateTests(unittest.TestCase):
    def fake_programs(self):
        calls = []
        score = SimpleNamespace(
            output_rows=128,
            write_row=lambda row, value: calls.append(("key", row, value.copy())),
            run=lambda _query: np.arange(128, dtype=np.float16),
        )
        value = SimpleNamespace(
            output_rows=256,
            write_column=lambda column, item: calls.append(("value", column, item.copy())),
        )
        return calls, score, value

    def test_append_updates_matching_ring_positions(self):
        calls, score, value = self.fake_programs()
        state = MODULE.AttentionGemmState(score, value, context=128, dimension=256)
        key = np.arange(256, dtype=np.float16)
        item = key + np.float16(1)

        for _ in range(130):
            state.append(key, item)

        self.assertEqual([(call[0], call[1]) for call in calls[-4:]], [("key", 0), ("value", 0), ("key", 1), ("value", 1)])
        self.assertEqual(state.length, 128)
        self.assertEqual(state.cursor, 2)

    def test_scores_mask_unused_rows(self):
        _calls, score, value = self.fake_programs()
        state = MODULE.AttentionGemmState(score, value, context=128, dimension=256)
        key = np.zeros(256, dtype=np.float16)
        state.append(key, key)
        state.append(key, key)

        actual = state.scores(key)

        np.testing.assert_array_equal(actual[:2], np.array([0, 1], dtype=np.float16))
        np.testing.assert_array_equal(
            actual[2:], np.full(126, np.finfo(np.float16).min, dtype=np.float16)
        )

    def test_rejects_program_geometry_mismatch(self):
        _calls, score, value = self.fake_programs()
        score.output_rows = 64
        with self.assertRaisesRegex(ValueError, "score program"):
            MODULE.AttentionGemmState(score, value, context=128, dimension=256)
        score.output_rows = 128
        value.output_rows = 512
        with self.assertRaisesRegex(ValueError, "value program"):
            MODULE.AttentionGemmState(score, value, context=128, dimension=256)


if __name__ == "__main__":
    unittest.main()
