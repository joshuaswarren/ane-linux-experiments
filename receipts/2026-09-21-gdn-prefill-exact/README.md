# 2026-09-21 — GDN prefill exact (GatedDeltaPrefillBF16 digest + wall)

Lane: GdnPrefillExact. Target: fused GDN prefill on the omarchy Vulkan
backend with the greedy token digest identical to the ops reference
`cceba7527e064f49...` (30 greedy records, gpu-host protocol), and prefill-512
faster than the ops path.

## Status: NOT GREEN — digest still flipped, wall still regressed. Root
cause narrowed to a per-token 1-ulp-class arithmetic difference between the
fused shader and the ops path; two of three identified defects are fixed
(committed), one remains open.

## What landed (branch `bf16-prefill-gdn-exact`, off
`bf16-prefill-coopmat-925cf`; local only, no pushes)

- `fde61f60a` — fast.cpp vendored patch (`patches/mlx-gated-delta-mask.patch`
  regenerated): T>1 keeps compute_g's f32 gates (no bf16 cast); T==1 decode
  keeps the bf16 cast the decode kernel widens exactly (coordinated with
  BF16DecodeKernels, who confirmed his decode identity is untouched).
  Plus: chunked two-pass scan (pass 0 prefix scan with per-chunk snapshots;
  pass 1 heads x chunks output replay), register-resident state row,
  11th binding slot for the snapshot scratch; `prepare-mlx.sh` repair
  (975273471 dropped the `patch` prefix, silently skipping
  `mlx-python-buffer.patch` on every wheel since — restored).
- `359ae86c` — precise-op (NoContraction) guards; scratch array build fix.
- `2672349b` — pass 0 scans the whole token axis (first cut only scanned
  chunk 0 -> NaN snapshots); snapshot at every chunk boundary.
- `5361...(barrier)` — per-token barrier restored: row 0 overwrote
  `sk`/`sq` shared while other threads still read them (nondeterministic
  corruption).
- `+ fma commit` — state update written as explicit `fma(delta, sk, dec)`
  (no observable change on device, see below).
- `+ debug commit` — env-gated `GDN_FALLBACK_DEBUG` print of the
  fused-eligibility inputs (temporary, for the in-model routing check).

Wheel on gpu-host: `/var/tmp/gdn-exact-wt/dist/mlx_omarchy-0.32.3.dev202609220312+925cfa64-cp314-cp314-linux_aarch64.whl`
in venv `/var/tmp/gdn-exact-venv` (mlx-lm 0.31.3 + `patch-mlx-lm-gdn.py`
routing, which needed a fix to accept the commented gated_delta.py variant
— committed in ane-linux-experiments).

## Measurements (gpu-host, exclusive flock windows, llama-server 8002 stopped
and restored after each window)

Leg level (direct mx.fast.gated_delta_update vs gated_delta_ops, T=512,
B=1, H=16, Dk=Dv=128, scaled inputs; `leg_probe.py` / `nan_hunt.py` /
`gdn_bisect.py`):

| variant | fused | ops |
|---|---|---|
| wall (T=512) | 42.9 ms | 424 ms (9.9x) |

- decay / kv / output-dot / delta paths: bit-exact vs ops in isolation
  (`beta=0` and `v=0` bisect cases: state diff exactly 0).
- full recurrence: state max diff ~3e-4 (f32), output max diff 7.8e-3
  (bf16, a few ulps); NOT bit-identical.
- unscaled randn inputs explode to NaN in BOTH implementations (the
  recurrence is genuinely unstable out-of-distribution) — early NaN
  readings were probe artifacts, not kernel bugs.

End to end (prefill-512, greedy, 3x10 prompts, mlx-lm routed):

| run | prefill-512 | digest |
|---|---|---|
| ops path reference | 73.0 tok/s | cceba7527e064f49... |
| routed da3e8a4 (old, bf16 gates) | 57.8 | 5e093035... |
| routed this branch (f32 gates, two-pass) | 56.8–57.8 | 5e0930351bb6d6d5653dacba88642b9b6744330fe1bb68689b01f1292d3c63db |

`GDN-FALLBACK` debug count = 0 in the routed run: every in-model call
takes the fused kernel — the in-model regression is NOT the composed
fallback. The kernel leg saves ~7 ms/layer x 18 yet the wall regresses
~1.9 s, so ~110 ms/layer of host/runtime overhead remains unexplained
(candidate suspects: per-call `allocate_omarchy` for out/hf/snapshot
forcing allocator sync; 2 dispatches + 11-binding descriptor churn per
layer; snapshot scratch 7.3 MB/call allocation). This is the next thing
to profile (omarchy rtmod SUBMIT spam in the candidate log shows thousands
of tiny serialized command buffers during the bench).

## Root-cause state for the digest

1. f32 gates through the wrapper: DONE and verified (bisect `beta=0` case
   bit-exact vs ops proves the kernel sees unrounded f32 decay). The old
   receipt's attribution of the digest flip to the bf16 cast was wrong or
   incomplete — with f32 gates the digest is still 5e093035.
2. Remaining gap: a 1-ulp-class per-token difference in the delta-update
   region (bisect `g=1`: state diff 4.47e-8; full: 3e-4 after
   amplification). Working hypothesis: the honeykrisp driver contracts
   `a*b+c` to FMA in the shader regardless of `precise`/NoContraction
   (explicit-fma and separate-rounding wheels produced bit-identical
   results on device), while the ops path's kernel decomposition rounds
   separately (or vice versa at one site). Numpy strict-f32 simulation of
   the recurrence (`sim_probe.py`) still disagrees with BOTH
   implementations (0.14), so the sim itself has a residual modeling bug —
   fix that first when resuming: it is the ground truth that decides which
   side rounds differently.

## m1-host

Not started — gpu-host is not green.

## Artifacts

- receipts/2026-09-21-gdn-prefill-exact/{leg_probe,nan_hunt,gdn_bisect,sim_probe,oracle}.py
- receipts/2026-09-21-gdn-prefill-exact/run_gpu-host_window.sh
- gpu-host: /var/tmp/gdn-exact-probe/ (window logs, leg_results.json,
  candidate-*.log with digests), /var/tmp/gdn-exact-wt (build logs
  build1..7), /var/tmp/gdn-exact-venv (routed candidate venv)

## Residual risk / cleanup

- `GDN_FALLBACK_DEBUG` print and the fma experiment commit are debug
  scaffolding on the branch — strip before landing.
- llama-server 8002 restored after every window; last check: DOWN after
  window5 restore attempt ("SERVER NOT UP YET" is a 5 s probe race — the
  window4/5 restores need a health re-check).
- BF16DecodeKernels' decode path is untouched (T==1 cast preserved).
