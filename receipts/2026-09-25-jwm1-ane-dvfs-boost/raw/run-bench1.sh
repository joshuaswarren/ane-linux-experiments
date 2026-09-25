#!/bin/bash
# one bench rep (warmups 0, reps 1) at NORMAL priority with per-predict wall + schedstat(run_delay,run_time) + stime/utime ticks + cpu
set -u
cd /var/tmp/qwen38-layout-out
PROF_OUT=${PROF_OUT:-/var/tmp/parity7/prof-predicts-$(date +%H%M%S).json} PYTHONPATH=/var/tmp/gguf-py flock -w 600 /tmp/m1-gpu.lock   /var/tmp/jwm1-parity3-venv/bin/python /var/tmp/parity7/sqr-prof2.py   --gguf /var/tmp/Qwen3.8-2B-Q4_K_M.gguf   --export /var/tmp/qwen38-layout-anec   --libane-so /var/tmp/qwen38-layout-kit/bindings/python/dylib/libane_python.so   --ref /var/tmp/chunk_00.json   --backend-module /var/tmp/qwen38-layout-kit/tools/staged-qwen/libane_model.py --mode bench --warmups 0 --reps 1
