#!/usr/bin/env python3
"""Reference fp16 oracle for the H14 stage 1-4 ANEC fixtures.

  h14_oracle.py <op> <out-dir> [ <op> <out-dir> ... ]
  h14_oracle.py all <out-dir>

Per op it writes, into <out-dir>/<op>/:
  input-<name>.buffer   packed physical surface for each runtime input
  input-<name>.dense.fp16  the same values, dense fp16 (1 KiB class)
  expected.fp16         dense expected output
  output-sentinel.buffer  allocation-sized 0x7e00 NaN sentinel
and prints SHA-256 for every file.

Rounding: add/sub/scalar-add use half-away-from-zero fp16, the rounding the
M2 ANE was proven to use on exact half-ulp ties (first-inference.md, boot
8f468602). mul uses half-away too; its device rounding mode is not yet
proven, but a product of two fp16 values is exact in fp32, so only one
rounding happens and ties are the only exposure. matvec accumulates each
output in fp32 over K and rounds once, half-away; the device accumulation
order and width are UNPROVEN - treat exact equality as the hypothesis and
1-2 ulp as the fallback band. relu/clip/power-of-two scalars are exact.

Shapes: elementwise ops [1,512,1,1] (the proven add geometry); matvec
x [1,256], W [256,256] (transposed y), y [1,256].

Surface packing (mil-hwx-compiler research/inspect_anec.py convert_tensor):
element i lands at (i // width) * row + (i % width) * 2, width = nchw[3],
row = nchw[5]; the buffer is allocationBytes long.
"""
import hashlib
import struct
import sys
from pathlib import Path

C = 512
K = 256
N = 256
ALLOCATION_ELEMENTWISE = 0x8000
NCHW_ELEMENTWISE = [1, 512, 1, 1, 64, 64]
NCHW_MATVEC = [1, 1, 1, 256, 512, 512]    # width 256, row 512: dense rows


def fp16_half_away(value: float) -> bytes:
    """Pack a finite float as fp16, ties rounded away from zero."""
    if value != value or abs(value) == float("inf"):
        return struct.pack("<e", value)
    import math
    sign = 0x8000 if math.copysign(1.0, value) < 0 else 0
    v = abs(value)
    if v == 0:
        return struct.pack("<H", sign)
    mant, E = math.frexp(v)                    # v = mant * 2**E, mant in [0.5, 1)
    if E < -13:                                # subnormal (v < 2**-14): quantum 2**-24
        q = mant * 2.0 ** (E + 24)             # exact in float64
        n = int(q) + (1 if q - int(q) >= 0.5 else 0)
        if n == 0:
            return struct.pack("<H", sign)
        if n >= 1024:                          # rounded up to the smallest normal
            return struct.pack("<H", sign | 0x0400)
        return struct.pack("<H", sign | n)
    if E > 16:                                 # v >= 2**16 -> infinity
        return struct.pack("<H", sign | 0x7C00)
    q = mant * 2048.0                          # exact: [1024, 2048)
    n = int(q) + (1 if q - int(q) >= 0.5 else 0)
    if n == 2048:
        n, E = 1024, E + 1
        if E > 16:
            return struct.pack("<H", sign | 0x7C00)
    return struct.pack("<H", sign | ((E + 14) << 10) | (n - 1024))


def self_check() -> None:
    """RNE agreement off-tie, away-from-zero on exact ties, subnormals."""
    import random
    random.seed(1234)
    for _ in range(200000):
        bits = random.randrange(0, 0x8000)
        v = struct.unpack("<e", struct.pack("<H", bits))[0]
        if v != v or abs(v) == float("inf"):
            continue
        mine = fp16_half_away(v)
        assert mine == struct.pack("<e", v), f"RNE mismatch at {v!r}"
    ties = 0
    for _ in range(20000):
        bits = random.randrange(1, 0x7BFF)
        lo = struct.unpack("<e", struct.pack("<H", bits))[0]
        hi = struct.unpack("<e", struct.pack("<H", bits + 1))[0]
        mid = (lo + hi) / 2
        if fp16_half_away(mid) != struct.pack("<H", bits + 1):
            raise AssertionError(f"tie {mid!r} did not round away from zero")
        ties += 1
    # negative tie rounds away from zero (toward -inf)
    lo = struct.unpack("<e", struct.pack("<H", 0x3C01))[0]
    hi = struct.unpack("<e", struct.pack("<H", 0x3C02))[0]
    neg = fp16_half_away(-(lo + hi) / 2)
    assert struct.unpack("<H", neg)[0] == 0xBC02, "negative tie"
    # known subnormal tie: midpoint of k=1,2 quanta (step 2**-24) -> k=2
    q = 1.5 * 2.0 ** -24
    assert fp16_half_away(q) == struct.pack("<H", 2), "subnormal tie"
    print(f"fp16 half-away self-check ok ({ties} tie cases)")


def dense_input_a(i: int) -> float:
    return (i - 256) / 32                      # the proven add input


def dense_input_b_add(i: int) -> float:
    return ((i % 17) - 8) / 16                 # the proven add input


def dense_input_b_mul(i: int) -> float:
    return ((i * 7) % 13 - 6) / 8


def weight(n: int, k: int) -> float:
    return ((n % 8) - 3.5) * 0.25 + ((k % 4) - 1.5) * 0.0625


def pack_surface(values: list[bytes], nchw: list[int], allocation: int) -> bytes:
    width, row = nchw[3], nchw[5]
    out = bytearray(allocation)
    for i, two in enumerate(values):
        offset = (i // width) * row + (i % width) * 2
        out[offset:offset + 2] = two
    return bytes(out)


def matvec_f32_acc(x: list[float], w: list[list[float]]) -> list[bytes]:
    out = []
    for n in range(N):
        acc = 0.0
        for k in range(K):
            acc += x[k] * w[n][k]
        out.append(fp16_half_away(acc))
    return out


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(op: str, out_root: Path) -> None:
    out = out_root / op
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, bytes] = {}
    nchw, allocation = NCHW_ELEMENTWISE, ALLOCATION_ELEMENTWISE
    a = [fp16_half_away(dense_input_a(i)) for i in range(C)]

    if op == "add":
        b = [fp16_half_away(dense_input_b_add(i)) for i in range(C)]
        y = [fp16_half_away(struct.unpack("<e", x)[0] + struct.unpack("<e", v)[0])
             for x, v in zip(a, b)]
        inputs = {"a": a, "b": b}
    elif op == "mul":
        b = [fp16_half_away(dense_input_b_mul(i)) for i in range(C)]
        y = [fp16_half_away(struct.unpack("<e", x)[0] * struct.unpack("<e", v)[0])
             for x, v in zip(a, b)]
        inputs = {"a": a, "b": b}
    elif op == "relu":
        y = [x if struct.unpack("<e", x)[0] > 0 else struct.pack("<H", 0) for x in a]
        inputs = {"a": a}
    elif op == "add-scalar":
        half = fp16_half_away(0.5)
        y = [fp16_half_away(struct.unpack("<e", x)[0] + 0.5) for x in a]
        inputs = {"a": a}
    elif op == "mul-scalar":
        y = [fp16_half_away(struct.unpack("<e", x)[0] * 0.5) for x in a]
        inputs = {"a": a}
    elif op == "clip-low":
        half = fp16_half_away(0.5)
        y = [x if struct.unpack("<e", x)[0] >= 0.5 else half for x in a]
        inputs = {"a": a}
    elif op == "clip-high":
        half = fp16_half_away(0.5)
        y = [x if struct.unpack("<e", x)[0] <= 0.5 else half for x in a]
        inputs = {"a": a}
    elif op == "real-div-scalar":
        y = [fp16_half_away(struct.unpack("<e", x)[0] * 2.0) for x in a]
        inputs = {"a": a}
    elif op == "matvec":
        nchw, allocation = NCHW_MATVEC, 0x4000
        x = [fp16_half_away(((k % 16) - 8) / 8) for k in range(K)]
        w = [[weight(n, k) for k in range(K)] for n in range(N)]
        y = matvec_f32_acc([struct.unpack("<e", v)[0] for v in x], w)
        inputs = {"x": x}
        dense_w = b"".join(struct.pack("<e", weight(n, k)) for n in range(N) for k in range(K))
        files["weights.dense.fp16"] = dense_w
    else:
        raise SystemExit(f"unknown op {op}")

    for name, dense in inputs.items():
        files[f"input-{name}.buffer"] = pack_surface(dense, nchw, allocation)
        files[f"input-{name}.dense.fp16"] = b"".join(dense)
    files["expected.fp16"] = b"".join(y)
    files["output-sentinel.buffer"] = b"\x00\x7e" * (allocation // 2)
    print(f"== {op}")
    for name, data in sorted(files.items()):
        path = out / name
        path.write_bytes(data)
        print(f"  {name}: {len(data)} B sha256 {sha(path)}")


def main() -> int:
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "all":
        ops = ["add", "mul", "relu", "add-scalar", "mul-scalar",
               "real-div-scalar", "clip-low", "clip-high", "matvec"]
        for op in ops:
            emit(op, Path(args[1]))
        return 0
    if len(args) % 2:
        print(__doc__)
        return 2
    for i in range(0, len(args), 2):
        emit(args[i], Path(args[i + 1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
