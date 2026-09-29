#!/usr/bin/env python3
"""Minimal stand-in for `llama-tokenize -m MODEL -p PROMPT --ids` using the pinned Qwen3.8 tokenizer.json
(same vocabulary as the GGUF; Qwen adds no BOS). Used only where llama.cpp's binary is absent (jw16).
Prints one line like llama-tokenize --ids: [id, id, ...]."""
import glob
import os
import sys

from tokenizers import Tokenizer

args = sys.argv[1:]
prompt = args[args.index("-p") + 1]
path = glob.glob(os.path.expanduser("~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/tokenizer.json"))[0]
ids = Tokenizer.from_file(path).encode(prompt, add_special_tokens=False).ids
print(ids)
