#!/usr/bin/env python3
"""Build the fixed, public prompt corpus used by ANE comparisons."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


TOPICS = (
    ("science", "why seasons change on Earth"),
    ("history", "how a public library changed its neighborhood"),
    ("software", "how a process should handle a temporary network failure"),
    ("math", "why prime numbers matter in computer science"),
    ("writing", "how to make a technical paragraph easier to scan"),
    ("civics", "how local governments can reduce traffic noise"),
    ("nature", "how wetlands protect towns from heavy rain"),
    ("design", "how a team can test whether a button label is clear"),
    ("economics", "why a price can change when supply changes"),
    ("daily-life", "how to plan a reliable morning routine"),
)

VARIANTS = (
    "Answer in one clear sentence: {subject}.",
    "Explain {subject} to a student who is new to the topic.",
    "Give three key facts about {subject}.",
    "List the main causes and effects of {subject}.",
    "Compare two common views about {subject}.",
    "Describe a simple example that demonstrates {subject}.",
    "Write a short checklist for learning about {subject}.",
    "State one common mistake about {subject} and correct it.",
    "Explain {subject} with a concrete example and one limitation.",
    "Give a careful answer about {subject}, using plain language and ordered steps.",
)


def build_records() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    number = 1
    for category, subject in TOPICS:
        for variant in VARIANTS:
            records.append(
                {
                    "id": f"p{number:03d}",
                    "category": category,
                    "text": variant.format(subject=subject),
                }
            )
            number += 1
    return records


def validate(records: list[dict[str, str]]) -> None:
    if len(records) != 100:
        raise ValueError(f"expected 100 prompts, got {len(records)}")
    ids = [record["id"] for record in records]
    texts = [record["text"] for record in records]
    if len(set(ids)) != len(ids) or len(set(texts)) != len(texts):
        raise ValueError("prompt IDs and texts must be unique")
    lengths = [len(text) for text in texts]
    if min(lengths) >= max(lengths):
        raise ValueError("prompt lengths must vary")
    if len({record["category"] for record in records}) != 10:
        raise ValueError("expected ten prompt categories")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    records = build_records()
    validate(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    lengths = [len(record["text"]) for record in records]
    print(
        f"corpus={args.output} prompts={len(records)} categories=10 "
        f"chars_min={min(lengths)} chars_max={max(lengths)}"
    )


if __name__ == "__main__":
    main()
