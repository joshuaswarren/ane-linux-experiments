#!/usr/bin/env python3
"""Compose 128-wide softmax from reusable Linux ANE elementwise programs."""

import importlib.util
import math
from fcntl import ioctl
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
LANES = 64
WIDTH = 128
ELEMENTWISE_BYTES = 0x4000
ELEMENTWISE_MODES = ("add", "mul", "max", "sq")
EXP_LIMIT = -64.0
ACTIVATION_EXP_LIMIT = -16.0
ACTIVATION_EXP_DIVISOR = 8
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
                raise ValueError(f"{mode} descriptor must be {ELEMENTWISE_BYTES} bytes")

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
        del values
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
        maximum = self._run("max", self._const(left_max), self._const(right_max))[0]
        negative_maximum = self._run("mul", self._const(maximum), self._const(-1.0))
        left_exp = self._exp(self._run("add", left, negative_maximum))
        right_exp = self._exp(self._run("add", right, negative_maximum))
        left_sum = self._reduce("add", left_exp)
        right_sum = self._reduce("add", right_exp)
        total = self._run("add", self._const(left_sum), self._const(right_sum))[0]
        reciprocal = self._reciprocal(total)
        left_probability = self._run("mul", left_exp, self._const(reciprocal))
        right_probability = self._run("mul", right_exp, self._const(reciprocal))
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

    def _exp(self, values, limit=EXP_LIMIT, divisor=128):
        clamped = self._run("max", values, self._const(limit))
        reduced = self._run("mul", clamped, self._const(1.0 / divisor))
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
        for _ in range(divisor.bit_length() - 1):
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


class Activations:
    """Run Qwen activation functions on the shared ANE backend."""

    def __init__(self, run_elementwise):
        self.math = Softmax128(run_elementwise)

    def sigmoid(self, value):
        return self._apply(value, multiplier=None, multiply_input=False)

    def sigmoid_mul(self, value, multiplier):
        return self._apply(value, multiplier=multiplier, multiply_input=False)

    def silu(self, value):
        return self._apply(value, multiplier=None, multiply_input=True)

    def silu_mul(self, value, multiplier):
        return self._apply(value, multiplier=multiplier, multiply_input=True)

    def decay_multiplier(self, alpha, bias, a_log):
        alpha = self._value(alpha)
        bias = self._value(bias)
        a_log = self._value(a_log)
        if bias.shape != alpha.shape or a_log.shape != alpha.shape:
            raise ValueError("alpha, bias, and a_log shapes must match")
        if np.any(a_log > 0):
            raise ValueError("a_log must be non-positive")

        alpha_flat = alpha.reshape(-1)
        bias_flat = bias.reshape(-1)
        a_log_flat = a_log.reshape(-1)
        result = np.empty_like(alpha_flat)
        zero = self.math._const(0.0)
        negative_one = self.math._const(-1.0)
        for offset in range(0, alpha_flat.size, LANES):
            width = min(LANES, alpha_flat.size - offset)
            alpha_chunk = self.math._const(0.0)
            bias_chunk = self.math._const(0.0)
            a_log_chunk = self.math._const(0.0)
            alpha_chunk[:width] = alpha_flat[offset : offset + width]
            bias_chunk[:width] = bias_flat[offset : offset + width]
            a_log_chunk[:width] = a_log_flat[offset : offset + width]

            combined = self.math._run("add", alpha_chunk, bias_chunk)
            positive = self.math._run("max", combined, zero)
            negative = self.math._run("mul", combined, negative_one)
            absolute = self.math._run(
                "add", positive, self.math._run("max", negative, zero)
            )
            exp_negative = self._exp(self.math._run("mul", absolute, negative_one))
            denominator = self.math._run("add", exp_negative, self.math._const(2.0))
            ratio = self.math._run("mul", exp_negative, self._reciprocal(denominator))
            ratio_squared = self.math._run("sq", ratio, self.math._const(0.0))
            term = ratio
            series = ratio
            for power in (3, 5, 7, 9):
                term = self.math._run("mul", term, ratio_squared)
                series = self.math._run(
                    "add",
                    series,
                    self.math._run("mul", term, self.math._const(1.0 / power)),
                )
            correction = self.math._run("mul", series, self.math._const(2.0))
            softplus = self.math._run("add", positive, correction)
            scaled = self.math._run("mul", softplus, a_log_chunk)
            multiplier = self._exp(scaled)
            result[offset : offset + width] = multiplier[:width]
        return result.reshape(alpha.shape)

    def _apply(self, value, multiplier, multiply_input):
        value = self._value(value)
        multiplier_flat = None
        if multiplier is not None:
            multiplier = self._value(multiplier)
            if multiplier.shape != value.shape:
                raise ValueError(
                    f"multiplier shape must match value shape {value.shape}, "
                    f"got {multiplier.shape}"
                )
            multiplier_flat = multiplier.reshape(-1)
        flat = value.reshape(-1)
        result = np.empty_like(flat)
        for offset in range(0, flat.size, LANES):
            width = min(LANES, flat.size - offset)
            chunk = self.math._const(0.0)
            chunk[:width] = flat[offset : offset + width]
            activated = self._sigmoid(chunk)
            if multiply_input:
                activated = self.math._run("mul", chunk, activated)
            if multiplier_flat is not None:
                right = self.math._const(0.0)
                right[:width] = multiplier_flat[offset : offset + width]
                activated = self.math._run("mul", activated, right)
            result[offset : offset + width] = activated[:width]
        return result.reshape(value.shape)

    def _sigmoid(self, value):
        zero = self.math._const(0.0)
        negative = self.math._run("mul", value, self.math._const(-1.0))
        negative_half = self.math._run("max", negative, zero)
        positive_half = self.math._run("max", value, zero)
        numerator = self._exp(
            self.math._run("mul", negative_half, self.math._const(-1.0))
        )
        other = self._exp(self.math._run("mul", positive_half, self.math._const(-1.0)))
        denominator = self.math._run("add", numerator, other)
        return self.math._run("mul", numerator, self._reciprocal(denominator))

    def _reciprocal(self, value):
        reciprocal = self.math._const(0.5)
        for _ in range(6):
            product = self.math._run("mul", value, reciprocal)
            correction = self.math._run(
                "add",
                self.math._const(2.0),
                self.math._run("mul", product, self.math._const(-1.0)),
            )
            reciprocal = self.math._run("mul", reciprocal, correction)
        return reciprocal

    def _exp(self, value):
        return self.math._exp(
            value,
            limit=ACTIVATION_EXP_LIMIT,
            divisor=ACTIVATION_EXP_DIVISOR,
        )

    @staticmethod
    def _value(value):
        value = np.asarray(value)
        if value.dtype != np.float16:
            raise ValueError(f"value dtype must be float16, got {value.dtype}")
        if not value.size:
            raise ValueError("value must not be empty")
        if not np.isfinite(value).all():
            raise ValueError("value must be finite")
        return value


class TensorOperations:
    """Run residual addition and rotary embedding math on ANE."""

    def __init__(self, run_elementwise):
        self.run_elementwise = run_elementwise

    def add(self, left, right):
        left = self._value(left, "left")
        right = self._value(right, "right")
        if right.shape != left.shape:
            raise ValueError(
                f"right shape must match left shape {left.shape}, got {right.shape}"
            )
        left_flat = left.reshape(-1)
        right_flat = right.reshape(-1)
        result = np.empty_like(left_flat)
        for offset in range(0, left_flat.size, LANES):
            width = min(LANES, left_flat.size - offset)
            left_chunk = np.zeros(LANES, dtype=np.float16)
            right_chunk = np.zeros(LANES, dtype=np.float16)
            left_chunk[:width] = left_flat[offset : offset + width]
            right_chunk[:width] = right_flat[offset : offset + width]
            added = self.run_elementwise("add", left_chunk, right_chunk)
            result[offset : offset + width] = added[:width]
        return result.reshape(left.shape)

    def rope(
        self,
        value,
        position,
        rotary_dim=64,
        theta=10_000_000.0,
    ):
        value = self._value(value, "value")
        if value.ndim != 2:
            raise ValueError(f"value shape must be two-dimensional, got {value.shape}")
        if rotary_dim < 2 or rotary_dim > LANES or rotary_dim % 2:
            raise ValueError(f"rotary_dim must be even and between 2 and {LANES}")
        if rotary_dim > value.shape[1]:
            raise ValueError(
                f"rotary_dim {rotary_dim} exceeds value width {value.shape[1]}"
            )
        if not isinstance(position, (int, np.integer)) or position < 0:
            raise ValueError("position must be a non-negative integer")
        if theta <= 0:
            raise ValueError("theta must be positive")
    
        inverse = theta ** (-np.arange(0, rotary_dim, 2, dtype=np.float32) / rotary_dim)
        frequencies = position * inverse
        cosine = np.cos(frequencies).astype(np.float16)
        sine = np.sin(frequencies).astype(np.float16)
        half = rotary_dim // 2
        direct_factors = np.zeros(LANES, dtype=np.float16)
        cross_factors = np.zeros(LANES, dtype=np.float16)
        direct_factors[:rotary_dim] = np.concatenate((cosine, cosine))
        cross_factors[:rotary_dim] = np.concatenate((-sine, sine))
    
        result = value.copy()
        for head, row in enumerate(value):
            direct = np.zeros(LANES, dtype=np.float16)
            cross = np.zeros(LANES, dtype=np.float16)
            direct[:rotary_dim] = row[:rotary_dim]
            cross[:rotary_dim] = np.concatenate((row[half:rotary_dim], row[:half]))
            direct = self.run_elementwise("mul", direct, direct_factors)
            cross = self.run_elementwise("mul", cross, cross_factors)
            rotated = self.run_elementwise("add", direct, cross)
            result[head, :rotary_dim] = rotated[:rotary_dim]
        return result

    @staticmethod
    def _value(value, name):
        value = np.asarray(value)
        if value.dtype != np.float16:
            raise ValueError(f"{name} dtype must be float16, got {value.dtype}")
        if not value.size:
            raise ValueError(f"{name} must not be empty")
        if not np.isfinite(value).all():
            raise ValueError(f"{name} must be finite")
        return value


class CausalConvolution:
    """Run one depthwise causal convolution through the ANE backend."""

    def __init__(self, run_elementwise, channels, kernel_size):
        if channels < 1 or kernel_size < 1:
            raise ValueError("channels and kernel_size must be positive")
        self.run_elementwise = run_elementwise
        self.channels = channels
        self.kernel_size = kernel_size
        self.history = np.zeros((kernel_size, channels), dtype=np.float16)
        self.cursor = 0

    def __call__(self, value, weight):
        value = np.asarray(value)
        weight = np.asarray(weight)
        if value.dtype != np.float16 or value.shape != (self.channels,):
            raise ValueError(
                f"value shape and dtype must be ({self.channels},) float16"
            )
        expected_weight_shape = (self.channels, self.kernel_size)
        if weight.dtype != np.float16 or weight.shape != expected_weight_shape:
            raise ValueError(
                f"weight shape and dtype must be {expected_weight_shape} float16"
            )
        if not np.isfinite(value).all() or not np.isfinite(weight).all():
            raise ValueError("value and weight must be finite")

        self.history[self.cursor] = value
        order = [
            (self.cursor + offset + 1) % self.kernel_size
            for offset in range(self.kernel_size)
        ]
        result = np.empty_like(value)
        for start in range(0, self.channels, LANES):
            width = min(LANES, self.channels - start)
            source = np.zeros(LANES, dtype=np.float16)
            coefficient = np.zeros(LANES, dtype=np.float16)
            source[:width] = self.history[order[0], start : start + width]
            coefficient[:width] = weight[start : start + width, 0]
            total = self.run_elementwise("mul", source, coefficient)
            for tap, history_index in enumerate(order[1:], start=1):
                source.fill(0)
                coefficient.fill(0)
                source[:width] = self.history[history_index, start : start + width]
                coefficient[:width] = weight[start : start + width, tap]
                product = self.run_elementwise("mul", source, coefficient)
                total = self.run_elementwise("add", total, product)
            result[start : start + width] = total[:width]
        self.cursor = (self.cursor + 1) % self.kernel_size
        return result


class Normalization:
    """Run row-wise RMS and L2 normalization through the ANE backend."""

    def __init__(self, run_elementwise):
        self.math = Softmax128(run_elementwise)

    def rms_norm(self, value, weight, eps=1e-6):
        value = self._value(value)
        weight = np.asarray(weight)
        if weight.dtype != np.float16 or weight.shape != (value.shape[-1],):
            raise ValueError(
                "weight shape and dtype must match the final value dimension float16"
            )
        return self._normalize(value, weight, eps, mean=True)

    def l2_norm(self, value, scale=1.0, eps=1e-6):
        value = self._value(value)
        return self._normalize(value, None, eps, mean=False, output_scale=scale)

    def _normalize(self, value, weight, eps, mean, output_scale=1.0):
        dimension = value.shape[-1]
        rows = value.reshape(-1, dimension)
        result = np.empty_like(rows)
        divisor = dimension if mean else 1
        operation = "max" if mean else "add"
        for row_index, row in enumerate(rows):
            total = self._sum_squares(row)
            scaled_total = self.math._run(
                "mul",
                self.math._const(total),
                self.math._const(1.0 / divisor),
            )
            adjusted = self.math._run(
                operation,
                scaled_total,
                self.math._const(eps),
            )[0]
            inverse = self._inverse_sqrt(adjusted)
            if output_scale != 1.0:
                inverse = self.math._run(
                    "mul",
                    self.math._const(inverse),
                    self.math._const(output_scale),
                )[0]
            for offset in range(0, dimension, LANES):
                chunk = self.math._run(
                    "mul",
                    row[offset : offset + LANES],
                    self.math._const(inverse),
                )
                if weight is not None:
                    chunk = self.math._run(
                        "mul", chunk, weight[offset : offset + LANES]
                    )
                result[row_index, offset : offset + LANES] = chunk
        return result.reshape(value.shape)
    def _sum_squares(self, row):
        partials = self.math._const(0.0)
        for index, offset in enumerate(range(0, row.size, LANES)):
            squared = self.math._run(
                "sq", row[offset : offset + LANES], self.math._const(0.0)
            )
            partials[index] = self.math._reduce("add", squared)
        return self.math._reduce("add", partials)

    def _inverse_sqrt(self, value):
        if not np.isfinite(value) or value <= 0:
            raise RuntimeError("ANE normalization sum must be positive and finite")
        _, exponent = math.frexp(float(value))
        factor = 0.7071067811865476 if exponent % 2 else 1.0
        initial = math.ldexp(factor, -(exponent // 2))
        source = self.math._const(value)
        estimate = self.math._const(initial)
        for _ in range(5):
            product = self.math._run("mul", source, estimate)
            product = self.math._run("mul", product, estimate)
            negative = self.math._run("mul", product, self.math._const(-1.0))
            correction = self.math._run("add", self.math._const(3.0), negative)
            half = self.math._run("mul", correction, self.math._const(0.5))
            estimate = self.math._run("mul", estimate, half)
        return estimate[0]

    @staticmethod
    def _value(value):
        value = np.asarray(value)
        if value.dtype != np.float16:
            raise ValueError(f"value dtype must be float16, got {value.dtype}")
        if (
            not value.shape
            or value.shape[-1] % LANES
            or value.shape[-1] > LANES * LANES
        ):
            raise ValueError(
                "final value dimension must be a multiple of 64 up to 4096"
            )
        if not np.isfinite(value).all():
            raise ValueError("value must be finite")
        return value
