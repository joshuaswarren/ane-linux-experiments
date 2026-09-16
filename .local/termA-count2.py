#!/usr/bin/env python3
"""Count copies/fills/submissions per decode token with the diag wheel."""
import ctypes, json, pathlib, subprocess, sys, os

MODEL = "/home/joshuawarren/models/Qwen2.5-0.5B-Instruct-4bit-mlx"
WHEEL = "/var/tmp/termA-diag/dist/mlx_omarchy-0.32.2.dev202609162015+diag.612eddc-cp314-cp314-linux_aarch64.whl"
BENCH = "/var/tmp/Jwm1AneAccelSmoke2-a9f14124/scripts/bench_decode.py"

def main():
    prompt_file = sys.argv[1]
    text = open(prompt_file).read()
    env = dict(os.environ)
    env.update({"MLX_DISABLE_COMPILE": "1", "HF_HUB_OFFLINE": "1"})
    p = subprocess.run(["/var/tmp/termA-diag-venv/bin/python", BENCH,
                        "--model", MODEL, "--prompt", text, "--tokens", "8",
                        "--temp", "0.0", "--seed", "0", "--warmup-tokens", "4",
                        "--wheel", WHEEL],
                       capture_output=True, text=True, env=env, timeout=600)
    print("bench rc", p.returncode, p.stdout.strip().splitlines()[-1][:120])

    # Now a separate short run that samples the trace counters around decode.
    # bench_decode does not expose counters; do it inline instead.
    sys.path.insert(0, "/var/tmp/DecodeEpilogueFold")
    os.environ["MLX_DISABLE_COMPILE"] = "1"
    os.environ["HF_HUB_OFFLINE"] = "1"
    from mlx.core import core as _c  # noqa: F401  (ensures lib loaded)
    import mlx.core as mx
    from mlx_lm import load, generate

    class Snapshot(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            "gpu_primitive_dispatches", "vk_submissions",
            "vk_buffer_copies", "vk_buffer_fills", "vk_compute_dispatches",
            "omarchy_finalize_calls", "commit_calls_with_work",
            "commit_calls_noop")]
    so = pathlib.Path(mx.__file__).parent / "lib" / "libmlx.so"
    lib = ctypes.CDLL(str(so))
    lib.mlx_omarchy_trace_snapshot.argtypes = [ctypes.POINTER(Snapshot)]
    snap = Snapshot()
    def read():
        lib.mlx_omarchy_trace_snapshot(ctypes.byref(snap))
        return {n: getattr(snap, n) for n, _ in Snapshot._fields_}

    model, tok = load(MODEL)
    msgs = [{"role": "user", "content": text}]
    prompt = tok.apply_chat_template(msgs, add_generation_prompt=True)
    before = read()
    out = ""
    toks = []
    for i in range(9):
        t = generate(model, tok, prompt=mx.array(prompt) if i == 0 else toks[-1],
                     max_tokens=1, temp=0.0)
        toks.append(t)
        after = read()
        print(f"tok{i}:", {k: after[k] - before[k] for k in after})
        before = after

if __name__ == "__main__":
    main()
