import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "qwen_token_runtime", Path(__file__).with_name("qwen-token-runtime.py")
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeMutableGemm:
    instances: ClassVar[list] = []

    def __init__(self, _device, _descriptor, output_rows):
        self.output_rows = output_rows
        self.closed = False
        self.instances.append(self)

    def close(self):
        self.closed = True


class FakeAttentionState:
    instances: ClassVar[list] = []

    def __init__(self, score, value, context, dimension):
        self.score = score
        self.value = value
        self.context = context
        self.dimension = dimension
        self.appends = []
        self.queries = []
        self.instance_index = len(self.instances)
        self.instances.append(self)

    def append(self, key, value):
        self.appends.append((key.copy(), value.copy()))

    def scores(self, query):
        self.queries.append(query.copy())
        return np.full(self.context, query[0], dtype=np.float16)

    def attend(self, probabilities):
        value = np.float16(1 + self.instance_index)
        return np.full(self.dimension, value * probabilities.sum(), dtype=np.float16)


class FakeElementwiseBackend:
    instances: ClassVar[list] = []

    def __init__(self, _device, _descriptors):
        self.closed = False
        self.instances.append(self)

    def __call__(self, mode, left, right):
        if mode != "mul":
            raise AssertionError(mode)
        return np.multiply(left, right, dtype=np.float16)

    def close(self):
        self.closed = True


class FakeSoftmax:
    instances: ClassVar[list] = []

    def __init__(self, _backend):
        self.inputs = []
        self.instances.append(self)

    def __call__(self, scores):
        self.inputs.append(scores.copy())
        return np.full(128, np.float16(1.0 / 128.0), dtype=np.float16)


class FakeNormalization:
    instances: ClassVar[list] = []

    def __init__(self, _backend):
        self.calls = []
        self.instances.append(self)

    def rms_norm(self, value, weight):
        self.calls.append(("rms", value.copy(), weight.copy()))
        return value.copy()

    def l2_norm(self, value, scale=1.0):
        self.calls.append(("l2", value.copy(), scale))
        return value.copy()


class FakeActivations:
    instances: ClassVar[list] = []

    def __init__(self, _backend):
        self.calls = []
        self.instances.append(self)

    def sigmoid(self, value):
        self.calls.append(("sigmoid", value.copy(), None))
        return value.copy()

    def sigmoid_mul(self, value, multiplier):
        self.calls.append(("sigmoid_mul", value.copy(), multiplier.copy()))
        return value.copy()

    def silu(self, value):
        self.calls.append(("silu", value.copy(), None))
        return value.copy()

    def silu_mul(self, value, multiplier):
        self.calls.append(("silu_mul", value.copy(), multiplier.copy()))
        return value.copy()

    def decay_multiplier(self, alpha, bias, a_log):
        self.calls.append(
            ("decay_multiplier", alpha.copy(), bias.copy(), a_log.copy())
        )
        return alpha.copy()


class FakeRecurrentRunner:
    instances: ClassVar[list] = []

    def __init__(self, path, device):
        self.path = Path(path)
        self.device = device
        self.initialized = None
        self.steps = []
        self.closed = False
        self.instances.append(self)

    def initialize(self, state):
        self.initialized = state.copy()

    def step(self, q, k, v, beta, decay):
        self.steps.append((q.copy(), k.copy(), v.copy(), beta.copy(), decay.copy()))
        return q.copy()

    def close(self):
        self.closed = True


class QwenTokenRuntimeTests(unittest.TestCase):
    def setUp(self):
        FakeMutableGemm.instances = []
        FakeAttentionState.instances = []
        FakeElementwiseBackend.instances = []
        FakeSoftmax.instances = []
        FakeNormalization.instances = []
        FakeActivations.instances = []
        FakeRecurrentRunner.instances = []
        self.original_attention = MODULE.ATTENTION
        self.original_softmax = MODULE.SOFTMAX
        self.original_recurrent = MODULE.RECURRENT
        MODULE.ATTENTION = SimpleNamespace(
            MutableGemm=FakeMutableGemm,
            AttentionGemmState=FakeAttentionState,
        )
        MODULE.SOFTMAX = SimpleNamespace(
            LANES=64,
            ElementwiseBackend=FakeElementwiseBackend,
            Softmax128=FakeSoftmax,
            Normalization=FakeNormalization,
            Activations=FakeActivations,
        )
        MODULE.RECURRENT = SimpleNamespace(RecurrentRunner=FakeRecurrentRunner)
        self.runtime = MODULE.QwenTokenRuntime(
            device=object(),
            descriptor=b"descriptor",
            elementwise_descriptors={"add": b"descriptor"},
            recurrent_artifact="recurrent.anec",
            full_layers=2,
            recurrent_layers=3,
        )

    def tearDown(self):
        self.runtime.close()
        MODULE.ATTENTION = self.original_attention
        MODULE.SOFTMAX = self.original_softmax
        MODULE.RECURRENT = self.original_recurrent

    def test_harvest_closes_fresh_softmax_device(self):
        descriptors = {"add": b"descriptor"}
        with (
            patch.object(
                MODULE.runpy,
                "run_path",
                return_value={"fd": 17, "_descriptors": descriptors},
            ) as run_path,
            patch.object(MODULE.os, "close") as close,
        ):
            actual = MODULE.harvest_elementwise_descriptors("ane-softmax.py")

        self.assertIs(actual, descriptors)
        run_path.assert_called_once_with(
            "ane-softmax.py", run_name="qwen_elementwise_harvest"
        )
        close.assert_called_once_with(17)

    def test_allocates_bounded_state_programs(self):
        self.assertEqual(len(FakeMutableGemm.instances), 8)
        self.assertEqual(
            [program.output_rows for program in FakeMutableGemm.instances],
            [128, 256] * 4,
        )
        self.assertEqual(len(FakeAttentionState.instances), 4)
        self.assertEqual(len(FakeRecurrentRunner.instances), 3)
        for runner in FakeRecurrentRunner.instances:
            np.testing.assert_array_equal(
                runner.initialized, np.zeros((16, 128, 128), dtype=np.float16)
            )

    def test_decay_multiplier_uses_shared_activation_backend(self):
        alpha = np.arange(16, dtype=np.float16)
        bias = np.full(16, -1, dtype=np.float16)
        a_log = np.full(16, -2, dtype=np.float16)

        actual = self.runtime.decay_multiplier(alpha, bias, a_log)

        np.testing.assert_array_equal(actual, alpha)
        self.assertEqual(
            FakeActivations.instances[0].calls[-1][0], "decay_multiplier"
        )

    def test_full_attention_maps_four_query_heads_to_each_kv_head(self):
        query = np.repeat(
            np.arange(8, dtype=np.float16)[:, None], 256, axis=1
        )
        key = np.repeat(
            np.arange(2, dtype=np.float16)[:, None], 256, axis=1
        )
        value = key + np.float16(10)

        actual = self.runtime.full_attention(1, query, key, value)

        states = FakeAttentionState.instances[2:4]
        self.assertEqual([len(state.appends) for state in states], [1, 1])
        self.assertEqual([len(state.queries) for state in states], [4, 4])
        np.testing.assert_array_equal(states[0].queries[0], query[0])
        np.testing.assert_array_equal(states[0].queries[-1], query[3])
        np.testing.assert_array_equal(states[1].queries[0], query[4])
        np.testing.assert_array_equal(states[1].queries[-1], query[7])
        softmax_inputs = FakeSoftmax.instances[0].inputs
        self.assertEqual(len(softmax_inputs), 8)
        np.testing.assert_array_equal(
            softmax_inputs[7], np.full(128, np.float16(7.0 / 16.0))
        )
        np.testing.assert_array_equal(actual[:4], np.full((4, 256), 3, dtype=np.float16))
        np.testing.assert_array_equal(actual[4:], np.full((4, 256), 4, dtype=np.float16))

    def test_recurrent_step_uses_selected_resident_runner(self):
        q = np.ones((16, 128), dtype=np.float16)
        gate = np.ones(16, dtype=np.float16)

        actual = self.runtime.recurrent(2, q, q, q, gate, gate)

        np.testing.assert_array_equal(actual, q)
        self.assertEqual(len(FakeRecurrentRunner.instances[2].steps), 1)
        self.assertEqual(len(FakeRecurrentRunner.instances[0].steps), 0)

    def test_normalization_uses_shared_elementwise_backend(self):
        value = np.ones((2, 128), dtype=np.float16)
        weight = np.full(128, np.float16(2.0))

        rms = self.runtime.rms_norm(value, weight)
        l2 = self.runtime.l2_norm(value, 0.125)

        np.testing.assert_array_equal(rms, value)
        np.testing.assert_array_equal(l2, value)
        self.assertEqual(
            [call[0] for call in FakeNormalization.instances[0].calls],
            ["rms", "l2"],
        )
        self.assertEqual(FakeNormalization.instances[0].calls[1][2], 0.125)

    def test_activations_use_shared_elementwise_backend(self):
        value = np.ones((2, 128), dtype=np.float16)
        multiplier = np.full((2, 128), np.float16(2.0))

        sigmoid = self.runtime.sigmoid(value)
        silu = self.runtime.silu(value)
        sigmoid_fused = self.runtime.sigmoid_mul(value, multiplier)
        silu_fused = self.runtime.silu_mul(value, multiplier)

        np.testing.assert_array_equal(sigmoid, value)
        np.testing.assert_array_equal(silu, value)
        np.testing.assert_array_equal(sigmoid_fused, value)
        np.testing.assert_array_equal(silu_fused, value)
        self.assertEqual(
            [call[0] for call in FakeActivations.instances[0].calls],
            ["sigmoid", "silu", "sigmoid_mul", "silu_mul"],
        )

    def test_close_is_idempotent(self):
        self.runtime.close()
        self.runtime.close()
        self.assertTrue(all(item.closed for item in FakeMutableGemm.instances))
        self.assertTrue(all(item.closed for item in FakeRecurrentRunner.instances))
        self.assertTrue(FakeElementwiseBackend.instances[0].closed)


if __name__ == "__main__":
    unittest.main()
