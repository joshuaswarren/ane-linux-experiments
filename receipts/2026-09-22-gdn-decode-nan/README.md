# 2026-09-22 — Fused GDN decode kernel: OOD NaN root cause + fix

Lane: GdnDecodeNan. Target: `gated_delta_decode.comp` +
`GatedDeltaUpdate::eval_gpu` fused decode path (T=1). Non-goals honored:
prefill kernel, GEMV, ANE untouched.

## Verdict: root-caused and fixed

The NaN is a **stale shader in the wheel**, not a defect in current kernel
source. The fix already exists on the branch; this lane verified it end to
end.

## Root cause

The wheel under test (`f6db574c`, gdn-exact-tmp6 line) embeds the decode
shader **before** commit `22866d44`, i.e. with:

```c
uint head = gl_GlobalInvocationID.x;   // wrong: must be gl_WorkGroupID.x
```

Dispatch is `(Hv, 1, 1)` groups of 128 threads. With the flattened global
id, `head = group*128 + row`, so the `head >= hv` guard kills every thread
except group 0, rows 0..15. Consequences (shader lines, pre-22866d44):

1. The shared-memory load loop `for (i = row; i < dk; i += 128)` executes
   exactly one iteration per surviving thread → only `sk[row]`/`sq[row]`
   are written; `sk`/`sq` are **uninitialized shared memory** for all other
   127 indices.
2. Each active thread acts as `head == row`, so `out[h,h]` (diagonal) gets
   16 garbage writes and state rows `h*128..` get 16 garbage rows; the rest
   of the freshly allocated out/state buffers stays whatever the allocator
   left behind.

Write-mask proof (`write_mask.py`, all-zero inputs, f6db574c wheel on
m1-host): out had exactly 2048−16 finite + **16 NaN at the (head, head)
diagonal**, 16 nonzero; state had exactly 2048 nonzero (16 rows × 128) and
2048 NaN. Input-independent — all-zero inputs and h0=0 reproduce
(`decode_nan_repro.py`: every case fused_out/state=False while the composed
ops path is finite). Nondeterministic across processes (allocator state),
which is why single-shot probes sometimes looked finite
(`min_probe.py` case 1).

Why in-model decode was never affected: in-model gates are f32
(`compute_g` emits f32), so `fused_ready` (requires `g.dtype == bfloat16`)
is false and every in-model call took the composed fallback. The fused
kernel was effectively dead code in-model on the affected wheels.

## Fix

Commit `22866d44` on `bf16-decode-gdn` (m1max-host:~/src/mlx-omarchy, local,
unpushed):

- `head = gl_WorkGroupID.x` (one workgroup per head, 128 threads = one Dv
  row each, full `sk`/`sq` load),
- per-array buffer item offsets (`checked_item_offset` → push constants,
  added to every shader index) so strided T-slice views read the right
  elements — fixes `strided==contig` (was False/NaN on the old wheel,
  `nc_probe.py`).

No code change was needed in this lane: the fix was already the branch tip.
Verification wheel built from that tip:

- `dist/mlx_omarchy-0.32.3.dev202609220712+22866d44-cp314-cp314-linux_aarch64.whl`
- sha256 `98b607313bd064bc07dcdd9732d09c24027581c66de0f4a32d0e330e06250714`
- build log: m1max-host:/var/tmp/decode-nan-build.log (worktree /var/tmp/decode-nan-wt)
- venv on m1-host: /var/tmp/gdn-nan-fix-venv (control NaN venv: /var/tmp/gdn-nan-venv)

## Verification (all on m1-host, /tmp/m1-gpu.lock held)

1. **Probe clean** — `decode_nan_repro.py` on 22866d44 wheel: all 10 cases
   finite (randn g, g=±0.1, g=0, h0=0, all-zeros, beta=0, with mask [1,1]
   and [1,1,H]). Same script NaNs in all cases on the f6db574c wheel.
2. **Composed equivalence (T=1)** — `verify_fix.py`:
   state f32 maxabs diff 5.96e-08 (rel 3.6e-08, reduction-order noise);
   out bf16 **within 1 bf16 ulp** (max 0.5 ulp); strided `q[:,3:4]` slice
   bitwise-equal to the contiguous call (`strided==contig: True True`).
3. **In-model token identity on m1-host** — `identity_probe.py`, pinned
   SiddhJagani/Qwen3.8-2B model, greedy 32 tokens, three prompts
   ("France "*16 chat+raw, "The capital of France is a city in Europe."
   chat): fused-kernel arm **== forced-ops arm token-for-token** on every
   prompt (GD_FORCE_OPS env switch). Reference-stream note: the second
   prompt's stream opens `760 1156 369` exactly like the 2026-09-21 bf16
   reference stream; the exact original prompt of that stream was not
   reconstructed, so identity is gated on the fused==ops A/B, which is the
   same gate the prior receipt used (fused==ops token-for-token).

## Reproducers

- `decode_nan_repro.py` (from GdnPrefillHost, m1max-host:/var/tmp/gdn-exact-probe/)
  — NaN on every input class on the f6db574c wheel, all finite on 22866d44.
- `write_mask.py` — write-pattern forensics (diagonal NaN signature).
- `min_probe.py`, `verify_fix.py`, `identity_probe.py` — this lane.

## Operational notes

- mlx_lm routing in the verification venv: stock 0.31.3 `gated_delta.py`
  + the two-line `mx.fast.gated_delta_update` hook (GPU-gate dropped for
  Vulkan, ops path via `gated_delta_ops`); `GD_FORCE_OPS=1` forces ops.
- m1-host venvs: /var/tmp/gdn-nan-venv (f6db574c, NaNs), /var/tmp/gdn-nan-fix-venv
  (22866d44, clean). Both disposable.
- The composed ops path never NaNs on OOD inputs — this was kernel-only,
  step 2 of the assignment (no OOD-artifact exit).
