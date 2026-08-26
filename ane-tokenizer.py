#!/usr/bin/env python3
"""Tokenize real GGUF prompts through llama.cpp's tokenizer binary.

The tokenizer is deliberately a CPU component. BPE and SentencePiece operate
on UTF-8 text, regex or byte boundaries, and vocabulary lookups. Vulkan has no
standard tokenizer API, and moving those small, branch-heavy steps to the GPU
would add transfer and synchronization cost before ANE inference. The wrapper
keeps the boundary explicit so a GPU tokenizer can replace it later without
changing the runtime's token-ID contract.

  python3 ane-tokenizer.py -m model.gguf -p "The capital of France is"
  python3 ane-tokenizer.py -m model.gguf --stdin --ids
"""
import argparse
import ast
import os
import re
import subprocess
import sys


class Tokenizer:
    """A real GGUF tokenizer backed by llama.cpp."""

    def __init__(self, model, binary=None):
        self.model = os.path.abspath(model)
        self.binary = binary or os.environ.get("LLAMA_TOKENIZE", "llama-tokenize")

    def encode(self, text, add_bos=True, parse_special=True):
        args = [self.binary, "-m", self.model, "-p", text, "--ids"]
        if not add_bos:
            args.append("--no-bos")
        if not parse_special:
            args.append("--no-parse-special")
        result = subprocess.run(args, check=True, capture_output=True, text=True)
        match = re.search(r"(?m)^\[[-, 0-9]+\]$", result.stdout)
        if match is None:
            raise RuntimeError(f"llama-tokenize returned no ID list: {result.stdout!r}")
        ids = ast.literal_eval(match.group(0))
        if not isinstance(ids, list) or not all(isinstance(token, int) for token in ids):
            raise RuntimeError("llama-tokenize returned an invalid ID list")
        return ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--model", required=True)
    parser.add_argument("-p", "--prompt")
    parser.add_argument("--stdin", action="store_true")
    parser.add_argument("--no-bos", action="store_true")
    parser.add_argument("--no-parse-special", action="store_true")
    args = parser.parse_args()
    if args.stdin:
        text = sys.stdin.read()
    elif args.prompt is not None:
        text = args.prompt
    else:
        parser.error("choose --prompt or --stdin")
    ids = Tokenizer(args.model).encode(
        text, add_bos=not args.no_bos, parse_special=not args.no_parse_special
    )
    print(ids)


if __name__ == "__main__":
    main()
