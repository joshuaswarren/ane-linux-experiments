# 2026-09-22 — GDN prefill host path: strided-input fallback elimination

Lane: GdnPrefillHost. Target: GatedDeltaPrefillBF16 host path
(`overlay/mlx/backend/omarchy/primitives.cpp` `GatedDeltaUpdate::eval_gpu`).
Branch `bf16-prefill-gdn-exact` (worktree `m1max-host:/var/tmp/gdn-exact-wt`),
local commits only. Final wheel:
`dist/mlx_omarchy-0.32.3.dev202609220645+f6db574c-cp314-cp314-linux_aarch64.whl`.

## Status: GREEN — all acceptance criteria met

| host | path | prefill-512 tok/s | digest (ordered_records_sha256) |
|---|---|---|---|
| m1max-host | ops reference | 73.0 | cceba7527e064f49... (per prior receipt) |
| m1max-host | routed, before (da3e8a4 lib actually loaded) | 57.8–59.4 | 5e093035... |
| m1max-host | routed, after 117133d0 | 245.4 (wall 2.087 s) | 5e093035... |
| m1max-host | routed, final f6db574c | 237.3 (wall 2.158 s) | 5e093035... |
| m1-host | routed, before (old wheel) | 21.5 | 6f21e665... (WRONG — see below) |
| m1-host | routed, final f6db574c | 32.9 (decode 27.6, ttft 24.6) | 5e093035... |

Per-pass determinism: 3 passes x 10 prompts, zero divergent prompt outputs
on both m1max-host and m1-host (`candidate-hostfix.json` on both hosts).

## Root cause (not descriptor churn, not allocator sync)

The prior receipt's suspects (per-call allocations, 11-binding churn,
snapshot scratch) were all second-order. The real cost:

`eval_gpu` required every input `row_contiguous` or it fell back to the
per-token composed graph **plus a full `encoder.synchronize` per layer**
(primitives.cpp `encoder.synchronize("gated_delta_fallback")`). In-model
`v` is a strided slice of the fused qkv projection, so EVERY GDN call in
the model ran the composed fallback. rtmod evidence: 36
`JOIN reason=gated_delta_fallback` per two prefills (18 layers x 2), and
~157k dispatches per prefill in the fallback vs ~960 on the fused path.
That fallback is also SLOWER than the ops reference (~480 ms/layer vs
424 ms) because of the per-layer host sync.

### Compounding discovery: the venv was running a stale library

`/var/tmp/gdn-exact-venv/bin/pip` has a shebang pointing at
`/var/tmp/bf16-prefill-venv/bin/python3`, so every prior `pip install`
into gdn-exact-venv silently landed in bf16-prefill-venv. gdn-exact-venv
was still running the da3e8a4 (Sep 21 20:53) libmlx while `pip list`
reported the new version. installs must use
`/var/tmp/gdn-exact-venv/bin/python -m pip`. Note: bf16-prefill-venv on
m1max-host accumulated mlx-omarchy wheels from this (harmless, but it is a
different build than its dist-info suggests if anyone reuses it).

## Fix (commits, both on primitives.cpp eval_gpu only)

- `117133d0` — drop the `row_contiguous` gate for the fused path;
  materialize any strided input into a same-shape dense temporary via
  `contiguous_copy_gpu` + `encoder.add_temporary` (recorded device copy,
  no host sync), rebind the input handles, dispatch the fused kernels.
- `f6db574c` — extend the predicate to nonzero storage offsets: strided
  T-slice views are still flagged row_contiguous, and offsets were
  mishandled on m1-host (digest 6f21e665 there; materializing fixed it and
  m1-host's digest now equals m1max-host's exactly).

The two passes already record into one open command buffer with no host
sync between them; per-call out/hf/snapshot allocations are served by the
buffer cache and were confirmed non-blocking by the post-fix profile
(prefill wall 2.07 s with zero per-layer joins), so no further host-path
work was needed.

## Profiling method

`MLX_OMARCHY_TRACE_DISPATCH=1` rtmod stderr trace + `profile_prefill.py`
(single 512-token prefill, warmup + measured) under /tmp/m1-gpu.lock,
llama-server 8002 stopped and health-verified restored after every
window. Artifacts on m1max-host `/var/tmp/gdn-exact-probe/`:
`prof-run-20260922-010312.log` (before: 36 fallback joins, 8.47 s),
`prof-run-20260922-012634.log` (after: 0 fallback joins, 2.07 s),
`candidate-hostfix-20260922-012816.log`, `candidate-hostfix-20260922-015533.log`;
m1-host `/var/tmp/gdn-hostfix-m1-host/candidate-hostfix-20260922-015708.log`.
Bench protocol: greedy, 3x10 prompts, warmup 2, prefill leg 512.

## Out-of-lane observations

- The known `fast(T=1)` NaN on strided T-slices is NOT the composed
  fallback: `nc_probe.py` shows the fused decode shape returns NaN state
  even for fully contiguous, offset-0 T=1 inputs with OOD probe inputs
  (randn g/beta). In-model decode is unaffected (digest + 27.6 tok/s
  decode on m1-host, 54.1 on m1max-host). Decode kernel is a non-goal for this
  lane; left for the decode lane.
- m1-host's mlx_lm gated_delta.py was verified already routed to
  mx.fast.gated_delta_update (patch present), so the earlier 6f21e665
  digest there was genuine wrong-answer arithmetic on offset views, now
  fixed by f6db574c.
- m1max-host bf16-prefill-venv has stray mlx-omarchy wheels installed (see
  above). Cleanup optional.

Resident llama-server 8002 on m1max-host: health ok after last window.

## Follow-up (Main): fused DECODE-shape NaN — characterization

Reproducer: `decode_nan_repro.py` (this dir; run on m1max-host via
`repro_window.sh`, wheel f6db574c). Direct
`mx.fast.gated_delta_update(q,k,v,g,beta,h0)` with B=1, T=1, H=16,
Dk=Dv=128, bf16 q/k/v/g/beta, f32 h0 — the decode shape, fully
contiguous, zero offsets.

Findings (each line one window-verified observation):

- NaN is INPUT-INDEPENDENT: reproduces with all-zero q/k/v, g=0,
  beta=0.5; with randn everything; with h0=0; with an explicit mask
  passed ([1,1] and [1,1,H]). Ops-path math (`ops_step`, the fast.cpp
  composed-fallback algebra in mx ops) is FINITE on every identical
  input set. So this is NOT an out-of-distribution-magnitude artifact
  and NOT rounding-order divergence — the ops path produces finite
  results where the fused decode produces NaN.
- With beta=0 the fused STATE is finite but the OUTPUT is still NaN:
  the output write itself is broken, not the recurrence arithmetic.
- Inconsistent finiteness between mathematically identical states
  (zeros q/k/v vs beta=0) points at garbage/uninitialized reads
  (binding or scratch), not overflow in the decay/exp path.

Conclusion: real kernel/host-binding defect of the fused decode path
(GatedDeltaDecodeBF16 or its no-mask binding set, which uses
`binding(out)` placeholders for unused slots), triggered when the
decode shape is invoked as a bare fast.op. It does NOT occur in-model
(digest 5e093035 + decode 54.1/27.6 tok/s on m1max-host/m1-host held across all
benches here), so some aspect of the in-model call context (buffer
state, prior prefill hf feeding h0, masked bindings) diverges from the
bare call. Decode kernel is out of this lane's scope; hand to the
decode lane with this reproducer.
