import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "qwen_recurrent_graph", Path(__file__).with_name("qwen-recurrent-graph.py")
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class QwenRecurrentGraphTests(unittest.TestCase):
    def test_qwen_shape_keeps_state_and_dynamic_rows_in_one_buffer(self):
        self.assertEqual(MODULE.recurrent_shape(16, 128), (16, 133, 128))

    def test_rejects_layout_without_two_gate_columns(self):
        with self.assertRaisesRegex(ValueError, "dimension must be at least two"):
            MODULE.recurrent_shape(16, 1)


if __name__ == "__main__":
    unittest.main()
