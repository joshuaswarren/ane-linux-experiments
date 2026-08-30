import importlib.util
import json
import plistlib
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    "qwen_espresso_graphs", ROOT / "tools/qwen-espresso-graphs.py"
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeTensor:
    def __init__(self, name, value):
        self.name = name
        self.data = np.asarray(value, dtype=np.float32)
        self.shape = np.asarray(self.data.shape[::-1])
        self.tensor_type = None


class FakeReader:
    def __init__(self, tensors):
        self.tensors = tensors


class FakeWeights:
    def __init__(self, tensors):
        self.reader = FakeReader(tensors)
        self.dequantize = lambda data, _tensor_type: data


class QwenEspressoGraphTests(unittest.TestCase):
    def test_projection_names_follow_runtime_order(self):
        names = {
            "blk.0.attn_q.weight",
            "blk.0.attn_k.weight",
            "blk.0.attn_v.weight",
            "blk.0.attn_output.weight",
            "blk.0.ffn_gate.weight",
            "blk.0.ffn_up.weight",
            "blk.0.ffn_down.weight",
            "blk.1.attn_qkv.weight",
            "blk.1.attn_gate.weight",
            "blk.1.ssm_beta.weight",
            "blk.1.ssm_alpha.weight",
            "blk.1.ssm_out.weight",
            "blk.1.ffn_gate.weight",
            "blk.1.ffn_up.weight",
            "blk.1.ffn_down.weight",
            "token_embd.weight",
        }
        self.assertEqual(
            MODULE.projection_names(names, layer_count=2),
            [
                "blk.0.attn_q.weight",
                "blk.0.attn_k.weight",
                "blk.0.attn_v.weight",
                "blk.0.attn_output.weight",
                "blk.0.ffn_gate.weight",
                "blk.0.ffn_up.weight",
                "blk.0.ffn_down.weight",
                "blk.1.attn_qkv.weight",
                "blk.1.attn_gate.weight",
                "blk.1.ssm_beta.weight",
                "blk.1.ssm_alpha.weight",
                "blk.1.ssm_out.weight",
                "blk.1.ffn_gate.weight",
                "blk.1.ffn_up.weight",
                "blk.1.ffn_down.weight",
                "token_embd.weight",
            ],
        )

    def test_write_sources_chunks_only_tied_head(self):
        tensors = []
        names = [
            "blk.0.attn_q.weight",
            "blk.0.attn_k.weight",
            "blk.0.attn_v.weight",
            "blk.0.attn_output.weight",
            "blk.0.ffn_gate.weight",
            "blk.0.ffn_up.weight",
            "blk.0.ffn_down.weight",
        ]
        for index, name in enumerate(names):
            tensors.append(FakeTensor(name, np.full((2, 3), index + 1)))
        tensors.append(FakeTensor("token_embd.weight", np.arange(21).reshape(7, 3)))

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "graphs"
            model = Path(directory) / "model.gguf"
            model.write_bytes(b"model")
            manifest = MODULE.write_sources(
                FakeWeights(tensors), model, output, layer_count=1, head_chunk_rows=4
            )

            self.assertEqual(manifest["projection_count"], 9)
            self.assertEqual(
                [entry["row_range"] for entry in manifest["projections"][-2:]],
                [[0, 4], [4, 7]],
            )
            self.assertTrue(
                manifest["projections"][-1]["source"].endswith("rows-000004-000007")
            )
            first = output / manifest["projections"][0]["source"]
            with (first / "net.plist").open("rb") as handle:
                network = plistlib.load(handle)["net"]
            self.assertEqual(network["image"]["InputChannels"], 3)
            self.assertEqual(network["projection"]["OutputChannels"], 2)
            self.assertEqual((first / "model.espresso.weights").stat().st_size, 12)
            saved = json.loads((output / "manifest.json").read_text())
            self.assertEqual(saved, manifest)

    def test_projection_names_reject_missing_runtime_matrix(self):
        with self.assertRaisesRegex(ValueError, "blk.0.attn_k.weight"):
            MODULE.projection_names(
                {
                    "blk.0.attn_q.weight",
                    "blk.0.attn_v.weight",
                    "blk.0.attn_output.weight",
                    "blk.0.ffn_gate.weight",
                    "blk.0.ffn_up.weight",
                    "blk.0.ffn_down.weight",
                    "token_embd.weight",
                },
                layer_count=1,
            )


if __name__ == "__main__":
    unittest.main()
