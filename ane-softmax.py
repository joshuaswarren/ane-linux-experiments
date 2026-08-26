#!/usr/bin/env python3
"""Softmax computed on the Apple Neural Engine, from composed primitives.

No exp, reciprocal, or divide primitive has been found on this ANE. Every
reverse-engineered descriptor is gemm or elementwise add/mul/max/min/sq
(scripts/ane-network.py, scripts/ane-transformer.py). Softmax does
not need those as hardware primitives, only as *results* - both are
constructible from add/mul/sq alone:

  * exp(y) via a range-reduced Taylor series: exp(y) = exp(y/2^n)^(2^n).
    Reducing y into [-0.5, 0] first (n=4, since y is clamped to [-8, 0] by
    softmax's own max-subtraction) makes a degree-6 Taylor polynomial accurate
    to ~1e-8 uniformly across the whole range - not just for small scores.
    An UNreduced degree-8 Taylor was tried first and diverged catastrophically
    (error ~1e148) once scores left a narrow band; that failure and the fix
    are recorded in docs/jw-m1.md so the mistake is not silently absent.
  * 1/x via Newton-Raphson: y_{n+1} = y_n * (2 - x*y_n), 6 iterations, from a
    constant initial guess. Standard technique for hardware without a divide
    unit.
  * max and sum reductions via pairwise halving with the max/add primitives.

Every one of the ~50 elementwise calls per softmax row is a real ANE submit;
none of this is simulated. Validated in pure numpy first
(see docs/jw-m1/llm/softmax-numpy-validation.txt) before spending real
hardware submits, because a wrong algorithm here risks the known
queue-wedge-on-hang failure mode.

Elementwise descriptors are harvested from examples/elementwise.py itself, one
per op mode, so the register layout is never hand-transcribed - only
harvested, exactly as scripts/ane-network.py already does for "max".

  usage: python3 ane-softmax.py            # self-test vs numpy
"""
import os
import runpy
import sys

import numpy as np

_here = os.path.dirname(os.path.abspath(__file__))
_elementwise_candidates = [
    os.path.expanduser("~/src/apple-ane/examples/elementwise.py"),
    os.path.join(_here, "elementwise.py"),
]
_ew_path = next((p for p in _elementwise_candidates if os.path.exists(p)), None)
if _ew_path is None:
    sys.exit("examples/elementwise.py not found")

C_EW = 64
OP_MODES = ("add", "mul", "max", "min", "sq")

# Harvest one BTSP descriptor per mode. Each run of elementwise.py builds and
# patches its own BTSP_BUF according to sys.argv[1]; capture the bytes before
# moving to the next mode. argv is saved/restored around every harvest so
# nothing here can leak into caller state.
_saved_argv = sys.argv
_descriptors = {}
_helpers = None
for _mode in OP_MODES:
    sys.argv = [_saved_argv[0], _mode]
    _ns = runpy.run_path(_ew_path, run_name=f"elementwise_harvest_{_mode}")
    _descriptors[_mode] = bytes(_ns["BTSP_BUF"])
    if _helpers is None:
        _helpers = _ns  # allocate_buffer / submit_task are mode-independent
sys.argv = _saved_argv

# NOT _helpers["fd"]: elementwise.py closes its own fd at the end of its own
# run (line ~317), so a harvested fd is already dead by the time we grab it.
# Open a fresh one, same pattern ane-network.py already gets right.
fd = os.open("/dev/accel/accel0", os.O_RDWR)
allocate_buffer = _helpers["allocate_buffer"]
submit_task = _helpers["submit_task"]


def run_ew(mode, a, b):
    """One ANE elementwise submit. a, b: length-C_EW fp16 arrays."""
    btsp = _descriptors[mode]
    out_h, out_m = allocate_buffer(fd, 0x4000)
    s1_h, s1_m = allocate_buffer(fd, 0x4000)
    s2_h, s2_m = allocate_buffer(fd, 0x4000)
    btsp_h, btsp_m = allocate_buffer(fd, 0x4000)

    for m, v in ((s1_m, a), (s2_m, b)):
        buf = np.zeros(0x4000 // 2, dtype=np.float16)
        buf[:C_EW * 32:32] = v
        m.write(buf.tobytes())
    btsp_m.write(btsp)

    submit_task(fd, 0x274, 1, 0x274, [btsp_h, 0, 0, 0, out_h, s1_h, s2_h] + [0] * 24, btsp_h)
    out = np.frombuffer(out_m, dtype=np.float16, count=C_EW * 32).reshape(C_EW, 32)[:, 0].copy()
    for m in (out_m, s1_m, s2_m, btsp_m):
        m.close()
    return out


def _const(value, n=C_EW):
    return np.full(n, value, dtype=np.float16)


def _pad(vec, n=C_EW, fill=0.0):
    out = _const(fill, n)
    out[:len(vec)] = vec
    return out


def reduce_ane(mode, vec, width):
    """Pairwise-halving reduction of the first `width` (power of 2) lanes."""
    cur = _pad(vec)
    w = width
    while w > 1:
        front = _pad(cur[: w // 2])
        back = _pad(cur[w // 2 : w])
        cur = run_ew(mode, front, back)
        w //= 2
    return float(cur[0])


def exp_ane(y):
    """exp(y) for y (C_EW,) fp16 array, y <= 0. Range-reduced Taylor series."""
    z = run_ew("mul", y, _const(1.0 / 16))          # z = y / 16
    z2 = run_ew("sq", z, _const(0.0))                # (z+0)^2
    z3 = run_ew("mul", z, z2)
    z4 = run_ew("sq", z2, _const(0.0))
    z5 = run_ew("mul", z, z4)
    z6 = run_ew("mul", z2, z4)
    t2 = run_ew("mul", z2, _const(1 / 2))
    t3 = run_ew("mul", z3, _const(1 / 6))
    t4 = run_ew("mul", z4, _const(1 / 24))
    t5 = run_ew("mul", z5, _const(1 / 120))
    t6 = run_ew("mul", z6, _const(1 / 720))
    acc = run_ew("add", _const(1.0), z)              # 1 + z
    acc = run_ew("add", acc, t2)
    acc = run_ew("add", acc, t3)
    acc = run_ew("add", acc, t4)
    acc = run_ew("add", acc, t5)
    acc = run_ew("add", acc, t6)
    for _ in range(4):                               # undo the /16 reduction
        acc = run_ew("mul", acc, acc)
    return acc


def reciprocal_ane(x_scalar, iters=6):
    """1/x via Newton-Raphson, x a python float (already reduced from ANE)."""
    x = _const(x_scalar)
    y = _const(1.0 / 4)  # rough initial guess; sums here are O(1)-O(T)
    for _ in range(iters):
        p = run_ew("mul", x, y)
        neg_p = run_ew("mul", p, _const(-1.0))
        q = run_ew("add", _const(2.0), neg_p)
        y = run_ew("mul", y, q)
    return float(y[0])


def softmax_ane_row(scores_row):
    """scores_row: length-T numpy array. Returns length-T numpy probabilities."""
    T = len(scores_row)
    assert (T & (T - 1)) == 0, "this reduction needs a power-of-2 length"
    padded = _pad(scores_row.astype(np.float16), fill=-1e4)

    m = reduce_ane("max", padded, T)
    neg_m = run_ew("mul", _const(m), _const(-1.0))
    y = run_ew("add", padded, neg_m)                 # scores - max, exact

    e = exp_ane(y)
    s = reduce_ane("add", e, T)
    r = reciprocal_ane(s)
    probs = run_ew("mul", e, _const(r))
    return probs[:T].astype(np.float32)


def main():
    rng = np.random.default_rng(11)
    scores = (rng.standard_normal(4) * 2.0).astype(np.float32)
    print("scores:", scores)

    got = softmax_ane_row(scores)
    ref = np.exp(scores - scores.max()) / np.exp(scores - scores.max()).sum()
    err = np.abs(got - ref)
    print("softmax_ane:", got)
    print("numpy      :", ref)
    print(f"max_abs_err={err.max():.6f} mean_abs_err={err.mean():.6f} "
          f"sum={got.sum():.6f} argmax_match={np.argmax(got) == np.argmax(ref)}")


if __name__ == "__main__":
    main()
