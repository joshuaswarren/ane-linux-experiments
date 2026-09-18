#!/usr/bin/env python3
"""Conv/rel-pos/transpose island lane: mint the 77 placement bundles from the
real per-layer encoder weights with the pinned mil-hwxc (F3 writeout-inverse
build, 389664f) and device-gate every minted bundle through
libane-strict-fill against fp32 numpy references (rngs 11/33/57, budget 0.05).

Families (bundle -> proven form, receipts 2026-09-18-encoder-conv-device-gate
and 2026-09-18-f3-writeout-inverse):
  island-conv-pw1-L{ll}  F1 in-proj  k1x1 g1 valid 1024->2048 bias-free
  island-conv-dw-L{ll}   F2 depthwise k1x9 g1024 same +bias
  island-conv-pw2-L{ll}  F3 out-proj k1x1 g1 valid 1024->1024 (fixed packing)
  island-relpos-pad      F4 padconv g8 k1x1 custom pad [0,0,1,0], W = ones
                         (bit-identical to the coreml pad: value 0.0, left 1)
  island-relpos-slice    last-dim slice [1,8,375,749] -> [..., 375]
  island-tr-r3-in        transpose r3 [0,2,1] [1,375,1024] -> [1,1024,375]
  island-tr-r3-out       transpose r3 [0,2,1] [1,1024,375] -> [1,375,1024]
  island-tr-r4-out       transpose r4 [0,2,1,3] [1,8,375,128] -> [1,375,8,128]

The conv MIL spellings are the exact gate spellings (research/oracles/h13
encoder_*); weights come from the deparalettized encoder source blobs, so a
weight-order bug cannot hide behind uniform payloads.

  mint  --source <encoder-source> --compiler <mil-hwxc> --adapter <dir with
          h13_v2_to_schema4.py> --out <bundles dir>
  gate  --bundles <bundles dir> --source <encoder-source> --libane <strict so>

Run mint anywhere (CPU only); run gate on the ANE host under /tmp/m1-gpu.lock.
"""
from __future__ import annotations
import argparse, ctypes, hashlib, json, re, struct, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

BLOB_MAGIC = 0xDEADBEEF
DATA_START = (64 + 4096 * 24 + 63) & ~63
STMT = re.compile(
    r"^\s*(?P<type>tensor<[^>]*>|string|int32|bool|fp16|fp32)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_@]*)\s*=\s*"
    r"(?P<op>[a-z_][a-z_0-9]*)\((?P<args>.*)\)\s*(?:\[(?P<attrs>.*)\])?;\s*$"
)
TYPE = re.compile(r"^tensor<\s*(?P<dtype>\w+)\s*,\s*\[(?P<shape>[^\]]*)\]>$")
BLOBFILE = re.compile(
    r'BLOBFILE\(path = string\("(?P<path>[^"]+)"\), offset = uint64\((?P<offset>\d+)\)\)'
)

CONV_HEAD = """program(1.3)
[buildInfo = dict<string, string>({{}})]
{{
  func main<ios18>(tensor<fp16, {x_shape}> x) {{
{wconst}{bconst}    string pt = const()[name = string("pt"), val = string("{pad_type}")];
    tensor<int32, [2]> st = const()[name = string("st"), val = tensor<int32, [2]>([1, 1])];
    tensor<int32, [4]> pd = const()[name = string("pd"), val = tensor<int32, [4]>([{pd_vals}])];
    tensor<int32, [2]> dl = const()[name = string("dl"), val = tensor<int32, [2]>([1, 1])];
    int32 gp = const()[name = string("gp"), val = int32({groups})];
    tensor<fp16, {y_shape}> y = conv({bias_arg}dilations = dl, groups = gp, pad = pd, pad_type = pt, strides = st, weight = w, x = x)[name = string("y")];
  }} -> (y);
}}
"""
W_LINE = ('    tensor<fp16, {w_shape}> w = const()[name = string("w"), '
          'val = tensor<fp16, {w_shape}>(BLOBFILE(path = string("@model_path/weights.bin"), '
          'offset = uint64(64)))];\n')
B_LINE = ('    tensor<fp16, {b_shape}> b = const()[name = string("b"), '
          'val = tensor<fp16, {b_shape}>(BLOBFILE(path = string("@model_path/weights.bin"), '
          'offset = uint64(88)))];\n')

MIL_SLICE = """program(1.3)
[buildInfo = dict<string, string>({})]
{
  func main<ios18>(tensor<fp16, [1, 8, 375, 749]> x) {
    tensor<int32, [4]> eb = const()[name = string("eb"), val = tensor<int32, [4]>([0, 0, 0, 0])];
    tensor<int32, [4]> ee = const()[name = string("ee"), val = tensor<int32, [4]>([1, 8, 375, 375])];
    tensor<fp16, [1, 8, 375, 375]> y = slice_by_index(x = x, begin = eb, end = ee)[name = string("y")];
  } -> (y);
}
"""


def mil_transpose(x_shape, y_shape, rank):
    perm = "[0, 2, 1]" if rank == 3 else "[0, 2, 1, 3]"
    pl = (f'tensor<int32, [{rank}]> perm = const()[name = string("perm"), '
          f'val = tensor<int32, [{rank}]>({perm})];')
    return f"""program(1.3)
[buildInfo = dict<string, string>({{}})]
{{
  func main<ios18>(tensor<fp16, {list(x_shape)}> x) {{
    {pl}
    tensor<fp16, {list(y_shape)}> y = transpose(perm = perm, x = x)[name = string("y")];
  }} -> (y);
}}
"""


def parse_consts(text):
    consts = {}
    for line in text.split("\n"):
        m = STMT.match(line)
        if m is None or m.group("op") != "const":
            continue
        blob = BLOBFILE.search((m.group("args") or "") + (m.group("attrs") or ""))
        if blob is None:
            continue
        t = TYPE.match(m.group("type"))
        if t is None:
            continue
        dims = [d.strip() for d in t.group("shape").split(",")]
        consts[m.group("name")] = {
            "shape": tuple(int(d) for d in dims if d),
            "path": blob.group("path"),
            "offset": int(blob.group("offset")),
        }
    return consts


class Blobs:
    def __init__(self, root: Path):
        self.root = root
        self._maps = {}

    def read(self, path, offset, want):
        name = path.replace("@model_path/", "")
        if name not in self._maps:
            self._maps[name] = (self.root / name).read_bytes()
        raw = self._maps[name]
        magic, _s, length, payload = struct.unpack_from("<IIQQ", raw, offset)
        if magic != BLOB_MAGIC:
            raise SystemExit(f"blob magic {magic:#x} at {path}:{offset}")
        if want > length:
            raise SystemExit(f"blob at {path}:{offset} holds {length}, want {want}")
        return raw[payload:payload + want]


def write_blob(dest, payloads):
    blobs = [np.asarray(p).tobytes() for p in payloads]
    blob = bytearray(DATA_START + sum(len(p) for p in blobs))
    struct.pack_into("<II", blob, 0, len(blobs), 2)
    off = DATA_START
    for i, p in enumerate(blobs):
        struct.pack_into("<IIQQ", blob, 64 + i * 24, BLOB_MAGIC, 1, len(p), off)
        blob[off:off + len(p)] = p
        off += len(p)
    dest.write_bytes(bytes(blob))


ENV = {
    "LD_LIBRARY_PATH": str(Path.home() / ".local/mil-hwx-gnustep/lib"),
    "PATH": "/usr/bin:/bin",
    "HOME": str(Path.home()),
}


def compile_island(compiler, mil, root, out):
    r = subprocess.run(
        [str(compiler), "--mil", str(mil), "--model-root", str(root),
         "--target", "H13", "--format", "anec", "--output", str(out)],
        capture_output=True, text=True, timeout=600, env=ENV, check=False)
    if r.returncode != 0:
        raise SystemExit(f"mil-hwxc failed for {mil.parent.name}: {r.stdout}{r.stderr}")


def conv_mil(x_shape4, w_shape4, b, pad_type, groups):
    """The exact gate conv spelling (stride 1, dilation 1)."""
    n, cin, h, w = x_shape4
    cout, cin_g, kh, kw = w_shape4
    if pad_type == "same":
        pt = max(0, (h - 1) + kh - h); pb = pt - pt // 2; pt = pt // 2
        pl = max(0, (w - 1) + kw - w); pr = pl - pl // 2; pl = pl // 2
        pd_vals = "0, 0, 0, 0"
    else:
        pt, pb, pl, pr = (0, 0, 0, 0) if pad_type == "valid" else (0, 0, 1, 0)
        pd_vals = f"{pt}, {pb}, {pl}, {pr}"
    y_shape = (n, cout, (h + pt + pb - kh) + 1, (w + pl + pr - kw) + 1)
    body = CONV_HEAD.format(
        x_shape=list(x_shape4), y_shape=list(y_shape),
        wconst=W_LINE.format(w_shape=list(w_shape4)),
        bconst=B_LINE.format(b_shape=[cout]) if b else "",
        bias_arg="bias = b, " if b else "",
        pad_type=pad_type, pd_vals=pd_vals, groups=groups,
    )
    return body, y_shape


def ref_conv(x32, W32, b32, pad_type, groups):
    n, cin, h, w = x32.shape
    cout, cin_g, kh, kw = W32.shape
    if pad_type == "same":
        pt = max(0, (h - 1) + kh - h); pb = pt - pt // 2; pt = pt // 2
        pl = max(0, (w - 1) + kw - w); pr = pl - pl // 2; pl = pl // 2
    elif pad_type == "valid":
        pt = pb = pl = pr = 0
    else:  # custom [0,0,1,0]
        pt, pb, pl, pr = 0, 0, 1, 0
    xp = np.pad(x32, ((0, 0), (0, 0), (pt, pb), (pl, pr)))
    oh = (h + pt + pb - kh) + 1
    ow = (w + pl + pr - kw) + 1
    s = xp.strides
    cols = np.lib.stride_tricks.as_strided(
        xp, shape=(n, cin, kh, kw, oh, ow),
        strides=(s[0], s[1], s[2], s[3], s[2], s[3]), writeable=False)
    per = cout // groups
    out = np.empty((n, cout, oh, ow), dtype=np.float32)
    if cin_g == 1 and per == 1:
        out = np.einsum("nckhij,ckh->ncij", cols, W32[:, 0], optimize=True)
    else:
        for g in range(groups):
            xg = cols[:, g * cin_g:(g + 1) * cin_g].reshape(n, cin_g * kh * kw, oh * ow)
            wg = W32[g * per:(g + 1) * per].reshape(per, cin_g * kh * kw)
            out[:, g * per:(g + 1) * per] = (wg @ xg).reshape(n, per, oh, ow)
    if b32 is not None:
        out = out + b32.reshape(1, cout, 1, 1)
    return out


# Site table: name -> (bundle kind, x4, w4 or None, bias, pad_type, groups)
def collect_sites(source: Path):
    text = (source / "model.mil").read_text()
    consts = parse_consts(text)
    blobs = Blobs(source / "model-root")
    pw1_w = re.compile(r"encoder_layers_(\d+)_conv_pointwise_conv1_weight_to_fp16")
    pw2_w = re.compile(r"encoder_layers_(\d+)_conv_pointwise_conv2_weight_to_fp16")
    sites = []          # (name, payload_records, kind, x4, w4, b32 or None, pad_type, groups)
    seen = {"pw1": 0, "pw2": 0, "dw": 0}
    for line in text.split("\n"):
        m = STMT.match(line)
        if m is None or m.group("op") != "conv":
            continue
        wm = re.search(r"weight = ([A-Za-z_0-9]+)", m.group("args"))
        if wm is None:
            continue
        wname = wm.group(1)
        w = consts.get(wname)
        if w is None:
            continue
        kind = layer = None
        pm = pw1_w.fullmatch(wname)
        if pm is not None:
            kind, layer = "pw1", int(pm.group(1))
        else:
            pm = pw2_w.fullmatch(wname)
            if pm is not None:
                kind, layer = "pw2", int(pm.group(1))
            elif w["shape"] == (1024, 1, 9):
                kind, layer = "dw", seen["pw2"]
        if kind is None:
            continue
        seen[kind] += 1
        assert w["shape"] in ((2048, 1024, 1), (1024, 1024, 1), (1024, 1, 9)), wname
        W = np.frombuffer(blobs.read(w["path"], w["offset"], int(np.prod(w["shape"])) * 2),
                          dtype="<f2").reshape(w["shape"]).astype(np.float16)
        b = None
        bm = re.search(r"bias = ([A-Za-z_0-9]+)", m.group("args"))
        if bm is not None:
            bc = consts[bm.group(1)]
            b = np.frombuffer(blobs.read(bc["path"], bc["offset"], bc["shape"][0] * 2),
                              dtype="<f2").astype(np.float16)
        x4 = (1, 1024, 1, 375)
        w4 = {"pw1": (w["shape"][0], w["shape"][1], 1, 1),
              "pw2": (w["shape"][0], w["shape"][1], 1, 1),
              "dw": (w["shape"][0], 1, 1, w["shape"][2])}[kind]
        sites.append((f"island-conv-{kind}-L{layer:02d}", kind, x4, w4, b,
                      "valid" if kind != "dw" else "same",
                      1 if kind != "dw" else 1024, W))
    if seen != {"pw1": 24, "pw2": 24, "dw": 24}:
        raise SystemExit(f"conv site census off: {seen}")
    return sites


def adapt_package(adapter: Path, pkg: Path, out: Path, name: str, graph_hash: str,
                  commit: str, dropped_log: list) -> None:
    """Pre-clean the v2 manifest for schema-4: constant-role tensor entries
    (conv weights the anec already embeds) have no schema-4 representation —
    the certified linear bundles carry no tensors section at all — so they
    are dropped before the certified adapter runs. The adapter itself is
    used unmodified."""
    manifest = pkg / "manifest.json"
    import json as _json
    m = _json.loads(manifest.read_text())
    tensors = m.get("tensors")
    if isinstance(tensors, dict):
        keep = {"input", "output", "state", "intermediate"}
        dropped = [n for n, t in tensors.items()
                   if isinstance(t, dict) and t.get("role") not in keep]
        for n in dropped:
            del tensors[n]
        if dropped:
            dropped_log.append((name, dropped))
            manifest.write_text(_json.dumps(m, indent=2, sort_keys=True) + "\n")
    r = subprocess.run(
        [sys.executable, str(adapter / "h13_v2_to_schema4.py"),
         str(pkg), "--out-dir", str(out / name), "--name", name,
         "--graph-hash", graph_hash,
         "--compiler-host-build", "389664f",
         "--compiler-toolchain", "gnustep-linux",
         "--source-repo", "mil-hwx-compiler",
         "--source-commit", commit,
         "--model", "parakeet-tdt-0.6b-v3-coreml b650695c",
         "--exported-at", "2026-09-18"],
        capture_output=True, text=True, timeout=300, check=False)
    if r.returncode != 0:
        raise SystemExit(f"adapter failed for {name}: {r.stdout}{r.stderr}")


def mint(args):
    source = Path(args.source)
    sites = collect_sites(source)
    dropped_log: list = []
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir="/tmp") as td:
        work = Path(td)
        for name, kind, x4, w4, b, pad_type, groups, W in sites:
            records = [W] + ([b] if b is not None else [])
            root = work / name
            root.mkdir()
            write_blob(root / "weights.bin", records)
            mil, y4 = conv_mil(x4, w4, b is not None, pad_type, groups)
            (root / "island.mil").write_text(mil)
            pkg = root / "pkg"
            compile_island(Path(args.compiler), root / "island.mil", root, pkg)
            graph_hash = hashlib.sha256((pkg / "program-0.anec").read_bytes()).hexdigest()
            adapt_package(Path(args.adapter), pkg, out, name, graph_hash,
                          args.commit, dropped_log)
        # Weightless rel-pos / transpose bundles: the exact gate structural
        # spellings; the padconv rides ones weights so its output is the
        # coreml zero-pad bit-for-bit.
        struct_bundles = [
            ("island-relpos-pad", "padconv",
             dict(x4=(1, 8, 375, 749), w4=(8, 1, 1, 1), bias=False,
                  pad_type="custom", groups=8, W=np.ones((8,), np.float16),
                  b=None)),
            ("island-relpos-slice", MIL_SLICE,
             dict(x=(1, 8, 375, 749), y=(1, 8, 375, 375))),
            ("island-tr-r3-in", mil_transpose((1, 375, 1024), (1, 1024, 375), 3),
             dict(x=(1, 375, 1024), y=(1, 1024, 375))),
            ("island-tr-r3-out", mil_transpose((1, 1024, 375), (1, 375, 1024), 3),
             dict(x=(1, 1024, 375), y=(1, 375, 1024))),
            ("island-tr-r4-out", mil_transpose((1, 8, 375, 128), (1, 375, 8, 128), 4),
             dict(x=(1, 8, 375, 128), y=(1, 375, 8, 128))),
        ]
        for name, mil, kw in struct_bundles:
            root = work / name
            root.mkdir()
            if isinstance(mil, str) and mil.startswith("program"):
                (root / "island.mil").write_text(mil)
                y4 = kw["y"]
            else:
                mil_text, y4 = conv_mil(kw["x4"], kw["w4"], kw["bias"],
                                        kw["pad_type"], kw["groups"])
                (root / "island.mil").write_text(mil_text)
                write_blob(root / "weights.bin", [kw["W"]])
            pkg = root / "pkg"
            compile_island(Path(args.compiler), root / "island.mil", root, pkg)
            graph_hash = hashlib.sha256((pkg / "program-0.anec").read_bytes()).hexdigest()
            adapt_package(Path(args.adapter), pkg, out, name, graph_hash,
                          args.commit, dropped_log)
    print(f"mint: PASS bundles={len(sites) + len(struct_bundles)} out={out}"
          + (f" dropped-constant-tensors={len(dropped_log)}" if dropped_log else ""))
    (out / "mint-log.json").write_text(json.dumps(
        {"bundles": len(sites) + len(struct_bundles),
         "compiler": str(args.compiler), "commit": args.commit,
         "dropped_constant_tensor_sites": [n for n, _ in dropped_log]},
        indent=2) + "\n")


# ------------------------------------------------------------------ gate

def row_bytes(width):
    return (width * 2 + 63) & ~63


def pack(x):
    """NCHW fp16 [N,C,H,W] -> ANE tile bytes (row = alignUp(width*2, 64))."""
    n, c, h, w = x.shape
    rb = row_bytes(w)
    tile = np.zeros(n * c * h * rb, dtype=np.uint8)
    flat = x.reshape(n * c, h, w).astype("<f2")
    raw = flat.tobytes()
    view = tile.reshape(n * c, h, rb)
    view[:, :, :w * 2] = np.frombuffer(raw, dtype=np.uint8).reshape(n * c, h, w * 2)
    return tile


def unpack(buf, shape):
    n, c, h, w = shape
    rb = row_bytes(w)
    view = np.frombuffer(buf, dtype=np.uint8, count=n * c * h * rb).reshape(n * c, h, rb)
    halves = view[:, :, :w * 2].copy().view("<f2")
    return halves.reshape(n, c, h, w).astype(np.float32)


def load_lib(path):
    lib = ctypes.CDLL(path)
    sig = (
        ("__ane_init", ctypes.c_void_p, [ctypes.c_char_p, ctypes.c_int]),
        ("__ane_free", None, [ctypes.c_void_p]),
        ("ane_exec", ctypes.c_int, [ctypes.c_void_p]),
        ("__ane_src_size", ctypes.c_uint64, [ctypes.c_void_p, ctypes.c_uint32]),
        ("__ane_dst_size", ctypes.c_uint64, [ctypes.c_void_p, ctypes.c_uint32]),
        ("__ane_send", None, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]),
        ("__ane_read", None, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]),
    )
    for name, rest, argt in sig:
        f = getattr(lib, name)
        f.restype = rest
        f.argtypes = argt
    return lib


def run_case(lib, anec, x4, y4):
    """Send packed x4, return the unpacked [N,C,H,W] fp32 output."""
    nn = lib.__ane_init(str(anec).encode(), 0)
    assert nn
    try:
        s0, d0 = int(lib.__ane_src_size(nn, 0)), int(lib.__ane_dst_size(nn, 0))
        tile = pack(x4)
        assert s0 >= tile.nbytes, f"anec src {s0} < packed {tile.nbytes}"
        lib.__ane_send(nn, ctypes.c_char_p(tile.ctypes.data), 0)
        assert lib.ane_exec(nn) == 0
        out = np.zeros(d0, dtype=np.uint8)
        lib.__ane_read(nn, ctypes.c_char_p(out.ctypes.data), 0)
        expected = row_bytes(y4[3]) * int(np.prod(y4[:3]))
        assert d0 >= expected, f"dst {d0} < expected {expected}"
        return unpack(out[:expected], y4)
    finally:
        lib.__ane_free(nn)


def gate(args):
    bundles = Path(args.bundles)
    source = Path(args.source)
    sites = collect_sites(source)
    lib = load_lib(args.libane)
    rngs = (11, 33, 57)
    budget = 0.05
    results = {}
    worst_all = 0.0
    for name, kind, x4, w4, b, pad_type, groups, W in sites:
        anec = bundles / name / "program-0.anec"
        _, y4 = conv_mil(x4, w4, b is not None, pad_type, groups)
        W32 = np.asarray(W, dtype=np.float16).reshape(w4).astype(np.float32)
        b32 = (np.asarray(b, dtype=np.float16).astype(np.float32)
               if b is not None else None)
        rows = []
        for seed in rngs:
            rng = np.random.default_rng(seed)
            x = rng.standard_normal(x4).astype(np.float16)
            ref = ref_conv(x.astype(np.float32), W32, b32, pad_type, groups)
            y = run_case(lib, anec, x, y4)
            rel = float(np.linalg.norm(y - ref) / np.linalg.norm(ref))
            rows.append({"seed": seed, "rel_l2": rel})
        worst = max(r["rel_l2"] for r in rows)
        worst_all = max(worst_all, worst)
        results[name] = {"rngs": rows, "worst": worst,
                         "anec_sha256": hashlib.sha256(anec.read_bytes()).hexdigest()}
        print(f"{name}: worst {worst:.6g} {'PASS' if worst <= budget else 'FAIL'}",
              flush=True)
    # Weightless structural bundles.
    struct_cases = [
        ("island-relpos-pad", (1, 8, 375, 749), (1, 8, 375, 750),
         lambda x: np.pad(x.astype(np.float32), ((0, 0), (0, 0), (0, 0), (1, 0)))),
        ("island-relpos-slice", (1, 8, 375, 749), (1, 8, 375, 375),
         lambda x: x.astype(np.float32)[..., :375]),
        ("island-tr-r3-in", (1, 375, 1024), (1, 1024, 375),
         lambda x: x.astype(np.float32).reshape(1, 375, 1024).transpose(0, 2, 1)),
        ("island-tr-r3-out", (1, 1024, 375), (1, 375, 1024),
         lambda x: x.astype(np.float32).reshape(1, 1024, 375).transpose(0, 2, 1)),
        ("island-tr-r4-out", (1, 8, 375, 128), (1, 375, 8, 128),
         lambda x: x.astype(np.float32).transpose(0, 2, 1, 3)),
    ]
    for name, x_shape, y_shape, ref_fn in struct_cases:
        anec = bundles / name / "program-0.anec"
        rows = []
        for seed in rngs:
            rng = np.random.default_rng(seed)
            x = rng.standard_normal(x_shape).astype(np.float16)
            x4 = x.reshape(1, 1, *x.shape[-2:]) if x.ndim == 3 else x
            y4d = (1, 1, *y_shape[-2:]) if len(y_shape) == 3 else y_shape
            y = run_case(lib, anec, x4, y4d).reshape(y_shape)
            ref = ref_fn(x)
            rel = float(np.linalg.norm(y - ref) / np.linalg.norm(ref))
            rows.append({"seed": seed, "rel_l2": rel})
        worst = max(r["rel_l2"] for r in rows)
        worst_all = max(worst_all, worst)
        results[name] = {"rngs": rows, "worst": worst,
                         "anec_sha256": hashlib.sha256(anec.read_bytes()).hexdigest()}
        print(f"{name}: worst {worst:.6g} {'PASS' if worst <= budget else 'FAIL'}",
              flush=True)
    passed = worst_all <= budget
    summary = {"bundles": len(results), "worst": worst_all,
               "budget": budget, "pass": passed, "results": results}
    out = bundles / "conv-gate.json"
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"gate: {'PASS' if passed else 'FAIL'} bundles={len(results)} "
          f"worst={worst_all:.6g} budget={budget} summary={out}")
    if not passed:
        raise SystemExit(1)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mint")
    m.add_argument("--source", required=True)
    m.add_argument("--compiler", required=True)
    m.add_argument("--adapter", required=True)
    m.add_argument("--out", required=True)
    m.add_argument("--commit", default="389664f")
    m.set_defaults(fn=mint)
    g = sub.add_parser("gate")
    g.add_argument("--bundles", required=True)
    g.add_argument("--source", required=True)
    g.add_argument("--libane", required=True)
    g.set_defaults(fn=gate)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
