import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "ane_qwen_model", Path(__file__).parent.parent / "ane-qwen-model.py"
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeTokenRuntime:
    def __init__(self):
        self.full_calls = []
        self.recurrent_calls = []
        self.normalization_calls = []
        self.activation_calls = []
        self.convolution_calls = []
        self.tensor_calls = []

    def full_attention(self, layer_index, query, key, value):
        self.full_calls.append((layer_index, query.copy(), key.copy(), value.copy()))
        return np.ones((8, 256), dtype=np.float16)

    def causal_convolution(self, layer_index, value, weight):
        self.convolution_calls.append((layer_index, value.copy(), weight.copy()))
        return value.copy()

    def residual_add(self, left, right):
        self.tensor_calls.append(("residual", left.copy(), right.copy()))
        return left.copy()

    def rope(self, value, position):
        self.tensor_calls.append(("rope", value.copy(), position))
        return value.copy()

    def recurrent(self, layer_index, query, key, value, beta, decay):
        self.recurrent_calls.append(
            (
                layer_index,
                query.copy(),
                key.copy(),
                value.copy(),
                beta.copy(),
                decay.copy(),
            )
        )
        return np.zeros((16, 128), dtype=np.float16)

    def rms_norm(self, value, weight):
        self.normalization_calls.append(("rms", value.shape, weight, 1.0))
        return value

    def l2_norm(self, value, scale=1.0):
        self.normalization_calls.append(("l2", value.shape, None, scale))
        return value

    def sigmoid(self, value):
        self.activation_calls.append(("sigmoid", value.shape, None))
        return np.ones_like(value)

    def sigmoid_mul(self, value, multiplier):
        self.activation_calls.append(("sigmoid_mul", value.shape, multiplier.shape))
        return np.float16(0.5) * multiplier

    def silu(self, value):
        self.activation_calls.append(("silu", value.shape, None))
        return value

    def silu_mul(self, value, multiplier):
        self.activation_calls.append(("silu_mul", value.shape, multiplier.shape))
        return multiplier

    def decay_multiplier(self, alpha, bias, a_log):
        self.activation_calls.append(
            ("decay_multiplier", alpha.shape, bias.shape, a_log.shape)
        )
        return np.full_like(alpha, np.float16(0.75))


class QwenModelMathTests(unittest.TestCase):
    def test_causal_attention_normalizes_equal_scores(self):
        query = np.zeros((4, 2), dtype=np.float16)
        keys = np.zeros((1, 2, 2), dtype=np.float16)
        values = np.asarray([[[2, 2], [4, 4]]], dtype=np.float16)
        actual = MODULE.causal_attention(query, keys, values)
        np.testing.assert_array_equal(actual, np.full((4, 2), 3, dtype=np.float16))

    def test_rms_norm_uses_epsilon_as_floor(self):
        values = np.full((16, 128), np.float16(0.0015), dtype=np.float16)
        weight = np.ones(128, dtype=np.float16)

        actual = MODULE.rms_norm(values, weight)

        np.testing.assert_allclose(actual, np.ones_like(values), atol=0.001)

    def test_rope_uses_contiguous_neox_frequencies(self):
        value = np.arange(128, dtype=np.float16).reshape(2, 64) / 32
        position = 7

        actual = MODULE.rope(value, position).astype(np.float32)

        inverse = 10_000_000.0 ** (
            -np.arange(0, 64, 2, dtype=np.float32) / 64
        )
        cosine = np.cos(position * inverse)
        sine = np.sin(position * inverse)
        expected = value.astype(np.float32).copy()
        left = expected[:, :32].copy()
        right = expected[:, 32:64].copy()
        expected[:, :32] = left * cosine - right * sine
        expected[:, 32:64] = right * cosine + left * sine

        np.testing.assert_allclose(actual, expected, atol=0.002, rtol=0)
    def test_mlp_uses_fused_activation_runtime(self):
        model = MODULE.QwenModel.__new__(MODULE.QwenModel)
        model.cpu_reference = False
        model.token_runtime = FakeTokenRuntime()
        layer = {
            "post_norm": np.ones(2048, dtype=np.float16),
            "ffn_gate": "gate",
            "ffn_up": "up",
            "ffn_down": "down",
        }
        outputs = {
            "gate": np.ones(6144, dtype=np.float16),
            "up": np.full(6144, 2, dtype=np.float16),
            "down": np.zeros(2048, dtype=np.float16),
        }
        model.projection = lambda matrix, _activation, in_cols=None: outputs[matrix]

        actual = model.mlp(layer, np.zeros(2048, dtype=np.float16))

        self.assertEqual(
            [call[:3] for call in model.token_runtime.activation_calls],
            [("silu_mul", (6144,), (6144,))],
        )
        self.assertEqual(
            [call[0] for call in model.token_runtime.tensor_calls],
            ["residual"],
        )
        np.testing.assert_array_equal(actual, np.zeros(2048, dtype=np.float16))

    def test_full_layer_uses_resident_attention_runtime(self):
        model = MODULE.QwenModel.__new__(MODULE.QwenModel)
        model.cpu_reference = False
        model.token_runtime = FakeTokenRuntime()
        model.mlp = lambda _layer, value: value
        layer = {
            "state_index": 3,
            "input_norm": np.ones(2048, dtype=np.float16),
            "q": "q",
            "k": "k",
            "v": "v",
            "o": "o",
            "q_norm": np.ones(256, dtype=np.float16),
            "k_norm": np.ones(256, dtype=np.float16),
        }
        query = np.concatenate(
            (
                np.ones((8, 256), dtype=np.float16),
                np.zeros((8, 256), dtype=np.float16),
            ),
            axis=1,
        ).reshape(-1)
        outputs = {
            "q": query,
            "k": np.ones(512, dtype=np.float16),
            "v": np.full(512, 2, dtype=np.float16),
            "o": np.zeros(2048, dtype=np.float16),
        }
        output_activation = []

        def projection(matrix, activation, in_cols=None):
            del in_cols
            if matrix == "o":
                output_activation.append(activation.copy())
            return outputs[matrix]

        model.projection = projection
        hidden = np.zeros(2048, dtype=np.float16)
        with patch.object(MODULE, "rope", side_effect=lambda value, _position: value):
            actual = model.full_layer(layer, hidden, 0)

        self.assertEqual(len(model.token_runtime.full_calls), 1)
        self.assertEqual(
            [call[:2] for call in model.token_runtime.normalization_calls],
            [("rms", (2048,)), ("rms", (8, 256)), ("rms", (2, 256))],
        )
        self.assertEqual(
            [call[:3] for call in model.token_runtime.activation_calls],
            [("sigmoid_mul", (2048,), (2048,))],
        )
        self.assertEqual(
            [call[0] for call in model.token_runtime.tensor_calls],
            ["rope", "rope", "residual"],
        )
        self.assertEqual(
            [call[2] for call in model.token_runtime.tensor_calls[:2]],
            [0, 0],
        )
        layer_index, q_heads, k_heads, v_heads = model.token_runtime.full_calls[0]
        self.assertEqual(layer_index, 3)
        self.assertEqual(q_heads.shape, (8, 256))
        self.assertEqual(k_heads.shape, (2, 256))
        self.assertEqual(v_heads.shape, (2, 256))
        np.testing.assert_array_equal(
            output_activation[0], np.full(2048, np.float16(0.5))
        )
        np.testing.assert_array_equal(actual, hidden)

    def test_linear_layer_uses_resident_recurrent_runtime(self):
        model = MODULE.QwenModel.__new__(MODULE.QwenModel)
        model.cpu_reference = False
        model.token_runtime = FakeTokenRuntime()
        model.mlp = lambda _layer, value: value
        layer = {
            "state_index": 5,
            "input_norm": np.ones(2048, dtype=np.float16),
            "post_norm": "post_norm",
            "qkv": "qkv",
            "z": "z",
            "beta": "beta",
            "alpha": "alpha",
            "out": "out",
            "conv_state": np.zeros((6144, 3), dtype=np.float16),
            "conv": np.ones((6144, 4), dtype=np.float16),
            "a_log": np.full(16, -1, dtype=np.float16),
            "dt_bias": np.zeros(16, dtype=np.float16),
            "ssm_norm": np.ones(128, dtype=np.float16),
        }
        outputs = {
            "qkv": np.zeros(6144, dtype=np.float16),
            "z": np.zeros(2048, dtype=np.float16),
            "beta": np.zeros(16, dtype=np.float16),
            "alpha": np.zeros(16, dtype=np.float16),
            "out": np.zeros(2048, dtype=np.float16),
        }
        model.projection = lambda matrix, _activation, in_cols=None: outputs[matrix]
        hidden = np.zeros(2048, dtype=np.float16)
        actual = model.linear_layer(layer, hidden)

        self.assertEqual(len(model.token_runtime.recurrent_calls), 1)
        self.assertEqual(len(model.token_runtime.convolution_calls), 1)
        convolution_call = model.token_runtime.convolution_calls[0]
        self.assertEqual(convolution_call[0], 5)
        self.assertEqual(convolution_call[1].shape, (6144,))
        self.assertEqual(convolution_call[2].shape, (6144, 4))
        np.testing.assert_array_equal(
            layer["conv_state"], np.zeros((6144, 3), dtype=np.float16)
        )
        self.assertEqual(
            [call[:2] for call in model.token_runtime.normalization_calls],
            [
                ("rms", (2048,)),
                ("l2", (16, 128)),
                ("l2", (16, 128)),
                ("rms", (16, 128)),
            ],
        )
        self.assertEqual(
            [call[:3] for call in model.token_runtime.activation_calls],
            [
                ("sigmoid", (16,), None),
                ("silu", (6144,), None),
                ("decay_multiplier", (16,), (16,)),
                ("silu_mul", (16, 128), (16, 128)),
            ],
        )
        self.assertEqual(
            [call[0] for call in model.token_runtime.tensor_calls],
            ["residual"],
        )
        self.assertAlmostEqual(
            model.token_runtime.normalization_calls[1][3],
            1.0 / np.sqrt(128.0),
        )
        self.assertEqual(model.token_runtime.normalization_calls[2][3], 1.0)
        call = model.token_runtime.recurrent_calls[0]
        self.assertEqual(call[0], 5)
        self.assertTrue(all(value.dtype == np.float16 for value in call[1:]))
        np.testing.assert_array_equal(call[-1], np.full(16, np.float16(0.75)))
        np.testing.assert_array_equal(actual, hidden)

    def test_ane_step_rejects_missing_tensor_runtime(self):
        model = MODULE.QwenModel.__new__(MODULE.QwenModel)
        model.cpu_reference = False
        model.token_runtime = None
        model.layers = []

        with self.assertRaisesRegex(RuntimeError, "ANE tensor runtime is required"):
            model.step(np.zeros(2048, dtype=np.float16), 0)

    def test_cpu_step_allows_explicit_reference_backend(self):
        model = MODULE.QwenModel.__new__(MODULE.QwenModel)
        model.cpu_reference = True
        model.token_runtime = None
        model.layers = []
        hidden = np.zeros(2048, dtype=np.float16)
    
        self.assertIs(model.step(hidden, 0), hidden)
    
    def test_step_captures_each_layer_boundary(self):
        model = MODULE.QwenModel.__new__(MODULE.QwenModel)
        model.cpu_reference = True
        model.token_runtime = None
        model.layers = [{"full": False}, {"full": True}]
        model.output_norm = np.ones(2, dtype=np.float16)
        model.linear_layer = lambda _layer, hidden: hidden + 1
        model.full_layer = lambda _layer, hidden, _position: hidden + 2
        model.normalize_rms = lambda value, _weight: value * 10
        checkpoints = {}
    
        actual = model.step(
            np.zeros(2, dtype=np.float16), 3, checkpoints=checkpoints
        )
    
        np.testing.assert_array_equal(actual, np.full(2, 3, dtype=np.float16))
        self.assertEqual(
            list(checkpoints),
            ["chunk_000_step_003", "chunk_001_step_003"],
        )
        np.testing.assert_array_equal(
            checkpoints["chunk_000_step_003"],
            np.ones((1, 2), dtype=np.float16),
        )
        np.testing.assert_array_equal(
            checkpoints["chunk_001_step_003"],
            np.full((1, 2), 30, dtype=np.float16),
        )

    def test_projection_accumulates_partial_tiles_on_ane(self):
        class Device:
            def __init__(self):
                self.calls = 0

            def gemm(self, _weights, _activation, _descriptor):
                self.calls += 1
                return np.full(512, self.calls, dtype=np.float16)

        class Runtime:
            def __init__(self):
                self.calls = []

            def residual_add(self, left, right):
                self.calls.append((left.copy(), right.copy()))
                return left + right

        model = MODULE.QwenModel.__new__(MODULE.QwenModel)
        model.cpu_reference = False
        model.token_runtime = Runtime()
        model.device = Device()
        model.descriptor = object()
        model.descriptor_512 = object()
        matrix = np.ones((2, 512), dtype=np.float16)

        actual = model.projection(matrix, np.ones(512, dtype=np.float16), in_cols=256)

        self.assertEqual(model.device.calls, 2)
        self.assertEqual(len(model.token_runtime.calls), 1)
        np.testing.assert_array_equal(actual, np.full(2, 3, dtype=np.float16))

    def test_cli_rejects_ane_without_recurrent_artifact(self):
        argv = ["ane-qwen-model.py", "-m", "model.gguf", "-p", "prompt"]
        stderr = io.StringIO()

        with (
            patch.object(sys, "argv", argv),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            MODULE.main()

        self.assertIn("--backend ane requires --recurrent-anec", stderr.getvalue())

    def test_save_parity_outputs_writes_comparator_contract(self):
        result = {
            "model_bytes": 1,
            "model_sha256": "model",
            "max_new_tokens": 2,
            "n_layers": 1,
            "prompts": [{"id": "p1", "runs": [{"generated_ids": [3, 4]}]}],
        }
        logits = [
            np.array([0.0, 1.0], dtype=np.float32),
            np.array([1.0, 0.0], dtype=np.float32),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / "result.json"
            logits_path = root / "logits.npz"
    
            MODULE.save_parity_outputs(result_path, logits_path, result, logits)
    
            saved = json.loads(result_path.read_text(encoding="utf-8"))
            with np.load(logits_path, allow_pickle=False) as archive:
                self.assertEqual(archive.files, ["run_000"])
                np.testing.assert_array_equal(
                    archive["run_000"], np.asarray(logits)
                )
        self.assertEqual(saved["prompts"][0]["id"], "p1")
    
    def test_save_checkpoints_uses_reference_keys_and_float32(self):
        checkpoints = {
            "chunk_000_step_000": np.ones((1, 2), dtype=np.float16)
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoints.npz"
    
            MODULE.save_checkpoints(path, checkpoints)
    
            with np.load(path, allow_pickle=False) as archive:
                self.assertEqual(archive.files, ["chunk_000_step_000"])
                self.assertEqual(archive["chunk_000_step_000"].dtype, np.float32)


if __name__ == "__main__":
    unittest.main()
