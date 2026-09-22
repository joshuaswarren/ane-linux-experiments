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

## 4. ADDENDUM (DecodeDispatchCut2, addendum) — gate CLOSED, A/B landed on m1-host

Root cause of the "beta-leg ulp mismatch" was NOT rounding: the 10-binding
decode dispatch bound the tail one slot late (`SIn←hf`, `SOut←out`), so every
standalone probe compared garbage against garbage — the earlier "g-leg
bit-exact" result was two broken outputs coinciding, and the in-model logits
run was dominated by the fallback. Three fixes, all committed on
`agent/decode-dispatch-cut` (m1-host worktree /var/tmp/integ-wt):

- `14930789` binding slot order corrected (5=SIn h0, 6=YBuf out, 7=SOut hf;
  3/4 and 8/9 overridden per mode) and the shader's extra bf16 rounds on
  exp(A_log)/g removed (eager keeps g f32 end to end).
- `6056969a` in-model `dt_bias` is bf16 in the Qwen3.8 checkpoint, so the
  f32-only raw contract never fused (957 dispatches/tok, 12.3 tok/s, all 18
  raw calls/step falling back — proven with GDN_FALLBACK_DEBUG=1). Contract
  now accepts bf16 dt_bias (DtBuf slot retyped to uint16 words), and the
  prologue replicates the eager chain's bf16 roundings on x = a + dt_bias
  and softplus(x) (verified with a mx dtype-chain probe: x bf16, softplus
  bf16, g f32; the all-f32 chain drifted up to 9.7e-4).

Identity (teacher-forced greedy, 10 prompts × 32 steps, vs
/tmp/q38c/logits-integ-m1host.json, same host/driver/model): 3 first-flips
(margins 0.125 / 0.125 / 0.0 — bf16 quantum ≤ 0.25 class), max |Δ logit|
before first divergence 0.25, downstream flips cascade. This is the
documented equivalence class (receipts/2026-09-22-qwen38-correctness §3/§4).

A/B, m1-host (M1 Max, stock kernel, flock windows, France×16 / 32 tok,
10-prompt cadence):

| metric | baseline dc7ca4a0 | raw arm 6056969a | delta |
| --- | --- | --- | --- |
| dispatches/decode-token | 705 (21,855/31) | **543** (16,833/31) | −162/tok (−23%) |
| decode gpu_busy | 942.6 ms | 758 ms | −184 ms (−19.5%) |
| decode tok/s (median) | 53.55 | **62.58** | +16.8% |
| ttft tok/s (median) | 60.08 | 65.94 | +9.8% |
| GatedDeltaDecodeBF16 | 594/step-set | 594 (fused, 0 fallbacks) | — |

Artifacts: m1-host /var/tmp/decodecut/{cadence-rawfix4.json, prof-rawfix4.jsonl,
analyze-rawfix4.txt, logits-fix2.json, spy3.out, gate_class.py, ab-final.sh};
wheels 0.32.3.dev202609221337+diag.393b771 (interim) and 0.32.3.dev202609221401+
diag.1493078 (bf16-dt, the measured arm).

Open items, with state:
1. m1max-host A/B: BLOCKED — m1max-host was taken to macOS for the T6021
   ANE bring-up (M2UartProxy lane) mid-flight and has since returned to
   Linux; m1max-host worktree sits at dc7ca4a0 with the model cached.
   Steps: bundle-transport 6056969a from m1-host (git bundle over scp), apply
   patch-mlx-lm-gdn.py + patch-mlx-lm-gdn-raw.py to a fresh venv, build
   diag wheel there (scripts/build-wheel.sh --diagnostics), run baseline +
   raw arms with /tmp/q38c window protocol.
2. rope-pair bf16 via fast_trio: NOT STARTED (design done). fast_trio.comp
   is f16-only by an #error; the bf16 port should copy fast_rope.comp's
   USE_BF16 pair-granular form (whole-word outputs, plain stores, host-guards
   dims%4==0 + even offsets), add FastTrioRopePairBF16 (compute.h + compute.cpp
   case + CMake omarchy_shader with -DUSE_BF16=1 -DTRIO_ROPE_PAIR=1), and
   extend dispatch_rope_pair's dtype gate. Scoped ≈ −6..18/tok (pair fuses
   2 rope dispatches → 1); dispatch_rope_pair currently refuses bf16 at
   "dtype not f16" (primitives.cpp ~7802).
3. conv-ring default-on: the ring IS live in the venv qwen3_5.py and was
   active in BOTH A/B arms (identical CopyGeneralBF16 n=1993 both arms), and
   both gate runs passed with it on → decision: KEEP default-on (identity in
   the documented class on this lineage). Same-lineage ring-off count delta
   not re-measured (Addendum 11's −18/tok stands as the old-wheel number).
4. m1-host is now on GpuTlbKernel's TLB2M test kernel — the numbers above are
   pre-reboot stock-kernel measurements; re-run the raw arm if cross-kernel
   comparability is ever claimed.
