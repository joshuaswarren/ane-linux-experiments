#!/usr/bin/env python3
"""Run deterministic Qwen3.8-2B decode through ANEForge on macOS."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_PROMPT = "The engine runs"


def sha256_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def validate_contract(
    contract_path: Path,
    *,
    model_size: int,
    model_sha256: str,
    n_layers: int,
    max_new_tokens: int,
    prompt_corpus: Path | None,
) -> None:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    model = contract["model"]
    if model_size != model["bytes"]:
        raise ValueError(f"model size does not match contract: {model_size} != {model['bytes']}")
    if model_sha256 != model["sha256"]:
        raise ValueError("model SHA-256 does not match contract")
    if n_layers != model["layers"]:
        raise ValueError(f"layer count does not match contract: {n_layers} != {model['layers']}")
    if max_new_tokens != contract["generation"]["new_tokens"]:
        raise ValueError(
            "max-new-tokens does not match contract: "
            f"{max_new_tokens} != {contract['generation']['new_tokens']}"
        )
    if prompt_corpus is None:
        raise ValueError("contract validation requires --prompt-corpus")
    _, corpus_sha256 = sha256_file(prompt_corpus)
    if corpus_sha256 != contract["corpus"]["sha256"]:
        raise ValueError("prompt corpus SHA-256 does not match contract")
    rows = load_prompt_corpus(prompt_corpus)
    if len(rows) != contract["corpus"]["prompts"]:
        raise ValueError("prompt count does not match contract")
    if len({row["category"] for row in rows}) != contract["corpus"]["categories"]:
        raise ValueError("prompt category count does not match contract")

def tokenize(binary: str, model: Path, prompt: str) -> list[int]:
    result = subprocess.run(
        [binary, "-m", str(model), "-p", prompt, "--ids"],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"(?m)^\[[-, 0-9]+\]$", result.stdout)
    if match is None:
        raise RuntimeError(f"tokenizer returned no ID list: {result.stdout!r}")
    ids = ast.literal_eval(match.group(0))
    if not isinstance(ids, list) or not all(isinstance(token, int) for token in ids):
        raise RuntimeError("tokenizer returned an invalid ID list")
    return ids


def load_prompt_corpus(path: Path) -> list[dict[str, str]]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            row = json.loads(line)
            if not all(
                isinstance(row.get(key), str) and row[key]
                for key in ("id", "category", "text")
            ):
                raise ValueError(
                    f"{path}:{line_number}: expected non-empty id, category, and text"
                )
            rows.append({"id": row["id"], "category": row["category"], "text": row["text"]})
    if not rows:
        raise ValueError(f"{path}: prompt corpus is empty")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError(f"{path}: prompt IDs are not unique")
    return rows


def configure_checkpoint_chunks(model: Any, layers_per_chunk: int) -> None:
    if layers_per_chunk < 1:
        raise ValueError("layers-per-chunk must be positive")
    first_layer = model.w["layers"][0]
    bytes_per_layer = sum(
        int(np.asarray(value).size) * 2
        for value in first_layer.values()
        if isinstance(value, (np.ndarray, list, tuple))
    )
    model._chunk_bytes = bytes_per_layer * layers_per_chunk


def instrument_decoder(model: Any, state: dict[str, Any]) -> None:
    state["chunk_layers"] = [list(group) for group in model._layer_chunks()]
    for chunk_index, chunk in enumerate(model._dec["chunks"]):
        program = chunk["net"].prog
        params = chunk["p"]
        original_execute = program.execute
        original_read_output = program.read_output
        state["counts"].append(0)
        state["seconds"].append(0.0)

        def execute(original=original_execute, index=chunk_index) -> None:
            started = time.perf_counter()
            try:
                original()
            finally:
                state["counts"][index] += 1
                state["seconds"][index] += time.perf_counter() - started
                if state["step_is_generated"]:
                    state["decode_calls"] += 1

        def read_output(name, original=original_read_output, index=chunk_index, p=params):
            value = original(name)
            if state["capture"] and name == p["h"]:
                state["checkpoints"].append(
                    {
                        "chunk": index,
                        "step": state["counts"][index] - 1,
                        "values": np.asarray(value, dtype=np.float32).copy(),
                    }
                )
            return value

        program.execute = execute
        program.read_output = read_output


def run_once(
    model: Any,
    token_ids: list[int],
    max_new_tokens: int,
    trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logits: list[np.ndarray] = []
    stages: list[dict[str, Any]] = []
    original = model._decode_logits
    started = time.perf_counter()
    first_decode_stage_at: float | None = None
    first_token_at: float | None = None
    prefill_tokens = max(0, len(token_ids) - 1)
    if trace is not None:
        trace["decode_started"] = False
        trace["step_is_generated"] = False
        trace["model_step"] = 0
        trace["decode_calls"] = 0
        trace["capture"] = bool(trace.pop("capture_next", False))
        trace["checkpoints"] = []
        trace["counts"] = [0] * len(trace.get("chunk_layers", ()))
        trace["seconds"] = [0.0] * len(trace.get("chunk_layers", ()))

    def capture(hidden: np.ndarray, ane: bool | None, greedy: bool) -> np.ndarray:
        output = np.asarray(original(hidden, ane, greedy), dtype=np.float32).copy()
        logits.append(output)
        return output

    def on_stage(name: str, elapsed: float) -> None:
        nonlocal first_decode_stage_at, first_token_at
        now = time.perf_counter()
        if name == "embedding" and trace is not None:
            trace["model_step"] += 1
            trace["step_is_generated"] = trace["model_step"] > prefill_tokens
            if trace["step_is_generated"] and first_decode_stage_at is None:
                first_decode_stage_at = now
                trace["decode_started"] = True
        if name == "sample" and first_token_at is None:
            first_token_at = now
        stages.append({"name": name, "seconds": elapsed})

    model._decode_logits = capture
    try:
        generated = model.generate(
            token_ids,
            max_new_tokens=max_new_tokens,
            temperature=0.0,
            top_p=1.0,
            top_k=0,
            batched_prefill=False,
            on_stage=on_stage,
        )
    finally:
        model._decode_logits = original
    elapsed = time.perf_counter() - started
    stage_totals = {
        name: sum(event["seconds"] for event in stages if event["name"] == name)
        for name in {event["name"] for event in stages}
    }
    prefill_seconds = max(
        0.0, (first_decode_stage_at or time.perf_counter()) - started
    )
    decode_seconds = stage_totals.get("step", 0.0)
    if trace is not None:
        trace["capture"] = False
    return {
        "generated_ids": [int(token) for token in generated],
        "elapsed_seconds": elapsed,
        "stages": stages,
        "stage_totals": stage_totals,
        "prefill_tokens": prefill_tokens,
        "prefill_seconds": prefill_seconds,
        "prefill_tokens_per_second": (
            prefill_tokens / prefill_seconds if prefill_seconds else None
        ),
        "decode_seconds": decode_seconds,
        "decode_tokens_per_second": (
            len(generated) / decode_seconds if decode_seconds else None
        ),
        "time_to_first_token_seconds": (
            first_token_at - started if first_token_at is not None else None
        ),
        "ane_decoder_submissions": trace["decode_calls"] if trace is not None else None,
        "ane_submissions_per_generated_token": (
            trace["decode_calls"] / len(generated)
            if trace is not None and generated
            else None
        ),
        "logits": logits,
        "logits_shape": list(logits[0].shape) if logits else [0],
        "logits_finite": bool(all(np.isfinite(value).all() for value in logits)),
    }


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    captured = np.asarray([run["logits"] for run in runs], dtype=np.float32)
    return {
        "runs": [
            {key: value for key, value in run.items() if key != "logits"}
            for run in runs
        ],
        "token_sequences_match": len({tuple(run["generated_ids"]) for run in runs}) == 1,
        "logits_repeatability_max_abs": (
            float(np.max(np.abs(captured[1:] - captured[:1]))) if len(captured) > 1 else 0.0
        ),
        "logits_repeatability_mean_abs": (
            float(np.mean(np.abs(captured[1:] - captured[:1]))) if len(captured) > 1 else 0.0
        ),
        "logits_repeatability_relative_l2": (
            float(
                np.max(
                    np.linalg.norm(captured[1:] - captured[:1], axis=-1)
                    / np.maximum(np.linalg.norm(captured[:1], axis=-1), 1e-12)
                )
            )
            if len(captured) > 1
            else 0.0
        ),
    }


def save_checkpoints(path: Path, trace: dict[str, Any]) -> None:
    records = trace["checkpoints"]
    if not records:
        raise RuntimeError("decoder produced no layer checkpoints")
    arrays = {
        f"chunk_{record['chunk']:03d}_step_{record['step']:03d}": record["values"]
        for record in records
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)

def save_logits(
    path: Path, logits_by_prompt: list[list[list[np.ndarray]]]
) -> None:
    """Save variable-length per-step logits with prompt and run boundaries."""
    if not logits_by_prompt:
        raise RuntimeError("reference run produced no logits")
    arrays = {}
    for prompt_index, runs in enumerate(logits_by_prompt):
        if not runs:
            raise RuntimeError(f"prompt {prompt_index} produced no logits runs")
        for run_index, logits in enumerate(runs):
            array = np.asarray(logits, dtype=np.float32)
            if array.ndim != 2 or array.shape[0] == 0:
                raise RuntimeError("reference run produced an empty or invalid logits trace")
            arrays[f"prompt_{prompt_index:03d}_run_{run_index:03d}"] = array
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        np.savez_compressed(stream, **arrays)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--contract", type=Path, default=None)
    prompt = parser.add_mutually_exclusive_group()
    prompt.add_argument("--prompt", default=DEFAULT_PROMPT)
    prompt.add_argument("--prompt-corpus", type=Path)
    parser.add_argument(
        "--tokenizer", default=os.environ.get("LLAMA_TOKENIZE", "llama-tokenize")
    )
    parser.add_argument(
        "--aneforge-root",
        type=Path,
        default=Path(os.environ.get("ANEFORGE_ROOT", "~/src/ANEForge")).expanduser(),
    )
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--max-len", type=int, default=None)
    parser.add_argument("--resid-scale", type=float, default=1.0)
    parser.add_argument("--n-layers", type=int, default=24)
    parser.add_argument("--chunk-layers", type=int, default=None)
    parser.add_argument("--checkpoints-output", type=Path, default=None)
    parser.add_argument("--logits-output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_new_tokens < 1 or args.warmup < 0 or args.repetitions < 1 or args.n_layers < 1:
        raise SystemExit(
            "max-new-tokens, repetitions, and n-layers must be positive; warmup cannot be negative"
        )
    if args.chunk_layers is not None and args.chunk_layers < 1:
        raise SystemExit("chunk-layers must be positive")
    size, model_sha256 = sha256_file(args.model)
    if args.contract is not None:
        validate_contract(
            args.contract,
            model_size=size,
            model_sha256=model_sha256,
            n_layers=args.n_layers,
            max_new_tokens=args.max_new_tokens,
            prompt_corpus=args.prompt_corpus,
        )
    sys.path.insert(0, str(args.aneforge_root))
    import aneforge.qwen35 as qwen35

    corpus = (
        load_prompt_corpus(args.prompt_corpus)
        if args.prompt_corpus is not None
        else [{"id": "single", "category": "single", "text": args.prompt}]
    )
    tokenized = [tokenize(args.tokenizer, args.model, row["text"]) for row in corpus]
    max_len = args.max_len or max(
        len(ids) + args.max_new_tokens for ids in tokenized
    )
    model = qwen35.load_gguf(
        args.model, n_layers=args.n_layers, resid_scale=args.resid_scale
    )
    model.ane_lm_head = False
    if args.chunk_layers is not None:
        configure_checkpoint_chunks(model, args.chunk_layers)
    try:
        compile_started = time.perf_counter()
        model.warmup(max_len)
        compile_seconds = time.perf_counter() - compile_started
        trace = {
            "capture_next": False,
            "chunk_layers": [],
            "checkpoints": [],
            "counts": [],
            "seconds": [],
            "decode_started": False,
            "decode_calls": 0,
        }
        instrument_decoder(model, trace)
        for _ in range(args.warmup):
            run_once(model, tokenized[0], args.max_new_tokens, trace)
        prompt_results = []
        all_logits = []
        for row, token_ids in zip(corpus, tokenized):
            runs = []
            prompt_logits = []
            for _ in range(args.repetitions):
                trace["capture_next"] = (
                    args.checkpoints_output is not None and not all_logits
                )
                run = run_once(model, token_ids, args.max_new_tokens, trace)
                if args.checkpoints_output is not None and trace["checkpoints"]:
                    save_checkpoints(args.checkpoints_output, trace)
                    args.checkpoints_output = None
                prompt_logits.append(run["logits"])
                runs.append(run)
            all_logits.append(prompt_logits)
            prompt_summary = summarize_runs(runs)
            prompt_summary.update(
                {
                    "id": row["id"],
                    "category": row["category"],
                    "prompt": row["text"],
                    "prompt_token_ids": token_ids,
                }
            )
            prompt_results.append(prompt_summary)
    finally:
        model.release()

    result = {
        "model_bytes": size,
        "model_sha256": model_sha256,
        "max_new_tokens": args.max_new_tokens,
        "max_len": max_len,
        "warmup": args.warmup,
        "repetitions": args.repetitions,
        "resid_scale": args.resid_scale,
        "n_layers": args.n_layers,
        "compile_seconds": compile_seconds,
        "prompt_count": len(prompt_results),
        "prompts": prompt_results,
        "decoder_chunk_layers": trace["chunk_layers"],
    }
    if args.logits_output is not None:
        save_logits(args.logits_output, all_logits)
        result["logits_output"] = str(args.logits_output)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
