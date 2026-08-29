import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "aneforge_qwen_reference", ROOT / "tools/aneforge-qwen-reference.py"
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReferenceRunnerTests(unittest.TestCase):
    def test_load_prompt_corpus_validates_ids_and_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prompts.jsonl"
            path.write_text(
                json.dumps({"id": "p1", "category": "science", "text": "Why?"}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(MODULE.load_prompt_corpus(path), [
                {"id": "p1", "category": "science", "text": "Why?"}
            ])

            path.write_text(
                json.dumps({"id": "p1", "category": "science", "text": "Why?"})
                + "\n"
                + json.dumps({"id": "p1", "category": "science", "text": "Again?"})
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "not unique"):
                MODULE.load_prompt_corpus(path)

    def test_summarize_runs_checks_repeatability(self):
        logits = [np.array([[1.0, 0.0]], dtype=np.float32)]
        run = {
            "generated_ids": [3, 4],
            "elapsed_seconds": 1.0,
            "stages": [],
            "stage_totals": {},
            "prefill_tokens": 1,
            "prefill_seconds": 0.1,
            "prefill_tokens_per_second": 10.0,
            "decode_seconds": 0.2,
            "decode_tokens_per_second": 10.0,
            "time_to_first_token_seconds": 0.3,
            "ane_decoder_submissions": 2,
            "ane_submissions_per_generated_token": 1.0,
            "logits": logits,
            "logits_shape": [2],
            "logits_finite": True,
        }
        result = MODULE.summarize_runs([run, {**run, "logits": logits}])
        self.assertTrue(result["token_sequences_match"])
        self.assertEqual(result["logits_repeatability_max_abs"], 0.0)
        self.assertNotIn("logits", result["runs"][0])

    def test_save_checkpoints_writes_named_arrays(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoints.npz"
            MODULE.save_checkpoints(
                path,
                {
                    "checkpoints": [
                        {"chunk": 0, "step": 2, "values": np.ones((1, 4), np.float32)}
                    ]
                },
            )
            with np.load(path) as archive:
                self.assertEqual(archive.files, ["chunk_000_step_002"])
                np.testing.assert_array_equal(
                    archive["chunk_000_step_002"], np.ones((1, 4), np.float32)
                )
    def test_save_logits_preserves_ragged_prompt_lengths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "logits.npz"
            MODULE.save_logits(
                path,
                [
                    [[np.array([1.0, 2.0], dtype=np.float32)]],
                    [
                        [
                            np.array([3.0, 4.0], dtype=np.float32),
                            np.array([5.0, 6.0], dtype=np.float32),
                        ]
                    ],
                ],
            )
            with np.load(path) as archive:
                self.assertEqual(
                    archive.files,
                    ["prompt_000_run_000", "prompt_001_run_000"],
                )
                self.assertEqual(archive["prompt_000_run_000"].shape, (1, 2))
                self.assertEqual(archive["prompt_001_run_000"].shape, (2, 2))
    def test_save_logits_preserves_prompt_and_run_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "logits.npz"
            MODULE.save_logits(
                path,
                [
                    [
                        [np.array([1.0, 2.0], dtype=np.float32)],
                        [np.array([3.0, 4.0], dtype=np.float32)],
                    ],
                    [[np.array([5.0, 6.0], dtype=np.float32)]],
                ],
            )
            with np.load(path) as archive:
                self.assertEqual(
                    archive.files,
                    [
                        "prompt_000_run_000",
                        "prompt_000_run_001",
                        "prompt_001_run_000",
                    ],
                )



    def test_validate_contract_checks_model_and_corpus_artifacts(self):
        contract = ROOT / "benchmarks/qwen38-2b-contract.json"
        corpus = ROOT / "benchmarks/qwen38-2b-prompts.jsonl"

        MODULE.validate_contract(
            contract,
            model_size=1_312_164_224,
            model_sha256="4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff",
            n_layers=24,
            max_new_tokens=32,
            prompt_corpus=corpus,
        )

        with self.assertRaisesRegex(ValueError, "model SHA-256"):
            MODULE.validate_contract(
                contract,
                model_size=1_312_164_224,
                model_sha256="wrong",
                n_layers=24,
                max_new_tokens=32,
                prompt_corpus=corpus,
            )

if __name__ == "__main__":
    unittest.main()
