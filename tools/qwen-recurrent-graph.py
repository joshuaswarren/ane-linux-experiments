#!/usr/bin/env python3
"""Build the Qwen 3.5 DeltaNet state update for the Monterey ANE compiler."""

import argparse
from pathlib import Path


def recurrent_shape(heads, dimension):
    if heads < 1 or dimension < 2:
        raise ValueError("heads must be positive and dimension must be at least two")
    return heads, dimension + 5, dimension


def add_rows(builder, source, name, start, end, heads, dimension):
    builder.add_slice_static(
        name=f"slice_{name}",
        input_name=source,
        output_name=name,
        begin_ids=[0, start, 0],
        end_ids=[heads, end, dimension],
        strides=[1, 1, 1],
        begin_masks=[False, False, False],
        end_masks=[False, False, False],
        squeeze_masks=[False, False, False],
    )


def add_gate(builder, source, name, column, heads):
    builder.add_slice_static(
        name=f"slice_{name}",
        input_name=source,
        output_name=name,
        begin_ids=[0, 0, column],
        end_ids=[heads, 1, column + 1],
        strides=[1, 1, 1],
        begin_masks=[False, False, False],
        end_masks=[False, False, False],
        squeeze_masks=[False, False, False],
    )


def build(path, heads, dimension):
    from coremltools.models import datatypes
    from coremltools.models.neural_network import NeuralNetworkBuilder
    from coremltools.models.utils import save_spec

    heads, rows, dimension = recurrent_shape(heads, dimension)
    shape = datatypes.Array(heads, rows, dimension)
    builder = NeuralNetworkBuilder(
        [("packed", shape)],
        [("next", shape)],
        disable_rank5_shape_mapping=True,
        use_float_arraytype=True,
    )
    add_rows(builder, "packed", "q", 0, 1, heads, dimension)
    add_rows(builder, "packed", "k", 1, 2, heads, dimension)
    add_rows(builder, "packed", "v", 2, 3, heads, dimension)
    add_rows(builder, "packed", "gates", 3, 4, heads, dimension)
    add_rows(builder, "packed", "state", 4, 4 + dimension, heads, dimension)
    add_gate(builder, "gates", "beta", 0, heads)
    add_gate(builder, "gates", "decay", 1, heads)
    builder.add_multiply_broadcastable("decay_state", ["state", "decay"], "state_decay")
    builder.add_batched_mat_mul("key_state", ["k", "state_decay"], "key_state_product")
    builder.add_subtract_broadcastable("delta_error", ["v", "key_state_product"], "delta_error_out")
    builder.add_multiply_broadcastable("gate_delta", ["delta_error_out", "beta"], "delta")
    builder.add_transpose("transpose_key", [0, 2, 1], "k", "key_transposed")
    builder.add_batched_mat_mul("outer_update", ["key_transposed", "delta"], "outer")
    builder.add_add_broadcastable("update_state", ["state_decay", "outer"], "state_next")
    builder.add_batched_mat_mul("read_state", ["q", "state_next"], "output")
    builder.add_concat_nd(
        "pack_next",
        ["q", "k", "v", "gates", "state_next", "output"],
        "next",
        axis=1,
    )
    builder.spec.specificationVersion = 4
    save_spec(builder.spec, str(path))
    print(
        f"QWEN_RECURRENT_GRAPH_OK heads={heads} dimension={dimension} "
        f"shape={heads}x{rows}x{dimension}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--heads", type=int, default=16)
    parser.add_argument("--dimension", type=int, default=128)
    args = parser.parse_args()
    build(args.output, args.heads, args.dimension)


if __name__ == "__main__":
    main()
