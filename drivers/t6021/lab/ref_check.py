"""Exact check of y against a+b with fp16 round-half-away-from-zero (the ANE add rounding)."""
import sys

import numpy as np


def rha(exact):
    """float64 -> fp16, ties away from zero. exact holds sums of two fp16 values (exact in float64)."""
    r = exact.astype(np.float16)
    rf = r.astype(np.float64)
    direction = np.sign(exact - rf)
    other = np.nextafter(r, (direction * np.inf).astype(np.float16))
    of = other.astype(np.float64)
    tie = (direction != 0) & (np.abs(exact - rf) == np.abs(of - exact))
    bigger = np.where(np.abs(of) > np.abs(rf), other, r)
    return np.where(tie, bigger, r).astype(np.float16)


for step in sys.argv[1:]:
    root = "/sys/kernel/debug/ane_t6021_seq/"
    bufs = []
    for n in ("b00", "b01", "b02"):
        with open(root + f"s{step}{n}", "rb") as f:
            bufs.append(np.frombuffer(f.read(), "<f2"))
    a, b, y = bufs
    ref = rha(a.astype(np.float64) + b.astype(np.float64))
    same = int(np.count_nonzero(ref.view("<u2") == y.view("<u2")))
    sent = int(np.count_nonzero(y.view("<u2") == 0x7E00))
    print(f"step {step}: {same}/{y.size} bit-exact vs half-away reference; sentinel {sent}",
          "PASS" if same == y.size else "FAIL")
