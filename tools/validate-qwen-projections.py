#!/usr/bin/env python3
"""Validate one compiled Qwen projection from each tensor geometry class."""

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np


def load_projection_runner():
    path = Path(__file__).with_name("projection-runtime.py")
    spec = importlib.util.spec_from_file_location("projection_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ProjectionRunner


def validation_input(channels):
    indices = np.arange(channels, dtype=np.int32)
    return (
        (((indices * 37) % 251 - 125) / 128)
        .astype(np.float16)
        .reshape(1, channels, 1, 1)
    )


def validate_geometry_classes(
    manifest, source_root, anec_root, runner_factory, tolerance=0.1
):
    if tolerance < 0:
        raise ValueError("tolerance must not be negative")
    selected = {}
    for entry in manifest["projections"]:
        shape = tuple(map(int, entry["shape"]))
        if len(shape) != 2 or min(shape) < 1:
            raise ValueError(f"invalid projection shape {shape}")
        selected.setdefault(shape, entry)
    if not selected:
        raise ValueError("manifest has no projections")

    geometries = []
    for shape, entry in selected.items():
        output_channels, input_channels = shape
        relative = Path(entry["source"])
        weights_path = Path(source_root) / relative / "model.espresso.weights"
        artifact_path = Path(anec_root) / relative / "model.anec"
        matrix = np.fromfile(weights_path, dtype=np.float16)
        if matrix.size != output_channels * input_channels:
            raise ValueError(
                f"{weights_path} has {matrix.size} values, expected "
                f"{output_channels * input_channels}"
            )
        matrix = matrix.reshape(output_channels, input_channels)
        source = validation_input(input_channels)
        expected = (
            (matrix.astype(np.float32) @ source.reshape(-1).astype(np.float32))
            .astype(np.float16)
            .astype(np.float32)
        )
        with runner_factory(artifact_path) as runner:
            observed = runner.run(source).reshape(-1).astype(np.float32)
        if observed.size != output_channels:
            raise ValueError(
                f"{artifact_path} returned {observed.size} values, expected {output_channels}"
            )
        error = np.abs(observed - expected)
        finite = bool(np.isfinite(observed).all())
        max_error = float(error.max())
        geometries.append(
            {
                "tensor": entry["tensor"],
                "source": relative.as_posix(),
                "shape": list(shape),
                "finite": finite,
                "max_absolute_error": max_error,
                "mean_absolute_error": float(error.mean()),
                "passed": finite and max_error <= tolerance,
            }
        )
    return {
        "format": "qwen-projection-geometry-validation-v1",
        "geometry_count": len(geometries),
        "tolerance": tolerance,
        "passed": all(item["passed"] for item in geometries),
        "geometries": geometries,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("anec_root", type=Path)
    parser.add_argument("--qid", type=int)
    parser.add_argument("--tolerance", type=float, default=0.1)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    projection_runner = load_projection_runner()

    def runner_factory(path):
        return projection_runner(path, qid=args.qid)

    report = validate_geometry_classes(
        manifest,
        args.source_root,
        args.anec_root,
        runner_factory,
        args.tolerance,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not report["passed"]:
        raise SystemExit("QWEN_PROJECTION_GEOMETRY_VALIDATION_FAILED")
    print("QWEN_PROJECTION_GEOMETRY_VALIDATION_OK")


if __name__ == "__main__":
    main()
