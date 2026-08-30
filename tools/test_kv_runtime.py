import importlib.util
import mmap
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "kv_runtime", Path(__file__).with_name("kv-runtime.py")
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeBuffer:
    next_handle = 1

    def __init__(self, size):
        self.map = mmap.mmap(-1, size)
        self.bo = SimpleNamespace(handle=FakeBuffer.next_handle)
        FakeBuffer.next_handle += 1

    def write(self, data):
        self.map.seek(0)
        self.map.write(data)

    def close(self):
        self.map.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class FakeDevice:
    def __init__(self):
        self.fd = 9
        self.buffers = []

    def buffer(self, size):
        buffer = FakeBuffer(size)
        self.buffers.append(buffer)
        return buffer


class KvSubmit:
    def __init__(self, device):
        self.device = device
        self.inputs = []
        self.outputs = []
        self.handles = []

    def __call__(self, _fd, _request_code, request):
        source = self._buffer(request.handles[5])
        output = self._buffer(request.handles[4])
        shape = (1, 4, 9, 4, 576, 64)
        source_view = MODULE.BASE.tensor_view(source, shape)
        output_view = MODULE.BASE.tensor_view(output, shape)
        self.inputs.append(source_view.copy())
        self.handles.append((request.handles[5], request.handles[4]))
        if not np.isinf(output_view[:, :, -1:, :]).all():
            raise AssertionError("completion row sentinel was not reset")

        key = source_view[0, :, 0:1, :]
        value = source_view[0, :, 1:2, :]
        keys = np.concatenate((source_view[0, :, 3:5, :], key), axis=1)
        values = np.concatenate((source_view[0, :, 6:8, :], value), axis=1)
        output_view[...] = source_view
        output_view[0, :, 2:5, :] = keys
        output_view[0, :, 5:8, :] = values
        output_view[0, :, 8:9, :] = value
        self.outputs.append(output_view.copy())

    def _buffer(self, handle):
        return next(buffer for buffer in self.device.buffers if buffer.bo.handle == handle)


def write_artifact(path):
    tiles = [0] * 32
    tiles[0] = tiles[3] = tiles[4] = tiles[5] = 1
    nchw = [0] * 192
    shape = [1, 4, 9, 4, 576, 64]
    nchw[4 * 6 : 5 * 6] = shape
    nchw[5 * 6 : 6 * 6] = shape
    size = 0x274
    header = MODULE.BASE.PROBE.ANEC_HEADER.pack(
        size, size, 1, size, 0, 1, 1, *tiles, *nchw
    )
    task = bytearray(size)
    struct.pack_into("<I", task, 0x28, 0xF401F800)
    path.write_bytes(header + b"\0" * (MODULE.BASE.PROBE.HEADER_SIZE - len(header)) + task)


class KvRuntimeTests(unittest.TestCase):
    def setUp(self):
        FakeBuffer.next_handle = 1
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "kv.anec"
        write_artifact(self.path)
        self.device = FakeDevice()
        self.submit = KvSubmit(self.device)

    def tearDown(self):
        self.tmp.cleanup()

    def test_keeps_cache_in_ping_pong_buffers_across_steps(self):
        key = np.arange(8, dtype=np.float16).reshape(2, 4) / 20
        value = key + np.float16(0.25)
        with MODULE.KvStateRunner(
            self.path, kv_heads=2, device=self.device, submit=self.submit
        ) as runner:
            runner.initialize()
            runner.step(key, value)
            first_keys, first_values = runner.snapshot_cache()
            runner.step(key + 0.2, value + 0.3)
            second_keys, second_values = runner.snapshot_cache()

        self.assertEqual(self.submit.handles, [(3, 4), (4, 3)])
        np.testing.assert_array_equal(self.submit.inputs[1][0, :, 2:5, :], first_keys)
        np.testing.assert_array_equal(self.submit.inputs[1][0, :, 5:8, :], first_values)
        np.testing.assert_array_equal(second_keys, self.submit.outputs[1][0, :, 2:5, :])
        np.testing.assert_array_equal(second_values, self.submit.outputs[1][0, :, 5:8, :])

    def test_rejects_invalid_grouped_query_layout(self):
        with self.assertRaisesRegex(ValueError, "query heads must be divisible"):
            MODULE.KvStateRunner(
                self.path, kv_heads=3, device=self.device, submit=self.submit
            )


if __name__ == "__main__":
    unittest.main()
