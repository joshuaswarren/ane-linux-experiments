# Conv/rel-pos/transpose island placement screen (V, P, T) — jw16, 2026-09-18

## Verdict

**NO-SHIP for the conv family (V): the transcript digest breaks in every
V arm (101/104, deterministic), so the placement is not shippable even
though it is the first family to CUT the Parakeet encoder wall in both
submission modes.** P (rel-pos padconv + slice) and T (proven-direction
transposes) are numerics-neutral (bit-exact forms, hidden digest
unchanged) and pure wall losses. The placement stack default stays
`ABC`; V/P/T remain opt-in, now with numbers.

Digest-first regression: all four certified arms pin EXACTLY on the new
runner bytes — ABC launch/resident hidden `38c73261…`, ABCO
launch/resident hidden `ef6afd13…`, transcript `db501a8c080380ea…`
EXACT, mel `5b54f4a9…` EXACT, 104/104, `cpu_tensor_events` 0,
0 timeouts. Any digest break would have been no-ship; the certified
arms are clean.

Refs (both sides of the handoff):
- mlx-omarchy `agent/ane-conv-placement` @ `486514b4`, cut from `044f297f`
  (the certified runner-of-record bytes, `e93500d2`); pushed. Runner bytes
  on device: sha256 `500256e2…` (`/tmp/conv-lane/vk_conv.py` = worktree
  `overlay/tools/coreml/vulkan_encoder.py` at the commit).
- gate branch follow-on of `agent/encoder-conv-device-gate` (`c6f86fb`)
  + mil-hwx-compiler main `389664f` (F3 writeout-inverse build, binary
  sha256 `d9194dd4…` on jw16 at `~/src/mil-hwx-compiler-f3inv/build/mil-hwxc`).
- mint+gate tool: `ane-linux-experiments/.local/conv_lane.py` (sha256
  `1e8057a6…`), arm script `.local/conv_e2e_jw16.sh` (`3c60f8b4…`).

## What landed

Additive hunks on the certified runner bytes, env-gated via
`MLX_OMARCHY_PLACED` (default `ABC`; new letters V, P, T compose):

- **V** — per-layer conv-module islands `island-conv-{pw1,dw,pw2}-L{ll}`
  in the device-proven spellings: pw1 = F1 in-proj k1×1 g1 valid
  1024→2048 bias-free; dw = F2 depthwise k1×9 g1024 same +bias; pw2 = F3
  out-proj k1×1 valid 1024→1024 (the writeout-inverse packing geometry of
  the fixed build). 3 sites/layer × 24 = 72 islands, real per-layer
  weights from the deparalettized encoder source.
- **P** — rel-pos shift forms: `island-relpos-pad` (the F4 padconv, g8
  k1×1 custom pad [0,0,1,0], ones weights) and `island-relpos-slice`
  (last-dim [1,8,375,749]→[…,375]). Shared weightless bundles, 24 sites
  each. Before minting, the composition equivalence was proven
  numerically: the coreml pad constant is fp16 0.0 and both spellings
  pad LEFT one W step, so ones-weight conv ≡ the coreml pad bit-for-bit
  through the whole pad→reshape→slice→reshape→slice dance.
- **T** — proven directions only: `island-tr-r3-in`
  ([1,375,1024]→[1,1024,375]), `island-tr-r3-out` (reverse),
  `island-tr-r4-out` ([1,8,375,128]→[1,375,8,128]). The head-SPLIT
  transposes (reverse direction of the proven program) and the
  subsampling-exit transpose stay on the GPU — unproven directions are
  not placed.
- Placed families extend the resident session's preload set
  (`AneIsland.resident_bundles`); dispatch guards re-verify the proven
  geometry per submit (pad widths, pad value 0.0, slice begin/end,
  input shapes) and refuse rather than approximate.

## Mint + device gate (jw16, under flock before any E2E)

77 bundles minted on jw16 from the pinned F3-fixed build with real
per-layer weights (BLOBFILE from the encoder source blobs — no uniform
payloads), wrapped schema-4 by the certified `h13_v2_to_schema4.py`
adapter (unmodified). The v2 compiler manifests carry conv weights as
`role: "constant"` tensor metadata; those 73 entries are dropped before
the adapter because the anec already embeds the weight bytes (the gate
executes `program-0.anec` alone) and the certified linear bundles carry
no tensors section at all. Dropped sites recorded in `mint-log.json`.

Device gate (`conv_lane.py gate`, libane-strict-fill `04a17653`, real
weights, fp32 numpy refs, rngs 11/33/57, budget 0.05):

| family | bundles | worst rel_l2 |
|---|---|---|
| island-conv-pw1 (F1) | 24 | 0.000208 |
| island-conv-dw (F2) | 24 | 0.000219 |
| island-conv-pw2 (F3, fixed packing) | 24 | 0.000208 |
| island-relpos-pad (F4 ones) | 1 | 0.00000056 |
| island-relpos-slice | 1 | 0 (bit-exact) |
| island-tr-r3-in / r3-out / r4-out | 3 | 0 (bit-exact) |

**gate PASS 77/77, worst 0.000219** — the certified fp16-noise class, at
the exact E2E site geometries (`conv-gate.json`).

## E2E matrix (fused_e2e `0e38e7b1`, fixture FLAC, deadline 20000 ms)

| arm | placed/mode | subs | gpu_ops | enc_wall_ms | ane_exec_ms | total_ms | status | prefix | hidden |
|---|---|---:|---:|---:|---:|---:|---|---:|---|
| abc-launch | ABC launch | 72 | 1206 | 10910.9 | 2600.8 | 12264.5 | match | 104 | `38c73261…` PIN |
| abco-launch | ABCO launch | 96 | 1182 | 11233.0 | 2954.6 | 12567.9 | match | 104 | `ef6afd13…` PIN |
| abc-resident | ABC resident | 1 | 1206 | 9143.2 | 1684.9 | 10495.7 | match | 104 | `38c73261…` PIN |
| abco-resident | ABCO resident | 1 | 1182 | 9276.3 | 1819.6 | 10553.7 | match | 104 | `ef6afd13…` PIN |
| abcv-launch | ABCV launch | 144 | 1134 | 9716.3 | 3692.5 | 11031.8 | **diverged** | **101** | `4c831bf5…` |
| abcv-resident | ABCV resident | 1 | 1134 | 6921.0 | 1976.0 | 8253.8 | **diverged** | **101** | `4c831bf5…` |
| abcvp-launch | ABCVP launch | 192 | 1086 | 12808.8 | 5431.9 | 14135.9 | **diverged** | **101** | `4c831bf5…` |
| abcvt-launch | ABCVT launch | 216 | 1062 | 11530.6 | 4557.4 | 12837.3 | **diverged** | **101** | `4c831bf5…` |
| abcvpt-launch | ABCVPT launch | 264 | 1014 | 14159.6 | 6238.3 | 15507.6 | **diverged** | **101** | `4c831bf5…` |
| abcvpt-resident | ABCVPT resident | 1 | 1014 | 9171.3 | 3385.0 | 10503.2 | **diverged** | **101** | `4c831bf5…` |

Every arm: `cpu_tensor_events` 0, bounds vs the ANE reference PASS, mel
digest `5b54f4a9…` EXACT, 0 timeouts. Submissions land exactly on the
family arithmetic (+72 V, +48 P, +72 T, +24 O). The V-arm hidden digest
is deterministic and identical across launch/resident and across P/T
supersets — the perturbation is V's alone; P/T are bit-exact forms and
change nothing downstream of the conv output.

## The wall finding

V is the first family that moves the encoder wall the right way — and it
does so in BOTH modes, which is what the screen was for:

- launch: wall 10910.9 → 9716.3 ms (−1194.6 ms, −11.0%) while ane_exec
  grows 2600.8 → 3692.5 ms (72 extra submits at ~15.2 ms/island marginal).
- resident: wall 9143.2 → 6921.0 ms (−2222.2 ms, −24.3%) at only
  +291.1 ms ane_exec (~4.0 ms/island inside the one batch).

The mechanism is the mirror of the FFN loss: the GPU `apply_conv` path is
data-movement-heavy (fp32 upcast, pad, two transposes, conv2d, transpose
per conv), so removing 72 of them frees more GPU wall than the island
staging costs — where the certified-fast coopmat linear path made F a
double loss. P and T are losses on top of V (P: +64.4 ms wall per island
— the 8.6 MB pad/slice surfaces cost more to stage than they save; T:
+25.2 ms wall per island).

## Why it does not ship

**The transcript digest is the product contract, and V breaks it:**
101/104 matching emissions in every V arm, both modes. The perturbation
is the same fp16-noise class the device gate measured (0.0002 rel),
bounds still PASS vs the ANE reference — but three tail emissions flip.
The o-proj and FFN families rode the same class of perturbation with the
transcript EXACT; the conv path sits early enough in each layer's
dataflow (conv module feeds the residual stream) that the same noise
crosses emission boundaries here. Per the lane contract — digests EXACT
or no-ship — V stays opt-in default OFF.

What would have to change for V to be a ship candidate: per-form
attribution (pw1/dw/pw2 share the V letter today; which form carries the
divergence is unknown), and either a decode-side tolerance decision or
an ANE-exact conv lowering for the offending form. The wall win
(−1.2 s launch, −2.2 s resident) is real and recorded so the follow-up
can be priced against it.

## Discipline record

One jw16 window. TAKE announced to Main → `sudo systemctl stop
llm-inference` (active → inactive) → device gate + all ten arms under
`flock -w 900 /tmp/m1-gpu.lock` (never stolen/unlinked), stdout to files
(`/tmp/conv-lane/gate.log`, `/var/tmp/jw16-conv-place/*.log`) → service
restarted → `is-active=active` confirmed (MainPID 110029) → RELEASE
announced. /tmp 30 G free (≥3 GiB gate). Minting ran before the window
(CPU-only). No SET-block speculative writes, no release publishing, no
formatters. `git merge-base --is-ancestor 63c1d3cf HEAD` FAILS on the
branch (re-verified before push).

## Files

- ane-linux-experiments/receipts/2026-09-18-conv-placement-screen.md (this file)
- receipts/2026-09-18-conv-placement-screen/{arms.jsonl, conv-gate.json,
  mint-log.json, gate.log}
- mlx-omarchy branch `agent/ane-conv-placement` (pushed): `486514b4`
  runner hunks only. `docs/ane-encoder-placement.md` lives on origin/main
  above this branch's base (`044f297f`), so the V/P/T family rows and the
  disposition paragraph are carried HERE for the merge, not duplicated on
  the branch: add one row per letter to the letter-to-family table --
  `V` conv-module convs (`island-conv-{pw1,dw,pw2}-L{ll}`, 3/layer),
  `P` rel-pos padconv+slice (`island-relpos-{pad,slice}`, 2/layer),
  `T` proven-direction transposes (`island-tr-{r3-in,r3-out,r4-out}`,
  3/layer) -- and one measured-disposition bullet: "V/P/T (2026-09-18
  screen): opt-in, NOT default. V cuts the encoder wall (-11.0% launch,
  -24.3% resident) but transcript-diverges at 101/104 in every arm --
  no-ship under the digest contract; P/T are bit-exact and pure losses
  (+64/+25 ms wall per island)."
- lane tool `ane-linux-experiments/.local/conv_lane.py`, arm script
  `.local/conv_e2e_jw16.sh` (mirrored on jw16 `/tmp/conv-lane/`)
- bundles on jw16: `/var/tmp/jw16-conv-place/bundles-new` (77 new) +
  `bundles-conv` (symlinked certified base + new)
