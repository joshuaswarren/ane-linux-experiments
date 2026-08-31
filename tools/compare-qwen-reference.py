#!/usr/bin/env python3
"""Compare deterministic Qwen reference outputs and layer checkpoints."""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def _top_k(values: np.ndarray, k: int) -> np.ndarray:
    return np.argpartition(-values, kth=k - 1, axis=1)[:, :k]


def compare_logits(
    reference: np.ndarray,
    candidate: np.ndarray,
    generated_start: int,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    reference = np.asarray(reference, dtype=np.float32)
    candidate = np.asarray(candidate, dtype=np.float32)
    if reference.ndim != 2 or candidate.ndim != 2:
        raise ValueError("logits must be rank-2 [steps, vocabulary]")
    if reference.shape != candidate.shape:
        raise ValueError(f"logit shapes differ: {reference.shape} != {candidate.shape}")
    if not 0 <= generated_start < reference.shape[0]:
        raise ValueError("generated logits start is outside the trace")
    if not np.isfinite(reference).all() or not np.isfinite(candidate).all():
        raise ValueError("logits contain non-finite values")

    reference = reference[generated_start:]
    candidate = candidate[generated_start:]
    difference = np.abs(reference - candidate)
    top1_match = np.argmax(reference, axis=1) == np.argmax(candidate, axis=1)
    top_k = min(10, reference.shape[1])
    reference_top = _top_k(reference, top_k)
    candidate_top = _top_k(candidate, top_k)
    top10_overlap = np.mean(
        np.sum(np.isin(reference_top, candidate_top), axis=1) / top_k
    )
    relative_l2 = np.linalg.norm(reference - candidate, axis=1) / np.maximum(
        np.linalg.norm(reference, axis=1), 1e-12
    )
    report = {
        "generated_steps": int(reference.shape[0]),
        "top1_token_match": float(np.mean(top1_match)),
        "top10_overlap": float(top10_overlap),
        "max_absolute_logit_error": float(np.max(difference)),
        "mean_absolute_logit_error": float(np.mean(difference)),
        "relative_l2_error": float(np.max(relative_l2)),
    }
    report["passed"] = all(
        (
            report["top1_token_match"] == 1.0,
            report["top10_overlap"] >= thresholds["top10_overlap"],
            report["max_absolute_logit_error"]
            <= thresholds["max_absolute_logit_error"],
            report["mean_absolute_logit_error"]
            <= thresholds["mean_absolute_logit_error"],
            report["relative_l2_error"] <= thresholds["relative_l2_error"],
        )
    )
    return report


def compare_checkpoints(
    reference_path: Path,
    candidate_path: Path,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    with np.load(reference_path, allow_pickle=False) as reference, np.load(
        candidate_path, allow_pickle=False
    ) as candidate:
        reference_names = sorted(reference.files)
        candidate_names = sorted(candidate.files)
        common = sorted(set(reference_names) & set(candidate_names))
        report: dict[str, Any] = {
            "missing_in_candidate": sorted(set(reference_names) - set(candidate_names)),
            "unexpected_in_candidate": sorted(set(candidate_names) - set(reference_names)),
            "layers": {},
        }
        for name in common:
            left = np.asarray(reference[name], dtype=np.float32)
            right = np.asarray(candidate[name], dtype=np.float32)
            if left.shape != right.shape:
                report["layers"][name] = {
                    "passed": False,
                    "error": f"shapes differ: {left.shape} != {right.shape}",
                }
                continue
            if not np.isfinite(left).all() or not np.isfinite(right).all():
                report["layers"][name] = {
                    "passed": False,
                    "error": "checkpoint contains non-finite values",
                }
                continue
            difference = np.abs(left - right)
            relative_l2 = float(
                np.linalg.norm(left - right)
                / max(float(np.linalg.norm(left)), 1e-12)
            )
            layer = {
                "max_absolute_error": float(np.max(difference)),
                "mean_absolute_error": float(np.mean(difference)),
                "relative_l2_error": relative_l2,
            }
            layer["passed"] = thresholds is None or all(
                (
                    layer["max_absolute_error"]
                    <= thresholds["max_absolute_logit_error"],
                    layer["mean_absolute_error"]
                    <= thresholds["mean_absolute_logit_error"],
                    layer["relative_l2_error"] <= thresholds["relative_l2_error"],
                )
            )
            report["layers"][name] = layer
        report["passed"] = not report["missing_in_candidate"] and not report[
            "unexpected_in_candidate"
        ] and all(layer.get("passed", False) for layer in report["layers"].values())
        return report


def prompt_generated_ids(row: dict[str, Any]) -> list[int]:
    if "generated_ids" in row:
        return [int(token) for token in row["generated_ids"]]
    runs = row.get("runs", [])
    if not runs:
        return []
    sequences = [[int(token) for token in run.get("generated_ids", [])] for run in runs]
    if any(sequence != sequences[0] for sequence in sequences[1:]):
        raise ValueError(f"prompt {row.get('id', '<unknown>')} has divergent token runs")
    return sequences[0]


def generated_logits(
    logits: np.ndarray, *, prompt_tokens: int, new_tokens: int
) -> np.ndarray:
    logits = np.asarray(logits, dtype=np.float32)
    if logits.ndim != 2:
        raise ValueError("logits must be rank-2 [steps, vocabulary]")
    if logits.shape[0] == new_tokens:
        return logits
    prefill_steps = max(0, prompt_tokens - 1)
    if logits.shape[0] == prefill_steps + new_tokens:
        return logits[prefill_steps:]
    raise ValueError(
        f"logit trace has {logits.shape[0]} steps; expected {new_tokens} generated "
        f"or {prefill_steps + new_tokens} prefill-plus-generated steps"
    )


def compare_token_sequences(
    reference: dict[str, Any], candidate: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    expected_model = contract["model"]
    expected_generation = contract["generation"]
    errors = []
    for name in ("model_bytes", "model_sha256", "max_new_tokens", "n_layers"):
        expected = {
            "model_bytes": expected_model["bytes"],
            "model_sha256": expected_model["sha256"],
            "max_new_tokens": expected_generation["new_tokens"],
            "n_layers": expected_model["layers"],
        }[name]
        if reference.get(name) != expected:
            errors.append(f"reference {name} does not match contract")
        if candidate.get(name) != expected:
            errors.append(f"candidate {name} does not match contract")

    reference_prompts = {row["id"]: row for row in reference.get("prompts", [])}
    candidate_prompts = {row["id"]: row for row in candidate.get("prompts", [])}
    missing = sorted(set(reference_prompts) - set(candidate_prompts))
    unexpected = sorted(set(candidate_prompts) - set(reference_prompts))
    mismatches = []
    for prompt_id in sorted(set(reference_prompts) & set(candidate_prompts)):
        expected_ids = prompt_generated_ids(reference_prompts[prompt_id])
        actual_ids = prompt_generated_ids(candidate_prompts[prompt_id])
        if expected_ids != actual_ids:
            mismatches.append(
                {
                    "id": prompt_id,
                    "reference": expected_ids,
                    "candidate": actual_ids,
                }
            )
    report = {
        "missing": missing,
        "unexpected": unexpected,
        "mismatches": mismatches,
        "metadata_errors": errors,
        "matched_prompts": len(reference_prompts) - len(missing),
    }
    report["passed"] = not missing and not unexpected and not mismatches and not errors
    return report


def _archive_run_keys(archive: Any, prompt_index: int) -> list[str]:
    prompt_name = f"prompt_{prompt_index:03d}"
    repeated_prefix = f"{prompt_name}_run_"
    repeated = []
    for name in archive.files:
        if not name.startswith(repeated_prefix):
            continue
        suffix = name[len(repeated_prefix) :]
        if suffix.isdigit():
            repeated.append((int(suffix), name))
    if repeated:
        repeated.sort()
        indices = [index for index, _ in repeated]
        if indices != list(range(len(indices))):
            raise ValueError(f"run archive has non-contiguous keys for {prompt_name}")
        return [name for _, name in repeated]
    return [prompt_name] if prompt_name in archive else []

def load_prompt_runs(path: Path, prompt_index: int) -> list[np.ndarray]:
    archive_path = path / f"prompt_{prompt_index:03d}.npz" if path.is_dir() else path
    with np.load(archive_path, allow_pickle=False) as archive:
        if path.is_dir():
            repeated = []
            for name in archive.files:
                if name.startswith("run_") and name[4:].isdigit():
                    repeated.append((int(name[4:]), name))
            repeated.sort()
            if [index for index, _ in repeated] != list(range(len(repeated))):
                raise ValueError(f"run shard has non-contiguous keys: {archive_path}")
            keys = [name for _, name in repeated]
        else:
            keys = _archive_run_keys(archive, prompt_index)
        return [np.asarray(archive[key], dtype=np.float32).copy() for key in keys]


def compare_run_files(
    reference_json: Path,
    candidate_json: Path,
    reference_logits: Path,
    candidate_logits: Path,
    contract_path: Path,
    reference_checkpoints: Path | None = None,
    candidate_checkpoints: Path | None = None,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    reference = json.loads(reference_json.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_json.read_text(encoding="utf-8"))
    token_report = compare_token_sequences(reference, candidate, contract)
    thresholds = contract["numeric_thresholds"]
    logit_report: dict[str, Any] = {"prompts": {}, "passed": True}
    reference_rows = reference["prompts"]
    reference_prompts = {row["id"]: row for row in reference_rows}
    candidate_indices = {
        row["id"]: index for index, row in enumerate(candidate.get("prompts", []))
    }
    for index, row in enumerate(reference_rows):
        prompt_id = row["id"]
        reference_runs = load_prompt_runs(reference_logits, index)
        if prompt_id not in candidate_indices:
            logit_report["prompts"][prompt_id] = {
                "passed": False,
                "error": f"candidate is missing prompt {prompt_id}",
            }
            logit_report["passed"] = False
            continue
        candidate_index = candidate_indices[prompt_id]
        candidate_runs = load_prompt_runs(candidate_logits, candidate_index)
        if not reference_runs or not candidate_runs:
            logit_report["prompts"][prompt_id] = {
                "passed": False,
                "error": (
                    f"missing logits arrays reference={len(reference_runs)} "
                    f"candidate={len(candidate_runs)}"
                ),
            }
            logit_report["passed"] = False
            continue
        if len(reference_runs) != len(candidate_runs):
            logit_report["prompts"][prompt_id] = {
                "passed": False,
                "error": (
                    f"run counts differ reference={len(reference_runs)} "
                    f"candidate={len(candidate_runs)}"
                ),
            }
            logit_report["passed"] = False
            continue
        prompt_tokens = len(reference_prompts[prompt_id]["prompt_token_ids"])
        new_tokens = contract["generation"]["new_tokens"]
        runs = []
        for run_index, (reference_values, candidate_values) in enumerate(
            zip(reference_runs, candidate_runs)
        ):
            reference_values = generated_logits(
                reference_values,
                prompt_tokens=prompt_tokens,
                new_tokens=new_tokens,
            )
            candidate_values = generated_logits(
                candidate_values,
                prompt_tokens=prompt_tokens,
                new_tokens=new_tokens,
            )
            run_report = compare_logits(
                reference_values,
                candidate_values,
                0,
                thresholds,
            )
            run_report["run_index"] = run_index
            runs.append(run_report)
        prompt_report = {
            "runs": runs,
            "passed": all(run["passed"] for run in runs),
        }
        logit_report["prompts"][prompt_id] = prompt_report
        logit_report["passed"] &= prompt_report["passed"]

    checkpoint_report = None
    if reference_checkpoints is not None or candidate_checkpoints is not None:
        if reference_checkpoints is None or candidate_checkpoints is None:
            checkpoint_report = {"passed": False, "error": "checkpoint path pair is incomplete"}
        else:
            checkpoint_report = compare_checkpoints(
                reference_checkpoints, candidate_checkpoints, thresholds
            )
    result: dict[str, Any] = {"token_parity": token_report, "logit_parity": logit_report}
    if checkpoint_report is not None:
        result["layer_parity"] = checkpoint_report
    result["passed"] = token_report["passed"] and logit_report["passed"] and (
        checkpoint_report is None or checkpoint_report["passed"]
    )
    return result



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--reference-json", required=True, type=Path)
    parser.add_argument("--candidate-json", required=True, type=Path)
    parser.add_argument("--reference-logits", required=True, type=Path)
    parser.add_argument("--candidate-logits", required=True, type=Path)
    parser.add_argument("--reference-checkpoints", type=Path)
    parser.add_argument("--candidate-checkpoints", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare_run_files(
        args.reference_json,
        args.candidate_json,
        args.reference_logits,
        args.candidate_logits,
        args.contract,
        args.reference_checkpoints,
        args.candidate_checkpoints,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
