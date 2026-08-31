import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "softmax_runtime", Path(__file__).with_name("softmax-runtime.py")
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeElementwise:
    def __init__(self):
        self.modes = []

    def __call__(self, mode, left, right):
        self.modes.append(mode)
        if mode == "add":
            return np.add(left, right, dtype=np.float16)
        if mode == "mul":
            return np.multiply(left, right, dtype=np.float16)
        if mode == "max":
            return np.maximum(left, right).astype(np.float16)
        if mode == "sq":
            return np.square(left, dtype=np.float16)
        raise AssertionError(f"unexpected mode {mode}")


class Softmax128Tests(unittest.TestCase):
    def setUp(self):
        self.elementwise = FakeElementwise()
        self.softmax = MODULE.Softmax128(self.elementwise)

    @staticmethod
    def reference(scores):
        scores = scores.astype(np.float32)
        exponentials = np.exp(scores - scores.max())
        return exponentials / exponentials.sum()

    def test_matches_reference_for_full_context(self):
        rng = np.random.default_rng(20260830)
        scores = (rng.standard_normal(128) * 2.0).astype(np.float16)

        actual = self.softmax(scores)
        expected = self.reference(scores)

        self.assertLess(
            float(np.max(np.abs(actual.astype(np.float32) - expected))), 0.003
        )
        self.assertAlmostEqual(float(actual.astype(np.float32).sum()), 1.0, delta=0.001)
        self.assertEqual(int(actual.argmax()), int(expected.argmax()))
        self.assertIn("max", self.elementwise.modes)
        self.assertIn("add", self.elementwise.modes)
        self.assertIn("mul", self.elementwise.modes)
        self.assertIn("sq", self.elementwise.modes)

    def test_masked_unused_rows_receive_zero_probability(self):
        scores = np.full(128, np.finfo(np.float16).min, dtype=np.float16)
        scores[0] = np.float16(3.0)

        actual = self.softmax(scores)

        self.assertAlmostEqual(float(actual[0]), 1.0, delta=0.001)
        np.testing.assert_array_equal(actual[1:], np.zeros(127, dtype=np.float16))

    def test_uniform_scores_stay_uniform(self):
        actual = self.softmax(np.zeros(128, dtype=np.float16))

        np.testing.assert_array_equal(
            actual,
            np.full(128, np.float16(1.0 / 128.0), dtype=np.float16),
        )

    def test_rejects_wrong_shape_dtype_and_nonfinite_values(self):
        with self.assertRaisesRegex(ValueError, "shape and dtype"):
            self.softmax(np.zeros(64, dtype=np.float16))
        with self.assertRaisesRegex(ValueError, "shape and dtype"):
            self.softmax(np.zeros(128, dtype=np.float32))
        scores = np.zeros(128, dtype=np.float16)
        scores[0] = np.inf
        with self.assertRaisesRegex(ValueError, "finite"):
            self.softmax(scores)


class NormalizationTests(unittest.TestCase):
    def setUp(self):
        self.elementwise = FakeElementwise()
        self.normalization = MODULE.Normalization(self.elementwise)

    def test_rms_norm_matches_rowwise_reference(self):
        rng = np.random.default_rng(20260830)
        values = (rng.standard_normal((8, 256)) * 0.5).astype(np.float16)
        weight = rng.uniform(0.75, 1.25, 256).astype(np.float16)

        actual = self.normalization.rms_norm(values, weight)
        values32 = values.astype(np.float32)
        mean_square = np.mean(values32 * values32, axis=-1, keepdims=True)
        expected = values32 / np.sqrt(np.maximum(mean_square, 1e-6))
        expected *= weight.astype(np.float32)

        self.assertEqual(actual.dtype, np.float16)
        self.assertLess(
            float(np.max(np.abs(actual.astype(np.float32) - expected))),
            0.03,
        )

    def test_rms_norm_uses_epsilon_as_floor(self):
        values = np.full((16, 128), np.float16(0.0015), dtype=np.float16)
        weight = np.ones(128, dtype=np.float16)

        actual = self.normalization.rms_norm(values, weight)

        np.testing.assert_allclose(actual, np.ones_like(values), atol=0.02)

    def test_l2_norm_matches_rowwise_reference(self):
        rng = np.random.default_rng(20260831)
        values = rng.standard_normal((16, 128)).astype(np.float16)

        actual = self.normalization.l2_norm(values, scale=0.125)
        values32 = values.astype(np.float32)
        expected = (
            0.125
            * values32
            / np.sqrt(np.sum(values32 * values32, axis=-1, keepdims=True) + 1e-6)
        )

        self.assertEqual(actual.dtype, np.float16)
        self.assertLess(
            float(np.max(np.abs(actual.astype(np.float32) - expected))),
            0.003,
        )

    def test_rms_norm_handles_zero_input(self):
        values = np.zeros((16, 128), dtype=np.float16)
        weight = np.ones(128, dtype=np.float16)

        actual = self.normalization.rms_norm(values, weight)

        np.testing.assert_array_equal(actual, values)

    def test_normalization_rejects_non_target_shapes_and_dtypes(self):
        with self.assertRaisesRegex(ValueError, "multiple of 64"):
            self.normalization.l2_norm(np.ones(65, dtype=np.float16))
        with self.assertRaisesRegex(ValueError, "float16"):
            self.normalization.l2_norm(np.ones(128, dtype=np.float32))
        with self.assertRaisesRegex(ValueError, "weight"):
            self.normalization.rms_norm(
                np.ones(128, dtype=np.float16),
                np.ones(64, dtype=np.float16),
            )
class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.elementwise = FakeElementwise()
        self.activations = MODULE.Activations(self.elementwise)

    def test_sigmoid_matches_stable_reference(self):
        values = np.asarray(
            [-80.0, -10.0, -2.0, -1.0, 0.0, 1.0, 2.0, 10.0, 80.0],
            dtype=np.float16,
        )

        actual = self.activations.sigmoid(values)
        values32 = values.astype(np.float32)
        expected = 1.0 / (1.0 + np.exp(-values32))

        self.assertLess(
            float(np.max(np.abs(actual.astype(np.float32) - expected))),
            0.003,
        )

    def test_silu_mul_matches_reference_across_chunks(self):
        rng = np.random.default_rng(20260830)
        values = (rng.standard_normal((2, 96)) * 2.0).astype(np.float16)
        multiplier = rng.standard_normal((2, 96)).astype(np.float16)

        actual = self.activations.silu_mul(values, multiplier)
        values32 = values.astype(np.float32)
        expected = values32 / (1.0 + np.exp(-values32))
        expected *= multiplier.astype(np.float32)

        self.assertEqual(actual.shape, values.shape)
        self.assertLess(
            float(np.max(np.abs(actual.astype(np.float32) - expected))),
            0.03,
        )

    def test_sigmoid_mul_matches_reference(self):
        values = np.linspace(-5.0, 5.0, 96, dtype=np.float16)
        multiplier = np.linspace(2.0, -2.0, 96, dtype=np.float16)

        actual = self.activations.sigmoid_mul(values, multiplier)
        values32 = values.astype(np.float32)
        expected = multiplier.astype(np.float32) / (1.0 + np.exp(-values32))

        self.assertLess(
            float(np.max(np.abs(actual.astype(np.float32) - expected))),
            0.01,
        )

    def test_decay_multiplier_matches_stable_reference(self):
        alpha = np.linspace(-20.0, 10.0, 96, dtype=np.float16)
        bias = np.linspace(-2.0, 2.0, 96, dtype=np.float16)
        a_log = np.linspace(-0.1, -8.0, 96, dtype=np.float16)

        actual = self.activations.decay_multiplier(alpha, bias, a_log)
        combined = alpha.astype(np.float32) + bias.astype(np.float32)
        softplus = np.logaddexp(np.float32(0), combined)
        expected = np.exp(a_log.astype(np.float32) * softplus)

        self.assertLess(
            float(np.max(np.abs(actual.astype(np.float32) - expected))),
            0.03,
        )

    def test_activations_reject_bad_inputs(self):
        with self.assertRaisesRegex(ValueError, "float16"):
            self.activations.silu(np.ones(64, dtype=np.float32))
        with self.assertRaisesRegex(ValueError, "shape"):
            self.activations.silu_mul(
                np.ones(64, dtype=np.float16),
                np.ones(32, dtype=np.float16),
            )
        with self.assertRaisesRegex(ValueError, "non-positive"):
            self.activations.decay_multiplier(
                np.ones(16, dtype=np.float16),
                np.ones(16, dtype=np.float16),
                np.ones(16, dtype=np.float16),
            )


class TensorOperationsTests(unittest.TestCase):
    def setUp(self):
        self.elementwise = FakeElementwise()
        self.operations = MODULE.TensorOperations(self.elementwise)

    def test_residual_add_matches_reference_across_partial_chunk(self):
        left = np.arange(96, dtype=np.float16)
        right = np.linspace(1.0, -1.0, 96, dtype=np.float16)

        actual = self.operations.add(left, right)

        np.testing.assert_array_equal(actual, np.add(left, right, dtype=np.float16))
        self.assertEqual(self.elementwise.modes, ["add", "add"])

    def test_rope_matches_neox_reference_and_preserves_tail(self):
        rng = np.random.default_rng(20260901)
        value = rng.standard_normal((8, 256)).astype(np.float16)
        position = 37

        actual = self.operations.rope(value, position)

        expected = value.astype(np.float32).copy()
        inverse = 10_000_000.0 ** (-np.arange(0, 64, 2, dtype=np.float32) / 64)
        frequencies = position * inverse
        cosine = np.cos(frequencies)
        sine = np.sin(frequencies)
        left = expected[:, :32].copy()
        right = expected[:, 32:64].copy()
        expected[:, :32] = left * cosine - right * sine
        expected[:, 32:64] = right * cosine + left * sine

        self.assertLess(
            float(np.max(np.abs(actual.astype(np.float32) - expected))),
            0.004,
        )
        np.testing.assert_array_equal(actual[:, 64:], value[:, 64:])
        self.assertEqual(self.elementwise.modes, ["mul", "mul", "add"] * 8)

    def test_rejects_bad_tensor_inputs(self):
        with self.assertRaisesRegex(ValueError, "shape"):
            self.operations.add(
                np.ones(64, dtype=np.float16),
                np.ones(32, dtype=np.float16),
            )
        with self.assertRaisesRegex(ValueError, "float16"):
            self.operations.rope(np.ones((2, 256), dtype=np.float32), 0)
        with self.assertRaisesRegex(ValueError, "rotary_dim"):
            self.operations.rope(np.ones((2, 32), dtype=np.float16), 0, rotary_dim=64)


class CausalConvolutionTests(unittest.TestCase):
    def setUp(self):
        self.elementwise = FakeElementwise()
        self.convolution = MODULE.CausalConvolution(
            self.elementwise, channels=96, kernel_size=4
        )

    def test_matches_three_sequential_causal_steps(self):
        rng = np.random.default_rng(20260831)
        weight = (rng.standard_normal((96, 4)) * 0.2).astype(np.float16)
        history = np.zeros((96, 3), dtype=np.float16)

        for _ in range(3):
            value = rng.standard_normal(96).astype(np.float16)
            window = np.concatenate((history, value[:, None]), axis=1)
            expected = np.sum(
                window.astype(np.float32) * weight.astype(np.float32), axis=1
            )

            actual = self.convolution(value, weight)

            self.assertLess(
                float(np.max(np.abs(actual.astype(np.float32) - expected))),
                0.004,
            )
            history = window[:, 1:]
        self.assertIn("mul", self.elementwise.modes)
        self.assertIn("add", self.elementwise.modes)

    def test_rejects_wrong_input_and_weight_shapes(self):
        with self.assertRaisesRegex(ValueError, "value"):
            self.convolution(
                np.ones(64, dtype=np.float16),
                np.ones((96, 4), dtype=np.float16),
            )
        with self.assertRaisesRegex(ValueError, "weight"):
            self.convolution(
                np.ones(96, dtype=np.float16),
                np.ones((96, 3), dtype=np.float16),
            )


class FakeBuffer:
    next_handle = 1

    def __init__(self, size):
        self.map = bytearray(size)
        self.bo = SimpleNamespace(handle=FakeBuffer.next_handle)
        self.closed = False
        FakeBuffer.next_handle += 1

    def write(self, data):
        if len(data) > len(self.map):
            raise ValueError("buffer overflow")
        self.map[: len(data)] = data

    def close(self):
        self.closed = True


class FakeDevice:
    def __init__(self):
        self.fd = 7
        self.qid = 2
        self.buffers = []

    def buffer(self, size):
        buffer = FakeBuffer(size)
        self.buffers.append(buffer)
        return buffer


class ElementwiseBackendTests(unittest.TestCase):
    def setUp(self):
        FakeBuffer.next_handle = 1
        self.device = FakeDevice()
        self.descriptors = {
            mode: bytes([index]) * MODULE.ELEMENTWISE_BYTES
            for index, mode in enumerate(MODULE.ELEMENTWISE_MODES, 1)
        }

        def submit(_fd, _request_code, _request):
            output, left, right, descriptor = self.device.buffers
            output_values = np.ndarray(
                MODULE.ELEMENTWISE_BYTES // 2,
                dtype=np.float16,
                buffer=output.map,
            )
            left_values = np.frombuffer(left.map, dtype=np.float16)
            right_values = np.frombuffer(right.map, dtype=np.float16)
            left_lanes = left_values[: MODULE.LANES * 32 : 32]
            right_lanes = right_values[: MODULE.LANES * 32 : 32]
            if descriptor.map[0] == 1:
                result = left_lanes + right_lanes
            elif descriptor.map[0] == 2:
                result = left_lanes * right_lanes
            else:
                raise AssertionError("unexpected descriptor")
            output_values[: MODULE.LANES * 32 : 32] = result

        self.backend = MODULE.ElementwiseBackend(
            self.device, self.descriptors, submit=submit
        )

    def tearDown(self):
        self.backend.close()

    def test_reuses_four_buffers_across_submissions(self):
        left = np.arange(MODULE.LANES, dtype=np.float16)
        right = np.full(MODULE.LANES, 2.0, dtype=np.float16)

        added = self.backend("add", left, right)
        multiplied = self.backend("mul", left, right)

        np.testing.assert_array_equal(added, left + right)
        np.testing.assert_array_equal(multiplied, left * right)
        self.assertEqual(len(self.device.buffers), 4)
        self.assertEqual(
            self.backend.descriptor.map[: MODULE.ELEMENTWISE_BYTES],
            self.descriptors["mul"],
        )

    def test_rejects_bad_mode_and_vector(self):
        vector = np.zeros(MODULE.LANES, dtype=np.float16)
        with self.assertRaisesRegex(ValueError, "mode"):
            self.backend("min", vector, vector)
        with self.assertRaisesRegex(ValueError, "shape and dtype"):
            self.backend("add", vector.astype(np.float32), vector)

    def test_close_is_idempotent_and_blocks_reuse(self):
        self.backend.close()
        self.backend.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            self.backend(
                "add",
                np.zeros(MODULE.LANES, dtype=np.float16),
                np.zeros(MODULE.LANES, dtype=np.float16),
            )
        self.assertTrue(all(buffer.closed for buffer in self.device.buffers))


if __name__ == "__main__":
    unittest.main()
