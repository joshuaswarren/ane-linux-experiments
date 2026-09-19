# jw16 Q4 legs on v0.7.1 — gap reproduced, and the chain-batch Mesa lever screened NO-LAND (the G13X per-launch CDM barrier is load-bearing)

Date: 2026-09-19. Lane: GpuPerfLegs. Host: jw16mbp1-linux (Apple M1 Max,
T6001, G13C), kernel 7.1.6-1-1-ARCH. Wheel: v0.7.1
`mlx_omarchy-0.32.3.dev202609190758+50eeb29-cp314-cp314-linux_aarch64.whl`
(sha256 `e536056bcb23d8d93121edc662cebb0c4b14b8670233c8f018ad54150b9b8d49`,
re-verified on the box; loaded `libmlx.so` sha256 prefix `df3d4e74c597956c`,
pinned fatal on every run). Installed driver:
`mesa-honeykrisp-omarchy 26.3.0.devel.hk5deac1c-2` (G13X kitchen-sink CDM
barrier), untouched by every window in this lane.

## Verdict

1. **Baseline legs on v0.7.1 reproduce the parity-table state** (below).
2. **The one prepared Mesa fix for the dominant decode gap —
   `hk/cdm-chain-batch` @ `ae819e10cb6` ("batch the per-dispatch CDM barrier
   across dependent compute chains", written 2026-09-17, never screened) —
   FAILS its own screening gate on jw16**: generated-ID digests corrupt
   **nondeterministically** (two different wrong digests on two runs) while
   the emission reduction works exactly as designed (16 vs ~2500 barriers
   per 2-token run). **NO-LAND; branch stays unmerged; the box stays on
   `hk5deac1c-2`.**
3. Consequence for attribution: the G13X per-launch kitchen-sink CDM_BARRIER
   is **load-bearing memory-ordering between dependent compute launches**,
   not removable overhead — the commit's premise ("the dependency is already
   carried by the firmware/scheduler ordering") is false for the MLX decode
   chain on G13X. With the bit-trim family already closed by the 09-16 termA
   screens (coupled bits, −18..−40 % perf cliffs on subsets), the
   **amortize-the-barrier lever family is closed with direct evidence**: the
   ~50 % fixed per-token decode overhead is the price of correctness at this
   driver generation.

## Baseline ladder (installed driver, v0.7.1 wheel)

`gap_ladder.py`, 3 interleaved rounds, rotating leg order, fresh
bench_decode subprocess per leg, `MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1`,
local snapshot `/var/tmp/jw16gap-model`, harness byte-identical to the
receipt pins (`bench_decode.py` `f5062d88f34b0845…`,
`bench_matrix.json` `df8eb9f3ed8418260…`). Digests fatal.

| leg | N | decode tok/s (median, all) | prefill tok/s (median) | digest |
|---|---:|---|---:|---|
| short | 30 | **191.90** (188.47 / 193.76 / 191.90) | **457** | `7fd25a869ff21678` 3/3 |
| ctx256 | 414 | 177.81 | 3135 | `e8488554a9ff3d30` |
| ctx512 | 653 | 151.29 | 3266 | `296ad46feb95f62b` |
| ctx1024 | 1053 | **150.76** (157.30 / 150.76 / 150.58) | **3884** | `7da83f06ec9f001d` 3/3 |

Linear fit over leg medians: **t0 = 5.1979 ms, slope 1.529 µs/KV-token** —
same band as the post-two-pass receipt (t0 5.17, slope 1.589). Against the
README table (v0.6.1 wheel): short decode 190.6 → 191.9, ctx1024 decode
130.7 → 150.8 (the landed two-pass), short prefill 459.7 → 457, ctx prefill
3845 → 3884. No regression on v0.7.1; the table's gap state stands: short
decode ~67 % of native, ctx1024 decode ~53 %, short prefill ~30 %, ctx
prefill ~48 %.

## The screen (chain-batch vs rebuilt base vs installed)

Three arms, all extracted packages with per-arm ICD JSONs selected via
`VK_DRIVER_FILES` (termA flow):

| arm | source | identity |
|---|---|---|
| installed | `hk5deac1c-2` package (TermAJW16 staging) | the box's driver |
| base | package rebuilt this lane from `d8d4e1c500b` (same source as installed, same PKGBUILD recipe, `makepkg` on jw16) | `libvulkan_asahi.so` sha256 `4344c81ed4997c43…` |
| cand | package rebuilt this lane from `ae819e10cb6` (`hk/cdm-chain-batch`) | `libvulkan_asahi.so` sha256 `530e9dfe62d79f32…`, `vulkaninfo` reports `Mesa 26.3.0-devel (git-ae819e10cb)` |

### Emission (ASAHI_MESA_DEBUG=trace + AGXDECODE_DUMP_FILE, 2-token short run per arm)

| arm | CDM_BARRIER emissions | reading |
|---|---:|---|
| installed | 2493 | per-launch emission, pins hold |
| base | 2743 | same class (build-vs-build cs-split noise), pins hold |
| **cand** | **16** | the batching works — ~170× fewer barriers; chains run back-to-back |

The cand survivors carry the **identical kitchen-sink content**
(Unk 0–19 all true, USC cache inval true; see `forms-cand.txt`,
`dump-excerpt.txt`) — the commit's "content byte-identical, only emission
points move" holds. What corrupts results is the **absence** of the barrier
between dependent launches, not a changed barrier.

### Digest gate (32-token short leg, warm Mesa shader cache, per-arm warmup)

| arm | rc | generated-ID digest | verdict |
|---|---|---|---|
| base | 0 | `7fd25a869ff21678` | PASS (control clean — my rebuilds are sound; the earlier base r0 slowdown was cold shader cache, single round) |
| cand | 0 | **`82bea4112404efb0`** | **FAIL** |

With the cold-cache battery attempt earlier in the same window sequence,
cand's short digest was **`0fabaea06690079c`**. Two runs, two different
wrong digests = **nondeterministic corruption (a race), not a consistent
arithmetic change** — the dependent launches read not-yet-visible writes of
their predecessors mid-chain. The battery aborted at the warmup gate by
design (`WARMUP FAIL cand`, exit 7); installed/base controls were clean
before and after.

The commit's own gate reads: "the pinned generated-ID digests … must hold
exactly … else revert." Reverted = never merged; `hk/cdm-chain-batch`
remains on origin unmerged for archaeology, and this receipt is its
screening record.

## Standing attribution after this lane (jw16, Qwen2.5-0.5B Q4)

| hole | share | status after this lane |
|---|---:|---|
| fixed per-token overhead (G13X per-launch CDM_BARRIER + dispatch chain, ~29 µs/launch dependent-chain cost) | ~50 % of ctx1024 gap; ~64 % of short gap | **lever family CLOSED**: bit-trim dead (termA, coupled bits), chain-batch dead (this receipt, correctness). Load-bearing maintenance; not addressable in this driver generation |
| KV-walk excess (structural) | ~43 % ctx1024 | **Correction (KvTwoPass, `50852da`): the named global-scratch two-pass lever DID land** — `agent/decode-two-pass` @ `283aa076`, merged `23fc9a9a`, and this receipt's ctx1024 150.8 tok/s **is** the two-pass number (the v0.6.1 table's 130.7 predates it; post-two-pass receipt priced the landed win at 51–58 % of native across windows). The residual walk excess (k<1024 one-pass regime + two-pass residual, ~35 % of the ctx gap) is structural: insensitive to load restructuring (`266813b0` +2.46 %, inside wander) and to chain count (termB) |
| ctx prefill | 48 % of native | QMM at 90.2 % of Honeykrisp's own coopmat ceiling (`2026-09-17-qmm-prefill-ceiling.md`); driver-emulation-bound |
| short prefill | 30 % of native | m=30 latency-floored weight stream, fork-invariant (same receipt) |
| AGX trig-lowering invariance | — | closed 2026-09-16 (`mlx-omarchy/receipts/2026-09-16-mesa-trig-invariance.md`): one FMA contraction, fixed at shader source on the wave branch; the folded kernel is not in the shipped decode path, so no invariance exposure on v0.7.1 legs |

## Remaining decode levers after this lane

With the global-scratch two-pass landed and the amortize-the-barrier family
closed, the **remaining decode gap on jw16 is the union of two
proven-irreducible costs at this driver generation**:

1. The G13X per-launch CDM barrier maintenance (correctness, ~50 % ctx
   gap) — closed in this receipt (chain-batch fails).
2. The post-two-pass residual structural walk (~35 % ctx gap) — closed
   by the prior screens (load-staging restructure inside noise; chain
   count invariance; structural k/32 serial depth per workgroup). No
   remaining named driver-side or runtime-side lever within this lane's
   scope addresses it; the only further native-shape port (heads-grid
   32-thread pass-2 over a per-block scratch) was the lever that DID land
   as two-pass and is already in the measured numbers.

## Hardware safety / coordination

- Two GPU windows consumed, both under `/tmp/m1-gpu.lock` (inode 12),
  `flock -w 900`, one acquisition point per window; lock never stolen or
  unlinked. `llm-inference.service` stopped before and started after every
  window; **post-state confirmed `active`** after each (the "post:
  activating" lines in logs are the 2 s check racing systemd; a follow-up
  `is-active` returned `active` each time).
- Announced TAKE to EncoderWallTowardDivisor (queued next); RELEASE ping
  with inode follows this receipt.
- Package builds (base, cand) ran outside windows (CPU-only, niced); the
  makepkg trees were later removed during staging cleanup; the extracted
  arms live in `/var/tmp/MesaL2/pkg-{base,cand,installed}`.
- jwm1 and jw14m2 untouched. `63c1d3cf` not an ancestor of anything here
  (mlx-omarchy runtime source not modified by this lane at all).

## Artifacts

- This directory: `ladder-baseline.json` (full rounds + medians + fit),
  `window-ab.log` (emission counts, warmup digests, WARMUP FAIL),
  `forms-{base,cand,installed}.txt` (agxdecode barrier-field blocks),
  `dump-excerpt.txt` (head of one trace showing the kitchen-sink form).
- jw16: `/var/tmp/cb/` (scripts: `gap_ladder.py`, `cb_ab.py`,
  `window-baseline.sh`, `window-ab.sh`, `prep-pkg.sh`, `build-arm.sh`),
  `/var/tmp/cb/emit/` (full dumps), `/var/tmp/MesaL2/pkg-*/` (extracted
  arms), `/var/tmp/v071perf-venv` (v0.7.1 venv, mlx-lm 0.31.3).
- Mesa: `github.com/joshuaswarren/mesa` branch `hk/cdm-chain-batch`
  @ `ae819e10cb6` (unmerged; screened by this receipt).

## Reproduce

```sh
ssh 16m1mbp
# baseline legs (one flock window):
sudo systemctl stop llm-inference.service
flock -w 900 /tmp/m1-gpu.lock /var/tmp/v071perf-venv/bin/python \
  /var/tmp/cb/gap_ladder.py /var/tmp/v071perf-venv /var/tmp/cb/scripts \
  /tmp/out.json 3
sudo systemctl start llm-inference.service
# chain-batch screen: /var/tmp/cb/window-ab.sh (digest gate fatal)
```
