#!/usr/bin/env python3
"""Run the fixed Qwen corpus as resumable one-prompt processes."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_inputs(contract_path, model_path, corpus_path):
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    model = contract["model"]
    if model_path.stat().st_size != model["bytes"]:
        raise ValueError("model size does not match contract")
    if sha256_file(model_path) != model["sha256"]:
        raise ValueError("model SHA-256 does not match contract")
    if sha256_file(corpus_path) != contract["corpus"]["sha256"]:
        raise ValueError("corpus SHA-256 does not match contract")
    rows = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != contract["corpus"]["prompts"]:
        raise ValueError("prompt count does not match contract")
    return contract, rows


def prompt_paths(output_dir, index):
    stem = f"prompt_{index:03d}"
    return output_dir / f"{stem}.json", output_dir / f"{stem}.npz"


def load_completed_prompt(output_dir, index, row, new_tokens):
    result_path, logits_path = prompt_paths(output_dir, index)
    if not result_path.is_file() or not logits_path.is_file():
        return None
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        prompt = result["prompts"][0]
        run = prompt["runs"][0]
        if prompt["id"] != row["id"] or len(run["generated_ids"]) != new_tokens:
            return None
        with np.load(logits_path, allow_pickle=False) as archive:
            logits = archive["run_000"]
            if logits.ndim != 2 or logits.shape[0] != new_tokens:
                return None
            if not np.isfinite(logits).all():
                return None
    except (KeyError, OSError, ValueError, json.JSONDecodeError):
        return None
    return result


def write_summary(output_dir, completed):
    if not completed:
        raise ValueError("no completed prompts")
    first = completed[0]
    result = {
        "model_bytes": first["model_bytes"],
        "model_sha256": first["model_sha256"],
        "max_new_tokens": first["max_new_tokens"],
        "n_layers": first["n_layers"],
        "prompts": [item["prompts"][0] for item in completed],
    }
    path = output_dir / "result.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + chr(10), encoding="utf-8")
    temporary.replace(path)
    return path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--prompt-corpus", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--runner", type=Path, default=ROOT / "ane-qwen-model.py")
    parser.add_argument("--backend", choices=("ane", "cpu"), default="ane")
    parser.add_argument("--recurrent-anec", type=Path)
    parser.add_argument("--gguf-py")
    parser.add_argument("--qid", type=int)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.backend == "ane" and args.recurrent_anec is None:
        raise SystemExit("--backend ane requires --recurrent-anec")
    contract, rows = load_inputs(args.contract, args.model, args.prompt_corpus)
    new_tokens = contract["generation"]["new_tokens"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    completed = []
    for index, row in enumerate(rows):
        result = load_completed_prompt(args.output_dir, index, row, new_tokens)
        if result is None:
            result_path, logits_path = prompt_paths(args.output_dir, index)
            command = [
                sys.executable,
                str(args.runner),
                "--model",
                str(args.model),
                "--prompt",
                row["text"],
                "--prompt-id",
                row["id"],
                "--category",
                row["category"],
                "--backend",
                args.backend,
                "--generate",
                str(new_tokens),
                "--result-output",
                str(result_path),
                "--logits-output",
                str(logits_path),
            ]
            if args.recurrent_anec is not None:
                command.extend(("--recurrent-anec", str(args.recurrent_anec)))
            if args.gguf_py is not None:
                command.extend(("--gguf-py", args.gguf_py))
            if args.qid is not None:
                command.extend(("--qid", str(args.qid)))
            subprocess.run(command, check=True)
            result = load_completed_prompt(args.output_dir, index, row, new_tokens)
            if result is None:
                raise RuntimeError(f"prompt {row['id']} produced invalid artifacts")
        completed.append(result)
        write_summary(args.output_dir, completed)
        print(f"QWEN_CORPUS_PROMPT_OK {index + 1}/{len(rows)} {row['id']}", flush=True)
    print(f"QWEN_CORPUS_OK prompts={len(completed)}")


if __name__ == "__main__":
    main()
