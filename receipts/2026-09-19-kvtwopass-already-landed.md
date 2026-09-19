# KV-walk two-pass + global scratch — assignment closed ALREADY-LANDED (2026-09-19)

Lane: KvTwoPass. Assignment (from the GpuPerfLegs closure receipt's named
lever): implement the runtime-side KV-walk two-pass with global-scratch
plumbing, ceiling ~+15-18% on ctx1024 decode (150.8 -> ~175 tok/s class),
digests 7fd25a869ff21678 (short) / 7da83f06ec9f001d (ctx1024) held.

## Verdict

**ALREADY LANDED.** The priced design is implemented, merged to mlx-omarchy
main, gated, measured, and recorded in the parity table. No code remained to
write; this lane changed nothing and ran no GPU window.

## Evidence

- mlx-omarchy `agent/decode-two-pass` @ `283aa076` IS an ancestor of main
  (asserted via `git merge-base --is-ancestor`; merged via `23fc9a9a`,
  recorded in `receipts/2026-09-17-decode-two-pass.md` and
  `receipts/2026-09-17-gpu-parity-jw16-post-twopass.md`).
- The implementation matches the priced design line-for-line:
  - `overlay/mlx/backend/omarchy/shaders/sdpa_decode_native_p1.comp` —
    grid = heads x blocks, one 32-thread workgroup per (head, block),
    stride-fold key order (block + t*blocks), scratch stride factor
    `2u + SIMD` (global scratch stores f32 block max/sum + packed f16
    output pairs).
  - `shaders/sdpa_decode_native_p2.comp` — heads-grid pass-2 merge reading
    partials from the scratch binding.
  - `primitives.cpp` (~line 11400): `params.flags != 0` splits into pass 1 +
    pass 2; scratch = heads*blocks*34 uint32 words kept alive via
    `encoder.add_temporary`; one-pass (k<1024) and bf16 routes untouched.
  - `compute.h:642-643`: profile ids `SdpaDecodeNativeTwoPassP1F16`/`P2F16`.
- Gates, already run and recorded by DecodeTwoPass / DecodeTwoPassConfirm:
  - pins `7fd25a869ff21678` (short) and `7da83f06ec9f001d` (ctx1024) exact
    on BOTH hosts, every window (3/3 jw16 windows + original).
  - jwm1 flat (-0.7% to +0.4%); short flat everywhere.
  - primitive 103/103 + runtime 41/41 recorded at `afe07dfa` (post-merge
    lineage).
- Measurement: ctx1024 130.7 -> 150.8 tok/s in the README parity table
  (v0.6.1 -> v0.7.1); pooled across three jw16 windows: +8.5% paired-round
  median, +9.6% pooled medians, +10.3% median-of-window-medians; best
  steady-state 168.9 tok/s. That lands INSIDE the priced net ceiling band
  (gross +15-18% minus the extra dispatch sink ~0.23 ms/token = -0.7 to
  -1.0 ms/token net = ~166-176 tok/s class); the "~175" gross figure was
  pre-sink and is not reachable with the sink accepted. Today's v0.7.1
  ladder (`receipts/2026-09-19-q4-chainbatch-jw16.md`: 191.9 / 150.76,
  pins 3/3) re-measured the landed state hours before this assignment.

## Why the residual stays

Post-landing walk slope is 1.529-1.589 us/KV-token (vs native ~0.04): the
remaining excess lives in the one-pass regime (k in [256,1024)) and the
two-pass partial traffic. Lowering the two-pass crossover below k=1024
would change the fold width there and SHIFT THE NUMERICS (one-pass and
two-pass merge orders are not bit-identical; only the 64/128-block two-pass
identities are proven) — a behavior change outside the pins and divergent
from upstream's crossover, and the walk was independently shown insensitive
to restructuring (`2026-09-17-jw16-decode-gap.md`). Not attempted; not
priced.

## Corrections this receipt makes on the record

`receipts/2026-09-19-q4-chainbatch-jw16.md` lists "two-pass with
global-scratch plumbing ... not attempted here" among open levers. The
"not attempted here" is true of that lane, but the lever itself is landed
and its measured gain is the 150.8 number that same receipt reports —
future lanes should treat the KV-walk structural lever as CONSUMED, and the
remaining ~50% ctx gap as the closed G13X fixed-overhead family.

## Artifacts

- No new code, wheels, windows, or GPU locks. Verification was repo-state
  only (`~/src/mlx-omarchy` main `39bef329`, README parity rows at :111-116,
  shader/primitive/compute sources cited above).
- `63c1d3cf` not an ancestor of anything touched (nothing runtime-side was
  modified at all).
