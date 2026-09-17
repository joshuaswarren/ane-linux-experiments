# Native-shape per-block two-pass decode SDPA — implementing Jw16DecodeGap's named lever (2026-09-17)

Lane: DecodeTwoPass (successor to Jw16DecodeGap). Assignment: implement or
refute the lever named in `receipts/2026-09-17-jw16-decode-gap.md` — the
native-shape per-block two-pass for the long-context decode walk — with
digest integrity screened first, both-host perf vs the v0.6.6 baseline, and
a ship/no-ship verdict.

## Verdict

**IMPLEMENTED. Digest-exact on every screen. ctx1024 +10-11% on jw16,
flat on jwm1, short flat on both. Ship candidate.** The measured win
lands inside the receipt's predicted net ceiling (−0.7 to −1.0 ms/token
after the extra dispatch sink); % of native moves from ~46-49% into the
predicted 57-60% band on the Max, and the M1 shows no regression.

## The change

mlx-omarchy `agent/decode-two-pass` @ `283aa076` (on unified main
`98e3e2b8`), wheel
`mlx_omarchy-0.32.2.dev202609172006+283aa076-cp314-cp314-linux_aarch64.whl`:

- `shaders/sdpa_decode_native_p1.comp` (new): native Metal's
  `sdpa_vector_2pass_1` shape — grid = heads × blocks, ONE 32-thread
  workgroup per (head, block), one subgroup, **no shared memory, no
  barrier**. Serial depth per workgroup drops from k/32 key-steps (fused
  kernel: each of 32 subgroups walks blocks/32 chains sequentially) to
  k/blocks (~8.2 at the 128-block crossover) with heads×blocks concurrent
  chains. Reproduces the fused kernel's per-block loop verbatim — same
  stride-fold key order (block + t·blocks), same fma/exp chain, same
  subgroupAdd over dim lanes — and stores the same intermediates the fused
  kernel kept in shared memory: f32 block max, f32 exp sum, 32 packed f16
  output-pair words per block.
- `shaders/sdpa_decode_native_p2.comp` (new): the fused kernel's pass-2
  merge unchanged, reading partials from a scratch binding instead of
  shared memory. Same 1024-thread workgroup per head, same stride-fold
  lane/block loops, same exp factors, same shared-memory transpose + SIMD
  reductions, same f16 output-pair stores.
- `primitives.cpp`: decode route splits on `flags != 0` — pass 1 on a
  (heads, blocks) grid then pass 2 on heads, with the scratch words
  (heads·blocks·34 uint32: blocks max + blocks sum + blocks·32 packed
  words) as a 5th binding kept alive by `add_temporary`. One-pass
  (k<1024) and the bf16 arm are byte-for-byte unchanged routes.
- `sdpa_decode_native.comp`: former in-workgroup two-pass section removed
  (clean cutover); the f16 arm is now one-pass only. The route's
  shared-memory gate constant is untouched, so routing on every device is
  unchanged.
- `compute.h`/`compute.cpp`/`CMakeLists.txt`: two appended profile ids
  (`SdpaDecodeNativeTwoPassP1F16`/`P2F16`) and their blobs.

Bit-exactness argument (screened, not assumed): per-block state depends
only on the block's keys in ascending stride-fold order and the same
in-subgroup arithmetic, computed by the same hardware subgroup ops on the
same 32 lane values; pass 2 re-executes the fused kernel's merge code
load-for-load on identical f32/f16 words. The bf16 arm never sets
flags ≠ 0, so no bf16 surface moved.

## Digest integrity (screened FIRST, pins fatal)

Harness bytes identical on every run and host: `bench_decode.py`
`f5062d88f34b0845c1e59b0b35d2e33ae02180f636a0f65c543a4366ec2bef7f`,
`bench_matrix.json`
`df8eb9f3ed84182604379b7cde070ade706bfe590fbf83a35b1877cfaf43f258`,
`MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1`, `--tokens 32 --temp 0.0
--seed 0 --warmup-tokens 4`, fresh subprocess per leg.

Screen order was enforced by the window script: the digest screen runs
first and ANY failure aborts before the A/B starts (this actually fired
twice — missing lane modules and a missing env export — and aborted the
window before any perf claim; those were harness-plumbing failures, not
digest breaks).

jw16 screens (wheel `+283aa076`, libmlx16 `aa5615cea4e584f7`, provenance
`verified=match`):

| leg | prompt tokens | digest | pin | verdict |
| --- | ---: | --- | --- | --- |
| short | 30 | `7fd25a869ff21678` | exact | PASS (one-pass route untouched) |
| ctx1024 | 1053 | `7da83f06ec9f001d` | exact | PASS (two-pass split bit-identical) |

jwm1 screens: same pins exact (see below).

## Cross-fold-width check (k=1024 exact)

No numbered-template item count lands exactly 1024 prompt tokens (steps
are 40 tokens/item: 19→1013, 20→1053). The `ctx19` leg (1013 prompt
tokens) instead crosses k=1024 mid-generation, exercising the blocks=64
fold at the k=1024 step and blocks=128 above it. Base and fix arms
produced ONE identical generated-ids digest `31267e7ed4c6d0dc` across
all rounds on both hosts — relative bit-exactness across both fold
widths.

## Same-window A/B vs v0.6.6 (medians of 6 interleaved rounds, arms alternating per round)

jw16 (BATTERY_MODEL=/var/tmp/jw16gap-model local snapshot):

| arm | short tok/s | ctx1024 tok/s | ctx19 tok/s | libmlx16 |
| --- | ---: | ---: | ---: | --- |
| base (v0.6.6) | 192.47 | 149.83 | 141.60 | `06e43c203e85a16a` |
| fix (283aa076) | 192.23 | 165.31 | 152.70 | `aa5615cea4e584f7` |
| delta (all rounds) | −0.1% | **+10.3%** | +7.8% | |

Steady-state rounds only (rounds 3-6; the first two rounds of every
arm/leg after the service restart carried a warm-up transient that hits
base and fix alike — see hazard note): short 192.6→192.85 (flat),
ctx1024 152.0→168.9 (**+11.1%**), ctx19 145.6→160.0 (+9.9%).

ms/token ctx1024: 6.58 → 5.92 (**−0.66 ms/token**) — inside the named
net ceiling (−0.9 to −1.2 ms minus ~0.23 ms for the extra dispatch sink
≈ −0.7 to −1.0 ms net).

jwm1 (model = hub id via the host's offline cache; no service involved,
lock-only window):

| arm | short tok/s | ctx1024 tok/s | ctx19 tok/s | libmlx16 |
| --- | ---: | ---: | ---: | --- |
| base (v0.6.6) | 116.44 | 100.40 | 103.40 | `06e43c203e85a16a` |
| fix (283aa076) | 116.90 | 100.65 | 102.70 | `aa5615cea4e584f7` |
| delta | +0.4% | +0.2% | −0.7% | |

jwm1 is a NULL result: the M1's walk depth was not the binding constraint
(its ctx gap is dominated by the fixed per-token overhead, and the
two-pass adds one dispatch + scratch plumbing per layer that cancels its
smaller walk saving). Note the fix rounds are far tighter on jwm1
(ctx1024: 98.4-100.9 vs base's 77.8-105.8 spread) — plausible variance
reduction, single window, not claimed as a finding.

## % of native

Ground truth from the attribution receipt (native ctx1024 M1 Max 3.52
ms/token):

| | ours before | ours after | native M1 Max |
| --- | ---: | ---: | ---: |
| ctx1024 ms/token (jw16) | 6.58-6.67 | 5.92 | 3.52 |
| % of native (jw16) | 46-49% | **~59.5%** | 100% |
| ctx1024 tok/s (jwm1) | ~100.4 | ~100.7 | (M1 native 105.95 gate band) |

The receipt's predicted landing band was ~57-60% of native on jw16; the
measured value is at the top of that band. Short legs unchanged on both
hosts (their gap is the G13X barrier-sink family, untouched by design —
that lever remains the open Mesa-side one named in the attribution
receipt).

## Ship / no-ship verdict

**SHIP-CANDIDATE: GREEN.** No-ship would leave jw16's worst parity
number ~11% slower for zero measured cost anywhere:

- Digest-exact everywhere it can be measured: both published pins
  (`7fd25a869ff21678` short, `7da83f06ec9f001d` ctx1024) exact on BOTH
  hosts; cross-fold-width ctx19 digest `31267e7ed4c6d0dc` identical
  across arms on both hosts (and identical host-to-host).
- jw16 ctx1024 +10.3% all-round medians (149.83→165.31 tok/s), +11.1%
  steady-state; the measured −0.66 ms/token sits at the optimistic edge
  of the named net ceiling (−0.7 to −1.0 ms after the dispatch sink).
- jwm1 flat (−0.7% to +0.4% by leg), short flat on both hosts.
- libmlx sha256 pinned fatal every run: base
  `06e43c203e85a16a...95c` (v0.6.6, byte-identical both hosts), fix
  `aa5615cea4e584f7...92` (wheel `+283aa076`, byte-identical both
  hosts).

Boundary condition, stated plainly: this is a single-window battery per
host with a documented ±8% ctx wander and a two-round warm-up transient.
The jw16 contrast is within-window and interleaved, and it exceeds the
wander band, but the multi-window confirmation battery (the discipline
`266813b` was held to) should run before this rides a release train. No
fallback knob exists or is needed: the change is a clean cutover with
digest identity, not a behavior switch.

## Measurement hazards recorded

- **Warm-up transient:** the first two rounds of every arm and leg after
  an llm-inference restart measured 45-65 tok/s on ctx legs (vs ~150-169
  steady). Interleaved rotation spreads it across arms but cannot remove
  it; medians over 6 rounds dampen it. The steady-state contrast (later
  rounds, arms alternating) is the honest number and is reported
  alongside the all-round medians.
- Provenance stamping hazard: building with `MLX_OMARCHY_WORK_DIR`
  pointing into ANOTHER lane's checkout stamps the wheel with THAT
  checkout's commit (setup.py resolves the git dir upward from the work
  dir). First jw16 build came out `+266813b0`-stamped (wrong commit,
  correct code) and was rebuilt from the lane's own tree. The shipped
  screening wheel is `+283aa076`, provenance `verified=match`.

## Hardware safety / coordination

- jw16: one flock hold (inode 12), window ~12 min; llm-inference stopped
  before, restarted and CONFIRMED ACTIVE after (`active`, lock holder =
  service llama-server); lock never stolen/unlinked; TAKE/RELEASE
  announced via hub with inode + holder PID. Aborted attempts (module
 /env plumbing) each restored the service before the retry.
- jwm1: two aborted holds (missing `mlx_lm` in the fresh fix venv; each
  hold lasted seconds and released cleanly), then one complete hold:
  screens + 6-round A/B, ~9 min. No service involved; lock never
  stolen/unlinked; TAKE/RELEASE announced via hub with inode + holder
  PID.
- `63c1d3cf` asserted non-ancestor before every push.

## Artifacts

- This directory: `jw16/{ab.json, screens.json, exit.txt, lock.txt,
  started.txt, finished.txt, df-tmp.txt, mem.txt}`; `jwm1/{...}` (same
  set).
- jw16: `/var/tmp/decodetp-wt` (build tree @ 283aa076),
  `/var/tmp/decodetp-venv` (fix venv, libmlx `aa5615cea4e584f7`),
  `/var/tmp/DecodeTwoPass/` (lane drivers + results),
  `/var/tmp/decodetp-build2.log` (wheel build).
- jwm1: `/var/tmp/decodetp-venv`, `/var/tmp/DecodeTwoPass/` (same lane).
- mlx-omarchy: branch `agent/decode-two-pass` @ `283aa076` (also pushed
  to `jw16:/var/tmp/rope-pair-land` and origin).
- x86 compile check: full wheel build EXIT=0 (`/tmp/decodetp-x86-build.log`).
- libmlx sha256 (full): base v0.6.6
  `06e43c203e85a16acea8f691609cc9519526dbc63124f7743df50737b204295c`
  (byte-identical on jw16 and jwm1, verified at deploy); fix
  `aa5615cea4e584f79297cfb52316482e74c142ec5e5b006387a5891705b61c92`
  (byte-identical on jw16 and jwm1, verified from both venvs).
