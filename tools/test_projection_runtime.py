import importlib.util
import mmap
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "projection_runtime", Path(__file__).with_name("projection-runtime.py")
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


class FakeSubmit:
    def __init__(self, device, outputs):
        self.device = device
        self.outputs = iter(outputs)
        self.calls = []
        self.inputs = []

    def __call__(self, fd, request_code, request):
        self.calls.append((fd, request_code, request.td_count))
        source = next(
            buffer
            for buffer in self.device.buffers
            if buffer.bo.handle == request.handles[5]
        )
        output = next(
            buffer
            for buffer in self.device.buffers
            if buffer.bo.handle == request.handles[4]
        )
        strides = (4 * 64, 64, 64, 2)
        source_view = np.ndarray(
            (1, 4, 1, 1), dtype=np.float16, buffer=source.map, strides=strides
        )
        output_view = np.ndarray(
            (1, 4, 1, 1), dtype=np.float16, buffer=output.map, strides=strides
        )
        self.inputs.append(source_view.copy())
        self.assert_sentinel(output_view)
        output_view[...] = np.asarray(next(self.outputs), dtype=np.float16).reshape(
            1, 4, 1, 1
        )

    @staticmethod
    def assert_sentinel(values):
        if not np.isinf(values).all():
            raise AssertionError(f"output sentinel was not reset: {values}")


def write_artifact(path):
    tiles = [0] * 32
    tiles[0] = 1
    tiles[3] = 1
    tiles[4] = 1
    tiles[5] = 1
    nchw = [0] * 192
    nchw[4 * 6 : 4 * 6 + 6] = [1, 4, 1, 1, 64, 64]
    nchw[5 * 6 : 5 * 6 + 6] = [1, 4, 1, 1, 64, 64]
    task_stream_size = 0x274
    header = MODULE.PROBE.ANEC_HEADER.pack(
        task_stream_size,
        task_stream_size,
        1,
        task_stream_size,
        0,
        1,
        1,
        *tiles,
        *nchw,
    )
    task = bytearray(task_stream_size)
    struct.pack_into("<I", task, 0x28, 0xF401F800)
    path.write_bytes(header + b"\0" * (MODULE.PROBE.HEADER_SIZE - len(header)) + task)


class ProjectionRuntimeTests(unittest.TestCase):
    def setUp(self):
        FakeBuffer.next_handle = 1
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "projection.anec"
        write_artifact(self.path)
        self.device = FakeDevice()

    def tearDown(self):
        self.tmp.cleanup()

    def test_binds_output_and_source_to_compiler_slots(self):
        with MODULE.ProjectionRunner(self.path, device=self.device) as runner:
            self.assertEqual(runner.request.handles[4], runner.output.bo.handle)
            self.assertEqual(runner.request.handles[5], runner.source.bo.handle)

    def test_reuses_buffers_and_resets_output_before_each_submit(self):
        submit = FakeSubmit(self.device, ([1, 2, 3, 4], [5, 6, 7, 8]))
        with MODULE.ProjectionRunner(
            self.path, device=self.device, submit=submit
        ) as runner:
            first = runner.run(np.ones((1, 4, 1, 1), dtype=np.float16))
            second = runner.run(np.full((1, 4, 1, 1), 2, dtype=np.float16))
            np.testing.assert_array_equal(submit.inputs[0].reshape(-1), [1, 1, 1, 1])
            np.testing.assert_array_equal(submit.inputs[1].reshape(-1), [2, 2, 2, 2])
            self.assertEqual(len(self.device.buffers), 5)
        np.testing.assert_array_equal(first.reshape(-1), [1, 2, 3, 4])
        np.testing.assert_array_equal(second.reshape(-1), [5, 6, 7, 8])
        self.assertEqual(len(submit.calls), 2)

    def test_rejects_wrong_input_shape_before_submit(self):
        submit = FakeSubmit(self.device, ())
        with (
            MODULE.ProjectionRunner(
                self.path, device=self.device, submit=submit
            ) as runner,
            self.assertRaisesRegex(ValueError, "input shape"),
        ):
            runner.run(np.ones(3, dtype=np.float16))
        self.assertEqual(submit.calls, [])

    def test_rejects_partial_output(self):
        submit = FakeSubmit(self.device, ([1, 2, np.inf, np.inf],))
        with (
            MODULE.ProjectionRunner(
                self.path, device=self.device, submit=submit, timeout=0.002
            ) as runner,
            self.assertRaises(TimeoutError),
        ):
            runner.run(np.ones((1, 4, 1, 1), dtype=np.float16))

    def test_rejects_truncated_artifact(self):
        self.path.write_bytes(self.path.read_bytes()[:-1])

        with self.assertRaisesRegex(ValueError, "truncated"):
            MODULE.ProjectionRunner(self.path, device=self.device)

    def test_runs_projection_without_workspace_buffer(self):
        artifact = bytearray(self.path.read_bytes())
        struct.pack_into("<I", artifact, 52, 0)
        self.path.write_bytes(artifact)
        submit = FakeSubmit(self.device, ([1, 2, 3, 4],))

        with MODULE.ProjectionRunner(
            self.path, device=self.device, submit=submit
        ) as runner:
            output = runner.run(np.ones((1, 4, 1, 1), dtype=np.float16))

        np.testing.assert_array_equal(output.reshape(-1), [1, 2, 3, 4])
        self.assertEqual(len(self.device.buffers), 4)
        self.assertEqual(submit.calls, [(9, MODULE.RUNTIME.IOCTL_SUBMIT, 1)])


if __name__ == "__main__":
    unittest.main()
