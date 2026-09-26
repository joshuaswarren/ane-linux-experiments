# jw16-levers8 — pipeline cache hardware A/B: neutral on honeykrisp/T6001; corrected mel root cause; fusion + contract measured (2026-09-25)

Owner: Jw16Levers8. Host: jw16 (M1 Max, T6001, 16m1mbp). Continues
Jw16Levers7's receipts (ane-linux-experiments ecc2dce3, mel root-cause
hypothesis in part 2 section 6). Window coordinated with AneClockM1
(released jw16 after the dvfs_ane A/B — that lever falsified: 431-434 vs
436-439 ms/iter, inside boot band, receipt f026da17 — so the full contract
below runs on the stock omarchy-ane 5ecff86 baseline, no DVFS delta).

## VERDICT (read this first)

The persistent VkPipelineCache is compile-clean, unit-proven, and
correct under every pin and abuse probe — but it is **PERFORMANCE
NEUTRAL on T6001** (warm mel 111.9-117.1 ms with it vs 110.6-111.8 ms
without; cold-cache pass 1 114.5 ms — no delta in any direction).
Levers7's "~100 ms per-process pipeline recompile" attribution for the
mel host-side gap is **falsified on this stack**: Mesa's own on-disk
shader cache (`~/.cache/mesa_shader_cache`) already persists compiled
pipelines across processes on honeykrisp. Proof: with BOTH the Mesa
cache and the new .vkpc cleared, mel = **10,226 ms** (the real full
compile); one warm pass later (Mesa cache only, .vkpc ignored-level
warm), mel = 114.2 ms. The ~90 ms warm mel host cost lives elsewhere
(suspect: vulkan_mel.py host-side prep + marshaling — not investigated
in this lane). **Not merged to main** — no proven win for the target
box; branches and wheels preserved below for the jwm1/T8103 A/B, where
an older/different Mesa may behave differently. All correctness gates
hold with the wheel installed, so nothing blocks a future merge if a
host shows a real win.

## 1. Code (mlx-omarchy, pushed)

- `agent/pipeline-cache` = f97afca13 (levers7's cache) + **9efb728a2**
  (levers8): load the three core-1.0 pipeline-cache device functions
  (CreatePipelineCache / GetPipelineCacheData / DestroyPipelineCache)
  in DeviceTable + VKX_LOAD_DEVICE_FN — f97afca13 called them but never
  registered them; caught by the PVE compile gate (would have burned
  the jw16 window identically).
- `agent/pipeline-cache-ab` = 1faf7f00 (jw16's installed tree,
  agent/jw16-levers2 tip) + cherry-picked cache commits, tip
  **f26192bbf**. Reason: main and 1faf7f00 are content-identical for
  all four files the patch touches (empty diff verified), so this base
  makes the A/B single-lever vs the installed wheel
  (0.32.3.dev202609252013+1faf7f00).

## 2. PVE compile + unit gate (off-device, before the window)

- Compile: full `mlx` target (gcc 12.2, C++20, Vulkan headers 1.3.239,
  x86_64, MLX_BUILD_OMARCHY=ON) — 100% with 9efb728a2. First attempt
  (f97afca13 alone) failed: `DeviceTable has no member
  CreatePipelineCache` ×3.
- Unit check (lavapipe via MLX_OMARCHY_ALLOW_NON_APPLE=1, throwaway
  harness): run → sum(0..4095) = 8386560 exact, on teardown writes
  `<pipelineCacheUUID>.vkpc` (56 bytes, magic "MLXOPC1" verified);
  second process seeds from the file and recomputes identically;
  MLX_OMARCHY_PIPELINE_CACHE=0 leaves no file and computes identically.

## 3. Hardware A/B on jw16 (flock /tmp/m1-gpu.lock, llm-inference
stopped/restarted around each window, fresh process per pass, golden
fixture, pins: transcript db501a8c, hidden per pin json, 104 emissions)

Baseline (stock 1faf7f00 wheel):
| pass | total ms | mel | tdt | enc | dload | checks |
|---|---:|---:|---:|---:|---:|---|
| 1 (cold) | 3564.4 | 2044.3 | 198.8 | 1249.8 | — | all pass |
| 2 | 1211.5 | 111.8 | 176.1 | 863.6 | 44.2 | all pass |
| 3 | 1206.9 | 110.6 | 172.9 | 863.4 | 44.2 | all pass |
| 4 | 1215.1 | 111.3 | 179.7 | 864.2 | 44.9 | all pass |

After (f26192bbf wheel, mlx_omarchy-0.32.3.dev202609260243+f26192bbf,
sha256 2deccdd4dbeafec8b8e18569a42eae6b1341820e727f4653fa8831945acd418e;
verify OK; share pins intact):

| pass | total ms | mel | tdt | enc | dload | checks |
|---|---:|---:|---:|---:|---:|---|
| 1 (empty .vkpc) | 1624.5 | 114.5 | 177.1 | 1264.5 | 44.5 | all pass |
| 2 (.vkpc warm) | 1240.4 | 114.9 | 179.7 | 884.5 | 44.7 | all pass |
| 3 | 1235.8 | 114.7 | 176.7 | 883.5 | 44.7 | all pass |
| 4 | 1237.6 | 111.9 | 177.3 | 886.9 | 44.9 | all pass |
| opt-out (=0, no cache) | 1238.2 | 117.1 | 176.0 | 884.7 | 44.5 | all pass; no file written |
| regen | 1240.4 | 115.9 | 178.9 | 884.0 | 45.6 | all pass |
| corrupt (.vkpc truncated to 24 B) | 1234.5 | 114.2 | 174.2 | 884.7 | 45.3 | all pass |
| warm1 (fresh cache) | 1216.7 | 113.6 | 174.6 | 867.6 | 45.0 | all pass |
| warm2 | 1218.4 | 113.8 | 174.6 | 868.3 | 45.1 | all pass |
| cold-cold (Mesa cache + .vkpc cleared) | 11387.1 | **10226.3** | 200.2 | 868.6 | — | all pass |
| warm3 (after cold-cold) | 1219.0 | 114.2 | 174.6 | 868.5 | — | all pass |

Readings: warm mel is 110.6-117.1 in EVERY state (feature on, off,
opt-out, corrupted cache, fresh cache) = neutral within noise. The
10.2 s cold-cold vs 114 ms warm pair shows where pipeline persistence
actually lives on this stack: Mesa's disk cache, not VkPipelineCache.
The feature's corruption tolerance is real (truncated blob → all pins
green) and the opt-out is clean.

## 4. GPU pins (contract bench, 10 prompts, 32 tok, prefill 512, greedy)

| arm | 3-pass digest | 10-pass digest |
|---|---|---|
| baseline (1faf7f00) | **bc519c03c4ef5fd1** | **dbf704971617fdfc** |
| after (f26192bbf) | **bc519c03c4ef5fd1** | **dbf704971617fdfc** |

Both digest pins reproduce exactly before AND after; decode medians
~80.8 tok/s both sides. The cache layer does not touch token streams.

## 5. TDT decoder+joint single-eval fusion on T6001

The fusion (speculative joint window, jwm1 receipt
receipts/2026-09-23-tdt-speculative-window.md in mlx-omarchy: TDT
588.6 → 503.4 ms mean, submissions 277 → 145 on T8103) is already in
both the installed 1faf7f00 wheel and this lane's wheel — there was no
pre-fusion T6001 state to A/B in this window. Measured T6001
fused TDT stage wall: **172.9-200.2 ms** warm across every pass above
(baseline and after identical). Whole-pipeline submission count on the
f26192bbf wheel (MLX_OMARCHY_TRACE_DISPATCH=1, full log captured):
**12 SUBMIT / 9 COMMIT** — the newer jw16 lineage submits far less than
the b4757ac-era 277→145 TDT-stage figures from jwm1; cross-tree counts
are not comparable (different trees AND hosts). The stage wall is the
receipt.

## 6. Full Parakeet contract vs macOS 264 ms (per-process, pinned fixture)

| stage | jw16 Linux warm (ms) | macOS 264 ms breakdown |
|---|---:|---|
| audio_load | 6.5 | — |
| mel_frontend | 110.6-117.1 | mel 15 |
| encoder_ane (worker spawn + exec, non-resident) | 863-887 (cold first pass 1250-1265) | encoder 147 |
| decoder_load | 44.2-45.6 | — |
| tdt_decode (fused) | 172.9-200.2 | decode 102 |
| detokenize | 9.4 | — |
| **total_pipeline_ms** | **1206.9-1240.4 warm** | **264** |

Linux/T6001 is ≈ **4.6x macOS latency** per process. Even attributing
the resident-worker encoder exec alone (~440 ms/iter, Jw16Levers6
baseline; the 863-887 here adds worker spawn + island boot per
process), the resident stack would be ~770 ms ≈ 2.9x macOS. The
dominant open gaps are (a) ANE encoder exec time — 440 vs 147 ms;
dvfs_ane A/B falsified as a lever (AneClockM1, f026da17) — and (b) the
~90 ms unexplained warm mel host cost (NOT pipeline creation, per §3).
Pass rule (≤1.00x latency): **not met** — unchanged by this lane.

## 7. Caveats / honest notes

- The "278 jobs → ~139" fusion framing from earlier notes described
  the jwm1 lineage; jw16's 1faf7f00 wheel already carries the fused
  path, and its dispatch/submit internals differ from the b4757ac-era
  counts. Treat cross-tree submission counts as non-comparable; the
  T6001 TDT stage wall (~175 ms) is the number of record.
- llm-inference restore: service restarted after every window; final
  real-completion probe (finish_reason stop) recorded in
  window-trace/after logs. First probe after the control window hit
  the model-load window (503 "Loading model") — retried green.

## 8. Artifacts

- jw16 /tmp/levers8/: window-baseline.log, window-pins.log,
  window-after.log, window-control.log, window-trace.log,
  trace-full.log, base/ + after/ (transcribe reports + bench JSONs),
  build.log, all windows + scripts.
- jw16 /var/tmp/levers8-rollback/: mlx + dist-info snapshot of the
  pre-lane installed state, cache-good.vkpc.
- jw16 live state: f26192bbf wheel installed (all pins green), Mesa
  cache warm, .vkpc warm, llm-inference active with a real completion.
- Rollback: `pip install --force-reinstall --no-deps <1faf7f00 wheel>`
  or restore /var/tmp/levers8-rollback/* into
  /var/tmp/v072-venv-fused/lib/python3.14/site-packages/.
