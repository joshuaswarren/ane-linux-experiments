# F3 write-out inverse — fix landed, device re-gate green (jw16, 2026-09-18)

Verdict: **F3 out-proj conv computes correctly as-emitted on the real ANE:
rel_l2 0.000207 / 0.000208 / 0.000208 (worst 0.000208 ≤ 0.001, rngs 11/33/57)
— device gate 9/9 PASS. Compile parity holds at 891 cases / 1782 artifacts /
296 convolution. E2E encoder pins EXACT (104/104, db501a8c / 38c73261 /
5b54f4a9, cpu_tensor_events 0).** This closes the F3 finding from the device
gate receipt `f631ca8`.

Refs (both sides of the handoff):
- mil-hwx-compiler `agent/f3-writeout-inverse` @ `e7967f9` (fix) + `389664f`
  (receipt), off origin/main `504a1e4`; pushed; landed to `main` after the
  device gate went green. jw16 build: mil-hwxc sha256 `d9194dd4…`.
- gate branch `agent/encoder-conv-device-gate` @ `c6f86fb` (finding +
  `f3-writeout-permutation.json`), receipt commit `f631ca8` in this repo.

## What the fix is

The gate proved dev run k displays ref run R(k) with exact numerics, so the
engine computes output run k from the weights packed at slot R(k) (measured
against the compiler's identity packing with real random weights — the fetch
map is structural):

    R(k) = ((k >> 1) & 7) | (k & 0x10) | ((((~k) >> 5) & 1) << 3) | ((k & 1) << 5)

The fix parks ref run k at slot R(k) (slot p carries ref run R⁻¹(p),
within-run plane order preserved) — the conv spell of the engine class the
m375 k1024 n1024 linear lowering already compensates (67dfcf1). Per the
template-record protocol:

- `mint_conv_probes`: `writeout_inverse` + `pack_dense_writeout_inverse`,
  gated to the measured geometry only (1024→1024, chunks [16]×4, bias-free,
  spatial_width 375); every other dense capture keeps identity packing.
- `H13Program.cpp`: `packConvDenseWriteoutInverse` + dense-branch dispatch
  under the same gate; cross-checked byte-identical to the python packer on
  a random payload.
- F3 record set: `encoder_conv_c1024_n1024_k1x1_s1_g1_bias0_valid.json`
  gains `device_writeout_decode` (measured table, mechanism, device numbers)
  via `receipts/2026-09-18-f3-writeout-inverse/decode_f3_writeout.py`. The
  captured section is uniform per constant (`fp16 bits 0x3400 + index`, one
  value per constant), so its bytes are invariant under the run placement:
  section sha256 `b04df14b…` unchanged, byte parity against the Apple
  capture keeps holding, only device execution distinguishes the orders.
- `H13ConvTemplates.inc` regenerated via `mint_conv_probes --emit-templates`
  — byte-identical (the task stream carries no weight order); never
  hand-patched; `--check` in test-h13 enforces the pair.

## Compile side (jw16)

`make test-h13` PASS (encoding, anec, 19 CLI suites, `mint_conv_probes
--check`); `make test-h13-parity` PASS **891 / 1782 / 296** — identical to
504a1e4: the record content changed, the count did not.

## Device re-gate (one flock window, scripts/dev_gate_conv.py with
MHWC=fixed build)

| form | program sha256 | rel_l2 (11/33/57) | worst | vs f631ca8 baseline |
|---|---|---|---|---|
| F1 in-proj wmaj | `00a1da99…` | 0.000208 ×3 | 0.000208 | sha+rels unchanged |
| F2 depthwise +bias | `baaac08e…` | 0.000208/0.000207/0.000207 | 0.000208 | sha+rels unchanged |
| **F3 out-proj** | **`305456e7…`** (was `26c04852…`) | **0.000207/0.000208/0.000208** | **0.000208** | **fixed** |
| F4 padconv p0010 | `0c3a70c9…` | 0.000208/0.000207/0.000208 | 0.000208 | sha+rels unchanged |
| slice last-dim | `9515166f…` | 0 ×3 | 0 | unchanged |
| transpose r3 ×2 | `211f2bd1…`/`46307619…` | 0 ×3 ×2 | 0 | unchanged |
| transpose r4 ×2 | `7db7d022…`/`04bd10e2…` | 0 ×3 ×2 | 0 | unchanged |

The F3 program sha moved exactly where the fix applies and nowhere else;
no gate was weakened.

## E2E encoder pins after the fix (abc-launch arm; certified runner
`vulkan_encoder_main_o.py` e93500d2, `/var/tmp/jw16-encoder-islands/bundles`,
worker 6b63261a, libane-strict-fill 04a17653)

status match, 72 submissions, matching_prefix 104/104, cpu_tensor_events 0,
transcript `db501a8c080380ea…`, hidden `38c73261f2923027…`, mel
`5b54f4a9a2ba3434…`, exec_ms 2603.0 — identical to the f631ca8 pins.

## Discipline

TAKE and RELEASE announced to Main before/after; `flock -w 900
/tmp/m1-gpu.lock` (inode 12, never stolen/unlinked); llm-inference stopped
before the window, restarted and confirmed `active` (MainPID 106244) after;
/tmp 30 G free (≥3 GiB gate); stdout to files (`/tmp/f3-gate.log`,
`/tmp/f3-e2e.log`, gate-summary.json). No SET-block speculative writes, no
release publishing, no formatters.
