# Gates: Linux ANE speed crossover via persistent-buffer descriptor GEMM

Hypothesis: the ~2 ms per 512x256 tile call is dominated by per-call
BO_INIT/mmap/teardown ioctls, not device compute or the submit itself.
Persistent buffers + in-place kernel rewrite should cut the per-tile floor
enough that the full 248320x2048 tied head crosses CPU numpy (1.27 s) with
equal quality.

## G1: Persistent-buffer tile GEMM stays exact
One 512x256 random tile through the persistent path matches numpy fp32
reference (max_err < 0.01, argmax match); identity blob passes input
through unchanged.
  CHECK: ssh joshuawarren@100.84.184.102 'cd ~/src/ane-linux-experiments && python3 ane-gemm-fast.py --verify'
  EXPECT: PERSISTENT_GEMM_VERIFY_OK, exit 0
  STATUS: MET 2026-08-28 - identity passthrough ok, random 512x256
  max_err=0.0003 argmax ok, PERSISTENT_GEMM_VERIFY_OK exit 0.

## G2: Per-tile floor measured below 1.0 ms
Benchmark reports mean wall per tile call (persistent buffers, kernel
rewrite included) over >= 200 calls.
  CHECK: ssh joshuawarren@100.84.184.102 'cd ~/src/ane-linux-experiments && python3 ane-gemm-fast.py --bench'
  EXPECT: prints per-tile mean below 0.0010 s
  STATUS: MET 2026-08-28 - 0.304 ms/call with blob rewrite; submit-only
  floor 0.187 ms/call over 300 calls.

## G3: Full tied head crosses CPU
Full 248320x2048 head (pre-blobbed weights, 485x8 tiles) wall time beats
CPU numpy reference on the same host AND argmax + top-10 match with
max_err <= 0.05.
  CHECK: ssh joshuawarren@100.84.184.102 'cd ~/src/ane-linux-experiments && python3 ane-head-bench.py'
  EXPECT: prints ANE head wall < CPU head wall and QUALITY_OK
  STATUS: MET 2026-08-28 - ANE 791 ms vs CPU 1975 ms = 2.50x,
  max_err=0.0010, argmax ok, top10 10/10, HEAD_CROSSOVER_OK exit 0.

## G4: Receipts and commit
Results appended to receipts and committed on main.
  CHECK: git -C ~/src/ane-linux-experiments log --oneline -3
  EXPECT: crossover commits present, clean tree
  STATUS: MET 2026-08-28 - commits 04b0a10, 5a346ef, 8b02345, d10f118.

## G5: Full-model persistent head runs with CPU-matching quality
ANE logits match the CPU backend (generated token ids equal, argmax and
top-10 agreement); a wall-time comparison is recorded either way.
  CHECK: ssh joshuawarren@100.84.184.102 'cd ~/src/ane-linux-experiments && python3 ane-qwen-model.py -m ~/ane-models/Qwen3.8-2B-Q4_K_M.gguf -p "Hi" --backend ane --generate 2'
  EXPECT: generated_ids=[11, 488], next_token=628, ANE_QWEN_FULL_TOKEN_STEP_OK
  STATUS: MET 2026-08-28 - generated [11, 488], next 628; fp32 cross-check
  shift=0 max_err=0.0023. Timing recorded: ANE ~3.9 s/token vs CPU ~2.3 s;
  end-to-end speed parity NOT yet achieved (boundary documented).
