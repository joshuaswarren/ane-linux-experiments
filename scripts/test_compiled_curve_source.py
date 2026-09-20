#!/usr/bin/env python3
"""Source test for --pass compiled-curve with a FAKE mlx module
(Main requirement): drives the REAL producer path end-to-end with a
stubbed mlx so that

  * the compiled function receives the ACTUAL weight/add arrays as
    dynamic arguments per call (host-side group selection - proven by
    the fake's call log: each measured segment of width w touches
    exactly the 3*w member dispatches of ALL its groups, never a
    closure-captured subset);
  * ALL groups are warmed before the first measured segment;
  * synchronize placement: one after warmup + one per segment;
  * per-segment walls are serialized in the sidecar.

No GPU, no real mlx, no numpy. Complements
test_calibration_capture_regression.py (the actual later tiny
calibration on hardware).
"""
import importlib.util
import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
MICRO = HERE / "qmm_weight_curve_micro.py"
sys.path.insert(0, str(HERE))

K, COLS = 2048, 896


class FakeArr:
    def __init__(self, marker, shape, nbytes):
        self.marker = marker
        self.shape = shape
        self.nbytes = nbytes

    def astype(self, dt):
        return self

    def all(self):
        return True

    def __add__(self, other):
        return FakeArr("sum", self.shape, self.nbytes)


class FakeMX:
    def __init__(self):
        self.log = []
        self._gid = 0
        self.random = self

    def normal(self, shape):
        self._gid += 1
        n = 1
        for d in shape:
            n *= d
        return FakeArr("t%d" % self._gid, shape, n * 2)

    def array(self, v):
        return FakeArr("arr%s" % v, (), 0)

    def eval(self, arg):
        pass

    def quantize(self, w, group_size=64, bits=4):
        n = 1
        for d in w.shape:
            n *= d
        return (FakeArr(w.marker + ":q", w.shape, n // 2),
                FakeArr(w.marker + ":s", (n // 64,), n // 64 * 2),
                FakeArr(w.marker + ":b", (n // 64,), n // 64 * 2))

    def quantized_matmul(self, x, wq, s, b, transpose=True,
                         group_size=64, bits=4):
        cols = wq.shape[0]
        self.log.append(("qmm", id(wq), cols, wq))
        return FakeArr("out", (1, cols), cols * 2)

    def isfinite(self, a):
        return a

    def synchronize(self):
        self.log.append(("sync",))

    def compile(self, fn):
        return fn


def install():
    core = FakeMX()
    fake_core = types.ModuleType("mlx.core")
    for name in ("array", "eval", "quantize", "quantized_matmul",
                 "isfinite", "synchronize", "compile", "random"):
        setattr(fake_core, name, getattr(core, name))
    fake_mlx = types.ModuleType("mlx")
    fake_mlx.core = fake_core
    fake_mlx.__version__ = "fake"
    fake_core.float16 = "f16"   # dtype token the fakes accept
    sys.modules["mlx"] = fake_mlx
    sys.modules["mlx.core"] = fake_core
    return core


def load_micro():
    spec = importlib.util.spec_from_file_location("micro_mod", MICRO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    import tempfile
    mod = load_micro()
    core = install()
    plan = mod.build_plan()
    n_groups = max(s["w"] for s in plan)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        ident = mod.pass_compiled_curve(
            types.SimpleNamespace(out=str(td / "identity.json"),
                                  profile=str(td / "prof.ndjson")),
            K, COLS, plan)
        assert not (td / "prof.ndjson").exists(), \
            "producer must not fabricate a profile offline"

        # --- dynamic selection + coverage from the fake call log ---
        qmm_ids = [entry[1] for entry in core.log if entry[0] == "qmm"]
        warm = qmm_ids[:n_groups * 3]
        assert len(set(warm)) == n_groups * 3, \
            "warmup must touch every group member at least once"
        rest = qmm_ids[n_groups * 3:]
        pos = 0
        for s in plan:
            used = rest[pos:pos + 3 * s["steps"]]
            assert len(used) == 3 * s["steps"], (len(used), s)
            # complete coverage: each segment touches ALL its groups;
            # each group call expands to 3 member dispatches, so a full
            # set of w groups has 3*w distinct member ids
            distinct = len(set(used))
            assert distinct == 3 * min(s["w"], s["steps"]), \
                f"w={s['w']}: distinct {distinct} != {3 * min(s['w'], s['steps'])}"
            pos += 3 * s["steps"]
        assert pos == len(rest), "extra measured calls beyond plan"
        syncs = sum(1 for entry in core.log if entry[0] == "sync")
        assert syncs == 1 + len(plan), syncs
        print("PASS: dynamic input selection (no closure capture), "
              "complete group coverage per segment, sync placement")

        # --- walls serialized in the sidecar ---
        ident = json.loads((td / "identity.json").read_text())
        walls = ident["walls"]
        assert len(walls) == len(plan)
        for w in walls:
            assert w["wall_avg_us"] >= 0
            assert w["steps"] == -(-mod.MIN_STEPS // w["w"]) * w["w"]
        assert ident["dynamic_args"] is True
        assert ident["outputs_finite"] is True
        print("PASS: per-segment walls serialized with dynamic_args=True, "
              "outputs_finite=True")


if __name__ == "__main__":
    main()
