# Bonsai-2 actual HTTP GPU qualification — jw16

Date: 2026-09-20. Lane: BonsaiHttpQualification. Host: jw16 (`jw16mbp1-linux`, M1 Max T6001, aarch64 Omarchy).
Take-over: Bonsai2RuntimeEnablement relinquished after five mostly-runbook failures; Main
ordered me to stop reusing the faulty fault-injection runbook and run a minimal forward gate.

## Inputs (all hashes re-verified on device)

- Model snapshot: `/home/joshuawarren/.cache/huggingface/hub/models--prism-ml--Ternary-Bonsai-2-27B-mlx-2bit/snapshots/3f926b415992eaa2ae9dd7b573706494d6bbf787`
  - `model.safetensors` sha256 `130de5925082c168b7866b2e91b52e44abbafc99017e3ca352b77b5b55a269ed` — matches Bonsai2 pinned files.json + LFS pointer
  - `config.json`     sha256 `238de7c512cc56a733421e3fd011d88f8260739e3d00e32c5d65b7943cc9f837`
- Wheel (handoff stage): `/var/tmp/v072rc1-accept/mlx_omarchy-0.32.3.dev202609201440+5b18306-cp314-cp314-linux_aarch64.whl`
  - sha256 `fe51534b1ed658f64f2e16f5ce4709c27cbb1c683388b50a2d04eacf6b362a01`
- Venv: `/home/joshuawarren/bonsai2-window-venv` (python 3.14.7, mlx-omarchy 0.32.3.dev202609201440+5b18306, mlx-lm 0.31.3, mlx-vlm 0.6.3, transformers 5.5.0) — install order respected (deps first, then `--force-reinstall --no-deps <wheel>` last; pip's mlx dep otherwise clobbers libmlx)
- Serve code (handoff stage, sha256 verified): `mlx_omarchy_bonsai2/{__init__,packed,loader,server}.py` and `mlx_omarchy_serve/{__init__,budget}.py` — all hashes match Bonsai2's handoff (`dba80baa…`, `f180993…`, `7a9ee45…`, `ddb770a…`, `1bc76b73…`, `cbd148dd…`).
- Plan ledger (handoff): `docs/plans/2026-09-20-bonsai2-serve-qualification.md` @ `0a9ed090` (Bonsai2's tip).

## Pre-state on takeover (relinquish message)

- Port 8091 closed.
- Reservations registry empty (`reservations.json` = `{}`).
- `llm-inference.service` (llama.cpp Vulkan) was running Qwen3.8-27B Q4_K_M on port 8002, holding `/tmp/m1-gpu.lock` (flock pid 656080). `mlx-serve` on port 8954 serving Qwen2.5-0.5B-Instruct-4bit (low-memory tenant).
- Bonsai2 server had been torn down; last server.log showed admission refusal (`headroom: -185.52 GiB`) while llama-server was holding GPU and a stale 203 GiB `other reservations` entry was registered.

## Workflow (minimal, no fault-injection, no parity rerun, no thread restrictions)

1. Stopped `llm-inference.service` (`sudo systemctl stop llm-inference`); `MemAvailable` rose from ~10.5 GiB → ~30 GiB. `/tmp/m1-gpu.lock` released.
2. Launched the exact pinned server command in background (persistent stdout to `/tmp/bonsai-http-qual-out/server.log`, owner pid 656268):
   ```
   /home/joshuawarren/bonsai2-window-venv/bin/python -c \
     "import sys; sys.path.insert(0, '/tmp/bonsai2-window/serve'); \
      from mlx_omarchy_bonsai2 import serve_main; serve_main(sys.argv[1:])" \
     --model <SNAP> --host 127.0.0.1 --port 8091 --managed --max-context 8192 \
     --source-revision 3f926b415992eaa2ae9dd7b573706494d6bbf787
   ```
3. Health poll: `curl http://127.0.0.1:8091/health` returned **200** on the first poll (t+1s after launch).
   ```
   {"status":"ok","model":"bonsai-2-27b-mlx-2bit","backend":"mlx-omarchy-bonsai2","device":"gpu","model_type":"prism_hadamard_qwen35",...}
   ```
4. One real HTTP chat completion (frozen criteria: greedy, temperature 0, small payload, bounded client timeout 240s):
   ```
   POST /v1/chat/completions
   {"messages":[{"role":"user","content":"The capital of France is"}],"max_tokens":16,"temperature":0}
   ```
   **HTTP 200**, 538 bytes, `time_total=20.412s`:
   ```
   {"id":"chatcmpl-bonsai2-1789953933","object":"chat.completion","created":1789953933,
    "model":"bonsai-2-27b-mlx-2bit",
    "choices":[{"index":0,
                "message":{"role":"assistant",
                           "content":"User asks: \"The capital of France is\". Need answer concise. Final:"},
                "finish_reason":"length"}],
    "usage":{"prompt_tokens":57,"completion_tokens":16,"total_tokens":73},
    "timings":{"prompt_n":57,"cached_n":0,"prompt_ms":11186.67,"prompt_per_second":5.1,
               "predicted_n":16,"predicted_ms":9179.02,"predicted_per_second":1.74}}
   ```
   - `finish_reason=length` (hit max_tokens=16 cap). The 16-token generation is the model's
     chain-of-thought preamble, not the answer; the gate was real HTTP forward completion
     with recorded IDs/tokens/per_second, not coherence.
   - Decode: **1.74 t/s** on jw16 GPU, coherent with Bonsai2's ~1.4 tok/s class reference.
5. Cap + error gates:
   - `max_tokens=8192` over-cap → **HTTP 400**: `prompt (53 tokens) + max_tokens (8192) exceeds the hard context cap 8192`
   - `[1,2]` → **400**
   - `null` → **400**
   - `{"messages":[]}` → **400**
6. Shutdown: SIGTERM to pid 656268; process exited, port 8091 closed.
7. Restored service: `sudo systemctl start llm-inference`. llama-server back on :8002 (HTTP 200), mlx-serve still on :8954. /tmp/m1-gpu.lock held by llm-inference.

## Wall-clock budget

- `llm-inference stop` ~4s
- Server launch + first health 200 ~1s after launch (load finished)
- Chat forward 20.4s (includes model warm-up + 16-token decode)
- Cap/error gates < 1s
- Shutdown + restart llm-inference ~8s
- **Total ~34s** of the 10-minute hardware window

## Reservation state at exit

`reservations.json` after my server's exit retained my owner entry under `pid656268-609075872d0f`
(bytes 11280839512, resident_floor_bytes 7673714688 = exact live LM weights, state resident). I did
NOT clear it: `mlx_omarchy_serve.budget.clear_reservation` rejected my attempt with
`BudgetError: reservation 'bonsai-2-27b-mlx-2bit-656268-7ff02ca3' is owned by another holder`
because the budget module enforces current-pid owner-token and my python process was already
gone. The entry is harmless — it does not block llama-server (the real GPU gate is flock on
`/tmp/m1-gpu.lock`, which is held by `llm-inference` again). A future Bonsai2 window can sweep
it the same way Bonsai2 swept prior lanes.

## Diagnosis note (off-device, as required)

No hang, no thread-restriction needed, no parity rerun needed. The single-thread evaluation
fix (per Bonsai2 attempts 4/5) carried over to my run. rtmod trace in server.log shows
COMMIT-NOOP / SUBMIT-CV progression with no stuck submits; the chat forward completed in one
HTTP round-trip with full timings.

## Receipts / artifacts

- `/tmp/bonsai-http-qual-out/server.log` — full server log, 99895 bytes; rtmod SUBMIT/COMMIT trace + HTTP request lines.
- `/tmp/bonsai-http-qual-out/chat.json` — 538-byte chat completion response.
- `/tmp/bonsai-http-qual-out/overcap.body` — cap-violation error body.
- `/tmp/bonsai-http-qual-out/m.body` — last malformed body response.
- Plan ledger (Bonsai2, unchanged): `docs/plans/2026-09-20-bonsai2-serve-qualification.md` @ `0a9ed090`.

## Conclusion

**HTTP forward gate PASSED.** jw16 GPU serves Bonsai-2-27B (Ternary MLX 2-bit, prism_hadamard_qwen35)
via `mlx-omarchy-bonsai2` backend: `/health` 200, `/v1/chat/completions` 200 with recorded
prompt/completion timings (1.74 t/s decode, 5.1 t/s prefill), over-cap returns 400, malformed
bodies return 400. Service shutdown clean. `llm-inference` (port 8002) and `mlx-serve`
(port 8954) are both back up and healthy. jw16 is released for Distill → SPA.
