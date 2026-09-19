# Encoder wall on v0.7.1 bytes: re-baseline, per-round attribution, transport cut screen (2026-09-19, jw16)

Lane: EncoderWallTowardDivisor. Branch: `mlx-omarchy` `agent/encwall-transport`
`80ef5e16` off `50eeb290` (v0.7.1); `63c1d3cf` NOT-ANCESTOR asserted.

## Verdict

**Re-baseline:** AC serve **3359.9 ms**, ACO serve **3779.0 ms** (medians of 3,
v0.7.1 tag bytes, jw16) — within noise of the 3422/3797 numbers the
agent/ffn-chain-fusion lane carried (`30908306`); the wall is unchanged
across the timeline-stall fix merge (`50eeb290`).

**Attribution (AC serve median, baseline):**

| term            |  ms   | what it is                                                                             |
|-----------------|------:|----------------------------------------------------------------------------------------|
| encoder_ane wall| 3359.9| end-to-end encoder wall (fused_e2e `stages[encoder_ane].wall_ms`)                       |
| ane exec        | 1291.0| island-statement sum (round-trip on the worker pipe)                                  |
| &nbsp;&nbsp;child stage_ms| 172.0| child BO + stdin reads across 48 rounds                                                |
| &nbsp;&nbsp;child save_ms  | 192.0| child BO read + stdout emit across 48 rounds                                            |
| &nbsp;&nbsp;parent write_ns| 230.6| parent stdin write (mostly waiting on the relay to consume)                             |
| &nbsp;&nbsp;parent read_ns | 1023.2| parent stdout read (waits for child stage+exec+save, dominates exec)                  |
| marshal         |  965.5| runner-side `mx.eval` + numpy staging for the island input set; the drain waits for the GPU-side `matmul`/`const` work that feeds the next island |
| back            |   61.4| runner-side `np.frombuffer` + `mx.array` for the island output set                      |
| residual        |  983.8| wall − exec − marshal − back − batch_open: GPU-side `matmul`/`const`/`linear` synchronous drains BETWEEN islands |

Top terms, ranked: GPU-side `matmul`/`const` drains feeding & between
islands (~1950 ms = marshal drain + residual) > island exec round-trip
(1291 ms) > back/path (61 ms). The macOS CoreML divisor's 266.7 ms `.all`
wall is ~12× below us because the divisor runs the whole encoder inside
ONE ANE program chain per layer with no host orchestrator in the loop.

**Candidate (`80ef5e16`, transport cut) verdict:** **NO-LAND** on default.
Median wall moved −8 ms on AC serve, −6 ms on ACO serve, −53 ms on ACO
launch — inside the run-to-run spread (cells span ±150 ms across 3 reps).
**All 26 gated arms pins-EXACT (104/104, transcript `db501a8c…`, hidden
`38c73261…`/`ef6afd13…`, mel `5b54f4a9…`, bounds PASS, `cpu_tensor_events`
0, timeouts 0); 4 pure-GPU control arms diverged as designed.** The copy
chain (tobytes + bytearray append + bytes() + 64 KiB pipe buffer +
inbox-append + bytes() slice) was **not** the wall; the wall is
round-trip LATENCY (48 × (pipe handoff × 2 hops + protocol parse +
sync wakeup)), dominated by the parent-side 1023 ms read wait.

The branch is still pushed (`agent/encwall-transport`, `80ef5e16`) for the
`memoryview.nbytes` hardening alone — declaring payload size via
`len()` on a numpy array is a shape dimension, not a byte count, and
would have misframed every multi-MB input on the wire. Caught pre-window
by the scripted-worker round-trip proof. Future numpy-buffer callers
inherit the fix; the wall-neutral transport changes ride along and cost
nothing.

## The wall (medians of 3, v0.7.1 tag bytes `50eeb290`)

| cell             | baseline (b) median ms | candidate (c) median ms | delta   | verdict |
|------------------|-----------------------:|------------------------:|--------:|---------|
| AC  serve        | 3359.9 | 3351.8 | −8    | NO-LAND |
| ACO serve        | 3779.0 | 3773.4 | −6    | NO-LAND |
| AC  launch       | 4278.6 | 4274.0 | −5    | NO-LAND |
| ACO launch       | 4825.8 | 4773.1 | −53   | NO-LAND |
| gpu-serve control| 849.1  | 855.1  | +6    | control |

Per-arm walls (ms): `b-ac-serve` 3702 / 3266 / 3360;
`b-aco-serve` 3815 / 3723 / 3779; `b-ac-launch` 4181 / 4280 / 4279;
`b-aco-launch` 4867 / 4802 / 4826; `c-ac-serve` 3432 / 3199 / 3352;
`c-aco-serve` 3774 / 3517 / 3773; `c-ac-launch` 4274 / 4280 / 4195;
`c-aco-launch` 4814 / 4752 / 4773.

Per-round p50 (base, ms): `b-ac-serve` attn-a-kt 23.3 / 36.6 / 43.6
across reps, pv 8.4 / 13.3 / 17.7 — the round-trip is 20-25 ms even in
the fastest rep, against ~1.2 ms device compute on `a0` (probe-level
from `2026-09-17-ane-roundtrip-levers.md`). **20× of the per-round
overhead is host orchestration, not silicon.**

GPU control arm (`MLX_OMARCHY_PLACED=""` resident): 849 ms, `op_wall_ms`
top = conv 556 + const 229 + linear 6 + layer_norm 4 + add 2 + mul 2 +
transpose 1. Pure-GPU whole-encoder on this stack is now ~850 ms —
the v0.5.1 pure-GPU control of 3591 ms in `0a56933` no longer applies
(the conv-chunk cadence + serve-mode default + digest cache landed
since). The hybrid ANE path adds wall, not subtracts it, **on this
orchestration**. The island families exist for the encoder-on-ANE
parity research, not as a wall win in the current host shape.

## v0.7.1 re-baseline provenance

- Wheel: published v0.7.1 aarch64 sha256 `e536056b…`,
  dist `0.32.3.dev202609190758+50eeb29`, libmlx16 `df3d4e74c597956c`,
  `verify-release-assets.py v0.7.1` GREEN (per
  `receipts/2026-09-19-v071-ship.md`).
- Runner bytes: `overlay/tools/coreml/vulkan_encoder.py` sha
  `789aaec31029fe62…f4af74` (same as `30908306`); ane_resident
  `6551c6c0…` (base); candidate `f03c8524…` (ane_resident) +
  `f694873b…` (vulkan_encoder). Local mlx-omarchy at `50eeb290` ==
  origin/main.
- Venv: `/var/tmp/V071REL-venv` built from the published wheel +
  `protobuf==7.36.1` + `numpy==2.5.3`. `venv-identity-guard.py
  --expect df3d4e74c597956c` exit 0 before the window.
- `certified-libmlx-identities.txt` was stale past V067 (v0.7.0
  `38adf6efb80ee850` and v0.7.1 `df3d4e74c597956c` not present) —
  the documented post-publish bookkeeping step (`v0.6.8` receipt)
  had not been run for either release. Both lines added with ship
  provenance; prior list backed up at
  `/var/tmp/v063-jw16/scripts/certified-libmlx-identities.txt.pre-v071-20260919`.
  No list line added without a published, verify-gated identity.
- Module: `1fc2e02`, map_mode reads `3` (cached-read default landed
  per `receipts/2026-09-17-ane-cached-map-land.md`). llm-inference
  ACTIVE at TAKE; stopped inside the window; restarted with MainPID
  391997 post-release.

## Window discipline (one flock hold for the whole battery)

`TAKE EncoderWallTowardDivisor …` → `sudo systemctl stop llm-inference`
(active → inactive confirmed) → `flock -w 900 /tmp/m1-gpu.lock` for every
arm (inode 12, never stolen/unlinked) → 26 gated arms + 4 controls
(serial, interleave base↔cand per cell) → `RELEASE … inode=12
service=active MainPID=391997 2026-09-19T08:01:28-05:00`. Total runtime
~3 min for the gated battery; 30 rows in `rows.jsonl`, all gated arms
pins-EXACT or hard-failed (no partial scoring).

`ANE_OP_WALL=1` exported — the runner prints per-op GPU statement
wall sums to stdout (captured in arm-*.log); used for the GPU-side
attribution column.

## Harness / inputs (unchanged across the wall arc)

`fused_e2e.py` @ `/var/tmp/ParakeetE2EJw16/`, fixture FLAC, golden
`/var/tmp/EncoderParityAne/capture`, ANE ref same, pkg
`/var/tmp/TdtLoopDefault/pkg`, source `/var/tmp/EncoderParityAne/encoder-source`,
bundles `/var/tmp/jw16-conv-place/bundles-conv` (104 bundle dirs),
worker `/var/tmp/jw16-oproj-place/mlx-omarchy-ane-worker`, libane
`/var/tmp/jw16-oproj-place/libane-strict-fill.so`, SPIRV cache
shared `/var/tmp/MelFrontendPerf/spirv-ab.3KDGHZ`, deadline 20000 ms.
`PYTHONPATH` deliberately unset (the historical harness path pointed
at a marked non-certified mlx; the venv provides numpy + protobuf).
Harness args and inputs mirror the `3c9d612` window exactly.

## Why the transport cut did nothing

The runner-side copy chain removed (per byte, per round):

| side     | copies removed                                                        |
|----------|------------------------------------------------------------------------|
| parent send | tobytes() copy, bytearray append copy, bytes(request) copy → memoryview write straight from the numpy buffer |
| parent recv | inbox append copy, bytes() slice copy → os.readv direct into the final buffer |
| both pipes | 64 KiB → 1 MiB kernel pipe buffer (F_SETPIPE_SZ best-effort)         |

`readv` returns into a preallocated `bytearray(count)` (inbox prefix
copied first when the inbox already holds the frame header). The
candidate passes `test_ane_resident` 10/10 locally AND the
scripted-worker round-trip with 1-D and 2-D fp16 numpy buffers
byte-identical end to end (incl. child report parsing and clean close).

The wall didn't move because the per-round cost is not memcpy
bandwidth — it is the 2-hop relay round-trip latency (parent → worker
→ resident → device → resident → worker → parent): the parent's
`read_ns` (1023 ms across 48 rounds = 21 ms/round) is the dominant
ANE-side term, and it includes four process handoffs plus a
device sync per round. Removing three memcpy stages inside a 21 ms
round-trip that is bottlenecked on handoffs and a device sync is
not measurable.

## Named next lever (relay-bypass, NOT in scope for this lane)

The `mlx-omarchy-ane-worker` main.cpp relay forwards every byte from
the parent's stdin to the resident's pipe via AneWorker::submit
(`send_request` per frame + per payload, then `recv_bytes` per
output). Each round pays: parent → relay stdin (1 hop) → AneWorker
re-frame + send (2 hop) → resident parses + stages (3 hop) →
device → resident reads + sends → AneWorker recv → relay fwrite
stdout → parent os.readv (1 hop). Six process-state transitions +
a device sync per round.

Two options ranked by risk:

1. **Splice relay** in main.cpp: replace the buffer-read of inline
   payloads and the buffer-write of outputs with `splice()` between
   the relay's stdin and the resident channel (both are pipes on
   Linux), preserving the protocol owner. Pure C++ surgery inside
   the resident-child loop and AneWorker::submit; the device
   staging inside the resident process is unchanged.
2. **Python-direct protocol**: have the python client speak the
   resident frame protocol directly, spawning the resident
   `--serve` process from `ResidentAneWorker` and dropping the
   `main.cpp` relay entirely. Saves two process-state transitions
   per round but duplicates the protocol/deadline/quarantine
   semantics the relay owns.

Either lands in a worker-protocol-change lane. Receipts
(`2026-09-17-ane-roundtrip-levers.md`, `2026-09-17-ffn-chain-scale.md`)
have consistently named this as the remaining transport lever. The
GPU-side work (the marshal-drain / residual 1950 ms) is bounded by
the data-dependent serial chain between islands (`1d2233a`); the
ANE-family placements that could shift work off GPU either break
the digest (V family: 101/104, NO-SHIP) or net-lose on the
orchestration cost (G family: +1228 ms jw16 resident). None of
those are in this lane's scope.

## Disposition

- **Default stays on v0.7.1 main (`50eeb290`).** Re-baseline numbers
  and per-round attribution recorded; the wall arc carries over from
  `30908306` within noise.
- **Branch `agent/encwall-transport` (`80ef5e16`) pushed for the
  `memoryview.nbytes` hardening.** Future numpy-buffer callers
  inherit a correct byte-count; the transport-cut changes ride along
  at zero wall cost. Certified copy untouched per the prior
  screen-no-ship conventions (`0a56933`, `8e8db6d`, etc.).
- **Next lane:** relay-bypass (worker-protocol change) for the
  1000+ ms parent-read latency; named above.

## Artifacts

- Worktree: `~/src/mlx-omarchy-encwall` (branch
  `agent/encwall-transport`).
- jw16 staging: `/var/tmp/encwall-v071/{base,cand}/vulkan_encoder.py`
  + `ane_resident.py`; `/var/tmp/encwall-v071/{encwall_jw16.sh,
  take_release.sh, attr_row.py, summarize.py, roundstats.py}`.
- jw16 data: `/var/tmp/encwall-v071/rows.jsonl` (30 rows),
  `/var/tmp/encwall-v071/out-*/e2e-report.json` ×26, arm logs ×26,
  `window.log`.
- Local scripts: `.local/encwall-v071/{encwall_jw16.sh,
  take_release.sh, attr_row.py, summarize.py, roundstats.py,
  receipt-draft.md}`.
- venv guard backup: `/var/tmp/v063-jw16/scripts/certified-libmlx-identities.txt.pre-v071-20260919`.
