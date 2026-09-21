#!/usr/bin/env python3
"""ac-native-golden-test.py — A/C islands vs AUTHENTIC NATIVE goldens.

Main directive 2026-09-20: exact criterion UNCHANGED; accumulation class derived
from the compiler graph (see ac-accumulation-class-static.py output: fp32-accum,
single rounding, K<=512 => NOT chunked => exact-fp16 is the derived contract);
criterion is NEVER adjusted from results.

Protocol:
  1. Authenticity gate: staged input bytes must match stage-manifest sha256s
     (authentic capture-derived inputs, NOT synthetic).
  2. Native goldens: fresh fp32@fp32 -> fp16 numpy GEMMs on the SAME staged
     bytes (September stage.py semantics), cross-checked against the staged
     reference bins.
  3. Device: AneIsland.submit in LAUNCH mode (one process per submit), islands
     island-attn-a-kt (A) and island-pv (C), one iteration each.
  4. Comparison: EXACT fp16 equality (+-0 signed-zero equivalence). Deviation
     metrics (mismatch count, max_abs, ULP histogram, per-head corr) are
     RECORDED AS MEASUREMENT ONLY — they never relax the verdict.

Run with the v072rc1 venv python on jwm1. Writes ac-native-golden-result.json.
"""
import hashlib, json, os, sys, time
import numpy as np
import mlx.core as mx  # v072rc1 venv; fail fast if wrong interpreter

sys.path.insert(0, "/var/tmp/encwall-v071/base")
os.environ.setdefault("ANE_ISLAND_MODE", "launch")  # one process per submit
from vulkan_encoder import AneIsland  # noqa: E402

STAGE = "/var/tmp/IslandsExecJwm1/stage"
MANIFEST = "/var/tmp/IslandsExecJwm1/stage-manifest.json"
WORKER = "/var/tmp/jwm1-ane-step2/ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker"
LIBANE = "/var/tmp/jwm1-ane-step2/libane.so"
BUNDLES = "/var/tmp/jwm1-ane-step2/bundles"
SCRATCH = "/var/tmp/jwm1-ane-step2/ac-native-golden-scratch"
OUT_JSON = "/var/tmp/jwm1-ane-step2/ac-native-golden-result.json"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def load_staged(manifest, key):
    e = manifest["staged"][key]
    p = os.path.join(STAGE, e["file"])
    got = sha(p)
    assert got == e["sha256"], f"authenticity FAIL {key}: {got} != {e['sha256']}"
    a = np.fromfile(p, dtype="<f2").reshape(e["shape"])
    return a, p, got


def native_matmul_f16(a_f16, b_f16):
    """September stage.py semantics: (a.f32 @ b.f32).astype(f16), head-batched."""
    return (a_f16.astype(np.float32) @ b_f16.astype(np.float32)).astype("<f2")


def ulp_histogram(dev_u16, ref_u16):
    d = (dev_u16.astype(np.int32) - ref_u16.astype(np.int32))
    hist = {}
    for v in d:
        hist[int(v)] = hist.get(int(v), 0) + 1
    return dict(sorted(hist.items(), key=lambda kv: -kv[1])[:8])


def per_head_corr(dev, ref, heads):
    out = []
    dv = dev.astype(np.float32).reshape(heads, -1)
    rv = ref.astype(np.float32).reshape(heads, -1)
    for h in range(heads):
        a, b = dv[h], rv[h]
        c = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else float("nan")
        out.append(round(c, 6))
    return out


def compare(name, dev_path, ref_arr):
    dev = np.fromfile(dev_path, dtype="<f2")
    ref = ref_arr.reshape(-1)
    assert dev.size == ref.size, f"{name}: size {dev.size} != {ref.size}"
    du, ru = dev.view("<u2"), np.ascontiguousarray(ref).view("<u2")
    # exact fp16 equality with +-0 equivalence
    dev_f, ref_f = dev.astype(np.float32), ref.astype(np.float32)
    eq = (du == ru) | ((dev_f == 0) & (ref_f == 0))
    mism = int((~eq).sum())
    diff = np.abs(dev_f - ref_f)
    return {
        "output": name,
        "elements": int(dev.size),
        "exact_pass": bool(mism == 0),
        "mismatch_count": mism,
        "max_abs": float(diff.max()),
        "ulp_histogram_top": ulp_histogram(du, ru) if mism else {},
        "per_head_corr": per_head_corr(dev, ref, 8),
        "device_sha256": sha(dev_path),
    }


def main():
    manifest = json.load(open(MANIFEST))
    result = {"schema": "ac-native-golden/1", "date": "2026-09-20",
              "criterion": "EXACT fp16 equality (+-0), unchanged — never adjusted from results",
              "accumulation_class": "fp32-accumulate single rounding, K<=512, not chunked (static derivation)",
              "authenticity": {}, "islands": {}}

    # 1. authenticity gate
    for key in ("A/q_v", "A/pos_kT", "A/q_scaled", "A/k_headsT", "C/probs", "C/v_heads"):
        _, p, got = load_staged(manifest, key)
        result["authenticity"][key] = got

    q_v, _, _ = load_staged(manifest, "A/q_v")
    pos_kT, _, _ = load_staged(manifest, "A/pos_kT")
    q_scaled, _, _ = load_staged(manifest, "A/q_scaled")
    k_headsT, _, _ = load_staged(manifest, "A/k_headsT")
    probs, _, _ = load_staged(manifest, "C/probs")
    v_heads, _, _ = load_staged(manifest, "C/v_heads")

    # 2. native goldens from the SAME staged bytes + cross-check vs staged refs
    ref_matmul0 = native_matmul_f16(q_scaled, k_headsT)          # [1,8,375,375]
    ref_attn_out = native_matmul_f16(probs, v_heads)             # [1,8,375,128]
    staged_ref_m0 = os.path.join(STAGE, "A_ref_matmul_0.bin")
    staged_ref_pv = os.path.join(STAGE, "C_ref_attn_output_1.bin")
    xcheck_m0 = np.fromfile(staged_ref_m0, dtype="<f2")
    xcheck_pv = np.fromfile(staged_ref_pv, dtype="<f2")
    result["native_golden_crosscheck"] = {
        "matmul_0_fresh_equals_staged_ref": bool(np.array_equal(ref_matmul0.reshape(-1).view("<u2"), xcheck_m0.view("<u2"))),
        "attn_output_fresh_equals_staged_ref": bool(np.array_equal(ref_attn_out.reshape(-1).view("<u2"), xcheck_pv.view("<u2"))),
    }

    # 3. device submits (launch mode)
    island = AneIsland(worker=__import__("pathlib").Path(WORKER),
                       libane=__import__("pathlib").Path(LIBANE),
                       bundles=__import__("pathlib").Path(BUNDLES),
                       scratch=__import__("pathlib").Path(SCRATCH),
                       deadline_ms=20000)
    t0 = time.monotonic_ns()
    ra = island.submit("island-attn-a-kt", "acgold-A",
                       {"q_v": mx.array(q_v), "pos_kT": mx.array(pos_kT),
                        "q_scaled": mx.array(q_scaled), "k_headsT": mx.array(k_headsT)},
                       {"attention_scores_1": ([1, 8, 375, 749], "fp16"),
                        "matmul_0": ([1, 8, 375, 375], "fp16")})
    rc = island.submit("island-pv", "acgold-C",
                       {"probs": mx.array(probs), "v_heads": mx.array(v_heads)},
                       {"attn_output_1": ([1, 8, 375, 128], "fp16")})
    result["device_ms"] = round((time.monotonic_ns() - t0) / 1e6, 1)

    # 4. exact compare under unchanged criterion
    result["islands"]["A_matmul_0"] = compare("matmul_0", ra["matmul_0"], ref_matmul0)
    result["islands"]["A_attention_scores_1"] = compare("attention_scores_1", ra["attention_scores_1"], native_matmul_f16(q_v, pos_kT))
    result["islands"]["C_attn_output_1"] = compare("attn_output_1", rc["attn_output_1"], ref_attn_out)

    result["verdict_exact_criterion"] = "PASS" if all(v["exact_pass"] for v in result["islands"].values()) else "FAIL"
    json.dump(result, open(OUT_JSON, "w"), indent=1)
    print(json.dumps(result, indent=1))
    island.close()


if __name__ == "__main__":
    main()
