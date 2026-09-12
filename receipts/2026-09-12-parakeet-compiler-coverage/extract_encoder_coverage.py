#!/usr/bin/env python3
"""Reproduce the H13 encoder-coverage classification for the pinned Parakeet
encoder Core ML package (2026-09-12).

Pins:
  model  mweinbach1/parakeet-tdt-0.6b-v3-coreml @ b650695c2322ee5281dff48d7345b2f3a58ff018
         encoder.mlpackage/Data/com.apple.CoreML/model.mlmodel
         sha256 2e4e6b54f32029d7b2a69549c2cedf5cd9c6daa8e5274a2b357fc7911747204b
  compiler mil-hwx-compiler @ a0ce354cf800011a84420da4e12013eb8140b2a5 (clean tree)

The classifier replicates, in Python, the exact plan matchers of
plugins/H13/ANEH13Compiler.mm (broadcastPlan, parityPlan, normParityPlan,
convParityPlan, the generic binary fold, and the matmul/linear lowerings)
against the oracle template tables parsed from the H13 *.inc files, and
applies them to every operation of the encoder's raw MILSpec Model proto
(specificationVersion 9, CoreML8 block, 3351 operations). It classifies each
operation as:

  direct-const           constant data (filtered before the program stream)
  direct-alias           reshape/squeeze/expand_dims metadata alias
  direct                 lowerable by the current compiler as-is
  normalization-needed   lowerable after a handoff/weight-prep rewrite into an
                         already-covered path (no new oracles)
  missing-envelope       semantics implemented in H13 but this geometry/form is
                         outside the decoded oracle tables
  missing                no H13 encoder for the semantics at all

Usage: python3 extract_encoder_coverage.py <model.mlmodel> <compiler-plugins-H13-dir>
"""
import csv
import json
import re
import struct
import sys
from collections import Counter

from coremltools.proto import Model_pb2

BINOPS = {"add": "Add", "mul": "Multiply", "maximum": "Maximum",
          "minimum": "Minimum", "sub": "Subtract", "real_div": "RealDivide"}
UNOPS = {"abs": "Absolute", "exp": "Exponential", "gelu": "Gelu",
         "leaky_relu": "LeakyRelu", "relu": "Relu",
         "rsqrt": "ReciprocalSquareRoot", "sigmoid": "Sigmoid", "silu": "Silu",
         "sqrt": "SquareRoot", "tanh": "Tanh"}
NORMOPS = {"softmax": "Softmax", "layer_norm": "LayerNorm",
           "reduce_sum": "ReduceSum", "reduce_max": "ReduceMax",
           "reduce_mean": "ReduceMean"}

DT = {10: "fp16", 11: "fp32", 13: "bf16", 23: "int32", 24: "int64",
      1: "bool", 2: "string", 25: "int4", 35: "uint4"}


def parse_entries(text, table):
    m = re.search(re.escape(table) + r"\s*\[\]\s*=\s*\{(.*)", text, re.S)
    body, out, depth, cur = m.group(1), [], 0, ""
    for ch in body:
        if ch == "{":
            depth += 1
            if depth == 1:
                cur = ""
                continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                out.append(cur)
                continue
        if depth >= 1:
            cur += ch
    return out


def load_tables(h13_dir):
    def head(e, n):
        m = re.match(r"\s*" + r",\s*".join([r"([^,{]+)"] * n), e)
        return [f.strip() for f in m.groups()] if m else None

    t = {}
    env = open(h13_dir + "/H13EnvelopeTemplates.inc").read()
    t["mm"] = []
    for e in parse_entries(env, "kMatmulEnvelopeTasks"):
        h = head(e, 6)
        t["mm"].append((int(h[0]), int(h[1]), int(h[2]),
                        h[3] == "true", h[4] == "true", h[5] == "true"))
    t["bc"] = []
    for e in parse_entries(env, "kBroadcastTasks"):
        m = re.match(r"\s*(\d+),\s*BroadcastOperand::(\w+),\s*\{(\d+),\s*(\d+),"
                     r"\s*(\d+),\s*(\d+)\}(?:,\s*\{(\d+),\s*(\d+),\s*(\d+),"
                     r"\s*(\d+)\})?", e)
        x = tuple(int(m.group(i)) for i in range(3, 7))
        y = tuple(int(m.group(i)) for i in range(7, 11)) if m.group(7) else None
        t["bc"].append((int(m.group(1)), m.group(2), x, y))
    ew = open(h13_dir + "/H13ElementwiseTemplates.inc").read()
    t["ew"] = []
    for e in parse_entries(ew, "kElementwiseTasks"):
        m = re.match(r"\s*ElementwiseKind::(\w+),\s*static_cast<std::uint8_t>"
                     r"\((\w+)Operation::(\w+)\),\s*\{(\d+),\s*(\d+),\s*(\d+)\}", e)
        t["ew"].append((m.group(1), m.group(3), int(m.group(4)),
                        int(m.group(5)), int(m.group(6))))
    nt = open(h13_dir + "/H13NormTemplates.inc").read()
    t["nt"] = []
    for e in parse_entries(nt, "kNormTasks"):
        m = re.match(r"\s*NormOperation::(\w+),\s*\{(\d+),\s*(\d+),\s*(\d+)\},"
                     r"\s*\{(\d+),\s*(\d+),\s*(\d+)\},\s*(0x[0-9a-fA-F]+),"
                     r"\s*(true|false)", e)
        t["nt"].append((m.group(1),
                        (int(m.group(2)), int(m.group(3)), int(m.group(4))),
                        (int(m.group(5)), int(m.group(6)), int(m.group(7))),
                        int(m.group(8), 16), m.group(9) == "true"))
    cv = open(h13_dir + "/H13ConvTemplates.inc").read()
    t["conv"] = []
    for e in parse_entries(cv, "kConvTasks"):
        m = re.match(r"\s*(\d+),\s*(\d+),\s*(\d+),\s*(true|false),\s*\{(\d+),"
                     r"\s*(\d+),\s*(\d+)\},\s*\{(\d+),\s*(\d+),\s*(\d+)\}", e)
        t["conv"].append((int(m.group(1)), int(m.group(2)), int(m.group(3)),
                          m.group(4) == "true",
                          (int(m.group(5)), int(m.group(6)), int(m.group(7))),
                          (int(m.group(8)), int(m.group(9)), int(m.group(10)))))
    return {k: {v if isinstance(v, tuple) else v for v in vs} if k != "conv" else set(vs)
            for k, vs in t.items()}


def main(mlmodel_path, h13_dir):
    model = Model_pb2.Model()
    with open(mlmodel_path, "rb") as f:
        model.ParseFromString(f.read())
    fn = None
    for k, v in model.mlProgram.functions.items():
        if k == "main":
            fn = v
    blk = None
    for k, v in fn.block_specializations.items():
        if k == "CoreML8":
            blk = v
    ops = list(blk.operations)

    def tstr(t):
        tt = t.tensorType
        dt = DT.get(tt.dataType, str(tt.dataType))
        dims = ",".join("*" if d.WhichOneof("dimension") == "unknown"
                        else str(d.constant.size) for d in tt.dimensions)
        return f"{dt}[{dims}]"

    records, vtypes = [], {}
    for i in blk.inputs:
        vtypes[i.name] = tstr(i.type)
    for idx, o in enumerate(ops):
        ins = {k: [a.name if a.WhichOneof("binding") == "name"
                   else "<inline>" for a in ib.arguments]
               for k, ib in o.inputs.items()}
        outs = {}
        for out in o.outputs:
            vtypes[out.name] = tstr(out.type)
            outs[out.name] = vtypes[out.name]
        records.append({"i": idx, "type": o.type, "inputs": ins,
                        "outputs": outs, "attrs": {k: str(v) for k, v in o.attributes.items()}})
    prod = {}
    for r in records:
        for on in r["outputs"]:
            prod[on] = r["i"]

    tables = load_tables(h13_dir)
    EW, BCT, NT = tables["ew"], tables["bc"], tables["nt"]
    CONV, MM = tables["conv"], tables["mm"]

    FN = {"input_features": "fp32[1,3000,128]", "attention_mask": "int32[1,3000]"}

    def vinfo(name):
        s = FN.get(name) or (records[prod[name]]["outputs"].get(name)
                             if name in prod else None)
        if s is None:
            return None
        dt, dims = s.split("[", 1)
        dims = dims.rstrip("]")
        return (dt, tuple() if dims == "" else tuple(int(x) for x in dims.split(",")))

    def cval(name):
        i = prod.get(name)
        if i is None or records[i]["type"] != "const":
            return None
        iv = ops[i].attributes["val"].immediateValue
        if iv.WhichOneof("value") != "tensor":
            return None
        t = iv.tensor
        w = t.WhichOneof("value")
        if w == "bytes":
            raw = t.SerializeToString()
            j = 0
            while j < len(raw):
                tag = raw[j]; j += 1
                if tag & 7 == 2:
                    ln, sh = 0, 0
                    while True:
                        b = raw[j]; j += 1
                        ln |= (b & 0x7F) << sh; sh += 7
                        if not b & 0x80:
                            break
                    return struct.unpack(f"<{ln // 2}e", raw[j:j + ln])
                while raw[j] & 0x80:
                    j += 1
                j += 1
            return ()
        if w == "ints":
            return list(t.ints.values)
        if w == "strings":
            return list(t.strings.values)
        if w == "bools":
            return list(t.bools.values)
        return w

    scal = lambda v: v[0] if isinstance(v, list) and len(v) == 1 else v
    at = lambda v, k, d=None: (v[k] if isinstance(v, list) and len(v) > k else d)
    is_const = lambda n: n in prod and records[prod[n]]["type"] == "const"

    elem = lambda v: ((v[1], v[2], v[3]) if v and v[0] == "fp16" and len(v[1]) == 4
                      and v[1][0] == 1 and 0 not in v[1] else None)

    def nsurf(s):
        dims, sh = list(s), 0
        while len(dims) > 3 and dims[0] == 1:
            dims.pop(0); sh -= 1
        while dims and len(dims) < 3:
            dims.insert(0, 1); sh += 1
        return (tuple(dims), sh) if len(dims) == 3 else (None, None)

    def flat(v):
        c = 1
        for d in v[1]:
            c *= d
        return (c, 1, 1)

    rows = []
    for r in records:
        t, i, ins = r["type"], r["i"], r["inputs"]
        cls, note = None, ""
        outn = list(r["outputs"])[0] if r["outputs"] else None
        outv = vinfo(outn) if outn else None
        xv = vinfo(ins["x"][0]) if "x" in ins else None
        yv = vinfo(ins["y"][0]) if "y" in ins else None
        if t == "const":
            cls = "direct-const"
        elif t in ("reshape", "squeeze", "expand_dims"):
            cls, note = "direct-alias", "shape alias, no program"
        elif t == "relu":
            es = [e for e in [elem(outv)] if e] + [flat(outv)]
            cls = "direct"  # native surface or maximum(x,0) folded fallback
            note = "native" if any(("Unary", "Relu", c, h, w) in EW for c, h, w in es) \
                else "maximum(x,0) fallback"
        elif t == "conv":
            wv = vinfo(ins["weight"][0])
            padt = scal(cval(ins["pad_type"][0]))
            strides = cval(ins["strides"][0])
            s0, s1 = at(strides, 0), at(strides, 1)
            d0 = at(cval(ins["dilations"][0]), 0); d1 = at(cval(ins["dilations"][0]), 1)
            g = scal(cval(ins["groups"][0]))
            xin, out = elem(vinfo(ins["x"][0])), elem(outv)
            hit = (wv[1][2], s0, g, "bias" in ins, xin, out) in CONV \
                if xin and out and len(wv[1]) == 4 else False
            cls = "direct" if hit else "missing-envelope"
            note = f"pad_type={padt} k={wv[1][2] if len(wv[1])==4 else '?'} s={s0} g={g} hit={hit}"
        elif t in BINOPS:
            op = BINOPS[t]
            xn, yn = ins["x"][0], ins["y"][0]
            xc, yc = is_const(xn), is_const(yn)
            yscalar = yc and vinfo(yn)[0] == "fp16" and len(vinfo(yn)[1]) == 0
            bt = None
            if xv and xv[0] == "fp16" and len(xv[1]) == 4 and not xc and outv and len(outv[1]) == 4:
                if yscalar:
                    bt = (op, "Scalar", xv[1], None)
                elif yc and len(yv[1]) == 4 and yv[1][0] == 1 and yv[1][2] == 1 \
                        and yv[1][3] == 1 and yv[1][1] == xv[1][1]:
                    bt = (op, "Constant", xv[1], (1, xv[1][1], 1, 1))
                elif yv[0] == "fp16" and len(yv[1]) == 4:
                    bt = (op, "Runtime", xv[1], yv[1])
            bhit = bt is not None and any(o == bt[0] and od == bt[1] and xt == bt[2]
                                          and (bt[1] == "Scalar" or yt == bt[3])
                                          for o, od, xt, yt in BCT)
            es = ([e for e in [elem(outv)] if e] + [flat(outv)]) if outv and outv[0] == "fp16" else []
            if bhit:
                cls, note = "direct", f"broadcast template {bt[1]}"
            elif not xc and yscalar and any(("BinaryScalar", op, c, h, w) in EW for c, h, w in es):
                cls = "direct"
            elif not xc and not yc and any(("BinaryRuntime", op, c, h, w) in EW for c, h, w in es):
                cls = "direct"
            elif xv[0] != "fp16" or yv[0] != "fp16":
                cls, note = "missing", "int32 arithmetic, fp16-only stream"
            elif not xc and not yc:
                cls = "direct" if xv[1] == yv[1] == outv[1] else "missing-envelope"
            elif xc and yc:
                cls = "missing"
            elif yscalar:
                cls = "direct" if t == "mul" else "normalization-needed"
            else:
                cv = vinfo(yn if xc else xn)
                rt = yv if xc else xv
                cls = "direct" if cv[1] == rt[1] and outv[1] == rt[1] else "normalization-needed"
        elif t in UNOPS:
            op = UNOPS[t]
            es = [e for e in [elem(outv)] if e] + [flat(outv)]
            ok = any(("Unary", op, c, h, w) in EW for c, h, w in es)
            cls, note = ("direct" if ok else "missing-envelope"), str(es)
        elif t == "softmax":
            si, sh = nsurf(xv[1]); so, _ = nsurf(outv[1])
            ax = scal(cval(ins["axis"][0]))
            la = ax if ax >= 0 else len(xv[1]) + ax
            sa = la + sh + 1
            mask = (1 << sa) if 1 <= sa <= 3 else None
            hit = ("Softmax", si, so, mask, True) in NT if mask else False
            cls = "direct" if hit else "missing-envelope"
            note = f"in={si} mask={mask:#04x} hit={hit}"
        elif t == "layer_norm":
            cls = "missing"
            note = "affine form rejected by normParityPlan (no gamma/beta, fp32 eps==1e-5)"
        elif t in NORMOPS:
            if t == "reduce_min" or xv[0] != "fp16":
                cls = "missing"
            else:
                cls = "missing-envelope"
        elif t == "linear":
            cls = "normalization-needed"
            note = "LUT palettized weight; decompress to const BLOBFILE"
        elif t == "constexpr_lut_to_dense":
            cls, note = "normalization-needed", "host LUT decompression at weight-prep"
        elif t == "matmul":
            yn = ins["y"][0]
            tx = bool(scal(cval(ins["transpose_x"][0])))
            ty = bool(scal(cval(ins["transpose_y"][0])))
            yc = is_const(yn)
            rank = len(xv[1]); lead = rank - (2 if tx else 1)
            rowsn = 1
            for d in xv[1][:lead]:
                rowsn *= d
            red = xv[1][rank - (2 if tx else 1)]
            cols = outv[1][-1]
            if not yc:
                yv2 = vinfo(yn)
                ok = all(d == 1 for d in yv2[1][:-2]) and \
                    ((yv2[1][-2] == cols and yv2[1][-1] == red) if ty
                     else (yv2[1][-2] == red and yv2[1][-1] == cols))
                hit = (rowsn, red, cols, tx, ty, True) in MM and ok
                cls = "direct" if hit else "missing-envelope"
            else:
                hit = (rowsn, red, cols, tx, True, False) in MM
                cls = "direct" if hit else "normalization-needed"
                note = "chunked matvec path; re-emit weight as BLOBFILE const"
        else:
            cls, note = "missing", "no source-qualified encoder"
        rows.append((i, t, cls, note))

    if len(sys.argv) > 3:
        with open(sys.argv[3], "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["op_index", "op", "class", "note"])
            w.writerows(rows)
    c = Counter(cls for _, _, cls, _ in rows)
    for k, n in c.most_common():
        print(f"{k:24s} {n}")
    print("total", len(rows))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
