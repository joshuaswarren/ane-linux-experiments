import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "compare_qwen_reference", ROOT / "tools/compare-qwen-reference.py"
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class QwenParityComparatorTests(unittest.TestCase):
    def test_compare_logits_uses_generated_steps_and_top10_metrics(self):
        reference = np.zeros((3, 12), dtype=np.float32)
        candidate = reference.copy()
        reference[1] = np.arange(12, dtype=np.float32)
        reference[2] = np.arange(12, dtype=np.float32)[::-1]
        candidate[1] = reference[1] + 0.01
        candidate[2] = reference[2] + 0.01

        report = MODULE.compare_logits(
            reference,
            candidate,
            generated_start=1,
            thresholds={
                "top10_overlap": 0.9,
                "max_absolute_logit_error": 0.25,
                "mean_absolute_logit_error": 0.02,
                "relative_l2_error": 0.01,
            },
        )

        self.assertTrue(report["passed"])
        self.assertEqual(report["top1_token_match"], 1.0)
        self.assertEqual(report["top10_overlap"], 1.0)
        self.assertAlmostEqual(report["max_absolute_logit_error"], 0.01, places=6)

    def test_compare_logits_rejects_top1_mismatch(self):
        reference = np.zeros((2, 12), dtype=np.float32)
        candidate = reference.copy()
        reference[1, 3] = 1.0
        candidate[1, 4] = 1.0

        report = MODULE.compare_logits(
            reference,
            candidate,
            generated_start=1,
            thresholds={
                "top10_overlap": 0.9,
                "max_absolute_logit_error": 0.25,
                "mean_absolute_logit_error": 0.02,
                "relative_l2_error": 0.01,
            },
        )

        self.assertFalse(report["passed"])
        self.assertEqual(report["top1_token_match"], 0.0)

    def test_compare_checkpoints_rejects_missing_key(self):
        with tempfile.TemporaryDirectory() as directory:
            reference_path = Path(directory) / "reference.npz"
            candidate_path = Path(directory) / "candidate.npz"
            np.savez(reference_path, chunk_000_step_000=np.ones((1, 4), np.float32))
            np.savez(candidate_path, chunk_001_step_000=np.ones((1, 4), np.float32))

            report = MODULE.compare_checkpoints(reference_path, candidate_path)

        self.assertFalse(report["passed"])
        self.assertEqual(report["missing_in_candidate"], ["chunk_000_step_000"])
        self.assertEqual(report["unexpected_in_candidate"], ["chunk_001_step_000"])


    def test_compare_run_files_maps_logits_by_json_order(self):
        contract = {
            "model": {"bytes": 1, "sha256": "model", "layers": 1},
            "generation": {"new_tokens": 1},
            "numeric_thresholds": {
                "top10_overlap": 0.9,
                "max_absolute_logit_error": 0.25,
                "mean_absolute_logit_error": 0.02,
                "relative_l2_error": 0.01,
            },
        }
        rows = [
            {"id": "b", "generated_ids": [2], "prompt_token_ids": [1, 2]},
            {"id": "a", "generated_ids": [1], "prompt_token_ids": [1, 2]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference_json = root / "reference.json"
            candidate_json = root / "candidate.json"
            contract_path = root / "contract.json"
            reference_logits = root / "reference.npz"
            candidate_logits = root / "candidate.npz"
            base = {
                "model_bytes": 1,
                "model_sha256": "model",
                "max_new_tokens": 1,
                "n_layers": 1,
                "prompts": rows,
            }
            reference_json.write_text(json.dumps(base), encoding="utf-8")
            candidate_json.write_text(
                json.dumps({**base, "prompts": list(reversed(rows))}),
                encoding="utf-8",
            )
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            b_logits = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
            a_logits = np.array([[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
            np.savez(reference_logits, prompt_000=b_logits, prompt_001=a_logits)
            np.savez(candidate_logits, prompt_000=a_logits, prompt_001=b_logits)

            report = MODULE.compare_run_files(
                reference_json,
                candidate_json,
                reference_logits,
                candidate_logits,
                contract_path,
            )

        self.assertTrue(report["passed"])

    def test_compare_run_files_handles_repeated_runs_and_legacy_archives(self):
        contract = {
            "model": {"bytes": 1, "sha256": "model", "layers": 1},
            "generation": {"new_tokens": 1},
            "numeric_thresholds": {
                "top10_overlap": 0.9,
                "max_absolute_logit_error": 0.25,
                "mean_absolute_logit_error": 0.02,
                "relative_l2_error": 0.01,
            },
        }
        rows = [
            {"id": "b", "generated_ids": [2], "prompt_token_ids": [1, 2]},
            {"id": "a", "generated_ids": [1], "prompt_token_ids": [1, 2]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference_json = root / "reference.json"
            candidate_json = root / "candidate.json"
            contract_path = root / "contract.json"
            reference_logits = root / "reference.npz"
            candidate_logits = root / "candidate.npz"
            base = {
                "model_bytes": 1,
                "model_sha256": "model",
                "max_new_tokens": 1,
                "n_layers": 1,
                "prompts": rows,
            }
            reference_json.write_text(json.dumps(base), encoding="utf-8")
            candidate_json.write_text(
                json.dumps({**base, "prompts": list(reversed(rows))}),
                encoding="utf-8",
            )
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            b_logits = np.array(
                [[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32
            )
            a_logits = np.array([[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
            np.savez(
                reference_logits,
                prompt_000_run_000=b_logits,
                prompt_000_run_001=b_logits,
                prompt_001=a_logits,
            )
            np.savez(
                candidate_logits,
                prompt_000_run_000=a_logits,
                prompt_001_run_000=b_logits,
                prompt_001_run_001=b_logits,
            )

            report = MODULE.compare_run_files(
                reference_json,
                candidate_json,
                reference_logits,
                candidate_logits,
                contract_path,
            )

        self.assertTrue(report["passed"])
        self.assertEqual(len(report["logit_parity"]["prompts"]["b"]["runs"]), 2)

if __name__ == "__main__":
    unittest.main()
