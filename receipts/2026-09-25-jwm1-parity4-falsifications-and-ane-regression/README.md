# t8103-host lane: TDT fusion falsified, mel DFT attribution falsified, decoder-step Vulkan fix landed, ANE half-speed regression found (2026-09-25)

Owner: Jwm1Parity4. Host: jwm1-linux (T8103). Stack: mlx-omarchy main
`ce91f5b8e` (fix lands `ecda0fa33`), omarchy-ane kmod `9a0ec81`
(srcversion `0BE464B0928DD42B1E96D0F`, installed 07:49), venv
`/var/tmp/jwm1-parity3-venv` (wheel `+af73787`), pkg
`~/q38-build/mlx-omarchy/overlay/tools` unless noted. Prior lanes:
`2026-09-25-jwm1-parity3-main-battery`, `2026-09-25-jwm1-parity3-parakeet-298`.

## 1. TDT fold fusion (6->5 kernels/slot): implemented, BIT-EXACT, and FALSIFIED on wall time

The receipt §3 fusion design was implemented exactly: fold (layer-0
LSTM step) recomputed in-kernel from `bsum0` as a prologue in both
consumers — chains-l1 (per-workgroup, feeding the `x_in` rows) and
fold_proj (per-lane, feeding the state copy) — repeating the identical
ascending-order arithmetic, so every output is bit-identical. Branch
`agent/jwm1-parity4-tdt-fuse` @ `e87f50c65` (mlx-omarchy, pushed).

Correctness gates, all PASS on jwm1:
- validate_chain host-vs-chain bit-exact at 192 slots (token_ids,
  frame_indices, durations, hidden, cell), 5 reps.
- Duration sweep PASS at 1/2/7/8/13/33/100 encoder frames (all five
  checks each).
- sim_chain_walk 300 seeds ALL MATCH (dur0 coverage 286 seeds).
- test_tdt_decode_path 12/12; overlay tests clean.
- contract3 `all_gates: true` — transcript `db501a8c…`, hidden
  `51830b6f…`, `decoder_calls=0`, `joint_calls=0` (both under load and
  on the quiet box).
- Corpus gate (1089-134686-0000.wav, 375 frames, 104 emissions):
  loop-vs-chain bit-exact; chain 139.7-142.1 ms vs loop 222.6 ms.

Dispatch profile: 5 dispatches/slot confirmed (2880 vs 3456 on the
fixture, exact 6:5).

**Wall verdict — REJECTED.** Interleaved clean-box A/B (chain_bench
64/9, two rounds, quiet box):

| round | old (6-kernel) med/min ms | fused (5-kernel) med/min ms |
|---|---|---|
| 1 | 164.6 / 121.9 | 185.1 / 135.4 |
| 2 | 160.1 / 125.3 | 168.8 / 137.7 |

The fusion is ~12 ms SLOWER at min, not 18 ms faster. The receipt's
"-18 ms measured-equivalent (94 us x 192 slots)" treated the grid-1
kernels' 94 us profile attribution as recoverable dispatch latency;
the pipelines evidently already overlap most of it, and the prologue's
redundant per-workgroup recompute (100x fold work + 256K random LUT
lookups/slot) costs more than the dispatch saves. The same lesson
applies a fortiori to the remaining §3 legs: fold_proj -> window
prologue re-adds 33x the projector stream (measured memory-traffic
loss), and control -> window epilogue needs a cross-workgroup atomic
pattern for at best the same already-overlapped launch gap. The whole
§3 fusion lever is CLOSED as falsified; branch kept pushed for the
record. Nothing landed on main for this.

## 2. mel DFT: the "11 ms/rep" attribution was wrong (contention-polluted profile)

Direct measurement of the UNMODIFIED `_dft_frames` on the 3001x512
fixture frames: **2.7 ms/rep wall** (27.1 ms over 10 reps), not the
11.0 ms/rep in the parity3 receipt — that number came from the same
co-running-process profile whose chain wall inflated to 179 ms (§1 of
the prior receipt). A 256-thread component-split variant was built and
verified bit-exact (old-vs-new bitwise equal on 3001x512 random
frames, uint32 view) but measured **2.1x slower** (57.2 vs 27.5 ms per
10 reps) — reverted; the 64-thread kernel is already ~0.9 us/frame.
mel_frontend contract stage reproduces at 22.4-22.8 ms (receipt said
21.4) — the mel lever inside the stage is NOT the DFT and is at most
~1 ms vs macOS; effectively CLOSED. The remaining mel-stage deltas are
structural (kernel count / submit pattern), not the named kernel.

## 3. decoder-step Vulkan subset defect: FIXED and landed (mlx-omarchy main `ecda0fa33`)

`run_step`'s skip_lstm joint path binds the caller's fp32 decoder
state into the `pj16_in` slot; the jmode==0 branch read it into a
`float16_t` without a cast. Metal allows the implicit conversion; the
omarchy Vulkan translator emits an unconverted SSBO float read and
glslc rejects the kernel (`cannot convert from readonly highp float to
temp float16_t`, shape `[6,8198]`). Any host-path decode that exhausts
the six-frame speculative window hit this — validate_chain never did
(all its joint queries hit the fused/spec shortcuts), which is why the
latent defect survived on main.

Fix: explicit `float16_t(pj16_in[i])` in `_JOINT_SOURCE` and
`_JOINT_WINDOW_SOURCE`. Values unchanged (no-op on the fp16 binding;
same RN conversion Metal performed implicitly). Proven by the corpus
host-path gate: 1089-134686-0000.wav and syn-short.wav now pass
host-vs-chain bit-exact (727.6 vs 142.1 ms; 247.6 vs 70.4 ms) — the
exact path that failed to compile before the fix. Committed as
`ecda0fa33` on mlx-omarchy **main** (merged from
`agent/jwm1-parity4-tdt-fuse` @ `31240f286`).

## 4. NEW FINDING: ANE engine running ~1.8x slow on jwm1 since the 08:55 genpd resume

The certified battery (08:0x, this same boot) measured whole-encoder
`ane_exec_ms` 141.1/140.4/140.6 and contract encoder_ane 142.2.
Measured now, same venv/protocol/kmod/wheel, quiet box, twice:

- contract3 encoder_ane median 292-294 ms (2.00x), tdt_decode stage
  206-221 ms (vs 133.4), mel_frontend 22.6 (vs 21.4, unchanged),
  total 529 vs 298.6.
- Raw in-process engine exec (direct InProcessAne submit, golden
  inputs): 199.7-267.3 ms across 4 submits; send 0.2-0.5 ms, read
  0.1-0.3 ms — the engine itself, not the shim.
- All pins stay bit-exact (transcript/hidden) — correctness unaffected.

Timeline: kmod identical (`9a0ec81`); the driver logged
`ANE-resume: genpd raise complete` at 08:55:40 (6 resume cycles total;
the last one correlates with QwenAneRef-2's staged-runner prep). The
driver's own probe reads `ANERD ps probe act=0xffffff` ("live pmgr SET
block, every word on") — nominally healthy — yet the engine runs at
roughly half its morning speed. Consistent with the T6001 finding that
the ANE clock is firmware-mediated: a power-domain cycle appears to
leave the T8103 engine at a lower clock than the iBoot-preloaded
state. sysfs unbind/bind is not available (no bind/unbind attributes);
a reboot would re-preload but is forbidden while the M2 hv recovery
depends on jwm1's ACM.

Impact: the Parakeet parity cell cannot be re-certified against the
271 ms bar until the engine clock state is understood — the +150 ms
ANE regression dwarfs the 27.6 ms gap. Requested: QwenAneRef-2's
account of the 08:55 action, and the grouped macOS window's
`powermetrics --samplers ane` now has a concrete Linux-side signature
to correlate (141 ms -> 292 ms across a genpd cycle on the same boot).

## 5. State / handoff

- mlx-omarchy main: `ecda0fa33` (decoder-step Vulkan fix). Branch
  `agent/jwm1-parity4-tdt-fuse` @ `31240f286`: fusion (falsified,
  do not land) + fix (landed).
- ane-linux-experiments main: this receipt.
- Falsified levers (do not re-run): TDT fold->chains-l1/proj fusion
  (+12 ms measured); fold_proj->window prologue (33x projector
  stream); control->window epilogue (atomic last-block for overlapped
  launch gap); mel DFT 256-thread component-split (2.1x slower);
  slots_per_chunk (prior lane).
- Harnesses left on jwm1: `/var/tmp/jwm1-parity3/corpus_gate.py`
  (loop-vs-chain + host-path modes), `/tmp/ane_exec2.py` (raw engine
  exec probe), `/tmp/repro_host.py` (shader-subset repro),
  `vulkan_tdt_chain.6k.bak.py` (pre-fusion file).
- Open: macOS grouped window (powermetrics + `/tmp/macos-retry.sh`)
  still gated on M2FwStart-2; ANE clock state above is now the first
  thing to correlate there.
