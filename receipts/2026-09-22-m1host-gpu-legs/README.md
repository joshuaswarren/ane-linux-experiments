# 2026-09-22 — m1-host (jwm1 / T8103) GPU legs owed from the m1max-host lanes

Lane: M1HostGpuLegs. Host: **jwm1** (`jwm1-linux`, M1 G13G B1, Omarchy
7.1.13-3-2-ARCH, /dev/accel/accel0). jw16 (m1max-host) was dark all day, so the
second-host legs for three receipts ran here. All GPU work under
`flock /tmp/m1-gpu.lock`; llama-server/llm-inference were NOT running at session
start, were not stopped, and none were left running. Lock verified free at
wrap-up; no reboots; no pushes. **The receipt's §1 numbers were produced on a reconstruction of that branch
(now superseded by the recovered originals above, see §0 for the diff verdict).**

## 0. Provenance (UPDATED): original commits recovered from jw16

**The original branch survived.** jw16 returned to Linux (stock 7.1.6) after
this lane's runs; `hkc-direct-coopmat` @ 734ab7823 was found intact in
`/var/tmp/ppa-wt`. The original commit chain (42c10a68c → 77b914033 →
734ab7823 on 60c4903f4) is now durably preserved:

- bundle: `receipts/2026-09-22-m1host-gpu-legs/artifacts/
  hkc-direct-coopmat-original.bundle` (148 MB, full branch history)
- local clone: `jw16-original/hkc-direct-coopmat` in `~/src/mlx-omarchy`
- also fetched into the jwm1 worktree repo as `refs/remotes/orig/...`

Reconstruction-vs-original verification (diff `734ab7823` vs my `c07291d5` on
jwm1): the **shader `qmm_coopmat.comp` is byte-identical**, and `compute.cpp`
is byte-identical; `primitives.cpp`/`compute.h`/`CMakeLists.txt` differ in
comment wording and cast-pass placement details only (my host side was written
from the receipt text). The measured behavior stands on its own regardless:
digest `ac1b2695…` identical on all six A/B legs and equal to the m1max-host
class digest, plus microbench mismatch=0.

## 0a. Reconstruction note (historical, superseded by §0 for provenance)

The `hkc-direct-coopmat` branch (42c10a68 + 77b91403 + 734ab782) existed only in
`/var/tmp/ppa-wt` on m1max-host, which was dark; the commit objects are not on
jwm1 or the workstation. The branch was reconstructed on jwm1
(`/var/tmp/hkc-m1/src`, branch `hkc-direct-coopmat`, HEAD c07291d5) from:

- the **shipped final shader** `receipts/2026-09-22-hkc-direct-coopmat/artifacts/
  qmm_coopmat_final.comp` (X_F32 build, bf16 scales/biases) and
  `qmm_coopmat_direct.comp` (f16 route), copied verbatim into the tree;
- the receipt's description of the host side: new CMake builds
  `qmm_coopmat_x32` / `qmm_coopmat_m16_x32` (`-DX_F32=1 -DOUT_BF16=1`
  [-DTILE_ROWS=16]), compute.h enums `QmmPrefillCoopmatBF16X32`/`M16BF16X32`
  (append-only), compute.cpp cases, and a primitives.cpp bf16-hybrid route that
  widens bf16 x to f32 once via `copy_gpu` (CastBF16F32 path) and dispatches the
  X32 kernel; staged `X_BF16` route preserved.

Fidelity checks: in-model route spy shows `QmmPrefillCoopmatBF16X32` n=133 and
`QmmPrefillCoopmatM16BF16X32` n=48 dispatched with ZERO staged bf16-coopmat
kernels (artifacts on jwm1); microbench bit-check vs the 60c4903f base shader
gives mismatch=0 (§1). Wheels: base `diag.60c4903` (from src-base @ 60c4903f),
cand `diag.c07291d` (reconstruction), both diagnostics builds, venvs
`/var/tmp/hkc-m1/venv-{base,cand}` (mlx-lm 0.31.3 + GDN fast-route patch applied
to both).

## 1. Direct-global-load coopmat prefill (owed from 2026-09-22-hkc-direct-coopmat)

Microbench (`x32check.c`, finite inputs HKC_REAL=1 HKC_XMODE=b, X32 vs staged
`-DX_BF16 -DOUT_BF16` base, same-process ref compare):

| shape | mismatch | base ms_med | x32 ms_med | base TF/s | x32 TF/s |
|---|---:|---:|---:|---:|---:|
| 512×2048×2048 | 0 | 5.390/5.318/5.424 | 5.366/5.172/5.331 | 0.797 | 0.800 |
| 512×2048×6144 | 0 | 14.444/14.568/14.455 | 12.453/12.499/12.358 | 0.892 | 1.035 |
| 512×6144×2048 | 0 | 14.921/14.405/14.556 | 12.579/11.646/11.802 | 0.864 | 1.024 |
| 17×2048×6144 (m16 twin vs m16 base) | 0 | — | 2.082 | — | 0.206 |

All 6 bit-checks (3 m32 + m16 12×2048×2048 + m16 17×2048×6144 + 512×6144×2048)
mismatch=0; per-shape checksums identical across arms.

Model-level prefill-512 (Qwen3.8-2B-mlx-4Bit, 10 prompts × 3 passes, alternating
A/B ×3 legs, greedy temp 0):

| leg | base tok/s | cand tok/s |
|---|---:|---:|
| 1 | 127.53 | 136.80 |
| 2 | 127.36 | 137.96 |
| 3 | 127.87 | 138.08 |

**`ordered_records_sha256` = `ac1b2695…48f1` on every leg, both arms — the exact
m1max-host class digest, i.e. identity holds AND the digest is host-portable.**
Decode ~26.5 tok/s both arms (m1-host decode is slower than m1max; unchanged by
the lever).

**Verdict: TRANSFERS.** Pure prefill 127.5 → 138.0 tok/s median, **+8.1%** on
m1-host (m1max-host: +6.2%). The direction and size transfer; the relative gain
is slightly LARGER on the smaller SoC, consistent with the x staging being a
fixed overhead per k-step that matters more where the kernel is slower
(microbench: +2% at 2048×2048 but +15-16% at the 6144-wide shapes on T8103 vs
+27% on the same k=6144 shape class on M1 Max).

## 2. Submit-cost trace arm (owed from 2026-09-22-honeykrisp-submit-cost)

mesa-1 @ 5deac1c806 + AGX_SUBMIT_TRACE harness (patch_hk_queue_v4, the
f2cc0d3a546 content) built at `/var/tmp/hkc-submit-src/build2`
(`trace2.icd.json`, system ICD untouched). Bench: decodecut-venv (diag.822d186
wheel), 10 prompts × 3 passes.

| arm | decode tok/s | ttft | prefill-512 | digest |
|---|---:|---:|---:|---|
| system driver | 35.55 | 47.23 | 121.64 | `bc519c03…` |
| traced + AGX_SUBMIT_TRACE | 35.52 | 47.26 | 119.95 | `bc519c03…` (identical) |

Host-side decomposition over 3158 traced submits: command-buffer build
**1.33 us p50**, vkQueueSubmit ioctl **27.8 us p50** (p99 65 us, max 1.3 ms —
never blocks at scheduler limits). ~3 submits/token ⇒ host submit cost
≈ 87 us/token ≈ **0.31% of the 28.2 ms decode wall**.

**Caveat:** the per-CS GPU timestamp ring returned all-zero stamps on jwm1
(kernel 7.1.13-3-2-ARCH vs m1max's 7.1.6-1-1-ARCH), so the ~231 us
firmware job-boundary-gap figure could NOT be re-derived here. The ring
mechanism needs a kernel-compat check on this host before that split is
claimable.

**Verdict: the refutation TRANSFERS with the boundary-gap leg unverified.**
Decode is GPU-bound on m1-host too: identical output digest with tracing on,
decode tok/s unchanged (−0.03%), host submit+record cost 0.3% of wall. Whether
the ~4.3% boundary-gap residual also transfers remains unmeasured on this SoC.

## 3. Decode dispatch-cut identity re-check (owed from 2026-09-22-decode-dispatch-cut §5)

Branch bytes: jwm1 `/var/tmp/integ-wt` @ **822d186d** (verified commit), wheel
`diag.822d186` in `/var/tmp/decodecut-venv`; baseline = `/var/tmp/cut3-base`
diag.dc7ca4a in `/var/tmp/decodecut-base-venv`. France×16 / 32-token profile,
10-prompt cadence, current stock kernel 7.1.13-3-2-ARCH.

| metric | baseline dc7ca4a0 | raw 822d186 | delta |
|---|---:|---:|---:|
| dispatches/decode-token | 723 (22,413/31) | **561** (17,391/31) | −162 (−22.4%) |
| decode gpu_busy | 1441.3 ms | 1228.7 ms | −14.8% |
| decode tok/s (median) | 33.93 | 35.53 | +4.7% |
| cadence digest | `ac1b2695…` | `bc519c03…` | documented class |

**The dispatch counts are IDENTICAL to m1max-host: 723 → 561 (−162/tok), and
gpu_busy delta −14.8% vs m1max's −15.0%.** Decode tok/s +4.7% vs +4.3%.

Identity class (teacher-forced greedy, this host, same logits.py both arms):
first flips prompt 1 step 14 (margin 0.125), prompt 4 step 19 (0.125), prompt 7
step 19 (0.125) — bf16 quantum ≤ 0.25, downstream flips cascade, 52/320 raw
flips dominated by cascade. The regenerated baseline was cross-checked against
`receipts/2026-09-22-qwen38-correctness/private/logits-integ-m1-host.json`:
8/10 prompts flip-free 32/32, remaining flips anchored by a margin-0.000 exact
tie — same protocol-equivalence class (§3/§4 of the correctness receipt).

**Verdict: TRANSFERS, exactly.** −162 dispatches/tok and ~+4.5% decode on both
SoCs; the raw-gates fusion's dispatch reduction is SoC-independent and the
identity class is the documented one.

## Wrap-up state

- jwm1: GPU lock released (`flock -n` verified free), no measurement processes
  left, llama-server not running (was not running at start — nothing to
  restart), no reboots, no system ICD/driver changed (traced mesa is a private
  build + ICD json under /var/tmp).
- jwm1 local branches (no pushes): `/var/tmp/hkc-m1/src` `hkc-direct-coopmat`
  @ c07291d5 (+ src-base @ 60c4903f); `~/src/mesa-1` working tree was
  accidentally touched by the v4 patch script's hardcoded path and was restored
  (`git checkout -- hk_queue.c`, verified clean).
- Artifacts: this dir `artifacts/` (6 leg-1 cadence JSONs, leg-3 analyze txts +
  logits JSONs). On jwm1: `/var/tmp/hkc-m1/` (wheels, venvs, logs, leg3 dir),
  `/var/tmp/hkc-submit{,-src}/` (trace build, ICD, trace logs incl.
  trace2b.log with 3158 hk-submit lines).
