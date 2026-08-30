import importlib.util
import unittest
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "ane_qwen_model", Path(__file__).parent.parent / "ane-qwen-model.py"
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class QwenModelMathTests(unittest.TestCase):
    def test_causal_attention_normalizes_equal_scores(self):
        query = np.zeros((4, 2), dtype=np.float16)
        keys = np.zeros((1, 2, 2), dtype=np.float16)
        values = np.asarray([[[2, 2], [4, 4]]], dtype=np.float16)
        actual = MODULE.causal_attention(query, keys, values)
        np.testing.assert_array_equal(actual, np.full((4, 2), 3, dtype=np.float16))


if __name__ == "__main__":
    unittest.main()
