# TDT joint ILP2 on jw16: first A/B −17.5 ms REFUTED by pre-registered counterbalanced repeat (+0.7 ms) — NO-LAND (2026-09-19)

Verdict: **WIN — LAND candidate, scoped.** The joint two-output interleave
is bit-exact on device (all 12 measured runs hold the full pin set on
both arms) and faster in every interleaved pair: tdt_decode median
**base 852.4 ms vs candidate 834.9 ms (−17.5 ms, −2.1 %)**. Ranges
overlap (base 834.3–874.9, cand 826.7–851.4), so the claim is the
median delta plus the 6/6 paired sign consistency (every cand run beat
its interleaved base run), not a disjoint-range effect. Candidate branch
`agent/tdt-joint-ilp2` @ `f7fb7aec`, unmerged, ready for review-gated
merge.

## Baseline and provenance (per Main)

- Base arm = **post-#12 origin/main overlay (`fabe6697`)** — the landed
  LSTM rebalance is in the baseline; the base median (852.4 ms)
  corroborates the rebalance A/B's candidate arm (849.2 ms) — the landed
  state reproduces across days.
- Same wheel as every prior window
  (`0.32.3.dev202609192322+925cfa64`, sha256 `4ef82f5d…`, libmlx16
  `bbad05a26b32a8ee`): `git diff 925cfa64..origin/main` over `mlx/`,
  `src/`, `CMakeLists.txt`, `setup.py` is EMPTY, so the wheel's C++ bytes
  are identical to the `fabe6697` lineage — no rebuild, both arms share
  it. Arms differ by exactly `vulkan_tdt_loop.py` (pkg-delta line;
  `vulkan_decoder_step.py` byte-identical).
- `agent/tdt-lstm-rebalance` shows a force-update in the fetch log
  (`557db2de → 81c3c227`) — that is the reviewed duplicate-`__main__`
  test-only fix; the overlay's exercised bytes are identical (both tips
  carry `vulkan_tdt_loop.py` blob `9047bbb7…`).

## The change

The joint head gave each thread 8–9 sequential independent fp32 chains
(one per output) — no cross-output ILP unless the compiler invents it.
The pair loop now walks `(j, j + 1024)` in one fused k-loop with two
`precise` independent accumulators (bound `j < 8192`, so every `j2` is
valid), plus a scalar tail for outputs 8192–8197 (the six threads'
ninth output). Per output: identical fp32 ascending-k chain, one fp16
rounding, fp16 bias add, argmax first-max ascending order, dval writes.
No unpacking, no addressing or layout change, no new carriers — only
instruction scheduling by source order. `precise` qualifiers retained.

## Emitted-SPIRV ordering proof (Main requirement)

`RenderedShaderGuard.test_emitted_spirv_preserves_fp32_chains`: the real
rendered shader compiles (glslangValidator -V) and the disassembly shows
**zero fused fp32 ops** (no OpFma — `precise` chains uncontracted), ≥ 4
fp32 multiply-then-add chains, and ≥ 4 distinct function-scope fp32
accumulator variables whose FAdd results are stored back (acc1, acc2,
tail acc, projector acc). SPIR-V sequential-invocation semantics pin
each chain's add order — independent source accumulators alone were not
treated as proof; the emitted code carries the structure.

## Gates — 6/6 pins-EXACT per arm (every run)

status match; 104/104; transcript `db501a8c…`; `encoder_hidden`
`38c73261…`; mel bit-exact; bounds PASS; `control: gpu-loop`; fallback
null; `cpu_tensor_events` 0; timeouts 0. Decode pins hold.

## Result

| arm | tdt_decode median (ms) | per-run (ms) |
| --- | ---: | --- |
| base (post-#12 main) | **852.4** | 847.2, 843.2, 834.3, 864.7, 857.6, 874.9 |
| cand (ILP2) | **834.9** | 838.6, 826.7, 831.7, 834.6, 835.2, 851.4 |

Interleaved sign test: 6/6 pairs candidate-faster (one-sided p ≈ 0.016).

## Recert (same window)

`validate_loop` 5-seed at the candidate identity (pkg-cand overlay,
libmlx16 `bbad05a26b32a8ee`): **5/5 PASS, FAILURES: 0**, windowed mode OK
per seed — run INSIDE the hold before restore, so the recert and the
A/B share the identical window and identity. (Same qualification caveat
as every 5-seed run: 4/5 seeds are zero-emission short-frame controls;
the primary long-path evidence is the 104-token fixture battery above.)

## Window discipline

EncoderSubmitRepair consented to the open slot (their gate not
PASS-ready; they hold no lock). TAKE announced → both units stopped and
verified → lock free → one flock hold (19:49:25–19:50:36) → battery →
validate_loop in-window → restore: both units `active`, llama-server
re-acquired the lock (PIDs 595285/595287), real completion
`chatcmpl-9Fxifovh01wTflnfZwnoU2XF01paK3Or`. jwm1 untouched. Named
handoff to EncoderSubmitRepair.

## Artifacts

`receipts/2026-09-19-tdt-joint-ilp2-ab/`: `summary.json`,
`e2e-report-{base,cand}-1.json`, `decoder-trace-*.json` (14). jw16:
`/var/tmp/tdt-pairload-ab-ilp2/`. Raw JSON locations identical in
structure to the prior two A/B receipts.

## Not claimed

- No cross-host, cross-OS, or final-wheel qualification claims.
- The −2.1 % is scoped to this fixture/host/wheel with overlapping
  ranges; per-run attribution (register pressure, scheduling) not
  decomposed.

## COUNTERBALANCED REPEAT — NO-LAND (pre-registered rule, 2026-09-19 ~20:13)

The pre-registered counterbalanced battery (schedule AB/BA/AB/BA/AB/BA,
frozen at `040f456e` before execution; pins BASE `fabe6697…`, CAND
`040f456e…`; exercised-file hashes recorded pre-run) **fails to confirm
the win**:

| arm | tdt_decode median (ms) | per-run (ms) |
| --- | ---: | --- |
| base | **844.8** | 843.9, 844.6, 853.8, 858.1, 845.0, 843.6 |
| cand | **845.5** | 841.0, 827.5, 850.2, 827.2, 850.0, 875.7 |

- Median delta **+0.7 ms** — no effect.
- Paired deltas by round (cand − base): −2.9, −17.1, −3.6, −30.9, +5.0,
  +32.1 (4/6 paired wins) — split by order: AB [−2.9, −3.6, +5.0],
  BA [−17.1, −30.9, +32.1]. The largest pro-candidate deltas sit in
  BA rounds where the candidate ran SECOND — consistent with the
  order/warmup bias Main flagged on the first battery.
- Gates 6/6 pins-EXACT both arms (correctness intact; the change is
  exact, it just is not faster).

**Verdict: ILP2 = NO-LAND.** The first battery's 6/6 A-then-B paired
wins were order/warmup bias, not an effect. PR #13 closed as NO-LAND;
branch `agent/tdt-joint-ilp2` preserved unmerged; kernel stays at the
landed rebalance state (sequential per-thread chains). Next step:
device phase attribution of the ~845 ms baseline before any further
micro-bet.

Window: dual-named consent (Main + Encoder explicit release) → both
units stopped/verified → single flock hold (20:13:37–20:14:48) →
restore: both units active, llama-server PIDs 597146/597148, real
completion `chatcmpl-Y6XrU8llWNWoRZBp0OBJgJGwGDS4jUvf`. Artifacts:
`summary-counterbalanced.json`, `schedule.txt` mirrored here; jw16
`/var/tmp/tdt-pairload-ab-ilp2/`.


## Repository note

Commit `914906e` (this receipt's counterbalanced section + a rebalance
receipt cleanup) is an AMEND of GpuDispatchParity's `03de1fc` isolation
plan receipt — the shared checkout had both lanes' uncommitted edits when
their commit landed and my unconditional `--amend` folded in after.
Content of both changesets is intact; reflog preserves `03de1fc`;
`74b0276` (Jwm1RecoveryLive) stacks on the amended commit, so history is
left as-is rather than rewritten.
