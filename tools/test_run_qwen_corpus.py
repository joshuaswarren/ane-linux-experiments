import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "run_qwen_corpus", ROOT / "tools/run-qwen-corpus.py"
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class QwenCorpusRunnerTests(unittest.TestCase):
    def test_load_inputs_enforces_model_and_corpus_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "model.gguf"
            corpus = root / "prompts.jsonl"
            contract = root / "contract.json"
            model.write_bytes(b"model")
            corpus.write_text(
                json.dumps({"id": "p1", "category": "test", "text": "Prompt"}) + chr(10),
                encoding="utf-8",
            )
            contract.write_text(
                json.dumps(
                    {
                        "model": {
                            "bytes": model.stat().st_size,
                            "sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
                        },
                        "corpus": {
                            "prompts": 1,
                            "sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
                        },
                    }
                ),
                encoding="utf-8",
            )

            loaded_contract, rows = MODULE.load_inputs(contract, model, corpus)

        self.assertEqual(loaded_contract["corpus"]["prompts"], 1)
        self.assertEqual(rows[0]["id"], "p1")

    def test_completed_prompt_requires_finite_complete_shard(self):
        row = {"id": "p1", "category": "test", "text": "Prompt"}
        result = {
            "model_bytes": 1,
            "model_sha256": "model",
            "max_new_tokens": 2,
            "n_layers": 1,
            "prompts": [
                {
                    **row,
                    "prompt_token_ids": [1],
                    "runs": [{"generated_ids": [2, 3]}],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path, logits_path = MODULE.prompt_paths(root, 0)
            result_path.write_text(json.dumps(result), encoding="utf-8")
            np.savez(logits_path, run_000=np.ones((2, 4), dtype=np.float32))

            completed = MODULE.load_completed_prompt(root, 0, row, 2)
            summary = MODULE.write_summary(root, [completed])

            saved = json.loads(summary.read_text(encoding="utf-8"))
        self.assertEqual(saved["prompts"][0]["id"], "p1")


if __name__ == "__main__":
    unittest.main()
