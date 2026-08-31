import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent


class AneContractTests(unittest.TestCase):
    def test_benchmark_contract_pins_real_model_and_ane_policy(self):
        contract = json.loads(
            (ROOT / "benchmarks/qwen38-2b-contract.json").read_text(encoding="utf-8")
        )

        self.assertEqual(contract["model"]["bytes"], 1_312_164_224)
        self.assertEqual(
            contract["model"]["sha256"],
            "4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff",
        )
        self.assertEqual(contract["model"]["layers"], 24)
        self.assertEqual(contract["corpus"]["prompts"], 100)
        self.assertEqual(contract["corpus"]["categories"], 10)
        self.assertEqual(contract["backends"]["linux_ane"]["compute"], "ANE only")
        self.assertTrue(contract["backends"]["linux_ane"]["fallback"].startswith("forbidden"))

    def test_prompt_corpus_has_pinned_size_and_categories(self):
        rows = [
            json.loads(line)
            for line in (ROOT / "benchmarks/qwen38-2b-prompts.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]

        self.assertEqual(len(rows), 100)
        self.assertEqual(len({row["category"] for row in rows}), 10)
        self.assertEqual({row["id"] for row in rows}, {f"p{index:03d}" for index in range(1, 101)})

    def test_ane_projection_propagates_device_failure_without_cpu_fallback(self):
        spec = importlib.util.spec_from_file_location(
            "ane_qwen_model", ROOT / "ane-qwen-model.py"
        )
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class FailingDevice:
            tile_gemm = None


            def gemm(self, *_args):
                raise RuntimeError("simulated ANE submit failure")
            def blob_swap_gemm(self, *_args):
                raise RuntimeError("simulated ANE submit failure")

        model = object.__new__(module.QwenModel)
        model.cpu_reference = False
        model.token_runtime = object()
        model.device = FailingDevice()
        model.descriptor = object()
        model.descriptor_512 = object()

        with self.assertRaisesRegex(RuntimeError, "simulated ANE submit failure"):
            model.projection(
                np.zeros((512, 256), dtype=np.float16),
                np.zeros(256, dtype=np.float16),
            )


if __name__ == "__main__":
    unittest.main()
