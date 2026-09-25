# FINAL RESULTS — jwm1 patched serving stack (2026-09-24 16:30 CDT)

## Installed state (new)
- mlx-omarchy wheel `0.32.3.dev202609241734+f9d7bb2` (rel/v0.7.3 + SDPA hd256
  arm: 9d85ff18 + f9d7bb21d; wheel sha256 ad090148c450ba17b9ca09efece9a37c1ef946b629feeef08dd03938ada524c0)
- mlx-lm 0.31.3 + proven patches wired: GDN fast route (patch-mlx-lm-gdn.py),
  GDN raw route (patch-mlx-lm-gdn-raw.py; mx.fast.gated_delta_update_raw=True),
  greedy-prune head (patch applied, 3 refs in generate.py; kernel NOT in this
  wheel lineage — self-guarded inert fallback to full head, no breakage)
- venv: /var/tmp/m1-sdpa256/venv-patched — THE Qwen serving stack on jwm1
- ICD honeykrisp 7faf04c (09e3527d...) unchanged; MLX_DISABLE_COMPILE=1

## Contract vs macOS (10 passes x 10 prompts, n=100, greedy, 32 new tokens, prefill 512)

| metric | before (receipted) | AFTER | macOS | ratio | verdict | delta |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| decode tok/s | 17.46 | **36.37** | 47.05 | 0.77x | FAIL | **+108%** |
| ttft tok/s | 20.19 | **50.06** | 99.12 | 0.51x | FAIL | +148% |
| pure prefill tok/s (512) | 28.68 | **219.2** | 343.73 | 0.64x | FAIL | **+664%** |
| e2e s (32-tok prompt) | 2.4195 | **1.1145** (min 1.079, max 1.147) | 0.7898 | 0.71x | FAIL | -54% |

- pin: `dbf704971617fdfc` = IDENTICAL to the jw16 T6001 10-pass pin —
  cross-host digest identity T8103-Linux == T6001-Linux under the raw-route
  composition (the old bea37f48 row was the eager-composition stream; the
  raw route's bit-exactness vs its own composition was proven on jw16:
  gates 0/0/0 flips, 4/4 runs).

## Attribution chain (this session)
1. SDPA hd256 fused decode arm (pure effect): +0.139 tok/s, 95% CI
   [+0.127,+0.151], ratio 1.0084, n=10 paired, CI entirely positive;
   pins 1aa2f5f8 identical across arms (unpatched streams).
2. mlx-lm raw route + fast route wiring (swarm removal): decode
   16.69 -> 36.37 tok/s (+118%) — the elementwise swarm (84% of GPU
   busy, 903 dispatches/tok) collapses into the fused GDN path.
3. Greedy head: inert on this wheel (kernel absent, self-guarded).

## Budget (pre-patch profile, installed-then path, diag wheel @ f9d7bb21d)
- GPU busy 84% of wall / idle 16%; swarm = 84% of busy (Multiply 38.7%
  168 launches/tok, unnamed elementwise 21.2%, AsType 198/tok, RMSNorm
  121/tok...); qmm only 11%; 903 dispatches/tok, 1 submit/tok, 2
  barriers/dispatch 0 skipped, 1 join total (host NOT binding)
- roofline 22.0 ms/tok; wall was 57.27 = 38% of roofline -> now 31.2 ms
  (57.27/1.84) = 71% of roofline

## Remaining gap to parity
decode 0.77x: 36.37 -> 47.05 needs +29%. Next levers: vocab-prune head
kernel (needs the a213ea10a wheel lineage; sketch bounds 99.68% prune),
qmm kernel efficiency (1.8-2.6x family gap), CDM per-launch sink.
