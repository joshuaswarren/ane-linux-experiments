# jwm1 Parakeet TDT/mel reduction: fusion falsified, stages are dispatch-latency-bound (2026-09-25)

Owner: Jwm1Parity10. Host: jwm1 (T8103), post-oops reboot, stock ane `5a22ee3`
reprobed clean (`[drm] Initialized ane 1.0.0`, DART containment armed).
Assignment: reduce tdt_decode 133.4 ms and mel_frontend 21.4 ms while the
golden stays bit-exact.

## 1. Gates (all green on the serving path)

| gate | result |
|---|---|
| validate_chain (golden encoder tensor, chain vs landed host path) | tokens / frames / durations / hidden / cell **all PASS**, 104 emissions, 192 slots |
| corpus_gate: fixture.flac + 0.3s/1s/5s/10s variants + 1089-134686-0000.wav | **6/6 PASS, rc=0** (tok/frm/dur true, hidden/cell bitwise; emission counts 104/0/0/28/101/104 exercise skip, blank-hop, partial and full slot schedules) |
| Qwen contract pins (same box, same boot) | 1-pass `486872c410629f1d`, 3-pass `bc519c03c4ef5fd1` — both held |

## 2. TDT kernel-count fusion: FALSIFIED (measured)

The parity3 receipt's planned lever was 6 → 3 kernels/slot via fusion. I
implemented the aggressive form — two single-workgroup (1024-thread)
kernels per slot (`agent/jwm1-parity10-tdt` on mlx-omarchy, pushed) — and
it is **bit-exact** (every accumulation order preserved: exact_fma16
chains ascending-k, fold ascending-block with first term assigned,
projector/joint precise ascending loops, same max-with-tie argmax) but
**4.7x slower**:

| variant | best-of-5, golden encoder (harness-matched) |
|---|---:|
| landed 6-kernel chain (`jwm1-parity4-overlay/tools`) | **147.3 ms** (2.74x vs host) |
| fused 2-kernel chain (`pkg-j10/tools`) | 686.7 ms (0.55x) |

Why: the chains section (3.28M exact_fma16 per layer) is throughput-bound
and needs the 100-workgroup split; one workgroup = ~1/8 of the GPU and
~25x fewer threads in flight on the fma16-heavy exact path. The schedule
is already at the parallelism-forced minimum: fold, fold_proj and control
each consume a cross-workgroup reduction (all 100 chain workgroups / all
33 window workgroups) and cannot merge into their producers without
giving up that parallelism. Fusion lever closed; do not re-run.

## 3. Root cause of both stages: dispatch-sync latency, not GPU execution

Queued-vs-single probe (3001-frame input, venv python, GPU lock held):

| mel stage | single (submit+exec+sync) | queued per-dispatch |
|---|---:|---:|
| frames | 1.293 ms | 0.021 ms |
| dft | 17.343 ms | **0.568 ms** |
| dft+power | 17.266 ms | 0.576 ms |
| mel_project | 3.841 ms | 0.126 ms |
| stats | 1.604 ms | 0.055 ms |
| stats+normalize | 1.602 ms | 0.060 ms |

Real GPU execution for the whole mel pipeline is **~0.9 ms** inside a
21.5 ms wall; tdt_decode is the same shape (133–147 ms for ~15 ms of
exec; 192 slots x 6 dispatches x ~120 us submit-sync). Both stages are
bound by per-dispatch submit+completion latency in the omarchy submission
path, which also explains why dependent kernels cannot overlap: each
submit waits on the previous buffer (rtmod `SUBMIT ... waits=1`). The
next program lever is queue depth / batched submission in the runtime —
a stack-level fix, shared by every custom-kernel pipeline on this box —
not kernel work.

(Also verified not the cause: GPU clock ramp — mel_bench warm reps are
stable 21.5 ms within a process; first-rep 135–163 ms is compile/warmup.)

## 4. Translator findings (for future custom kernels)

* MSL-subset translator **rejects u-suffix array bounds**: `threadgroup
  int x[7u]` fails where `x[7]` compiles. Bounds must use suffix-free
  constants (the landed sources only ever used `ROWS6` = "4480", never
  the `u` form).
* Unsubstituted placeholders surface downstream as GLSL
  `undeclared identifier` errors at shader compile — check the subst
  table when a builder grows new control words.
* 19 inputs + 6 outputs (25 bindings) is accepted; neither binding count
  nor nested-scope local arrays nor early-return-before-threadgroup-decl
  is the limiting factor.

## 5. Decision

Nothing merges to mlx-omarchy main from this cell: the fusion is slower,
and the mel kernels are already execution-fast. `overlay/tools` on main
(`bfe2ddc6d`) remains the landed six-kernel chain, which is the verified
serving path. The falsified experiment is preserved pushed at
`agent/jwm1-parity10-tdt` with the probe scripts' outputs in
`/var/tmp/parity8/` (`pkg-j10/`, `audio/`, `j10.out`, `gpu/contract-p10c*.json`).
