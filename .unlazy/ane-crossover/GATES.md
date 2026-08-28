# Gates: Linux ANE speed crossover via persistent-buffer descriptor GEMM

OWNS: ane-gemm-fast.py, ane-head-bench.py, ane-runtime.py, ane-qwen-model.py, receipts/**

Scope: persistent-buffer descriptor GEMM on the Linux ANE crosses CPU on the
full tied head with matching quality, integrated into the full-model path.

- [x] G1: persistent-buffer tile GEMM stays exact (identity passthrough; random 512x256 vs numpy)
  CHECK: ssh joshuawarren@100.84.184.102 'cd ~/src/ane-linux-experiments && python3 ane-gemm-fast.py --verify'
  EXPECT: PERSISTENT_GEMM_VERIFY_OK
  EVIDENCE: 2026-08-28 identity passthrough ok, random max_err=0.0003 argmax ok, exit 0

- [x] G2: per-tile floor below 1.0 ms over 300 calls
  CHECK: ssh joshuawarren@100.84.184.102 'cd ~/src/ane-linux-experiments && python3 ane-gemm-fast.py --bench'
  EXPECT: persistent tile floor below 1.000 ms/call
  EVIDENCE: 2026-08-28 0.304 ms/call with blob rewrite; 0.187 ms/call submit-only

- [x] G3: full tied head beats CPU with matching argmax and top-10
  CHECK: ssh joshuawarren@100.84.184.102 'cd ~/src/ane-linux-experiments && python3 ane-head-bench.py'
  EXPECT: HEAD_CROSSOVER_OK
  EVIDENCE: 2026-08-28 ANE 791 ms vs CPU 1975 ms = 2.50x, max_err=0.0010, argmax ok, top10 10/10

- [x] G4: receipts appended and crossover committed on main
  CHECK: git -C /home/joshuawarren/src/ane-linux-experiments log --oneline -3
  EXPECT: crossover commits present
  EVIDENCE: 2026-08-28 commits 04b0a10, 5a346ef, 8b02345, d10f118

- [x] G5: full-model ANE head matches CPU quality; timing recorded
  CHECK: ssh joshuawarren@100.84.184.102 'cd ~/src/ane-linux-experiments && python3 ane-qwen-model.py -m ~/ane-models/Qwen3.8-2B-Q4_K_M.gguf -p "Hi" --backend ane --generate 2'
  EXPECT: generated_ids=[11, 488] next_token=628 ANE_QWEN_FULL_TOKEN_STEP_OK
  EVIDENCE: 2026-08-28 generated [11, 488], next 628, fp32 shift=0 max_err=0.0023; ANE ~3.9 s/token vs CPU ~2.3 s (end-to-end parity open, boundary documented)
