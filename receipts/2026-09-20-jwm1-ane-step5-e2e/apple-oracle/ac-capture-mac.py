#!/usr/bin/env python3
"""ac-capture-mac.py — Apple-executed encoder golden via ANEForge e5rt runtime.

Runs ON macstudio (M1 Ultra, Mac13,2 — H13D family; CROSS-SOC DIAGNOSTIC vs
jwm1's T8103, caveat per Main — same family, NOT identical native hardware).

Compiles the pinned encoder-source MIL (model.mil + weights, sha-recorded)
with Apple's e5rt/ANECompilerService backend via ANEForge's _runtime, then
evals with the authentic staged inputs (capture npys, sha-recorded) and
preserves raw outputs. Records full provenance: target hardware, ANE bundle
family, compiler backend, MIL/weights/input/output hashes, timings.
"""
import hashlib, json, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, "/Users/joshuawarren/src/ANEForge")
from aneforge import _runtime  # noqa: E402

SRC = Path("/Users/joshuawarren/ac-capture/encoder-source")
CAP = Path("/Users/joshuawarren/ac-capture/inputs")
OUT = Path("/Users/joshuawarren/ac-capture/outputs")
OUT.mkdir(parents=True, exist_ok=True)

INPUTS = {"input_features": (1, 3000, 128), "attention_mask": (1, 3000)}
OUTPUTS = {"encoder_hidden": (1, 375, 640), "encoder_mask": (1, 375)}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dir_digest(root):
    h = hashlib.sha256()
    for f in sorted(Path(root).rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(root)).encode())
            h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


def main():
    import aneforge
    result = {
        "schema": "apple-ac-capture/1",
        "date": "2026-09-20",
        "classification": "CROSS-SOC DIAGNOSTIC — Apple M1 Ultra H13D ANE execution of the pinned encoder graph; NOT jwm1 T8103 native hardware; valid compiler/oracle diagnostic with explicit caveat",
        "status_2026-09-20_2345": "COMPILE BLOCKED: e5rt rejects the Linux-exported model.mil dialect ('program(1)' header + external model-root blob store; e5rt parser: line 1:8 got '1' expecting 'FP' — expects self-contained MIL+weight-pool container). Adapter needed: embed blob pool / convert container, or Apple-side island sub-MIL extraction. Staging + driver complete and preserved.",
        "provenance": {
            "mil_sha256": sha(SRC / "model.mil"),
            "weights_note": "weights.bin inside model-root blob store; root sha below",
            "source_root": {"file_count": sum(1 for _ in SRC.rglob("*") if _.is_file()),
                            "total_bytes": sum(_.stat().st_size for _ in SRC.rglob("*") if _.is_file()),
                            "root_digest": dir_digest(SRC)},
            "compiler_backend": "Apple e5rt/ANECompilerService via ANEForge _runtime (libane_e5rt_dispatch.dylib)",
            "aneforge_version": getattr(aneforge, "__version__", "unknown"),
            "host": "macstudio (Apple M1 Ultra, Mac13,2)",
        },
    }
    try:
        result["provenance"]["chip"] = subprocess_chip()
    except Exception as e:
        result["provenance"]["chip"] = f"probe-failed: {e}"

    t0 = time.monotonic_ns()
    rt = _runtime.E5RT()
    prog = rt.compile(
        str(SRC / "model.mil"),
        inputs=INPUTS,
        outputs=OUTPUTS,
        cache_dir="/Users/joshuawarren/ac-capture/e5rt-cache",
    )
    result["compile_ms"] = round((time.monotonic_ns() - t0) / 1e6, 1)

    in_a = {
        "input_features": np.load(CAP / "encoder_input_features.npy"),
        "attention_mask": np.load(CAP / "encoder_input_mask.npy"),
    }
    result["inputs"] = {k: {"sha256": sha_file_arr(v), "dtype": str(v.dtype), "shape": list(v.shape)} for k, v in in_a.items()}

    t1 = time.monotonic_ns()
    out = prog.eval(in_a)
    t2 = time.monotonic_ns()
    result["eval_ms"] = round((t2 - t1) / 1e6, 1)

    outs = {}
    for name, arr in out.items():
        p = OUT / f"{name}.npy"
        np.save(p, arr)
        outs[name] = {"shape": list(arr.shape), "dtype": str(arr.dtype), "sha256": sha(p)}
    result["outputs"] = outs

    # measurement vs the device-side encoder hidden (cross-compiler)
    try:
        dev = np.load("/Users/joshuawarren/ac-capture/device_hidden_fp32.npy").astype(np.float32)
        app = np.asarray(out["encoder_hidden"]).astype(np.float32)
        if dev.shape == app.shape:
            d = np.abs(dev - app)
            result["vs_device_hidden"] = {
                "device_fp32_sha256_ref": "f4dbfff3c91da384431b21bf53efae8c6c7f075bf27b19393fa310703644199f",
                "max_abs": float(d.max()),
                "mean_abs": float(d.mean()),
                "corr": float(np.corrcoef(dev.reshape(-1), app.reshape(-1))[0, 1]),
                "note": "cross-compiler (Apple e5rt/ANE vs Linux mil-hwxc/Vulkan+ANE stack) — measurement only, no criterion change",
            }
        else:
            result["vs_device_hidden"] = {"shape_mismatch": [list(dev.shape), list(app.shape)]}
    except FileNotFoundError:
        result["vs_device_hidden"] = "device hidden not staged — compare offline"

    json.dump(result, open(OUT / "capture-result.json", "w"), indent=1)
    print(json.dumps(result, indent=1))


def sha_file_arr(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def subprocess_chip():
    import subprocess
    out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True)
    return out.stdout.strip()


if __name__ == "__main__":
    main()
