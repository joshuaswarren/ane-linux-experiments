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


def run_once(model: Any, token_ids: list[int], max_new_tokens: int) -> dict[str, Any]:
    logits: list[np.ndarray] = []
    stages: list[tuple[str, float]] = []
    original = model._decode_logits

    def capture(hidden: np.ndarray, ane: bool | None, greedy: bool) -> np.ndarray:
        output = np.asarray(original(hidden, ane, greedy), dtype=np.float32).copy()
        logits.append(output)
        return output

    model._decode_logits = capture
    started = time.perf_counter()
    try:
        generated = model.generate(
            token_ids,
            max_new_tokens=max_new_tokens,
            temperature=0.0,
            top_p=1.0,
            top_k=0,
            batched_prefill=False,
            on_stage=lambda name, elapsed: stages.append((name, elapsed)),
        )
    finally:
        model._decode_logits = original
    elapsed = time.perf_counter() - started
    return {
        "generated_ids": [int(token) for token in generated],
        "logits": logits,
        "elapsed_seconds": elapsed,
        "stages": [{"name": name, "seconds": seconds} for name, seconds in stages],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--tokenizer", default=os.environ.get("LLAMA_TOKENIZE", "llama-tokenize"))
    parser.add_argument("--aneforge-root", type=Path, default=Path(os.environ.get("ANEFORGE_ROOT", "~/src/ANEForge")).expanduser())
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--max-len", type=int, default=None)
    parser.add_argument("--resid-scale", type=float, default=1.0)
    parser.add_argument("--n-layers", type=int, default=24)
    parser.add_argument("--logits-output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_new_tokens < 1 or args.warmup < 0 or args.repetitions < 1 or args.n_layers < 1:
        raise SystemExit("max-new-tokens, repetitions, and n-layers must be positive; warmup cannot be negative")
    size, model_sha256 = sha256_file(args.model)
    sys.path.insert(0, str(args.aneforge_root))
    import aneforge.qwen35 as qwen35

    token_ids = tokenize(args.tokenizer, args.model, args.prompt)
    max_len = args.max_len or len(token_ids) + args.max_new_tokens
    model = qwen35.load_gguf(args.model, n_layers=args.n_layers, resid_scale=args.resid_scale)
    model.ane_lm_head = False
    try:
        compile_started = time.perf_counter()
        model.warmup(max_len)
        compile_seconds = time.perf_counter() - compile_started
        for _ in range(args.warmup):
            run_once(model, token_ids, args.max_new_tokens)
        runs = [run_once(model, token_ids, args.max_new_tokens) for _ in range(args.repetitions)]
    finally:
        model.release()

    captured = np.asarray([run.pop("logits") for run in runs], dtype=np.float32)
    result = {
        "model_bytes": size,
        "model_sha256": model_sha256,
        "prompt": args.prompt,
        "prompt_token_ids": token_ids,
        "max_new_tokens": args.max_new_tokens,
        "max_len": max_len,
        "warmup": args.warmup,
        "repetitions": args.repetitions,
        "resid_scale": args.resid_scale,
        "n_layers": args.n_layers,
        "compile_seconds": compile_seconds,
        "runs": [
            {
                **run,
                "logits_shape": list(captured[index].shape),
                "logits_finite": bool(np.isfinite(captured[index]).all()),
            }
            for index, run in enumerate(runs)
        ],
        "token_sequences_match": len({tuple(run["generated_ids"]) for run in runs}) == 1,
        "logits_repeatability_max_abs": float(np.max(np.abs(captured[1:] - captured[:1]))) if len(captured) > 1 else 0.0,
        "logits_repeatability_mean_abs": float(np.mean(np.abs(captured[1:] - captured[:1]))) if len(captured) > 1 else 0.0,
        "logits_repeatability_relative_l2": float(
            np.max(
                np.linalg.norm(captured[1:] - captured[:1], axis=-1)
                / np.maximum(np.linalg.norm(captured[:1], axis=-1), 1e-12)
            )
        )
        if len(captured) > 1
        else 0.0,
    }
    if args.logits_output is not None:
        args.logits_output.parent.mkdir(parents=True, exist_ok=True)
        np.save(args.logits_output, captured)
        result["logits_output"] = str(args.logits_output)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
