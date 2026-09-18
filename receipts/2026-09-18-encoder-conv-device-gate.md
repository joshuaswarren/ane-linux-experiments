# Encoder conv device gate + E2E pins at mil-hwx-compiler 504a1e4 (jw16, 2026-09-18)

Verdict: **8 of 9 lowered forms compute correctly on real ANE hardware at the
certified fp16 class (0.000208 / bit-exact); F3 out-proj FAILS as-emitted at
rel_l2 1.413157 — root-caused to its output write-out carrying a 64-run
permutation (exact after inverse: 0.000207).** The Parakeet E2E placement
stack pins EXACTLY on all four arms (transcript `db501a8c…`, hidden
`38c73261`/`ef6afd13`, mel `5b54f4a9`, 104/104, 0 cpu_tensor_events), and
both decode digest pins hold. No gate was weakened; no compiler edit was
made (the F3 fix belongs to the template-record protocol, see below).

Refs: mil-hwx-compiler `504a1e4` (`504a1e42e46432aa30db8068de5bb4b3dcad0282`,
built on jw16, binary sha256 `b16ae1749ad251aed…`); gate branch
`agent/encoder-conv-device-gate` @ `c6f86fb` (scripts/dev_gate_conv.py + F3
permutation record), pushed. Placement-stack side: certified runner of
record `e93500d2` (mlx-omarchy `044f297f` content, on-disk
`/var/tmp/ParakeetE2EJw16/vulkan_encoder_main_o.py`), certified bundle set
`/var/tmp/jw16-encoder-islands/bundles` (select `0879c627`, attn-a-kt
`d05e193a`, pv `76496b74`, oproj-L* `4b682b0f`), worker `6b63261a`,
libane-strict-fill `04a17653`.

## Device gate (scripts/dev_gate_conv.py, one flock window on jw16)

Each case is the exact lowered spelling (the research/oracles/h13 encoder_*
MIL), minted with real random fp16 weights — uniform payloads are
permutation-blind, which is the mechanism that let the wrong oproj lowering
ship green — executed via libane-strict-fill, checked against an fp32 numpy
reference across rngs 11/33/57, budget 0.05.

| form | geometry | program sha256 | rel_l2 (11/33/57) | worst | pass |
|---|---|---|---|---|---|
| F1 in-proj k1×1 wmaj | c1024→n2048, [1,1024,1,375] | `00a1da99…` | 0.000208 / 0.000208 / 0.000208 | 0.000208 | PASS |
| F2 depthwise k1×9 g1024 +bias | same, [1,1024,1,375] | `baaac08e…` | 0.000208 / 0.000207 / 0.000207 | 0.000208 | PASS |
| F3 out-proj k1×1 | c1024→n1024 valid | `26c04852…` | **1.413157 / 1.412878 / 1.412995** | **1.413157** | **FAIL** |
| F4 padconv custom pad [0,0,1,0] g8 | [1,8,375,749]→[1,8,375,750] | `0c3a70c9…` | 0.000208 / 0.000207 / 0.000208 | 0.000208 | PASS |
| slice last-dim | [1,8,375,749]→[…,375] | `9515166f…` | 0 / 0 / 0 | 0.000000 | PASS |
| transpose r3 [0,2,1] | [1,375,1024]↔[1,1024,375] | `211f2bd1…` / `46307619…` | 0 / 0 / 0 ×2 | 0.000000 | PASS ×2 |
| transpose r4 [0,2,1,3] | [1,8,375,128] and [1,375,256,16] | `7db7d022…` / `04bd10e2…` | 0 / 0 / 0 ×2 | 0.000000 | PASS ×2 |

### The F3 finding (reported, not weakened)

The device output is the **exact fp32 reference under a bijection of the
1024 output channels**: 64 runs of 16 planes, cos-sim 1.0 on all 1024
best-match pairs, all best matches distinct. Applying the inverse run
permutation drops rel_l2 from **1.413157 to 0.000207** (worst channel
0.000244) — the certified fp16 class. The run-order table is checked in at
`receipts/2026-09-18-encoder-conv-device-gate/f3-writeout-permutation.json`
on the gate branch.

Mechanism: this is the same engine write-out class the m375 k1024 n1024
**linear** lowering already compensates (67dfcf1, "the engine's 64-plane
permutation" — the oproj fix). The F3 2-task conv program (507f3ac vintage)
emits the engine's native run order without the consumer-side inverse, so a
manifest-order reader sees permuted planes. Byte-parity against the Apple
capture cannot see this: the capture encodes the same behavior; only device
execution exposes it. Fix path (not done in this lane): decode the output
order into the F3 record set and regenerate `H13ConvTemplates.inc` per
protocol — never a hand patch to the generated table — mirroring what
67dfcf1 did for the linear spell.

Gate-side corrections made while landing (commit `b99baad`): the F4 anec
allocates its source tile with slack beyond the manifest surface
(4620288 vs 4608000 bytes), so packing follows the manifest strides at
offset 0 with a ≥ check; cases run independently so one failure cannot
hide the rest. Both verified not to affect the pass/fail semantics.

## E2E encoder parity — all four arms pin EXACTLY (jw16, window 1)

`fused_e2e.py` (`0e38e7b1`), fixture FLAC, golden
`/var/tmp/EncoderParityAne/capture`, deadline 20000 ms. Hidden/transcript/mel
are sha256 of the saved `encoder_hidden.npy` / `transcript.txt` / `mel.npy`.

| arm | runner | placed / mode | subs | status | prefix | bounds | cpu_ev | transcript | hidden | mel |
|---|---|---|---:|---|---:|---|---:|---|---|---|
| abc-launch | `e93500d2` | ABC / launch | 72 | match | 104 | PASS | 0 | `db501a8c…` | `38c73261…` | `5b54f4a9…` |
| abco-launch | `e93500d2` | ABCO / launch | 96 | match | 104 | PASS | 0 | `db501a8c…` | `ef6afd13…` | `5b54f4a9…` |
| abc-resident | `e93500d2` | ABC / resident-batch | 1 | match | 104 | PASS | 0 | `db501a8c…` | `38c73261…` | `5b54f4a9…` |
| abco-resident | `vk_erev_o` `30547cf3` | ABCO / resident-batch | 1 | match | 104 | PASS | 0 | `db501a8c…` | `ef6afd13…` | `5b54f4a9…` |

Full-length digests (identical across the arms that share them):
transcript `db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790`,
hidden ABC `38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7`,
hidden ABCO `ef6afd137f1610901c1bce9cf4c9e199edc430c37bd4aeb27caa4622692d5e88`,
mel `5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde`.
exec_ms 2577.8 / 3028.6 / 1645.0 / 1774.2 (launch/launch/resident/resident).

## Decode digest pins (jw16, window 4)

`bench_decode` legs on the certified V063REL venv (v0.6.3 release wheel,
`0.32.2.dev202609171159+1ed1dab`, libmlx `a10cebf540565ccf` — the build
whose jw16 ctx1024 pin is release-certified):

| leg | generated-ids digest | pin | match | decode tok/s |
|---|---|---|---|---:|
| short ("Hi", 32 gen) | `7fd25a869ff21678` | `7fd25a869ff21678` | YES | 191.1 |
| ctx1024 (1053-token prompt, 32 gen) | `7da83f06ec9f001d` | `7da83f06ec9f001d` | YES | 130.8 |

Environment note for the next lane: the `/var/tmp/jw16gap-venv` and
`V064REL-venv` stacks have been upgraded past their certified libmlx
identities (loaded identities observed `65a641e4…`, `84664140…`, `e9e709f3…`
across windows, including site-dir shadowing under the E2E PYTHONPATH), so
ladder identity pre-gates fail there before the digest pins are reached.
The digest pins themselves hold on the certified build.

## Discipline record

Four jw16 windows, same protocol each time: TAKE announced to Main →
`sudo systemctl stop llm-inference` (active → inactive) → `flock -w 900
/tmp/m1-gpu.lock` (inode **12** every window, never stolen/unlinked) →
work, stdout to files → service restarted → `is-active=active` confirmed
with MainPID 87319→102089→102387→102513→102666 across windows → RELEASE
announced. ≥3 GiB /tmp free asserted (30 G). No lock stolen, no force-break.

## Disposition

- F1/F2/F4 + slice + all four transpose lowerings: **device-proven** at the
  certified class. The 96-of-101 encoder conv integration stands on hardware
  for every form that the placement stack could consume today.
- F3: device finding with exact mechanism and numbers; fix belongs to the
  template-record protocol (record-set decode → regenerated tables). The
  permutation table the fix needs is already decoded and checked in.
- Placement stack pins and decode pins: unchanged and green on jw16 today.
