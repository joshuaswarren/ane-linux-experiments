#!/usr/bin/env python3
"""Build a fixed-window Qwen KV cache update for the Monterey ANE compiler."""

import argparse
from pathlib import Path


def cache_shape(heads, context, dimension):
    if heads < 1 or context < 1 or dimension < 1:
        raise ValueError("heads, context, and dimension must be positive")
    return heads, 2 * context + 3, dimension


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


def build(path, heads, context, dimension):
    from coremltools.models import datatypes
    from coremltools.models.neural_network import NeuralNetworkBuilder
    from coremltools.models.utils import save_spec

    heads, rows, dimension = cache_shape(heads, context, dimension)
    shape = datatypes.Array(heads, rows, dimension)
    builder = NeuralNetworkBuilder(
        [("packed", shape)],
        [("next", shape)],
        disable_rank5_shape_mapping=True,
        use_float_arraytype=True,
    )
    add_rows(builder, "packed", "new_key", 0, 1, heads, dimension)
    add_rows(builder, "packed", "new_value", 1, 2, heads, dimension)
    key_start = 2
    value_start = key_start + context
    add_rows(builder, "packed", "old_keys", key_start + 1, value_start, heads, dimension)
    add_rows(builder, "packed", "old_values", value_start + 1, value_start + context, heads, dimension)
    builder.add_concat_nd("append_key", ["old_keys", "new_key"], "next_keys", axis=1)
    builder.add_concat_nd("append_value", ["old_values", "new_value"], "next_values", axis=1)
    builder.add_concat_nd(
        "pack_next",
        ["new_key", "new_value", "next_keys", "next_values", "new_value"],
        "next",
        axis=1,
    )
    builder.spec.specificationVersion = 4
    save_spec(builder.spec, str(path))
    print(
        f"QWEN_KV_STATE_GRAPH_OK heads={heads} context={context} "
        f"dimension={dimension} shape=({heads},{rows},{dimension})"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--heads", type=int, default=8)
    parser.add_argument("--context", type=int, default=128)
    parser.add_argument("--dimension", type=int, default=256)
    args = parser.parse_args()
    build(args.output, args.heads, args.context, args.dimension)


if __name__ == "__main__":
    main()
