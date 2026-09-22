# Encoder pipelining / issue-loop compile / extra islands: all three levers measured NO-GO (2026-09-22)

Branch: `agent/ane-inprocess-submit` (mlx-omarchy worktree
`~/src/ane-linux-experiments/.local/ane-v064-wt`), commits `2a3dbdf1c`,
`967f884c3`. Runner deployed to both hosts
(`/var/tmp/encwall-decomp/inproc-tmp/vulkan_encoder_inproc.py`,
sha `a49aedc1...`); pre-change backup `*.bak-20260922` on each. The
pipelining code is env-gated (`ANE_ASYNC_ISLANDS=1`, default OFF) and inert.

## Baselines (unchanged by this lane — all levers NO-GO)

| host | encoder_ane median | source | ratio to divisor |
| --- | ---: | --- | ---: |
| m1-host (T8103, divisor 113 ms) | 3485.3 ms | kab-20260922T065043 cached-module | 30.8 |
| m1-host | 3401.9 / 3509.6 ms | kab-20260922T072635 out-B-meas-1/-3 | 30.1 / 31.1 |
| m1max-host (T6001, divisor 158 ms) | 1187.7 / 1198.3 / 1228.7 ms | inproc-20260921T183101/185634/190204 | 7.5–7.8 |

Updated ratio to divisor: **m1-host ≈ 30–31, m1max-host ≈ 7.5–7.8 — unchanged**; no
lever moved the wall, so the divisors stand.

## Lever 1 — cross-layer async island pipelining: NO-GO (structural)

Two independent kill reasons, both measured:

1. **Dependency chain is strictly serial.** The per-layer graph alternates
   GPU → ANE → GPU: softmax/FFN consume island A/C outputs before the next
   island's inputs are produced, so at every submit block the GPU queue is
   empty — there is no independent feeder work to issue ahead. This is the
   same "data-dependent serial chain" the 2026-09-21 in-process-submit
   receipt recorded for spawn windows.
2. **MLX streams are thread-local.** `mx.eval` of a graph built on another
   thread raises `RuntimeError: There is no Stream(gpu, N) in current
   thread` — with N=0 in the encoder stage and N=1 in the mel-frontend
   pass (fused_e2e enters a different per-stage stream context). Worker-
   thread marshal fails in every variant, including a stream captured on
   the main thread (`Stream(gpu,0)` object is not registered in the worker)
   and `mx.stream(mx.default_stream(mx.gpu))` resolved inside the worker.
   Evidence: m1max-host smoke logs
   `pipe-20260922T074939/075624/log-B-smoke-pipeline.txt` (three distinct
   tracebacks). The marshal-on-main redesign (commit `967f884c3`) keeps all
   MLX graph work on the calling thread and ships for the record, but the
   overlap it can express is exactly the part the dependency chain forbids.

Also measured from clean-run island logs: dev send+exec+read ≈
1.25 + 0.64 + 3.4 ≈ 5.3 ms/island — the entire hideable budget even if
overlap were possible (~250 ms/pass), versus a marshaled wall of ~85
ms/layer that is real GPU feeder compute, not waste.

## Lever 2 — compile/batch the CPU issue loop: NO-GO by ceiling measurement

Feeder issue-wall per op, clean m1-host runs (kab-20260922T072635
`out-B-meas-1`, enc_ane 3401.9 ms; feeder_ops sums over 48 islands):

| op | n | wall | what it is |
| --- | ---: | ---: | --- |
| matmul (island submits) | 47 | 2649.4 ms | GPU-drain wait at island marshal — not issue |
| const | 1983 | 349.7 ms | blob view creation (post batched-upload path 745→351 ms, commit 8a6f3e7e4) — data marshaling, not dispatch |
| conv | 74 | 205.8 ms | GPU compute (pointwise convs) |
| everything else | ~1100 | ~60 ms | linear/LN/elementwise issue |

m1max-host ceiling trace (ceiling-20260922T081317, stmt trace): island-like
statements 1113.2 ms, all non-island statements ≥5 ms sum **246.8 ms**,
matching the m1-host structure.

`mx.compile` removes dispatch overhead only. The compile-able pure-CPU
issue is ~60 ms/pass (≈2% of wall); the const 350 ms is weights/blobs
entering the pipeline (already slice-view batched) and the matmul/conv
walls are GPU execution. Ceiling too small to pay for a rewrite with
bit-exactness risk on the custom-kernel chain. NO-GO.

## Lever 3 — extra islands (softmax, layer_norm): NO-GO, net-negative per island

Measured marginal cost of one island (m1-host island log, per submit):
marshal drain 0 + send 1.25 ms + exec 0.64 ms + read 3.4 ms + host pack
≈ **5.3–5.5 ms**. Measured GPU work removable:

- softmax per layer: reduce/exp/div ≈ 0.8 ms GPU → net **−4.7 ms/island**
  (−113 ms/pass over 24 layers).
- layer_norm: already served by the `_ln_cast/sq/tail` custom kernels
  (117 stmts, 14.3 ms issue, GPU compute smaller still) → strictly worse.

New bundles would also need the macOS ANECompiler export path
(`tools/ane-export`; Linux cannot compile bundles), and the capture host is gated
on the B->C capture bounce. Verdict: do not build.

## Side findings

- m1-host's 07:45Z drop was a **clean reboot** by M2ProxyLive (dwc3_apple
  unbind oops at 07:44:20, then orderly `systemctl reboot`; journal -b -1
  confirms). Not the pipelining battery. `writecombine=N` cached module
  survived the reboot (boot-persistent install verified).
- **Bug in m1max-host's `/var/tmp/ParakeetE2EJm16/fused_e2e.py`:** `NameError:
  name 'os' is not defined` at line 362 (`stage_tdt`, MLX_OMARCHY_TDT_BATCH
  read) — the e2e crashes after the encoder stage; `import os` is missing.
  Owner of that file should fix; my ceiling run (ceiling-20260922T081317)
  still yielded the full encoder statement trace despite the crash.
- Lock protocol: persistent-inode flock with recreate detection needs
  `stat -L` (dereference the `/proc/self/fd/N` symlink); scripts
  `pipelining-j1.sh` / `pipelining-j16.sh` staged in
  `/var/tmp/encwall-decomp/` carry the working version.

## Bottom line

The pass is GPU-feeder + island-marshal bound. m1-host's 2.3x slower GPU vs
m1max-host is the whole ratio story (30–31 vs 7.5–7.8). The next lever that can
move encoder_ane is making the feeder GPU compute itself faster (more
coopmat conversion) or the capture-gated B->C/C->O fusions — both outside
this assignment.

## Addendum: m1-host ane.ko boot build after the 08:19 reboot (Main query)

- `/lib/modules/7.1.13-3-2-ARCH/updates/ane.ko` = sha `82411a46...`
  (version 6fa243a-dirty, byte-identical to `/var/tmp/ane-6fa-src/ane/ane.ko`).
  The receipt-referenced cached-BO `4ebcfc10` copy at that same path is GONE
  (overwritten by the 6fa rebuild); no `4ebcfc10` artifact exists anywhere on
  m1-host or m1max-host (full-filesystem search).
- Functionally the loaded 6fa build behaves as the cached build: module param
  `writecombine = N` (cached BO mapping active), probe run
  `ceiling-20260922T082435` (rc=0, status **match**, all gold pins) shows
  dev read median 1.62 ms / max 4.5 ms across 48 islands — far from the
  ~4.4 ms-median stock-writecombine signature, and that under concurrent
  release-gate load (encoder_ane 4380.8 ms inflated by lane load; const
  feeder wall 1053 ms is cold page cache after reboot, was 350 ms warm).
- Recommendation adopted: keep `82411a46` as the boot module; do NOT swap
  with an unverified artifact. Re-pin the 3485 ms clean baseline in a quiet
  window when the release lane is done.
