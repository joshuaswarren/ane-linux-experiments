# jw16 decode-gap attribution — why the M1 Max sits further from native than the M1 (2026-09-17)

Lane: Jw16DecodeGap. Assignment: root-cause why jw16 (T6001 / M1 Max,
32-core GPU, G13C) sits much further from native than jwm1 (T8103 / M1,
8-core GPU, G13G) on decode — especially ctx1024 (the worst number in the
parity table) — with the same harness and pinned libmlx on both hosts,
then attempt the highest-share fix. Attribution first, fix second.

## Verdict

**Attributed; one digest-clean fix screened (marginal); residual named
with quantified ceilings.** The jw16 gap is two additive absolute
overheads that do NOT shrink as the die gets faster:

1. **Fixed per-token overhead ≈ +1.66 ms/token (47-50% of the ctx1024
   gap).** Dominated by the per-launch kitchen-sink CDM_BARRIER drain on
   G13X plus the dispatch chain — measured per-launch dependent-chain
   cost is **27.7 µs on jw16 vs 20.2 µs on jwm1**: the drain grows with
   the die, and native Metal has no equivalent. Absolute-ms overheads on
   a die whose native token is ~1.9× faster than the M1's is exactly why
   "bigger die, further from native".
2. **KV-walk excess ≈ +1.42 ms/token at ctx1053 (42-45% of the gap).**
   The SdpaDecodeNativeF16 walk is latency/structure-bound, not
   bandwidth-bound: effective KV streaming is **~9 GB/s on jw16 (worse
   than jwm1's ~14 GB/s)** vs native M1 Max's ~331 GB/s. Proven
   insensitive to chain count (termB) and, this lane, to load-staging
   restructure — the per-key-step cost (~2.5 µs serial depth atom) is
   intrinsic to the fused kernel's structure on this stack.

Candidate shares for ctx1024 (same-window base 6.67 ms/token vs native
3.52 ms): fixed overhead +1.66 ms (≈50%), KV-walk excess +1.42 ms
(≈43%), base compute at parity (residual ≈ noise + window wander ±8%).
Short leg (5.24 vs native 3.49 ms): fixed overhead is ~64% of the gap —
the barrier sink alone prices most of it.

## Same-harness measurement (v0.6.6 wheel, pinned libmlx, both hosts)

- Wheel: `mlx_omarchy-0.32.2.dev202609171827+2f58ead` (v0.6.6) in
  `/var/tmp/V064REL-venv` on BOTH hosts.
- Loaded `libmlx.so` sha256 (full):
  `06e43c203e85a16acea8f691609cc9519526dbc63124f7743df50737b204295c` —
  byte-identical file on both hosts; bench_decode's provenance line
  (`libmlx.so=sha256:06e43c203e85a16a`) asserted equal on every run by
  the drivers (pins fatal).
- Harness: `scripts/bench_decode.py`
  `f5062d88f34b0845c1e59b0b35d2e33ae02180f636a0f65c543a4366ec2bef7f`,
  `scripts/bench_matrix.json`
  `df8eb9f3ed84182604379b7cde070ade706bfe590fbf83a35b1877cfaf43f258` —
  same bytes on both hosts (sha-verified at deploy). Fresh subprocess
  per leg, `MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1`, `--tokens 32
  --temp 0.0 --seed 0 --warmup-tokens 4`, 3 interleaved rounds with
  rotating leg order, one `flock -w 900 /tmp/m1-gpu.lock` hold per host
  (jwm1 inode 35; jw16 inode 12), stdout to files.
- KV ladder legs: `short` (30 tokens) + numbered-template prompts at
  4/10/20 items → measured 414/653/1053 chat-template tokens.
- jw16 llm-inference stop/restart per protocol; ACTIVE confirmed after
  (service2.txt); lock never stolen or unlinked.

**Measurement hazard recorded (Main-directed):** jw16's venv
huggingface_hub refuses offline revision resolution for the pinned
model revision where jwm1's venv accepts it (venv hub versions differ);
the symptom is a silent `LocalEntryNotFoundError` — a skip, not a
number. The portable path is passing the LOCAL SNAPSHOT DIR to
bench_decode (`BATTERY_MODEL=/var/tmp/jw16gap-model` →
`snapshots/a5339a41…`). Anyone comparing hosts without pinning the
model path gets a silent skip.

### Ladder (medians of 3 interleaved rounds)

| leg | N (prompt tokens) | jwm1 tok/s | jwm1 ms/tok | jw16 tok/s | jw16 ms/tok |
| --- | ---: | ---: | ---: | ---: | ---: |
| short | 30 | 116.44 | 8.5879 | 190.95 | 5.2369 |
| ctx256 | 414 | 116.26 | 8.6011 | 179.18 | 5.5810 |
| ctx512 | 653 | 107.07 | 9.3394 | 161.49 | 6.1925 |
| ctx1024 | 1053 | 105.85 | 9.4472 | 150.00 | 6.6666 |

- jwm1 pins: short `7fd25a869ff21678`, ctx1024 `7da83f06ec9f001d`
  exact on all rounds. jw16 pins: same — exact on all rounds.
- jwm1 anchors vs the v0.6.6 gate (117.25 / 105.95) and jw16 short vs
  its gate (190.59): within run-to-run band. jw16 ctx today 150.0 vs
  gate 139.83 — inside the documented ±8% ctx window wander.
- Linear fits: **jwm1 t0 = 8.48 ms, slope 0.957 µs/KV-token; jw16
  t0 = 5.14 ms, slope 1.458 µs/KV-token.** The response is
  regime-structured (one-pass below k=1024, 64/128-block two-pass at
  and above; the ctx256→ctx512 wall step is the one-pass lengthening),
  so the fits summarize, they do not model.

### Micro probes (same code both hosts)

| probe | jwm1 | jw16 | reading |
| --- | ---: | ---: | --- |
| dependent-chain µs/launch | 20.24 | 27.69 | per-launch drain ~1.37× worse on the Max |
| stream GB/s (scalar fp32 add) | 8.0 | 30.9 | raw streaming scales with the die — bandwidth is not the decode limit |
| fp16 2048² matmul TFLOPS | 0.484 | 1.774 | compute advantage is real (receipt band 0.54 / 1.99) |

### SDPA kernel screens (batched-eval, route asserted, SdpaDecodeNativeF16)

jwm1 this lane (`screens.json`); jw16 base + fix (`screens.json`,
`screens-fix.json`); termB's window-wander caveat applies —
within-window adjacent contrasts only:

- One-pass marginal (14,2), k=30→768: jwm1 ~82 ns/key; jw16 similar
  order (52-57 ns/key chain rows, termB; ~89 ns/key ladder rows).
- Chain-count invariance reproduced on jwm1: (q,1) rows at k=1024 are
  flat 84.3-91.7 µs for q=1→14 — confirms termB's mechanism on the M1
  too: the walk is bound per-subgroup, not by aggregate traffic.
- Two-pass crossover reproduced on jwm1: k=1024 (64 blocks) 59.1 µs is
  FASTER than one-pass k=768 (103.5 µs); k=1053 (128 blocks) 77.7 µs.
  Screen floor ~30 µs + ~2.5 µs × serial depth (k/32 key-steps per
  workgroup) fits all rows within screen wander.
- jw16 fix screens vs base: (14,2,1053) 82.0 → 80.3 µs (−2.1%) — the
  kernel-level counterpart of the +2.46% wall win.

## The attribution table

Ground truth (this lane's same-window ladders; native from the
assignment-rounding Metal divisors):

| quantity | jwm1 ours | jw16 ours | native M1 | native M1 Max |
| --- | ---: | ---: | ---: | ---: |
| t0 fixed ms/token | 8.48 | 5.14 | ~6.62 | ~3.49 |
| KV slope µs/KV-token | 0.957 | 1.458 | ~0.43 | ~0.04 |
| ctx1024 ms/token | 9.44 | 6.67-7.15 | 7.10 | 3.52 |
| relative ctx gap | 1.33× | 1.89-2.03× | — | — |
| effective KV bandwidth | ~14 GB/s | ~6.8-9 GB/s | ~29 GB/s | ~331 GB/s |

Per-candidate shares of the **jw16 ctx1024 gap** (6.67 → 3.52 ms):

| candidate | share | evidence |
| --- | ---: | --- |
| fixed per-token overhead (barrier sink + dispatch chain) | **≈50%** (+1.66 ms) | t0 gap ours-vs-native on both dies ≈ the measured per-launch drain × 201 dispatches; drain is 27.7 µs/launch on jw16 vs 20.2 on jwm1 (grows with the die); termA addendum priced jw16's sink ~9 µs/launch |
| KV-walk excess (latency/structure-bound) | **≈43%** (+1.42 ms) | slope gap ours 1.458 vs native 0.039 µs/token; ~2.5 µs serial depth-step × k/32; insensitive to chain count (termB + this lane) and to load staging (this lane's screen) |
| memory bandwidth per core | **refuted as binding** | raw stream probe scales 3.9× with the die, yet the KV stream serves LESS effective bandwidth on jw16 than on jwm1 |
| kernel occupancy / chain starvation | **refuted** | chain-count invariance on both dies; depth is structural (k/32 per workgroup), not occupancy-limited |
| clock/power behavior | **<10% residual, unmeasured directly** | no userspace GPU-clock readback on Asahi (same gap as termB's counter finding); matmul probe within wheel-to-wheel band; ±8% ctx window wander documented |

Why jwm1 sits at 75-78% while jw16 sits at 46-49%: the same two absolute
overheads exist on both dies (jwm1: +1.83 ms fixed, +0.53 ms walk at
ctx1053), but native M1 Max's token is ~1.9× faster than native M1's, so
identical-or-worse absolute ms doubles the relative gap. The walk is
actually WORSE per key on the Max (slope 1.458 vs 0.957 µs/token; screen
per-step worse) — the opposite of native's bandwidth scaling.

## Fix attempt (screen-first discipline)

`agent/jw16-decode-gap` @ `266813b0` (mlx-omarchy, on unified main
98e3e2b8): restructures BOTH SdpaDecodeNativeF16 walks so loads are
staged ahead of the state-update chain while per-key arithmetic, key
order, and the state algebra are untouched (two-pass: j-major interleave
of the subgroup's owned blocks; one-pass: PIPE_B=4 key groups staged
before ordered updates). Digest-safety argument: identical loads, same
ops, ascending key order, no shared state between chains. glslang -V
clean, f16 + bf16.

**A/B on jw16 (6 interleaved rounds, alternating arms, fresh
subprocesses, pins fatal): 24/24 pins held.**

| arm | short tok/s | ctx1024 tok/s | libmlx16 |
| --- | ---: | ---: | --- |
| base (v0.6.6) | 190.67 | 133.30 | `06e43c203e85a16a` |
| fix (266813b) | 189.41 | 136.57 | `846641408618cc9c` |
| delta | −0.66% | **+2.46%** | |

**Labelled marginal, not shipped as the closer**: +2.46% ctx is inside
the leg's documented ±8% window wander, short is flat within noise, and
the kernel screens moved only −2.1% — the walk does not respond to
dependency restructuring within the workgroup. The j-major/PIPE_B wheel
is a legitimate digest-clean candidate for a multi-window battery, but
this lane does not claim it as the parity fix.

### Named next lever (with ceiling)

The walk's serial depth is k/32 key-steps per workgroup — invariant in
blocks, set by the fused one-dispatch structure (each workgroup = one
head, 32 subgroups, each owning blocks/32 sequential chains). Native
Metal's two-pass uses grid = heads × blocks with ONE 32-thread workgroup
per block: depth k/blocks ≈ 8.2 with 1792 concurrent chains. Porting
that shape (per-block pass-1 workgroups writing f16/f32 partials to a
global scratch binding + a heads-grid 32-thread pass-2 kernel
reproducing the exact stride-fold + SIMD-reduction order) has a ceiling
of roughly **−0.9 to −1.2 ms/token on ctx1024 (~+15-18% ctx, to ~57-60%
of native)**, minus one extra dispatch sink (~9.5 µs × 24 layers ≈
0.23 ms). It requires new scratch plumbing (5th binding + temporary
lifetime) and bit-exact reproduction of the pass-2 merge order — the
risk that stopped this lane at the screening stage, stated openly.

The fixed-overhead share (~50%) is the G13X barrier family (termA):
designed-bit trim recovers +13% short / −3.2% ctx — proven coupled; a
both-legs G13X set (e.g. adding usc_cache_inval/PBE bits) remains the
open Mesa-side lever and is untouched by this lane.

## Hardware safety / coordination

- jwm1: one flock hold (inode 35), 19:04-19:07Z, battery + probes; no
  service on jwm1 involved.
- jw16: two windows under the announced queue (TAKE/RELEASE with inode +
  holder announced via hub; llm-inference stopped before, restarted and
  CONFIRMED ACTIVE after each — service2.txt `post: active`); lock never
  stolen/unlinked; stray-llama recovery was GpuMatmulBisect's window.
- Mesa on jw16 untouched (`hk5deac1c-2` kitchen sink); no driver
  installed this lane; `63c1d3cf` asserted non-ancestor before every
  push.

## Artifacts

- This directory: `jw16-results/{ladder.json, ab.json, micro.json,
  screens.json, screens-fix.json, exit2.txt, service2.txt}` (jw16
  battery), `.local/jw16gap/` (drivers: ladder_driver.py, ab_driver.py,
  micro_dispatch.py, locked.sh/locked2.sh, window wrappers).
- jwm1: `/var/tmp/Jw16Gap/{ladder.json, micro.json, screens.json}`.
- jw16: `/var/tmp/Jw16Gap/` (all of the above + window logs),
  `/var/tmp/jw16gap-wt` (build tree @ 266813b),
  `/var/tmp/jw16gap-venv` (fix venv, libmlx
  `84664140…`), `/var/tmp/jw16gap-build.log`.
- Mesa/MLX repos: `joshuaswarren/mlx-omarchy` branch
  `agent/jw16-decode-gap` @ `266813b0` (screened candidate, preserved).
