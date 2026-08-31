import importlib.util
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

    def full_attention(self, layer_index, query, key, value):
        self.full_calls.append(
            (layer_index, query.copy(), key.copy(), value.copy())
        )
        return np.ones((8, 256), dtype=np.float16)

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

class QwenModelMathTests(unittest.TestCase):
    def test_causal_attention_normalizes_equal_scores(self):
        query = np.zeros((4, 2), dtype=np.float16)
        keys = np.zeros((1, 2, 2), dtype=np.float16)
        values = np.asarray([[[2, 2], [4, 4]]], dtype=np.float16)
        actual = MODULE.causal_attention(query, keys, values)
        np.testing.assert_array_equal(actual, np.full((4, 2), 3, dtype=np.float16))

    def test_full_layer_uses_resident_attention_runtime(self):
        model = MODULE.QwenModel.__new__(MODULE.QwenModel)
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
        with patch.object(
            MODULE, "rope", side_effect=lambda value, _position: value
        ):
            actual = model.full_layer(layer, hidden, 0)

        self.assertEqual(len(model.token_runtime.full_calls), 1)
        self.assertEqual(
            [call[:2] for call in model.token_runtime.normalization_calls],
            [("rms", (2048,)), ("rms", (8, 256)), ("rms", (2, 256))],
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
            "a_log": np.zeros(16, dtype=np.float16),
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
        with (
            patch.object(MODULE, "sigmoid", side_effect=lambda value: np.ones_like(value)),
            patch.object(MODULE, "silu", side_effect=lambda value: value),
        ):
            actual = model.linear_layer(layer, hidden)

        self.assertEqual(len(model.token_runtime.recurrent_calls), 1)
        self.assertEqual(
            [call[:2] for call in model.token_runtime.normalization_calls],
            [
                ("rms", (2048,)),
                ("l2", (16, 128)),
                ("l2", (16, 128)),
                ("rms", (16, 128)),
            ],
        )
        self.assertAlmostEqual(
            model.token_runtime.normalization_calls[1][3],
            1.0 / np.sqrt(128.0),
        )
        self.assertEqual(model.token_runtime.normalization_calls[2][3], 1.0)
        call = model.token_runtime.recurrent_calls[0]
        self.assertEqual(call[0], 5)
        self.assertTrue(all(value.dtype == np.float16 for value in call[1:]))
        np.testing.assert_array_equal(actual, hidden)


if __name__ == "__main__":
    unittest.main()
