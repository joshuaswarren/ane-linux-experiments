import importlib.util
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "validate_qwen_projections",
    Path(__file__).with_name("validate-qwen-projections.py"),
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)


class FakeRunner:
    calls: ClassVar[list] = []
    source_root: ClassVar[Path]
    anec_root: ClassVar[Path]

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def run(self, source):
        relative = self.path.parent.relative_to(FakeRunner.anec_root)
        matrix = np.fromfile(
            FakeRunner.source_root / relative / "model.espresso.weights",
            dtype=np.float16,
        ).reshape(-1, source.size)
        FakeRunner.calls.append((self.path, source.copy()))
        return (
            (matrix.astype(np.float32) @ source.reshape(-1).astype(np.float32))
            .astype(np.float16)
            .reshape(1, matrix.shape[0], 1, 1)
        )


class ValidateQwenProjectionsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source_root = self.root / "source"
        self.anec_root = self.root / "anec"
        FakeRunner.calls = []
        FakeRunner.source_root = self.source_root
        FakeRunner.anec_root = self.anec_root

    def tearDown(self):
        self.temporary.cleanup()

    def add_projection(self, name, matrix):
        relative = Path("projections") / name
        source = self.source_root / relative
        anec = self.anec_root / relative
        source.mkdir(parents=True)
        anec.mkdir(parents=True)
        matrix.astype(np.float16).tofile(source / "model.espresso.weights")
        (anec / "model.anec").write_bytes(b"artifact")
        return {
            "source": relative.as_posix(),
            "shape": list(matrix.shape),
            "tensor": name,
        }

    def test_validates_one_projection_per_unique_shape(self):
        entries = [
            self.add_projection("first", np.arange(12).reshape(3, 4) / 16),
            self.add_projection("duplicate", np.ones((3, 4))),
            self.add_projection("second", np.arange(10).reshape(2, 5) / 8),
        ]

        report = MODULE.validate_geometry_classes(
            {"projections": entries},
            self.source_root,
            self.anec_root,
            FakeRunner,
            tolerance=0.01,
        )

        self.assertTrue(report["passed"])
        self.assertEqual(report["geometry_count"], 2)
        self.assertEqual(
            [item["shape"] for item in report["geometries"]], [[3, 4], [2, 5]]
        )
        self.assertEqual(len(FakeRunner.calls), 2)
        for _, source in FakeRunner.calls:
            self.assertGreater(np.unique(source).size, 1)

    def test_rejects_projection_outside_tolerance(self):
        entry = self.add_projection("bad", np.eye(2))

        class BadRunner(FakeRunner):
            def run(self, source):
                return super().run(source) + np.float16(1)

        report = MODULE.validate_geometry_classes(
            {"projections": [entry]},
            self.source_root,
            self.anec_root,
            BadRunner,
            tolerance=0.1,
        )

        self.assertFalse(report["passed"])
        self.assertAlmostEqual(report["geometries"][0]["max_absolute_error"], 1.0)


SPEC.loader.exec_module(MODULE)

if __name__ == "__main__":
    unittest.main()
