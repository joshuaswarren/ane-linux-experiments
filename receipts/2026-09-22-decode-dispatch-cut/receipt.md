# 2026-09-22: decode dispatch cut — attribution complete, raw-gates fusion implemented, gate OPEN (beta leg)

Lane: DecodeDispatchCut. Base: `mlx-omarchy` `integration/qwen38-2026-09-22`
@ dc7ca4a0. Branch: local `agent/decode-dispatch-cut` @ 393b7712 on m1-host
(m1-host), worktree `/var/tmp/integ-wt`, venv `/var/tmp/decodecut-venv`
(mlux-lm 0.31.3 + gdn route patch + gdn-raw route patch). Diag wheel
`0.32.3.dev202609221308+diag.dc7ca4a`. m1max-host unavailable (rebooted twice,
dwc3 incident) — m1-host numbers only.

## 1. Per-op attribution (DONE — new profiler plumbing)

`gpu_profiler.h` d-records now carry the consuming primitive name
(`"p"`, from `trace::current_prim`). Analysis: `/var/tmp/decodecut/attrib.py`
(host), method = receipts/2026-09-21-decode-kv-direct Addendum 12
(MLX_OMARCHY_TRACE_DISPATCH + MLX_OMARCHY_GPU_PROFILE, markers,
France x16, temp 0, 32 tokens, MLX_DISABLE_COMPILE=1, flock
/tmp/m1-gpu.lock).

Baseline decode window @ dc7ca4a0, m1-host: **705 dispatches/token**
(21,855 over 31 intervals), decode gpu_busy 942.6 ms. Ranked decode table
(dispatches/token):

| kernel | prim | n/tok | ms |
| --- | --- | ---: | ---: |
| FastRmsNormBF16 | RMSNorm | 115.0 | 107.5 |
| QmmVecQ4MultiSubgroupBF16 | ? | 96.0 | 192.0 |
| CastBF16F32 | AsType (n=16 and n=2048) | 72.0 | 47.4 |
| ElementwiseBF16 | Sigmoid | 42.0 | 54.7 |
| ElementwiseF32 | Exp | 36.0 | 40.0 |
| CastF32BF16 | AsType | 36.0 | 31.4 |
| ElementwiseBF16 | Multiply | 36.0 | 46.9 |
| CopyGeneralBF16 | SliceUpdate | 30.0 | 21.4 |
| BinaryVecBF16 | Multiply | 24.0 | 20.9 |
| QmmVecQ4WordSubgroupBF16 | QuantizedMatmul | 19.0 | 73.5 |
| ConvBF16 / GatedDeltaDecodeBF16 / FusedChainF32 / LogAddExp / Negative / MultiplyF32 | — | 18.0 each | — |

GDN gate chain attribution (compute_g + sigmoid, per GDN layer/token):
Exp x2, Negative, LogAddExp (softplus), MultiplyF32, SigmoidBF16, CastF32BF16
(g), plus 2 n=16 CastBF16F32 + 1 n=2048 CastBF16F32 + 1 n=2048 CastF32BF16.
Identity-gates bisect (probe: beta=1, g=0 on the live model): **705 → 561
dispatches/token = −144/tok** available from fusing the gate chain into the
GDN decode kernel prologue.

Scale-into-rmsnorm-weight probe (fold inv_scale into rms_norm weight): net
zero (mul removed, mx.full weight creation added) — rejected.

## 2. Raw-gates GDN prologue fusion (IMPLEMENTED, gate OPEN)

End-to-end change, all committed on `agent/decode-dispatch-cut`:

- `patches/mlx-gated-delta-raw-gates.patch` (registered in
  `scripts/prepare-mlx.sh`): `fast::gated_delta_update_raw(q,k,v,a,b,A_log,
  dt_bias,state,mask)` — decode T==1 builds GatedDeltaUpdate with
  raw_gates=true carrying (q,k,v,a,b,A_log,dt_bias,h0[,mask]); T>1 falls
  back to eager gates + standard scan; C++ composed fallback included.
  Python binding `mx.fast.gated_delta_update_raw` in python/src/fast.cpp.
- `gated_delta_decode.comp` raw prologue (flag bit 8, bindings 8/9 =
  A_log/dt_bias, offsets in in_strides[0..1]): beta = bf16round(1/(1+exp(-b)))
  — same single-round-f32 formula as the Sigmoid kernel (verified identical
  in python); g = bf16round(exp(-exp(A_log_f32)*softplus)) with softplus in
  the elementwise kernel's exact logaddexp form (max + corrected log1p).
- `primitives.cpp` eval_gpu: raw mode input mapping, dtype gates, strided
  materialization, 10-binding decode dispatch.
- venv route: `scripts/patch-mlx-lm-gdn-raw.py` (this repo, staged to
  /tmp/decodecut on host).

**Verification so far:**

- g leg BIT-EXACT vs the eager chain (state-level probe, b=0 arm).
- mx.sigmoid(bf16) == single-round f32 1/(1+exp(-x)) — the shader formula.
- Teacher-forced logits gate (10 prompts x 32 steps,
  /tmp/q38c/logits.py protocol, vs /tmp/q38c/logits-integ-m1-host.json):
  **FAIL — 26/320 argmax flips** (first flip prompt 1 step 14, margin
  0.125 = bf16 near-tie; downstream flips are cascade on the divergent
  continuation). max |Δ logit| on matched trajectory prefix = 0 pre-flip;
  the beta leg still differs by ulps somewhere (state-level probe:
  beta-only arm unequal, mechanism NOT yet identified — sigmoid formula
  itself verified equal). 8/10 prompts flip-free 32/32.
- Dispatch count for the raw arm NOT measured (gate must pass first).

## 3. Remaining to close the ticket

1. Root-cause the beta-leg ulp difference (suspects: shader `exp()`
   specializing differently inside the GDN kernel compilation than in the
   elementwise kernel; or a binding/offset read of b at nonzero item
   offset in-model).
2. Re-run logits gate to zero-flips-beyond-near-ties with coherent text.
3. A/B window m1-host: dispatches/tok, gpu_busy, decode tok/s vs 705/tok
   baseline (expect ~ −120±/tok from the −144 bisect, net of the 3-4
   residual eager gate dispatches that stay).
4. m1max-host (m1max-host) A/B — host was down twice today; stage venv + wheel
   and repeat window.
5. bf16 rope-pair (fast_trio) lift: not started (scoped +6/tok saving,
   receipts/2026-09-21-decode-kv-direct Addendum 12 item 4).
6. Conv-state ring default-on: patch measured −18/tok + identity-holding on
   the old wheel (Addendum 11); needs one identity + count re-run on
   dc7ca4a0 lineage and a decision recorded; not started here.

## Artifacts

- m1-host: /var/tmp/decodecut/{attrib.py,compare_logits.py,gate_probe.py,
  prob-*.jsonl,prof-base-dc7ca4a.jsonl,markers-*,logits-raw{,2}.json,
  analyze-base-dc7ca4a.txt,cadence-base-dc7ca4a.json}
- m1-host branch `agent/decode-dispatch-cut` @ 393b7712 (local, not pushed)
- Local repo: .local/decodecut/ (all harness + patch scripts, this receipt's
  working copies)
