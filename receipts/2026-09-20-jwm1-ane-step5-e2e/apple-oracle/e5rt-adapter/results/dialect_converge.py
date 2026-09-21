#!/usr/bin/env python3
"""Converge e5rt-pair2/model.mil (coremltools export dialect, parent-normalized)
to the ANEForge e5rt emitter dialect (proven known-good: reference MIL compiled
+ evaluated on the ANE). Emits /Users/joshuawarren/ac-capture/e5rt-pair3/.

Transforms (from dialect diff vs reference MIL + aneforge/_compile.py emitter):
  1. insert buildInfo line after program(1.3)
  2. rank-0 consts  tensor<T, []> N = const()[name = string("N"), val = tensor<T, []>(V)];
     ->              T N = const()[name = string("N"), val = T(V)];
  3. BLOBFILE(offset = uint64(K)) -> BLOBFILE(path = string("@model_path/weights.bin"), offset = uint64(K))
  4. rank-N value lists tensor<T, [S]>(v0, v1) -> tensor<T, [S]>([v0, v1])  (skip BLOBFILE/already-bracketed)
weights.bin is copied unchanged (BLOBFILE offsets untouched).
"""
import re
import shutil
from pathlib import Path

SRC = Path("/Users/joshuawarren/ac-capture/e5rt-pair2/model.mil")
DST = Path("/Users/joshuawarren/ac-capture/e5rt-pair3")
text = SRC.read_text()
stats = {}

# 1. buildInfo
BI = ('[buildInfo = dict<string, string>('
      '{{"coremlc-component-MIL", "3520.4.1"}, {"coremlc-version", "3520.5.1"}})]')
assert text.startswith("program(1.3)\n"), text[:40]
assert "buildInfo" not in text.split("\n")[1]
text = text.replace("program(1.3)\n", "program(1.3)\n" + BI + "\n", 1)
stats["buildinfo"] = 1

# 2. scalar rank-0 consts -> typed scalars
scal_pat = re.compile(
    r'tensor<(int32|bool|string|fp16), \[\]> (\S+) = const\(\)\[name = string\("([^"]+)"\), '
    r'val = tensor<(?:int32|bool|string|fp16), \[\]>\(([^()]*)\)\];')

def scal(m):
    ty, name, val = m.group(1), m.group(2), m.group(4)
    return f'{ty} {name} = const()[name = string("{name}"), val = {ty}({val})];'

text, stats["scalars"] = scal_pat.subn(scal, text)

# 3. BLOBFILE path
blob_pat = re.compile(r'BLOBFILE\((offset = uint64\(\d+\))\)')
text, stats["blobpath"] = blob_pat.subn(
    r'BLOBFILE(path = string("@model_path/weights.bin"), \1)', text)

# 4. bracket rank-N value lists
val_pat = re.compile(r'val = tensor<(\w+), (\[[^\]]+\])>\(([^()]*)\)\];')

def bracket(m):
    ty, shape, inner = m.group(1), m.group(2), m.group(3)
    if inner.startswith("BLOBFILE") or inner.startswith("["):
        return m.group(0)
    return f'val = tensor<{ty}, {shape}>([{inner}])];'

text, stats["bracketed"] = val_pat.subn(bracket, text)

# 5. tuple multi-result bindings: (T a, T b) = op(..) -> T a, T b = op(..)
tup_pat = re.compile(r'^(\s*)\((.+)\) = (?=\w)', re.M)
text, stats["tuple_unparen"] = tup_pat.subn(r'\1\2 = ', text)

DST.mkdir(parents=True, exist_ok=True)
(DST / "model.mil").write_text(text)
w = DST / "weights.bin"
if not w.exists():
    shutil.copyfile("/Users/joshuawarren/ac-capture/e5rt-pair2/weights.bin", w)
print("STATS", stats)
print("MIL bytes", (DST / "model.mil").stat().st_size,
      "weights bytes", w.stat().st_size)
