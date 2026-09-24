# M1 timing-boundary reconciliation + T6001 whole-encoder anomaly — analysis receipt (2026-09-24)

Owner: AneBoundaries. Analysis only — no hardware was run. Every number below is
quoted from committed receipts and their artifact JSONs; every code boundary is
read from the pinned source revisions named in §3. Labels are neutral by SoC:
**T8103 host** = m1-host / m1-host, **T6001 host** = m1max-host / m1max-host.

## 1. Boundary table — where each M1 number is measured

All four numbers describe the same whole-encoder program: bundle `program-0.anec`
sha `13c74423…` (458 MB, manifest v4 `parakeet-encoder-whole`, 13701 TDs,
tile_shift 9), libane-strict `d06222a8…`, one submit, outputs bit-exact
(hidden `e1e061ab…` smoke / `554a3d66…` capture family, transcript `db501a8c…`).

| # | number | exact boundary (file:function) | config | control mode |
|---|---|---|---|---|
| 1 | **141.913 ms** ANE exec (T8103) | `overlay/tools/coreml/vulkan_encoder.py` @ `868fa7f1e`, `AneIsland._submit_resident`: `exec_ns += monotonic_ns()` bracketed **around the single `session.submit(bundle, tag, payload, out_names)` call** (lines ~873–886). Worker-side child record: `read_ns` 141.337 ms of the 141.913 (ANE completion wait + output read); `marshal_ns` 0.197, `write_ns` 0.407, `back_ns` 0.777. Session open (458 MB bundle read + sha256 + `ane_init` pread) and process spawn sit **outside** the bracket. | `receipts/2026-09-22-encoder-whole-program/m1host/e2e-report-r1.json` `ane.exec_ms` / `exec_ns`=141912988; r2 141.509, r3 141.888. Env: `MLX_OMARCHY_WHOLE_ENCODER_BUNDLE`, `ANE_ISLAND_MODE=resident-batch`, worker `84e8cc8f`, submissions 1, timeouts 0 | pipeline `execution.control = "gpu-loop"` — the megakernel `vulkan_tdt_loop.run_tdt_loop` (default at `868fa7f1e`; `MLX_OMARCHY_TDT_HOST` unset, `tdt_fallback_reason: null`) |
| 2 | **13,994.91 ms** total pipeline (T8103, rep 1) | `fused_e2e.py` `Stages.total_ns()` = **sum of the six per-stage `time.monotonic_ns` walls** (`Stages.run`), reported as `timing.total_pipeline_ms`. It is a stage sum, not one end-to-end clock. r1 is a cold process: `mel_frontend` 9756.7 ms (one-time SPIR-V/pipeline compile; `MLX_OMARCHY_SPIRV_CACHE` cold), `encoder_ane` stage wall 2740.7 ms (worker spawn + session open incl. 458 MB validation + the 141.9 ms submit), `audio_load` 341.9 (cold import), `tdt_decode` 955.8, `decoder_load` 155.6, `detokenize` 44.1 | same report, `timing.total_pipeline_ms` = 13994.91 | same gpu-loop |
| 3 | **2,026.82 ms** total pipeline (T8103, rep 2) | same boundary, warm process: audio 180.2 + mel 229.3 + encoder stage 687.9 + decoder_load 57.5 + tdt 831.5 + detok 40.4 (r3 = 2073.777). The 687.9 ms encoder stage ≈ spawn + session open + 141.5 ms submit — i.e. rep-to-rep the pipeline cost is dominated by TDT (831) and the per-process session open, not the ANE submit | same report r2 | same gpu-loop |
| 4 | **~260 ms/iter** (T8103, direct worker) | `mlx-omarchy-ane-worker --iterations N` (non-serve CLI): top-level `report.elapsed` process wall (bundle load + session open + N iterations), slope over iterations removes the intercept; per-iter = one whole-encoder submit + fp16 output compare | anomaly receipt §1b: (8647−1376)/28 = **260.4 ms/iter**, flat over 32 iters; same bytes/inputs as #1, hidden `e1e061ab…` bit-exact | none — encoder-only, no TDT in this harness |

T6001-host mirror values, same boundaries: e2e exec **440.578 / 440.303 / 439.972 ms**
(r5–r7), total pipeline 2380.4 / 2352.2 / 2368.6 (stage walls r5: audio 81.7,
mel 141.9, encoder stage 1050.5, decoder_load 45.9, tdt 1022.3, detok 38.1),
worker slope **441.3 ms/iter** = (14747−1077)/31. Control mode identical
(gpu-loop); only the host, worker sha (`d6c33e6f`), and kernel (7.1.6 vs
7.1.13) differ.

Metric-shape note (resolves anomaly-receipt §4b's "which costs sit inside
exec_ns"): `exec_ns` is the Python-side bracket around one resident `session.submit`;
the CLI slope is the same submit bracket plus per-iteration compare, amortized.
On T6001 the two shapes agree (440 ≈ 441). On T8103 they disagree
(141.9 one-shot vs 260.4 amortized): the **first** submit of a fresh session runs
~118 ms faster than the steady-state iterations. The CLI marginals confirm the
shape (iters 1→4: 233/iter; 4→16: 276/iter; 16→32: 247/iter) while the 1-iter
point implies a ~534 ms intercept — the intercept model, not the submit, is
what does not close. This residual is measurement-shape, T8103-only, and
remains the one open item; the discriminator is a warm-session single-submit
timed in the e2e shape (`--serve` + one `submit` line) vs iters=1, both on
T8103.

## 2. The T6001 whole-encoder anomaly — explained

**Observation.** Identical bytes on both hosts (program `13c74423`, libane
`d06222a8`, driver srcversion `EA1B0B74…`, `writecombine=N`), yet the
single-giant-submit runs 441 vs 260 ms/iter amortized (1.7x) and 440 vs 141 ms
in the e2e metric (3.1x). T6001 is not a slow chip — it **wins** island mode
(1210–1293 ms vs T8103's 3505.6 ms). Only the one-submit/13701-TD shape is
slow on it.

**Root cause (established by `receipts/2026-09-22-ane-dvfs`, confirmed by
`receipts/2026-09-23-m1max-ane-clock`): Linux programs no ANE clock at all, and
ANE clocking is firmware-mediated.**

- omarchy-ane does genpd raise + task-manager enable only; no clk/opp/perf-state
  code exists in the tree. The engine therefore runs at whatever clock iBoot's
  boot-time setup left, and the measured slope is flat — 440.1–441.3 ms/iter
  with zero ramp across 14 s of back-to-back submits and across every lever.
- macOS raises the same silicon to **140.1 ms sustained** (CoreML ANE arm,
  3 warmup + 200 reps, 0 mismatches) through the ANE's own firmware:
  AppleH11ANEInterface issues `CSNE_CMD_CH_PROPERTY_WRITE` ("setting FW perf
  mode"); the ADT wires the ANE perf-domain → `PLL_ANE0` → group-8
  `voltage-states8` ladder **300/540/780/1020/1260/1500 MHz** at
  550–909 mV. Frequency follows voltage; voltage belongs to the CLPC power
  firmware (the DPE blocks are CLPC address space, not AP-readable).
  3.19x = 440.1/138 is consistent with Linux parked at a fixed low clock
  (~470 MHz implied) against that ladder.
- **T8103-vs-T6001 residual (1.7x): different iBoot per-SoC boot-clock
  choices** — T8103 happens to boot its ANE at the higher fixed clock
  (ane-dvfs §6.2; `receipts/2026-09-20-iboot-j414c/iboot_j414c_dec.bin` is on
  file, clock-init sequence not yet decoded).
- **No AP-side register fix exists** (m1max-ane-clock §2–3): the PS words
  already read 0x3ff (max) on every live SET; direct SET writes are
  firmware-locked (external-abort class); `ane_set5` is unattached and ignores
  writes; both hosts run exactly 5 active ANE SET domains (topology symmetric,
  imbalance ruled out); the pmgr ANE perf/PLL pages beyond the SET grant are
  read-hostile (two hard resets logged, §5 of the dvfs receipt); the PMP
  coprocessor that would carry a report bit is `disabled` in DT with no
  firmware running (probe module built and tested: bit set, no ack, reverted);
  completion-poll cadence 1 µs–2 ms moves nothing (436.7–442.0 ms/iter spread
  = noise). Driver, libane, program, inputs, llama-server contention, CPU
  governor: all A/B-ruled out with evidence.
- **Fix route:** ANE firmware bring-up (rtkit/CSNE client, the t6021 lane's
  mission ported to T6001, per-SoC firmware builds) — not a driver register
  write. Until then the whole-encoder path on T6001 stays at the iBoot clock;
  it is still 2.7x faster than T6001's own island chain.

## 3. Recovered source revisions and artifacts

| artifact | revision / sha | where verified |
|---|---|---|
| whole-encoder one-submit path | mlx-omarchy `agent/encoder-whole-program` @ **`868fa7f1e`** ("whole-program encoder: per-bundle tile_shift + one-submit ANE path") | local `~/src/mlx-omarchy` |
| runtime pin (libane + bundle provenance) | mlx-omarchy **`5c2d60577`** (libane-strict `d06222a8…` w/o `LIBANE_CONFIG_STRICT_BIND`; bundle `13c74423…` manifest v4; receipt pointer) | same |
| libane per-container tile-count unit | omarchy-ane `agent/encoder-whole-program` @ **`df5c553`** (`__ane_init_shift`) | local `~/src/omarchy-ane` |
| whole-encoder correctness (T8103) | `receipts/2026-09-22-encoder-whole-program/m1host/e2e-report-r{1,2,3}.json` + gates (`gate-*.out`, `capsim/`) — all bit-exact, 104/104, transcript `db501a8c` | committed at `eb1e711` |
| whole-encoder correctness (T6001) | `receipts/2026-09-22-encoder-whole-program/m1max/e2e-report-r{1..7}.json` (certified r5–r7) — all bit-exact, hidden `554a3d66` identical across hosts | committed at `eb1e711` |
| host-TDT deferred knob (backend) | mlx-omarchy **`8bba36b21`** — `MLX_OMARCHY_DEFER_COMMIT` in `overlay/mlx/backend/omarchy/eval.cpp` `finalize()` (presence of env = defer; batches still close at node/byte budgets and every host-read sync); recovered from `agent/parakeet-defer-commit` 925cfa6 on the T6001 host; wheel `0.32.3.dev202609221218+925cfa6` | local, commit read |
| host-TDT control loop (tools) | `MLX_OMARCHY_TDT_HOST` introduced with the gpu-loop default in **`992feea98`/`298feb5c4`**; default flipped to host in **`8e050c6d5`** (post-dates the certified runs) | local, commit read |
| composition point | **`d3b295bd2`** = merge of whole-encoder (868fa7f1e + pin) into integrated-e2e — **parent of `8bba36b21`**, so `8bba36b21` is exactly whole-encoder + defer-commit | local, ancestry checked |
| repo-side probes / harness | this repo branch `agent/parakeet-perf-worker-lever`; `receipts/2026-09-22-parakeet-e2e-decomp/` (probe_tdt_hostloop.py, probe_tdt_loop.py, decomp battery) | committed |
| run scripts of the certified set | `.local/m1max-host-whole-gates.sh`, `.local/m1-host-whole-gates.sh` (worktree-local copies; T6001 host venv `~/venv-agxgen`, T8103 host venv `/var/tmp/v072-venv-fused`) | present in this worktree |

## 4. Combined Parakeet pipeline (encoder + decoder/joint + TDT + detok)

One pipeline = the certified `fused_e2e` harness (audio → mel → whole-encoder
ANE → decoder/joint → TDT → detok) with the two recovered levers composed:

- **source branch: mlx-omarchy `agent/combined-parakeet` @ `8bba36b21`**
  (whole-encoder `868fa7f1e`+pin via `d3b295bd2`, defer-commit, TDT host loop
  behind env — at this revision the gpu-loop is still the default, so the run
  pins the host-TDT deferred path explicitly).
- **env:** `MLX_OMARCHY_WHOLE_ENCODER_BUNDLE=<staging>/bundle`,
  `ANE_ISLAND_MODE=resident-batch`, `MLX_OMARCHY_TDT_HOST=1` (host control
  loop; report shows `control: "host"`),
  `MLX_OMARCHY_DEFER_COMMIT=1` (TDT step's 5 dispatches share one submit).
- staged runner: `combined-parakeet.sh` next to this receipt — host-tag
  argument `t6001-host` (m1max-host) or `t8103-host` (m1-host), wheel gate on the
  defer-commit lineage (`8bba36b2`/`925cfa6` stamp), sha preflight, 3 reps
  under `flock /tmp/m1-gpu.lock`, per-stage + gold summary. It runs nothing on
  this workstation and was not run on any host (device ownership respected).

### Build + run (staged 2026-09-24; nothing executed on hardware)

Already staged to both hosts (identical bytes, sha256 below):

```text
/var/tmp/combined-parakeet.sh                        3d7cf9cdcf11e128…
/var/tmp/combined-parakeet-8bba36b21.full.bundle     9681eb825024269b…
```

The bundle carries the complete history of `agent/combined-parakeet` @
`8bba36b21` (7.7 MB, no prerequisites — proven to fetch into a virgin repo and
to contain all three levers: `MLX_OMARCHY_DEFER_COMMIT` in eval.cpp,
`MLX_OMARCHY_WHOLE_ENCODER_BUNDLE` in vulkan_encoder.py, `MLX_OMARCHY_TDT_HOST`
in parakeet_tdt.py). The pre-existing per-host staging (bundle `13c74423`,
libane `d06222a8`, worker, staged mlx tree, `TdtLoopDefault` pkg — verified
present on m1-host) is reused unchanged.

```sh
# on m1max-host (t6001-host) or m1-host (t8103-host):
git clone /var/tmp/combined-parakeet-8bba36b21.full.bundle /var/tmp/combined-src
bash /var/tmp/combined-src/scripts/build-wheel.sh            # -> dist/*.whl (stamps +8bba36b2)
python3 -m venv /var/tmp/combined-venv
/var/tmp/combined-venv/bin/pip install /var/tmp/combined-src/dist/*.whl numpy soundfile
bash /var/tmp/combined-parakeet.sh t6001-host               # on m1max-host
bash /var/tmp/combined-parakeet.sh t8103-host               # on m1-host
```

The runner fails loud if the installed wheel is not the defer-commit lineage
(version stamp `8bba36b2`, or `925cfa6` for the original T6001-host defer
wheel) or if the pkg lacks the TDT_HOST knob.

Acceptance for a combined run: `status match`, `control: "host"`, submissions 1,
cpu_tensor_events 0, 104/104 prefix, transcript `db501a8c…`, mel/hidden
bit-exact; expected shape on T8103: encoder_ane stage ≈ session-open + ~141–260 ms
submit, tdt_decode well under the 975 ms megakernel bucket (decomp measured
398 ms host-loop class on T6001), total pipeline below the 2026.8/2380.4 ms
gpu-loop baselines of §1. First rep additionally pays the one-time SPIR-V
compile (~9.8 s class on T8103, lane-local `MLX_OMARCHY_SPIRV_CACHE`).
