#!/usr/bin/env python3
"""Compose 128-wide softmax from reusable Linux ANE elementwise programs."""

import importlib.util
from fcntl import ioctl
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
LANES = 64
WIDTH = 128
ELEMENTWISE_BYTES = 0x4000
ELEMENTWISE_MODES = ("add", "mul", "max", "sq")
EXP_LIMIT = -64.0
RECIPROCAL_ITERATIONS = 12


def load_runtime():
    path = ROOT / "ane-runtime.py"
    spec = importlib.util.spec_from_file_location("ane_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNTIME = load_runtime()


class ElementwiseBackend:
    """Reuse four ANE BOs across 64-lane elementwise submissions."""

    def __init__(self, device, descriptors, submit=ioctl):
        missing = set(ELEMENTWISE_MODES) - descriptors.keys()
        if missing:
            raise ValueError(f"missing elementwise descriptors: {sorted(missing)}")
        for mode in ELEMENTWISE_MODES:
            if len(descriptors[mode]) != ELEMENTWISE_BYTES:
                raise ValueError(
                    f"{mode} descriptor must be {ELEMENTWISE_BYTES} bytes"
                )

        self.device = device
        self.descriptors = descriptors
        self.submit = submit
        self.closed = False
        buffers = []
        try:
            self.output = device.buffer(ELEMENTWISE_BYTES)
            buffers.append(self.output)
            self.left = device.buffer(ELEMENTWISE_BYTES)
            buffers.append(self.left)
            self.right = device.buffer(ELEMENTWISE_BYTES)
            buffers.append(self.right)
            self.descriptor = device.buffer(ELEMENTWISE_BYTES)
            buffers.append(self.descriptor)
        except Exception:
            for buffer in reversed(buffers):
                buffer.close()
            raise
        self.request = RUNTIME.Submit(
            tsk_size=RUNTIME.TD_SIZE,
            td_count=1,
            td_size=RUNTIME.TD_SIZE,
            btsp_handle=self.descriptor.bo.handle,
            pad=0 if device.qid is None else 0x80 | device.qid,
        )
        self.request.handles[0] = self.descriptor.bo.handle
        self.request.handles[4] = self.output.bo.handle
        self.request.handles[5] = self.left.bo.handle
        self.request.handles[6] = self.right.bo.handle
        self._left_values = np.zeros(ELEMENTWISE_BYTES // 2, dtype=np.float16)
        self._right_values = np.zeros(ELEMENTWISE_BYTES // 2, dtype=np.float16)

    def __call__(self, mode, left, right):
        if self.closed:
            raise RuntimeError("elementwise backend is closed")
        if mode not in ELEMENTWISE_MODES:
            raise ValueError(f"unsupported elementwise mode: {mode}")
        left = self._vector(left, "left")
        right = self._vector(right, "right")
        self._left_values.fill(0)
        self._right_values.fill(0)
        self._left_values[: LANES * 32 : 32] = left
        self._right_values[: LANES * 32 : 32] = right
        self.left.write(memoryview(self._left_values).cast("B"))
        self.right.write(memoryview(self._right_values).cast("B"))
        self.descriptor.write(self.descriptors[mode])
        self.submit(self.device.fd, RUNTIME.IOCTL_SUBMIT, self.request)
        values = np.frombuffer(
            self.output.map,
            dtype=np.float16,
            count=ELEMENTWISE_BYTES // 2,
        )
        result = values[: LANES * 32 : 32].copy()
        if not np.isfinite(result).all():
            raise RuntimeError(f"ANE elementwise {mode} returned a non-finite output")
        return result

    @staticmethod
    def _vector(value, name):
        value = np.asarray(value)
        if value.dtype != np.float16 or value.shape != (LANES,):
            raise ValueError(
                f"{name} shape and dtype must be ({LANES},) float16, "
                f"got {value.shape} {value.dtype}"
            )
        return value

    def close(self):
        if self.closed:
            return
        for buffer in (self.output, self.left, self.right, self.descriptor):
            buffer.close()
        self.closed = True


class Softmax128:
    """Run softmax arithmetic through a 64-lane elementwise backend."""

    def __init__(self, run_elementwise):
        self.run_elementwise = run_elementwise

    def __call__(self, scores):
        scores = np.asarray(scores)
        if scores.dtype != np.float16 or scores.shape != (WIDTH,):
            raise ValueError(
                f"scores shape and dtype must be ({WIDTH},) float16, "
                f"got {scores.shape} {scores.dtype}"
            )
        if not np.isfinite(scores).all():
            raise ValueError("scores must be finite")

        left = scores[:LANES]
        right = scores[LANES:]
        left_max = self._reduce("max", left)
        right_max = self._reduce("max", right)
        maximum = self._run(
            "max", self._const(left_max), self._const(right_max)
        )[0]
        negative_maximum = self._run(
            "mul", self._const(maximum), self._const(-1.0)
        )
        left_exp = self._exp(self._run("add", left, negative_maximum))
        right_exp = self._exp(self._run("add", right, negative_maximum))
        left_sum = self._reduce("add", left_exp)
        right_sum = self._reduce("add", right_exp)
        total = self._run(
            "add", self._const(left_sum), self._const(right_sum)
        )[0]
        reciprocal = self._reciprocal(total)
        left_probability = self._run(
            "mul", left_exp, self._const(reciprocal)
        )
        right_probability = self._run(
            "mul", right_exp, self._const(reciprocal)
        )
        result = np.concatenate((left_probability, right_probability))
        if not np.isfinite(result).all():
            raise RuntimeError("ANE softmax returned a non-finite output")
        return result

    def _reduce(self, mode, values):
        current = values.copy()
        width = LANES
        while width > 1:
            half = width // 2
            front = self._const(0.0)
            back = self._const(0.0)
            front[:half] = current[:half]
            back[:half] = current[half:width]
            current = self._run(mode, front, back)
            width = half
        return current[0]

    def _exp(self, values):
        clamped = self._run("max", values, self._const(EXP_LIMIT))
        reduced = self._run("mul", clamped, self._const(1.0 / 128.0))
        square = self._run("sq", reduced, self._const(0.0))
        cube = self._run("mul", reduced, square)
        fourth = self._run("sq", square, self._const(0.0))
        fifth = self._run("mul", reduced, fourth)
        sixth = self._run("mul", square, fourth)
        result = self._run("add", self._const(1.0), reduced)
        for power, factor in (
            (square, 1.0 / 2.0),
            (cube, 1.0 / 6.0),
            (fourth, 1.0 / 24.0),
            (fifth, 1.0 / 120.0),
            (sixth, 1.0 / 720.0),
        ):
            term = self._run("mul", power, self._const(factor))
            result = self._run("add", result, term)
        for _ in range(7):
            result = self._run("mul", result, result)
        return result

    def _reciprocal(self, value):
        source = self._const(value)
        estimate = self._const(1.0 / WIDTH)
        for _ in range(RECIPROCAL_ITERATIONS):
            product = self._run("mul", source, estimate)
            negative = self._run("mul", product, self._const(-1.0))
            correction = self._run("add", self._const(2.0), negative)
            estimate = self._run("mul", estimate, correction)
        return estimate[0]

    def _run(self, mode, left, right):
        result = np.asarray(self.run_elementwise(mode, left, right))
        if result.dtype != np.float16 or result.shape != (LANES,):
            raise RuntimeError(
                f"elementwise {mode} output must be ({LANES},) float16, "
                f"got {result.shape} {result.dtype}"
            )
        return result

    @staticmethod
    def _const(value):
        return np.full(LANES, value, dtype=np.float16)
