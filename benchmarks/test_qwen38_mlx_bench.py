"""Checks for qwen38 bench record/hash/count handling (no hardware, no mlx)."""
import importlib.util, sys, unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "lib", Path(__file__).resolve().parent / "qwen38_bench_lib.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class T(unittest.TestCase):
    def test_hash_is_content_sensitive(self):
        base = {"pass": 0, "prompt_idx": 0, "input_ids": [1, 2], "output_ids": [5, 6]}
        swapped = dict(base, input_ids=[2, 1])
        self.assertNotEqual(mod.ordered_records_hash([base]),
                            mod.ordered_records_hash([swapped]))

    def test_hash_normalizes_list_order_not_labels(self):
        r0 = {"pass": 0, "prompt_idx": 0, "input_ids": [1], "output_ids": [5]}
        r1 = {"pass": 1, "prompt_idx": 0, "input_ids": [1], "output_ids": [5]}
        self.assertEqual(mod.ordered_records_hash([r0, r1]),
                         mod.ordered_records_hash([r1, r0]))
        r1b = dict(r1, **{"pass": 2})
        self.assertNotEqual(mod.ordered_records_hash([r0, r1]),
                            mod.ordered_records_hash([r0, r1b]))

    def test_summarize_counts(self):
        s = mod.summarize([10.0, 20.0])
        self.assertEqual(s["n"], 2)
        self.assertEqual(s["median"], 15.0)
        self.assertGreater(s["stdev"], 0)


if __name__ == "__main__":
    unittest.main()
