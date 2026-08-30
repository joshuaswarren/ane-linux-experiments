#!/usr/bin/env python3
"""Emit legacy Espresso sources for every Qwen projection used at runtime."""

import argparse
import hashlib
import importlib.util
import json
import plistlib
from pathlib import Path

FULL_ATTENTION_SUFFIXES = (
    "attn_q.weight",
    "attn_k.weight",
    "attn_v.weight",
    "attn_output.weight",
)
LINEAR_ATTENTION_SUFFIXES = (
    "attn_qkv.weight",
    "attn_gate.weight",
    "ssm_beta.weight",
    "ssm_alpha.weight",
    "ssm_out.weight",
)
MLP_SUFFIXES = ("ffn_gate.weight", "ffn_up.weight", "ffn_down.weight")
TIED_HEAD = "token_embd.weight"


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def projection_names(tensor_names, layer_count=24):
    available = set(tensor_names)
    names = []
    for index in range(layer_count):
        prefix = f"blk.{index}."
        suffixes = (
            FULL_ATTENTION_SUFFIXES
            if prefix + FULL_ATTENTION_SUFFIXES[0] in available
            else LINEAR_ATTENTION_SUFFIXES
        )
        required = [prefix + suffix for suffix in suffixes + MLP_SUFFIXES]
        missing = [name for name in required if name not in available]
        if missing:
            raise ValueError(f"missing runtime matrix: {missing[0]}")
        names.extend(required)
    if TIED_HEAD not in available:
        raise ValueError(f"missing runtime matrix: {TIED_HEAD}")
    names.append(TIED_HEAD)
    return names


def espresso_network(input_channels, output_channels):
    return {
        "Networks": ["net"],
        "Version": "1.0.9",
        "net": {
            "Inputs": ["image"],
            "Outputs": ["projection@output"],
            "Units": ["projection"],
            "Weights": ["model.espresso.weights"],
            "image": {
                "BatchSize": 1,
                "InputChannels": input_channels,
                "InputHeight": 1,
                "InputInterleave": 1,
                "InputPlaneStride": 64,
                "InputRowStride": 64,
                "InputType": "Float16",
                "InputWidth": 1,
            },
            "projection": {
                "Bottom": "image",
                "Name": "projection",
                "OutputChannels": output_channels,
                "OutputType": "Float16",
                "Params": {
                    "KernelHeight": 1,
                    "KernelWidth": 1,
                    "KernelType": "Float16",
                    "KernelMode": "Dense",
                    "KernelOffset": 0,
                    "Step": [1, 1],
                    "Type": "Conv",
                },
                "Type": "Conv",
            },
            "projection@output": {
                "Bottom": "projection",
                "OutputInterleave": 1,
                "OutputPlaneStride": 64,
                "OutputRowStride": 64,
                "OutputType": "Float16",
            },
        },
    }


def source_name(tensor_name, row_start, row_end, row_count):
    stem = tensor_name.replace(".", "-")
    if row_start == 0 and row_end == row_count:
        return stem
    return f"{stem}-rows-{row_start:06d}-{row_end:06d}"


def write_sources(weights, model_path, output, layer_count=24, head_chunk_rows=8192):
    output.mkdir(parents=True, exist_ok=True)
    records = {tensor.name: tensor for tensor in weights.reader.tensors}
    entries = []
    for tensor_name in projection_names(records, layer_count):
        tensor = records[tensor_name]
        if len(tensor.shape) != 2:
            raise ValueError(f"{tensor_name} is not a matrix")
        input_channels = int(tensor.shape[0])
        row_count = int(tensor.shape[1])
        chunk_rows = head_chunk_rows if tensor_name == TIED_HEAD else row_count
        for row_start in range(0, row_count, chunk_rows):
            row_end = min(row_start + chunk_rows, row_count)
            matrix = weights.dequantize(
                tensor.data[row_start:row_end], tensor.tensor_type
            ).astype("float16", copy=False)
            expected_shape = (row_end - row_start, input_channels)
            if matrix.shape != expected_shape:
                raise ValueError(
                    f"{tensor_name} rows have shape {matrix.shape}, expected {expected_shape}"
                )
            relative = Path("projections") / source_name(
                tensor_name, row_start, row_end, row_count
            )
            directory = output / relative
            directory.mkdir(parents=True, exist_ok=True)
            weights_path = directory / "model.espresso.weights"
            matrix.tofile(weights_path)
            with (directory / "net.plist").open("wb") as handle:
                plistlib.dump(
                    espresso_network(input_channels, row_end - row_start), handle
                )
            entries.append(
                {
                    "tensor": tensor_name,
                    "row_range": [row_start, row_end],
                    "shape": [row_end - row_start, input_channels],
                    "source": relative.as_posix(),
                    "weights_bytes": weights_path.stat().st_size,
                    "weights_sha256": sha256_file(weights_path),
                    "plist_sha256": sha256_file(directory / "net.plist"),
                }
            )
    model_path = Path(model_path)
    manifest = {
        "format": "qwen-espresso-projections-v1",
        "model_bytes": model_path.stat().st_size,
        "model_sha256": sha256_file(model_path),
        "layer_count": layer_count,
        "head_chunk_rows": head_chunk_rows,
        "projection_count": len(entries),
        "projections": entries,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def load_weights_module():
    path = Path(__file__).parent.parent / "ane-weights.py"
    spec = importlib.util.spec_from_file_location("ane_weights", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--gguf-py")
    parser.add_argument("--head-chunk-rows", type=int, default=8192)
    args = parser.parse_args()
    if args.head_chunk_rows < 1:
        parser.error("--head-chunk-rows must be positive")
    weights = load_weights_module().GGUFWeights(args.model, args.gguf_py)
    manifest = write_sources(
        weights, args.model, args.output, head_chunk_rows=args.head_chunk_rows
    )
    print(json.dumps({
        "manifest": str(args.output / "manifest.json"),
        "projection_count": manifest["projection_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
