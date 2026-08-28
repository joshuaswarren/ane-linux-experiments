# Gates: Linux ANE speed crossover via persistent-buffer descriptor GEMM

Hypothesis: the ~2 ms per 512x256 tile call is dominated by per-call
BO_INIT/mmap/teardown ioctls, not device compute or the submit itself.
Persistent buffers + in-place kernel rewrite should cut the per-tile floor
enough that the full 248320x2048 tied head crosses CPU numpy (1.27 s) with
equal quality.

## G1: MET 2026-08-28 — PERSISTENT_GEMM_VERIFY_OK (identity passthrough ok, random 512x256 max_err=0.0003 argmax ok)

## G1: Persistent-buffer tile GEMM stays exact
One 512x256 random tile through the persistent path matches numpy fp32
reference (max_err < 0.01, argmax match); identity blob passes input
through unchanged.
  CHECK: ssh joshuawarren@100.84.184.102 'PYTHONPATH=$HOME/src/eiln-ane/bindings/python/python python3 ane-gemm-fast.py --verify'
  EXPECT: PERSISTENT_GEMM_VERIFY_OK, exit 0

## G2: MET 2026-08-28 — 0.187 ms/call submit-only, 0.304 ms/call with blob rewrite (300 calls)

## G2: Per-tile floor measured below 1.0 ms
Benchmark reports mean wall per tile call (persistent buffers, kernel
rewrite included) over >= 200 calls.
  CHECK: ssh joshuawarren@100.84.184.102 'python3 ane-gemm-fast.py --bench'
  EXPECT: prints per-tile mean below 0.0010 s

## G3: MET 2026-08-28 — HEAD_CROSSOVER_OK: ANE 791 ms vs CPU 1975 ms = 2.50x, max_err=0.0010, argmax ok, top10 10/10

## G3: Full tied head crosses CPU
Full 248320x2048 head (pre-blobbed weights, 485x8 tiles) wall time beats
CPU numpy reference on the same host AND argmax + top-10 match with
max_err <= 0.05.
  CHECK: ssh joshuawarren@100.84.184.102 'python3 ane-head-bench.py'
  EXPECT: prints ANE head wall < CPU head wall and QUALITY_OK

## G4: Receipts and commit
Results appended to receipts/ane-static-graph-loop.log (or a new
crossover receipt) and committed on main.
  CHECK: git log --oneline -1 && git status --short
  EXPECT: crossover commit present, clean tree
