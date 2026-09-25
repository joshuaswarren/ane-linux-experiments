# m1max-host composed install — whole-program encoder + coopmat-direct + defer-commit + dispatch-cut (2026-09-22)

Owner: M1MaxCompose. Host: m1max-host = m1max-host (T6001, Omarchy kernel 7.1.6-1-1-ARCH).
Shared composition branch: `agent/integrated-e2e` (mlx-omarchy), final tip `066bed9c2`,
built and installed on m1max-host as the normal entry points. Labels follow repo convention
(m1max-host = m1max-host, m1-host = m1-host = T8103).

## 1. Composition (what the installed build contains)

Base `fa103c867` (installed fa103c86 wheel) plus, in order:

| commit | piece |
| --- | --- |
| d3b295bd2 + f45f5f5ea / 868fa7f1e | whole-program ANE encoder (one-submit path, bundle 13c74423, libane d06222a8 pin) |
| 8bba36b21 | defer-commit knob (`MLX_OMARCHY_DEFER_COMMIT`, eval.cpp finalize; joint-batching excluded as measured-negative) |
| 6ae7b85f0 | installed-layout: whole bundle + libane shipped as wheel assets under `site-packages/mlx/share/mlx-omarchy/parakeet-1/`, auto-discovery from installed share root |
| 1693741fe | coopmat-direct (hkc-direct-coopmat `42c10a68c..734ab7823`, production files only: qmm coopmat A tiles direct global load + X32 bf16 scales/biases; lane receipts/tools excluded) |
| 988b9be66 | dispatch-cut (m1max-host `agent/decode-dispatch-cut` `393b7712..6056969a` = GDN raw-gates decode prologue fusion; transport ref 822d186; the rope-pair bf16 arm staged in fast_trio.comp by the 822d186 reconstruction excluded as measurement-only) |
| 3c94db3a7 | raw-gates C++ patch + mlx-lm raw-route patcher carried from 822d186 (prepare-mlx.sh references them; m1max-host held them untracked) |
| 066bed9c2 | pin: whole-program encoder hidden sha (51830b6f…) + path-aware installed pin check (M1Integrate; bit-exact with certified staged r1-r4) |

Dispatch-cut provenance note: the assignment named 822d186 ("recover the source from
the m1host-gpu-legs receipt or the hkc-direct-coopmat bundle"). 822d186 was not in the
preserved bundle (its single ref is the coopmat tip); it was recovered from
m1-host `/var/tmp/integ-wt` (branch agent/decode-dispatch-cut) and cross-checked against
the m1max-host original line (`/var/tmp/integ-wt` on m1max-host, tip 6056969af). The m1max-host
3-commit line is the measured, fixed state (543 dispatches/token vs 705 baseline on
m1-host, decode 62.6 vs 53.6) and is what landed; 822d186 additionally carried the
rope-pair measurement arm which is not part of the dispatch-cut lever.

## 2. Publish blocker (structural, owner decision pending)

The local privacy pre-push hook blocks ANY ref whose ancestry contains
`services/community-data/test/unit/pii.test.ts` (regex literal
`192\.168\.[0-9]{1,3}\.[0-9]{1,3}` — a pii-DETECTION test fixture, i.e. a false
positive; the blob is absent from all current tip trees). The introducing commit is
`ed91550d9` ("feat(services): community-data pipeline — chunked D1 worker plus
collector upload"), which is inside BOTH the v072 line (ancestor of `fa103c867`) and
`main`. Consequence: no v072/main-based ref can be pushed from this workstation to
any remote without a history rewrite (`--no-verify` is forbidden by the task rules).
Transport used instead (approved by Main): incremental git bundles over scp, base
`fa103c867` — m1max-host built from `/var/tmp/compose-wt` fetched from
`/tmp/compose-m1max-host(-b).bundle`; M1Integrate received the format-patch series and the
`integ-e2e-b3.bundle` for m1-host. Publish of `agent/integrated-e2e` to a shared remote
needs the owner's call on the ancestry; not done in this lane.

## 3. Install on m1max-host (normal entry points)

- Build: `scripts/build-wheel.sh` in `/var/tmp/compose-wt` → final wheel
  `mlx_omarchy-0.32.3.dev202609230056+e273c66c-cp314-cp314-linux_aarch64.whl`
  (sha256 `cd374a3be7c40a5438fda232…`, 415,862,801 B; raw/build-compose.log; two earlier
  builds of the same tree at +3c94db3a and +066bed9c predate the pin-check fix —
  identical kernel content, the qwen arms in §6 ran on the +3c94db3a wheel).
  Wheel verified to contain `mlx/bin/mlx-omarchy-parakeet`,
  `mlx/bin/mlx-omarchy-ane-worker`, `share/mlx-omarchy/parakeet-1/libane/libane-strict.so`
  (71,456 B = d06222a8), island bundles, and
  `bundles/parakeet-encoder-whole/program-0.anec` (458,018,816 B, sha 13c74423…).
- Rollback wheel preserved: `/var/tmp/rollback-compose/mlx_omarchy-0.32.3.dev202609221309+fa103c86-cp314-cp314-linux_aarch64.whl`
  (sha256 `5dd224028975acaaa7ad27cf…`).
- Installed into the live venv `/var/tmp/v072-venv-fused` (pip --force-reinstall
  --no-deps) plus `soundfile` 0.14.0 (audio fast path) and `protobuf` (runtime dep of
  the transcribe CLI dependency check).
- Entry points after install: `/var/tmp/v072-venv-fused/bin/mlx-omarchy-parakeet`
  (created; execs the shipped `mlx/bin/mlx-omarchy-parakeet` under the venv python) and
  the same venv python for the Qwen3.8 backend path. mlx default device = gpu
  (`Device(gpu, 0)`), physical device `Apple M1 Max (G13C C0)` (Honeykrisp, Mesa
  26.3.0-devel git-5deac1c806) — also recorded per-run by the bench metadata.
- mlx-lm venv patches: gdn fast-route was already applied; the raw-route patcher
  (`patch-mlx-lm-gdn-raw.py`) applied (gated_delta.py now calls
  `mx.fast.gated_delta_update_raw`).

## 4. Parakeet qualification — golden fixture, installed entry point

Fixture: the single pinned clip (audio sha 30885601…, 166960 samples @ 16 kHz =
10.435 s). MacBaseline confirmed this is the COMPLETE referenced corpus (no other
clips have macOS goldens anywhere) — the corpus blocker stands.

Composed path selected the whole-program encoder (no env override):

| metric | value |
| --- | --- |
| ane submissions | **1** (worker_starts 1, timeouts 0) |
| encoder_ane_ops / encoder_gpu_ops | **13701 / 0** (island path would be 72 + 1230) |
| ane exec | 441.06 ms cold (certified T6001 steady rate 441.1) |
| libane | d06222a8 (whole-program certified build, sha verified) |
| placement | mel/TDT/decoder on Vulkan GPU; audio decode via soundfile 0.14.0; **cpu_tensor_events 0** |
| decode_control | gpu-loop |
| mlx | 0.32.3.dev202609230056+e273c66c (composed final) |

Gates: all green on the final wheel — detail in §5 and raw/transcribe-report-*.json.
All 10 verification checks pass on every arm with status=match — full table and
per-arm stage breakdown in §5; gate-level detail (sha pins, emissions, placement)
in raw/transcribe-report-*.json. RTF/peak-RSS summary: warm RTF 0.227 (was 0.586
on the fa103c86 islands path), cold RTF 0.265, peak child RSS ~0.97 GB.

## 5. Window results (final wheel, e273c66c = 0.32.3.dev202609230056+e273c66c)

Golden fixture via the installed entry point, whole-program encoder auto-selected,
flock-held GPU window, llm-inference stopped. Peak child RSS (getrusage
RUSAGE_CHILDREN, lane-rssrun.py): 991,808 / 992,368 / 993,264 KB (cold / warm /
warm-defer). RTF = total pipeline / 10.435 s audio.

| arm | rc | status | total ms | RTF | audio | mel | encoder_ane | dec_load | tdt | detok |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cold (drop_caches) | 0 | **match** | 2767.9 | **0.265** | 29.3 | 226.2 | 1527.3 | 93.2 | 851.6 | 40.4 |
| warm | 0 | **match** | 2364.4 | **0.227** | 6.7 | 141.6 | 1263.2 | 60.7 | 851.4 | 40.8 |
| warm + MLX_OMARCHY_DEFER_COMMIT=1 | 0 | **match** | 2383.0 | **0.228** | 6.7 | 136.8 | 1268.1 | 61.1 | 853.8 | 56.4 |

Every arm: ane submissions **1**, ane exec 440.4–440.8 ms (certified T6001 steady
rate), encoder_ane_ops **13701** / encoder_gpu_ops **0**, cpu_tensor_events **0**,
decode_control gpu-loop, audio decoder **soundfile 0.14.0**, libane d06222a8,
device Apple M1 Max (G13C C0).

Gates (all 10 pass on every arm): mel_sha256 (bcbaa3ca…), encoder_hidden_sha256
(actual 51830b6f… = pin's whole-path sha, bit-exact with certified staged r1-r4),
emissions 104/104, token_ids matching_prefix 104, frame_indices, durations,
transcript sha **db501a8c…** (the golden pin: "He hoped there would be stew for
dinner, turnips and carrots and bruised potatoes and fat mutton pieces…"),
cpu_tensor_events 0, decode_control gpu-loop (no fallback), finite_hidden
(0 NaN/inf).

vs the fa103c86 installed path (receipts/2026-09-22-m1-boundary-reconcile §3):
warm total 6112.0 ms → **2364.4 ms (−61%)**, encoder stage 4874.5 ms (islands,
72 ANE + 1230 GPU ops) → **1263.2 ms (one ANE submit, −74%)**, warm RTF 0.586 →
**0.227**, cold 37,372.5 ms → **2767.9 ms (13.5×)**. Cold-vs-warm residual is the
458 MB bundle load + first session open inside encoder_ane (1527.3 vs 1263.2 ms).

defer-commit knob: functional (arm runs green with MLX_OMARCHY_DEFER_COMMIT=1);
total within run noise of the default arm (+18.6 ms ≈ 0.8%). Default stays off
per M1Integrate's m1-host A/B decision.

Corpus: this fixture is the COMPLETE referenced corpus on m1max-host (MacBaseline: no
other clips have macOS goldens anywhere in receipts/repos); recorded as the
standing corpus blocker.

## 6. Qwen3.8 GPU contract (installed composed wheel, 3c94db3a wheel numbers)

Runner `benchmarks/qwen38-mlx-bench.py`, model SiddhJagani/Qwen3.8-2B-mlx-4Bit
snapshot 0867d98b, corpus sha 9299a3b2 (pinned), greedy, 32 new tokens, prefill-512
leg, `/tmp/m1-gpu.lock` held (llm-inference stopped for the window).

| arm | protocol | ttft tok/s | decode tok/s | prefill-512 tok/s | digest (ordered records) |
| --- | --- | ---: | ---: | ---: | --- |
| identity | 2 warmup, 3 passes × 10 prompts | 77.55 | 63.87 | 294.97 | `bc519c03…` (30 records, 10 unique streams, healthy family `271 248068 …`, 0 all-zero) |
| **contract** | **3 warmup, 10 passes × 10 prompts** | **76.48** | **63.58** | **294.31** | `dbf70497…` (100 records, 10 unique streams) |

vs numbers on record (dc7ca4a0 integration wheel, m1max-host): 61.89 / 57.59 /
238.32 → **+23.6% ttft, +10.4% decode, +23.5% prefill-512** on the composed wheel.
Digest differs from `ac1b2695…` (the ac1b2695 policy reference): per kernel-flags.md
cross-host digest equality is NOT a gate — per-host determinism (yes: identical
streams across passes; stdev decode 0.61 tok/s) and healthy streams (yes) are. The
digest change is attributed to dispatch-cut, whose receipt documents first-token
flips at bf16-quantum margins; coopmat-direct is identity-preserving (hkc-direct
receipt, ac1b2695 held on its lane).

vs macOS Metal (README matrix): 359.2 / 179.5 / 1019.7 → Linux/composed is 0.21×
ttft, 0.354× decode, 0.289× prefill-512.

Proof of Apple GPU execution: per-run metadata records `vk_devices = [Apple M1 Max
(G13C C0), llvmpipe…]`, `vk_drivers = [Honeykrisp, llvmpipe]`, `soc = Apple MacBook
Pro (16-inch, M1 Max, 2021)`; the transcribe report records
`mlx/device = Apple M1 Max (G13C C0)`; loader trace (raw/window2.log) shows the
backend enumerating both devices and selecting the Apple GPU; decode at 63.6 tok/s
on a 2B q4 model is physically out of reach of llvmpipe (CPU rasterizer). The
hk-only arm (VK_DRIVER_FILES restricted to asahi ICD) re-ran the identity protocol —
raw/hk-only.json.

## 7. Dominant remaining GPU gap vs macOS (installed path)

- Fresh: prefill-512 294.3 tok/s = 1.74 s/pass vs macOS 1019.7 (0.50 s) → 3.46×;
  decode 63.6 vs 179.5 → 2.82×.
- Prior per-kernel profile (receipts/2026-09-22-prefill512-profile-attack,
  m1max-host, pre-60c4903f wheel d03a7148): GPU busy 97.7%, host gaps ≈5% → the gap
  is in-kernel, not host-side. Top buckets then: GDN prefill
  (GatedDeltaPrefillBF16) 68.6%, QmmPrefillCoopmatBF16 26.6%, rest ~3%. 60c4903f
  attacked bucket 1 (landed, +11.7%); the composed coopmat-direct attacks bucket 2
  (+6.2% prefill on its lane); together they move m1max-host prefill-512 238.3 → 294.3.
- Remaining top cost centers on the installed path: the two same kernels — GDN
  prefill prefix/output passes (bf16, per-token sequential dependency across ns
  chunks) and qmm coopmat prefill GEMM; in decode, the qmm-vec GEMV family is
  latency/bandwidth-bound at ~160 GB/s vs the 310 GB/s pattern roof measured with
  nothing left in kernel-side tricks (receipts/2026-09-22-decode-m1max-occupancy:
  all candidates bit-exact-but-slower, production kernel at its dispatch-geometry
  ceiling). macOS Metal wins on fused bf16 GEMM throughput and kernel-library
  maturity; closing further needs the same two buckets (GDN prefill shader,
  coopmat qmm) — the next untried lever class per the occupancy receipt is more
  in-flight weight bytes (occupancy/L2 policy), which mesa/honeykrisp does not
  expose yet.

## 8. llm-inference restore (acceptance)

llm-inference.service stopped only inside measurement windows (GPU lock discipline;
never overlapping ANE and GPU work), restarted after each window, active at wrap-up.
Real completion verified twice: `POST /v1/chat/completions` (Bearer key from
`/etc/llm-inference/api-key`) → "The Pacific Ocean is the largest…" with
finish_reason=stop (raw/completion.json; the unit requires the API key — a keyless
probe correctly 401s, see raw/window.log tail).

## 9. Window discipline / host state

- Every measurement window announced on hub before start; ANE (whole-encoder submit)
  and GPU benchmarks sequential inside one lock; llm-inference stopped at window
  start, restored at window end with a health poll + real completion.
- No reboots, no kernel/boot changes, no module changes (the approved ane_tm P1/P2
  probe window is queued AFTER qualification and did not run in this lane).
- Files created on m1max-host: /var/tmp/compose-wt (build tree + dist wheels),
  /var/tmp/compose-qual/{window,window2,window3,window4}.log + run artifacts,
  /var/tmp/rollback-compose/ (rollback wheel), /tmp patches/bundles,
  /var/tmp/rope-pair-land fetched refs (compose/integrated-e2e-m1max, bundle refs),
  /var/tmp/v072-venv-fused/bin/mlx-omarchy-parakeet wrapper.
- Raw data: `raw/` in this receipt.

## 10. Raw data index

- raw/build-compose.log — full wheel build log (fail at missing raw-gates patch,
  clean rebuild at 066bed9c).
- raw/window.log — window 1 (parakeet deps fail; qwen identity + contract arms).
- raw/window2.log — window 2 (venv-routing fail; loader device trace; real
  completion with API key).
- raw/window3.log — window 3 (parakeet whole-path runs, encoder_hidden divergence
  pre-066bed9c).
- NOTE: the "window 4" run (066bed9c wheel; parakeet arms crashed at the pin check
  M1Finish later fixed; hk-only arm + real-completion check green) appended to
  raw/window2.log — the window4 script carried a stale LOG name (window2.log).
  Its lane4-* report dirs on m1max-host are empty (pre-check crash), so nothing is lost.
- raw/cadence-compose.json, raw/contract-compose.json — qwen arms.
- raw/transcribe-report-{cold,warm,defer}.json — final-wheel Parakeet reports.
- raw/hk-only.json — asahi-ICD-only identity arm.
- raw/completion.json — llm-inference real completion.
