#!/usr/bin/env python3
"""apple_remed_min.py — A/C island remediation on macstudio (rewritten, complete).
(1) Identity/onehot binding test on the A island (EXACT byte comparison).
(2) A MIL rebuild with const_7 INSIDE (3 func params; q_scaled derived in-graph).
(3) C island unchanged (prior Apple output sha re-verified).
(4) Per-element ULP histogram vs numpy fp32 reference on the SAME input bytes.
(5) Structured remediation-result.json + raw npys.
"""
import hashlib, json, platform, subprocess, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, "/Users/joshuawarren/src/ANEForge")
import aneforge
from aneforge import _runtime

ROOT = Path("/Users/joshuawarren/ac-capture")
ISL_A = ROOT / "island-A"
ISL_C = ROOT / "island-C"
OUT_A = ROOT / "outputs-island-A-correct"
BI = ('[buildInfo = dict<string, string>('
      '{{"coremlc-component-MIL", "3520.4.1"}, {"coremlc-version", "3520.5.1"}})]')
CONST7_OFFSET = 475477696   # genuine pair3 offset of op_7_to_fp16 (fp16 0.125)

def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha(p): return sha_bytes(Path(p).read_bytes())
def sha_arr(a): return sha_bytes(np.ascontiguousarray(a).tobytes())

def link_real_weights(dest: Path):
    """Symlink the REAL pair3 weights.bin (synthetic tiny blobs fail e5rt blob-bind)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        dest.symlink_to("/Users/joshuawarren/ac-capture/e5rt-pair3/weights.bin")

def a_mil_text():
    """A island, 3 func params, const_7 inside, exact pair3 semantics."""
    body = "\n".join([
        '    fp16 const_7_to_fp16 = const()[name = string("op_7_to_fp16"), val = fp16(0x1.0p-3)];',
        '    tensor<fp16, [1, 8, 375, 749]> attention_scores_1 = matmul(transpose_x = bool(false), '
        'transpose_y = bool(false), x = q_v, y = pos_kT)[name = string("attention_scores_1")];',
        '    tensor<fp16, [1, 8, 375, 128]> mul_0_cast_fp16 = mul(x = q_v, y = const_7_to_fp16)'
        '[name = string("mul_0_cast_fp16")];',
        '    bool matmul_0_transpose_y_0 = const()[name = string("matmul_0_transpose_y_0"), val = bool(true)];',
        '    bool matmul_0_transpose_x_0 = const()[name = string("matmul_0_transpose_x_0"), val = bool(false)];',
        '    tensor<fp16, [1, 8, 375, 375]> matmul_0 = matmul(transpose_x = matmul_0_transpose_x_0, '
        'transpose_y = matmul_0_transpose_y_0, x = mul_0_cast_fp16, y = k_headsT)[name = string("matmul_0")];',
    ])
    return ("program(1.3)\n" + BI + "\n{\n"
            "    func main<ios18>("
            "tensor<fp16, [1, 8, 375, 128]> q_v, "
            "tensor<fp16, [1, 8, 375, 128]> k_headsT, "
            "tensor<fp16, [1, 8, 128, 749]> pos_kT) {\n"
            + body + "\n    } -> (attention_scores_1, matmul_0);\n}\n")

A_IN = {"q_v": [1, 8, 375, 128], "k_headsT": [1, 8, 375, 128], "pos_kT": [1, 8, 128, 749]}
A_OUT = {"attention_scores_1": [1, 8, 375, 749], "matmul_0": [1, 8, 375, 375]}
C_IN = {"probs": [1, 8, 375, 375], "v_heads": [1, 8, 375, 128]}
C_OUT = {"attn_output_1": [1, 8, 375, 128]}

def compile_eval(mil: Path, arrays: dict, outputs: dict, cache: str):
    rt = _runtime.E5RT()
    t0 = time.monotonic_ns()
    inputs = {k: tuple(v.shape) for k, v in arrays.items()}
    prog = rt.compile(str(mil), inputs=inputs, outputs=outputs, cache_dir=cache)
    compile_ms = round((time.monotonic_ns() - t0) / 1e6, 1)
    t1 = time.monotonic_ns()
    out = prog.eval(arrays)
    eval_ms = round((time.monotonic_ns() - t1) / 1e6, 1)
    return out, compile_ms, eval_ms

def ulp_hist(apple: np.ndarray, ref32: np.ndarray):
    """Per-element ULP distance between apple fp16 and fp32-reference rounded to fp16."""
    a16 = apple.astype(np.float16)
    r16 = ref32.astype(np.float16)
    assert a16.shape == r16.shape
    ai = a16.view(np.uint16).astype(np.int64)
    ri = r16.view(np.uint16).astype(np.int64)
    d = np.abs(ai - ri)
    hist = {
        "ulp0": int((d == 0).sum()),
        "ulp1": int((d == 1).sum()),
        "ulp2": int((d == 2).sum()),
        "ulp3_5": int(((d >= 3) & (d <= 5)).sum()),
        "gt5": int((d > 5).sum()),
        "total": int(d.size),
    }
    f32 = np.abs(a16.astype(np.float32) - r16.astype(np.float32))
    return hist, {"max_abs": float(f32.max()), "mean_abs": float(f32.mean()),
                  "mismatch_frac": float((a16 != r16).mean())}

def main():
    result = {"schema": "apple-remediation/1", "date": "2026-09-21",
              "host": "macstudio M1 Ultra (Mac13,2)", "runtime": {
                  "aneforge_version": getattr(aneforge, "__version__", "unknown"),
                  "macos": subprocess.run(["sw_vers"], capture_output=True, text=True).stdout.strip(),
                  "chip": subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                         capture_output=True, text=True).stdout.strip(),
              }}
    print("=== RUNTIME ==="); print(json.dumps(result["runtime"], indent=1))

    # ---- inputs from the staged, sha-pinned fixtures ----
    q_v = np.load(ISL_A / "input_q_v.npy")
    k_headsT = np.load(ISL_A / "input_k_headsT.npy")
    pos_kT = np.load(ISL_A / "input_pos_kT.npy")
    probs = np.load(ISL_C / "input_probs.npy")
    v_heads = np.load(ISL_C / "input_v_heads.npy")
    result["input_shas"] = {
        "A_q_v": sha_arr(q_v), "A_k_headsT": sha_arr(k_headsT), "A_pos_kT": sha_arr(pos_kT),
        "C_probs": sha_arr(probs), "C_v_heads": sha_arr(v_heads)}
    print("=== INPUT BOUNDARY (sha256 of raw bytes) ===")
    for k, v in result["input_shas"].items():
        print(f"  {k}: {v}")

    # ---- STEP 1: identity/onehot test (EXACT) ----
    print("\n=== STEP 1: IDENTITY/ONEHOT BINDING TEST ===")
    tdir = ROOT / "island-A-correct/test"
    tdir.mkdir(parents=True, exist_ok=True)
    link_real_weights(tdir / "weights.bin")
    (tdir / "model.mil").write_text(a_mil_text())
    onehot = np.zeros((1, 8, 375, 128), dtype=np.float16); onehot[0, 0, 0, 0] = 1.0
    test_arrays = {"q_v": onehot, "k_headsT": k_headsT, "pos_kT": np.zeros_like(pos_kT)}
    t_out, t_cms, t_ems = compile_eval(
        tdir / "model.mil", test_arrays, A_OUT, str(tdir / "e5rt-cache"))
    attn_t, mm_t = t_out["attention_scores_1"], t_out["matmul_0"]
    exp_attn = np.zeros((1, 8, 375, 749), dtype=np.float16)          # q_v @ zeros(pos_kT) == 0
    # matmul_0 = (0.125*q_v) @ k_headsT^T ; with q_v=onehot(e0): row0 = 0.125*K[0,:], all other rows 0
    exp_mm32 = np.zeros((1, 8, 375, 375), dtype=np.float32)
    exp_mm32[0, 0, 0, :] = k_headsT[0, 0, :, 0].astype(np.float32) * np.float32(0.125)
    exp_mm = exp_mm32.astype(np.float16)
    attn_exact = bool(np.array_equal(attn_t, exp_attn))
    mm_exact = bool(np.array_equal(mm_t, exp_mm))
    dev = np.abs(mm_t.astype(np.float32) - exp_mm.astype(np.float32))
    mm_max_dev = float(dev.max())
    dev_loc = np.unravel_index(int(dev.argmax()), dev.shape)
    print(f"    dev@{dev_loc}: apple={mm_t[dev_loc]} exp={exp_mm[dev_loc]}")
    print(f"    apple row0[:6]={mm_t[0,0,0,:6].tolist()} exp row0[:6]={exp_mm[0,0,0,:6].tolist()}")
    print(f"    apple col0[:6]={mm_t[0,0,:6,0].tolist()} exp col0[:6]={exp_mm[0,0,:6,0].tolist()}")
    print(f"    nonzero rows in apple: {int((mm_t.reshape(375,-1).astype(np.float32).max(axis=1) != 0).sum())}")
    result["identity_test"] = {
        "compile_ms": t_cms, "eval_ms": t_ems,
        "attention_scores_1_all_zero": attn_exact,
        "matmul_0_exact_match": mm_exact,
        "matmul_0_max_abs_dev_from_hand_computed": mm_max_dev,
        "pass": bool(attn_exact and mm_exact)}
    print(f"  scores==zeros (pos_kT=0): {attn_exact}")
    print(f"  matmul_0 == hand-computed onehot row (EXACT): {mm_exact}  (max dev {mm_max_dev})")

    # ---- STEP 2-4: rebuilt A on REAL staged inputs + ULP histogram ----
    print("\n=== STEP 2-4: REBUILT A (const_7 inside) + ULP vs numpy ===")
    adir = ROOT / "island-A-correct"
    link_real_weights(adir / "weights.bin")
    (adir / "model.mil").write_text(a_mil_text())
    real_in = {"q_v": q_v, "k_headsT": k_headsT, "pos_kT": pos_kT}
    a_out, a_cms, a_ems = compile_eval(adir / "model.mil", real_in, A_OUT,
                                       str(ROOT / "e5rt-cache-island-correct"))
    ap_attn, ap_mm = a_out["attention_scores_1"], a_out["matmul_0"]
    np_attn32 = np.matmul(q_v.astype(np.float32), pos_kT.astype(np.float32))
    np_mm32 = np.matmul((q_v.astype(np.float32) * np.float32(0.125)),
                        k_headsT.astype(np.float32).transpose(0, 1, 3, 2))
    h_attn, s_attn = ulp_hist(ap_attn, np_attn32)
    h_mm, s_mm = ulp_hist(ap_mm, np_mm32)
    OUT_A.mkdir(parents=True, exist_ok=True)
    np.save(OUT_A / "attention_scores_1.npy", ap_attn)
    np.save(OUT_A / "matmul_0.npy", ap_mm)
    result["A_rebuilt"] = {
        "mil": str(adir / "model.mil"), "mil_sha256": sha(adir / "model.mil"),
        "weights_bin": "symlink -> e5rt-pair3/weights.bin (sha 95be02ec168f3c3d4eee9db5d9eac8187bc050c99fc1c3672c95f8adbcdbe5cb)",
        "func_params": ["q_v", "k_headsT", "pos_kT"],
        "const_7": "INLINE fp16 literal 0x1.0p-3 (=0.125); BLOBFILE path ABANDONED - pair3 blob offsets bind WRONG bytes (blob-record headers, not payload); see blob_binding_finding",
        "compile_ms": a_cms, "eval_ms": a_ems,
        "outputs": {"attention_scores_1": {"sha256": sha_arr(ap_attn), **s_attn, "ulp_hist": h_attn},
                     "matmul_0": {"sha256": sha_arr(ap_mm), **s_mm, "ulp_hist": h_mm}}}
    print(f"  A rebuilt compile_ms={a_cms} eval_ms={a_ems}")
    print(f"  attention_scores_1: sha={result['A_rebuilt']['outputs']['attention_scores_1']['sha256'][:16]} hist={h_attn}")
    print(f"  matmul_0:           sha={result['A_rebuilt']['outputs']['matmul_0']['sha256'][:16]} hist={h_mm}")

    # ---- STEP 5: C re-verify against prior Apple output sha ----
    print("\n=== STEP 5: C RE-VERIFY (prior sha 4e45274f...) ===")
    prev = Path(ROOT / "outputs-island-C/attn_output_1.npy")
    prev_sha = sha_arr(np.load(prev)) if prev.exists() else None
    c_out, c_cms, c_ems = compile_eval(ISL_C / "model.mil",
                                       {"probs": probs, "v_heads": v_heads}, C_OUT,
                                       str(ISL_C / "e5rt-cache"))
    cur_sha = sha_arr(c_out["attn_output_1"])
    np_c32 = np.matmul(probs.astype(np.float32), v_heads.astype(np.float32))
    h_c, s_c = ulp_hist(c_out["attn_output_1"], np_c32)
    np.save(OUT_A / "attn_output_1_C_reverify.npy", c_out["attn_output_1"])
    result["C_reverify"] = {
        "prior_run_sha256": prev_sha, "this_run_sha256": cur_sha,
        "byte_identical": bool(prev_sha == cur_sha),
        "compile_ms": c_cms, "eval_ms": c_ems,
        "output": {"sha256": cur_sha, **s_c, "ulp_hist": h_c}}
    print(f"  prior={str(prev_sha)[:16]} this={str(cur_sha)[:16]} identical={prev_sha == cur_sha}")
    print(f"  C ulp hist={h_c}")

    result["blob_binding_finding"] = {
        "symptom": "BLOBFILE scalar bound a wrong value (effective 0.033975 vs expected 0.125; ratio 0.2718 constant across all outputs)",
        "file_bytes_at_declared_offset": "0xBEEF sentinel + version (blob-record header), not payload",
        "search": "neither fp16(0.125) nor effective-scalar bytes exist anywhere in the 64KB window; 0.125 absent from region",
        "scope": "ALL 740 BLOBFILE refs in pair3-derived e5rt programs are suspect; params-only paths (C island, attention_scores_1) are proven correct",
        "workaround": "inline typed scalar literals (fp16(0x1.0p-3)) instead of BLOBFILE for scalars; weight TENSORS still need a working blob path (open defect)"}
    result["overall_pass"] = bool(result["identity_test"]["pass"]
                                   and result["C_reverify"]["byte_identical"])
    dest = ROOT / "remediation-result.json"
    dest.write_text(json.dumps(result, indent=1))
    print("\n=== WROTE ===")
    print(f"  {dest}")
    print(f"  outputs dir: {OUT_A}")
    print(json.dumps({"overall_pass": result["overall_pass"]}, indent=1))

if __name__ == "__main__":
    main()
