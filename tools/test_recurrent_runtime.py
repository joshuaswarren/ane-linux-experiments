import importlib.util
import mmap
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "recurrent_runtime", Path(__file__).with_name("recurrent-runtime.py")
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


class RecurrentSubmit:
    def __init__(self, device):
        self.device = device
        self.inputs = []
        self.handles = []

    def __call__(self, _fd, _request_code, request):
        source = self._buffer(request.handles[5])
        output = self._buffer(request.handles[4])
        source_view = MODULE.BASE.tensor_view(source, (1, 2, 9, 4, 576, 64))
        output_view = MODULE.BASE.tensor_view(output, (1, 2, 9, 4, 576, 64))
        self.inputs.append(source_view.copy())
        self.handles.append((request.handles[5], request.handles[4]))
        if not np.isinf(output_view[:, :, -1:, :]).all():
            raise AssertionError("output row sentinel was not reset")
        q = source_view[0, :, 0:1, :].astype(np.float32)
        k = source_view[0, :, 1:2, :].astype(np.float32)
        v = source_view[0, :, 2:3, :].astype(np.float32)
        beta = source_view[0, :, 3:4, 0:1].astype(np.float32)
        decay = source_view[0, :, 3:4, 1:2].astype(np.float32)
        state = source_view[0, :, 4:8, :].astype(np.float32)
        state_next = state * decay + np.transpose(k, (0, 2, 1)) @ (
            (v - k @ (state * decay)) * beta
        )
        output_view[...] = source_view
        output_view[0, :, 4:8, :] = state_next.astype(np.float16)
        output_view[0, :, 8:9, :] = (q @ state_next).astype(np.float16)

    def _buffer(self, handle):
        return next(buffer for buffer in self.device.buffers if buffer.bo.handle == handle)


def write_artifact(path):
    tiles = [0] * 32
    tiles[0] = tiles[3] = tiles[4] = tiles[5] = 1
    nchw = [0] * 192
    shape = [1, 2, 9, 4, 576, 64]
    nchw[4 * 6 : 5 * 6] = shape
    nchw[5 * 6 : 6 * 6] = shape
    size = 0x274
    header = MODULE.BASE.PROBE.ANEC_HEADER.pack(
        size, size, 1, size, 0, 1, 1, *tiles, *nchw
    )
    task = bytearray(size)
    struct.pack_into("<I", task, 0x28, 0xF401F800)
    path.write_bytes(header + b"\0" * (MODULE.BASE.PROBE.HEADER_SIZE - len(header)) + task)


class RecurrentRuntimeTests(unittest.TestCase):
    def setUp(self):
        FakeBuffer.next_handle = 1
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "recurrent.anec"
        write_artifact(self.path)
        self.device = FakeDevice()
        self.submit = RecurrentSubmit(self.device)

    def tearDown(self):
        self.tmp.cleanup()

    def test_keeps_state_in_ping_pong_buffers_across_steps(self):
        state = np.arange(32, dtype=np.float16).reshape(2, 4, 4) / 50
        vectors = np.arange(8, dtype=np.float16).reshape(2, 4) / 10
        beta = np.asarray([0.25, 0.75], dtype=np.float16)
        decay = np.asarray([0.9, 0.8], dtype=np.float16)
        with MODULE.RecurrentRunner(
            self.path, device=self.device, submit=self.submit
        ) as runner:
            runner.initialize(state)
            first = runner.step(vectors, vectors + 0.1, vectors + 0.2, beta, decay)
            first_state = runner.snapshot_state()
            second = runner.step(vectors + 0.3, vectors + 0.4, vectors + 0.5, beta, decay)
            second_state = runner.snapshot_state()

        self.assertEqual(self.submit.handles[0], (3, 4))
        self.assertEqual(self.submit.handles[1], (4, 3))
        np.testing.assert_array_equal(self.submit.inputs[1][0, :, 4:8, :], first_state)
        self.assertEqual(first.shape, (2, 4))
        self.assertEqual(second.shape, (2, 4))
        self.assertTrue(np.isfinite(second_state).all())

    def test_rejects_invalid_layout(self):
        artifact = bytearray(self.path.read_bytes())
        struct.pack_into("<Q", artifact, 160 + 5 * 6 * 8 + 2 * 8, 8)
        self.path.write_bytes(artifact)
        with self.assertRaisesRegex(ValueError, "recurrent tensor layout"):
            MODULE.RecurrentRunner(self.path, device=self.device, submit=self.submit)


if __name__ == "__main__":
    unittest.main()
