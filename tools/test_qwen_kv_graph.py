import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "qwen_kv_graph", Path(__file__).with_name("qwen-kv-graph.py")
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class QwenKvGraphTests(unittest.TestCase):
    def test_qwen_shape_keeps_fixed_cache_and_dynamic_rows_in_one_buffer(self):
        self.assertEqual(MODULE.cache_shape(8, 128, 256), (8, 259, 256))

    def test_rejects_empty_cache(self):
        with self.assertRaisesRegex(ValueError, "must be positive"):
            MODULE.cache_shape(8, 0, 256)


if __name__ == "__main__":
    unittest.main()
