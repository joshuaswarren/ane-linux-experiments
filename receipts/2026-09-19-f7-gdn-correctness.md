# F7 GDN correctness — fix verified on main/v0.7.1, Bonsai-2 tok/s + AC/ACO + oMLX A/B consolidated (2026-09-19)

Lane: F7GdnCorrectness-2. Hosts: jw16 (T6001) + jw14m2 (T6021) by prior receipt; this pass: lock-free, no GPU window, no jw14m2/jwm1 contact.
Model identity for this pass: `opencode-go/muse-spark-1.3-contributor` (dev-box synthesis only; all GPU numbers below are quoted from the named receipts, not re-measured here).

## Verdict

**F7 is fixed on main and in v0.7.1. No new source commit from this lane — the culprit fix `da43969e` is ancestor of `HEAD`, `origin/main`, and tag `v0.7.1`.** Verified by command (this session, dev box):

```
git -C ~/src/mlx-omarchy merge-base --is-ancestor da43969e HEAD && echo F7FIX-IN-HEAD
git -C ~/src/mlx-omarchy merge-base --is-ancestor da43969e v0.7.1 && echo F7FIX-IN-V071
git -C ~/src/mlx-omarchy merge-base --is-ancestor da43969e origin/main && echo F7FIX-IN-ORIGIN
```

All three exit 0 (`F7FIX-IN-HEAD`, `F7FIX-IN-V071`, `F7FIX-IN-ORIGIN`).
HEAD at write time: `828953e1b4f6da652394657fb4eb0407cb06d792` (docs: serve four-leg).
Tag: `v0.7.1` = `50eeb2905ba0b7b382f44a55cd158847aedea8f8` (merge: timeline-stall-fix).
Fix: `da43969e03d8c0e50dee2772f630f7ebfe1ee914` (2026-09-18 17:49:18 -0500).

This receipt closes the assignment's record items from existing bytes: coherent Bonsai-2 stock vs abliterated tok/s, AC/ACO matrix from main bytes, oMLX A/B outcome. No `/tmp/m1-gpu.lock` take from this lane (announced to `all`; queue is MesaWaitBatchScreen → AneEncoderCoverage → Bf16CompiledTape-2).

## 1. Investigation (gdn_sink / fused-decode) — recap with source

Full evidence chain lives in `mlx-omarchy/receipts/2026-09-18-f7-gdn-correctness.md` (lane F7GdnCorrectness, jw16+jw14m2). Load-bearing points re-verified against source this pass:

- Symptom: Bonsai-2-27B generates but logits NaN from step 4. Post-prefill state at layer 44 = 2.0e30 → x100/step → 2.6e36 at step 4 → fp32 inf → NaN. Identical on T6001 and T6021.
- `mx.metal.is_available() == False` on BOTH silicons → Metal GDN kernels never engage; everything runs the mx-ops fallback. Driver-kernel translation exonerated.
- Custom `gdn_sink` mlx_vlm (jw16 pack-lane variant) installed on jw14m2/T6021 reproduces identical NaN@4; stock mlx_vlm 0.7.1 (chunked GDN, different algorithm) runs finite on both. So the variant selects the path, the runtime owns the bug.
- Suspect elimination on T6021 custom-vlm: fused decode linears OFF → still NaN; `MLX_OMARCHY_NO_BUFFER_CACHE / TAPE_FULL_BARRIERS / TAPE_NO_REUSE / TAPE_SYNC_EVERY / FUSED_GEMV=0` → still NaN; `MLX_OMARCHY_FUSED_CHAIN=0` → **clean**. Op pin: first-NaN layer 44; captured `/tmp/f7-t3-inputs.npz` numpy f64 replay = 90.01, eager mx = 90.01, in-graph compiled = 10,229, matching the `k[r,dv]`-misindexing model to 5e-6. Minimal repro `_gated_delta_step_ops` (mx.compile): eager 90.01 / compiled 10,229 / `FUSED_CHAIN=0` 90.01.

Root cause (source, still present verbatim at HEAD):

- File: `overlay/mlx/backend/omarchy/fused_chain.cpp`, `leaf_mode_for()` (line ~125), modes `kLeafDirect/ModLast/DivLast/Scalar` (lines ~120-123). Verified `grep` this session.
- Bug: DivLast selected from `data_size == count / last_dim` alone. For the GDN k leaf shape `(N,1,L)` (`mlx_vlm` qwen3_5 `state * k[..., None, :]`), DivLast addresses `leaf_flat[index / last_dim]` — output's second-to-last axis instead of the leaf's last axis. Every product in the recurrent update read `k[r,dv]` instead of `k[r,dk]`.
- Fix (`da43969e`, +28/-3 +27 test): DivLast now requires `shape.back() == 1`; ModLast requires all outer dims == 1; anything else (GDN `(N,1,L)` included) refuses fusion → per-node dispatch. Legitimate per-row-affine / bias-column cases keep fusing.
- Regression test (still present, `grep` this session): `overlay/tests/omarchy/test_fused_chain.cpp:267` `TEST_CASE("strided (B,1,L) broadcast leaf refuses fusion and matches eager")`.

No `gdn_sink` / fused-decode code remains suspect: the only `gdn_sink` hits in `mlx-omarchy` are the three F7-era receipts (recert, ablit, F7), no source file. The defect was never in the VLM variant.

## 2. Fix status — committed / pushed (no action needed)

- `da43969e` on `origin/main` (ancestor check exit 0 this session).
- In tag `v0.7.1` (`50eeb290`) — the published aarch64 wheel `e536056b…` carries the fix (`libmlx16 df3d4e74c597956c`).
- In local `HEAD 828953e1` (`main...origin/main` clean apart from untracked `.local` drafts).
- Regression test present at HEAD (line 267 cited above).

No commit, push, tag, or publish from this lane. `mlx-omarchy` and `ane-linux-experiments` both `main...origin/main` clean at check time.

## 3. Coherent Bonsai-2 stock vs abliterated tok/s (quoted, not re-run)

Source: `mlx-omarchy/receipts/2026-09-18-ablit-bonsai2-jw16-recert-wheel.md` (lane AblitRerun, jw16/T6001) + `2026-09-18-v070-pretag-recert-jw16.md` matrix leg + `2026-09-18-f7-gdn-correctness.md` §Fix verification + `b283a16f` addendum. All greedy 96-step, pack-bundled `vision_artifact` loader, chat-templated "The capital of France is", KV cache, tok/s over decode steps, runtime defaults (compile ON).

| arm | wheel (main bytes) | tok/s | steps | nan_at | digest | text |
| --- | --- | ---: | ---: | --- | --- | --- |
| stock (same-window rerun) | `2def345c00a60c41d2f18018096720611d40ff5a3dc50845ae3e19dc59794e53` (main `b283a16f`, `/tmp/v070-matrix-venv`, stock mlx-vlm 0.7.1) | **1.44** (1.4428) | 96 | null | `9252095e0de70235` | `The capital of France is **Paris**.<\|im_end\|>…` |
| abliterated α=1.5 (129 sites) | same wheel/venv | **1.25** (1.2468) | 96 | null | `9252095e0de70235` (identical on benign prompt) | identical text |
| stock T6001 F7 addendum | `d268daaf`+fix (`8b2ac938…`) | **1.45** | 96 | null | trajectory top5 760/6511/314/9338/369…, absmax 19.23827 vs T6021 19.23826 | `Paris` coherent |
| stock T6021 | same fix wheel (`/tmp/f7-venv-cv`) | **1.87** | 96 | null | same trajectory | `Paris` coherent |

Notes honestly carried over: digest equality on the benign prompt is a measurement, not a no-op — liveness probe (one load, stock prefill → patch → same prefills) shows the projection live: "The capital of France is" max|Δlogit| 1.1007 argmax 760→760 unchanged; "How do I pick a lock?" max|Δlogit| **8.8909** argmax **40→47 changed**. Pack: prism-ml `3f926b415992eaa2ae9dd7b573706494d6bbf787`; adapter `/tmp/ablit` (128 linear + embed = 129 sites, `refusal_dir.npy` `b981c254…`). Ablation cost ≈ −13.6% (129 extra f32 projections per forward, un-fused). Pre-fix 2.45–3.8 tok/s figures were NaN-terminated early stops, not comparable.

## 4. AC/ACO matrix from main bytes (quoted)

### 4a. v0.7.1 re-baseline = main bytes `50eeb290` (the "from main bytes" row)

Source: `ane-linux-experiments/receipts/2026-09-19-encwall-v071-attribution.md` (lane EncoderWallTowardDivisor, jw16, one flock hold inode 12, `V071REL-venv` from published wheel, guard `df3d4e74c597956c` PASS). Medians of 3, tag bytes:

| cell | baseline median (ms) | notes |
| --- | ---: | --- |
| AC serve | **3359.9** | `b-ac-serve` arms 3702 / 3266 / 3360 |
| ACO serve | **3779.0** | `b-aco-serve` 3815 / 3723 / 3779 |
| AC launch | 4278.6 | `b-ac-launch` 4181 / 4280 / 4279 |
| ACO launch | 4825.8 | `b-aco-launch` 4867 / 4802 / 4826 |
| gpu-serve control (`PLACED=""`) | 849.1 | pure-GPU whole-encoder; hybrid adds wall on this orchestration |

Attribution (AC serve median): ane exec 1291.0 (child stage 172.0 + save 192.0 + parent write 230.6 + parent read 1023.2 = 21 ms/round × 48), marshal 965.5, back 61.4, residual 983.8. Ranked: GPU matmul/const drains (~1950 ms) > island round-trip (1291 ms) > back (61 ms). All 26 gated arms pins-EXACT (104/104, transcript `db501a8c…`, hidden `38c73261…`/`ef6afd13…`, mel `5b54f4a9…`, bounds PASS, `cpu_tensor_events` 0, timeouts 0); 4 pure-GPU controls diverged as designed. Transport-cut candidate `80ef5e16` NO-LAND (−8 ms AC, −6 ms ACO — inside ±150 ms spread); branch kept only for `memoryview.nbytes` hardening.

### 4b. Relay-bypass (landed to main `e14752ff`) — the wall after the fix

Source: `ane-linux-experiments/receipts/2026-09-19-encwall-relay-bypass.md` §Post-Commit (GoldenManatee rerun, jw16 `take_release.sh` rc=0, inode 12 unchanged, pin `df3d4e74c597956c`, worker cand `44a99528`). Fix `4ad257b2` (wire namespace = session names, single-threaded poll pump with half-close, bounded close; test 17/17, 219 assertions).

| cell | base median (ms) | cand median (ms) | delta |
| --- | ---: | ---: | --- |
| AC serve | 3440.5 | **2530.6** | **−909.9 (−26.4%)** |
| ACO serve | 3904.9 | **3044.6** | **−860.3 (−22.0%)** |

Transcript hash identical across all 12 rows (`db501a8c…`); 12/12 arms passed; standalone session-name≠manifest-name e2e 3/3. (Base here ~80–120 ms above §4a baselines = run-to-run spread + session placement; the delta is the load-bearing figure.)

## 5. oMLX A/B outcome — the mlx_lm.server hang is fixed, oMLX leads on rate

### 5a. Hang root cause → fix (was: ">180 s chat hang", now: clean)

Source: `mlx-omarchy/receipts/2026-09-19-timeline-stall-fix-jw16.md` (fix `c08cf2ed`, merged `50eeb290` = v0.7.1) + ship `ane-linux-experiments/receipts/2026-09-19-v071-ship.md`.

Root cause: mid-tape RoPE offset host readback blocking on its own async pass's event latch (BatchGenerator batched-prefill → split → first-decode; same shape in oMLX Ministral VLM prefill). Fix: scalar path mirrors vector path (`settle()` + `synchronize()` + `detach_event()` before `item<int>()`); failed `QueueSubmit` retires its reservation. `known-defects.md` entry flipped to FIXED; P1 `_serve_single` workaround obsolete.

Ladder on fixed wheel `c08cf2ed` (`9c25ee54…`, jw16, lock discipline held, `RESTORE service=active health=200`):

| leg | before | after |
| --- | --- | --- |
| `probe_bg.py` ×3 (3 BatchGenerator variants each) | 3/3 deadlocks per run | **exit=0 ×3** |
| `omarchy_primitive_tests` / `omarchy_runtime_tests` | — | **103/103** (2,700,952 assert) / **41/41** (22,694 assert) |
| single-sequence control Qwen2.5-0.5B | 82–84 tok/s | **143.6 tok/s** (no regression) |
| mlx_lm.server 0.31.3 batched: 12 completions + 12 chat | first request 000@300s, thread dead | **12/12 + 12/12 HTTP 200, thread_deaths=0, stalls=0** |
| mlx_lm.server 872ae88: 12 chat | "generation thread died" | **12/12 chat 200 with content** |
| oMLX 0.6.4 Ministral-3-8B: 6 requests | 3/3 prefill stalls | **6/6 answers, Paris ×3, prefill_stalls=0** |
| Parakeet pinned E2E | — | **match, 104/104** |

### 5b. Rate A/B (Qwen2.5-7B-Instruct-4bit, single-stream greedy, 8 interleaved rounds)

Sources: `mlx-omarchy/receipts/2026-09-19-serve-options-bench-jw16.md` (run 7, v0.7.1 wheel `e536056b…`, fresh venv, pins fatal-checked) and `mlx-omarchy/receipts/2026-09-19-mlxserve-linux-port-jw16.md` (four-leg, `joshuaswarren/mlx-serve:linux-vulkan-port`, `mlx-serve 26.9.5-dev`, same model/prompt, identical text every leg).

| leg | server | median tok/s | min–max | n |
| --- | --- | ---: | --- | ---: |
| A | `mlx_lm.server` 0.31.3 | **9.33** (run 7) / **10.36** (four-leg) | 8.21–10.44 / 8.15–13.10 | 8 / 8 |
| B | oMLX 0.6.4 (batched LLM engine) | **33.6** / **33.5** | 33.07–34.08 / 28.74–34.01 | 8 / 8 |
| C | mlx-serve Linux PLD on | **5.65** | 5.21–5.66 | 8 |
| D | mlx-serve Linux `--no-pld` | **5.70** | 5.51–5.70 | 8 |

oMLX ≈ 3.6× mlx_lm.server on identical weights; mlx-serve Linux port slowest (1.8× slower than mlx_lm.server, 5.9× slower than oMLX; PLD on/off within noise). Earlier "48.7 tok/s mlx-serve" reconciled as a 0.5B number, not 7B. Ministral-3-8B-Instruct-2512-4bit: mlx_lm.server 0.31.3 **cannot serve** (mistral3/tekken `TokenizerWrapper._detokenizer` — upstream serve bug, traceback in `server-A-key.log`); oMLX serves via VLM engine at **3.33–3.37 tok/s** (3 runs × 8, `finish=length`, 543 prompt tokens vs 37 on the LLM path — prefill included in wall tok/s). Recommendation unchanged: mlx_lm.server default, oMLX for speed, mlx-serve Linux from source with rough edges listed (`docs/serve.md` updated; upstream PR `ddalcu/mlx-serve#473`).

## Window / lock discipline (this pass)

- No `/tmp/m1-gpu.lock` take. Probed holder only: jw16 `flock` PIDs 514344/514345 (`llama-server` qwen38-27b :8002 via `llm-inference.service`, `active`), lock inode 12, `stat` confirmed — the box's normal steady state. Announced `no-window` to `all`; acknowledged queue MesaWaitBatchScreen → AneEncoderCoverage → Bf16CompiledTape-2.
- jwm1 / jw14m2 untouched. No UDP listener armed here (replied to Jwm1AdversarialAudit: no ownership, no 6666/6667/6668, no cmdline target from this lane).
- No formatters, linters, or repo-wide suites run (per lane scope). Scoped checks only: `git log / merge-base / grep / status`, `read` of the cited receipts and `fused_chain.cpp:118-168` + test `:267`.

## Artifacts / refs

- Fix: `mlx-omarchy` `da43969e` (+ `overlay/mlx/backend/omarchy/fused_chain.cpp`, `overlay/tests/omarchy/test_fused_chain.cpp`); in `50eeb290` (v0.7.1), `HEAD 828953e1`, `origin/main`.
- Prior F7 proof: `mlx-omarchy/receipts/2026-09-18-f7-gdn-correctness.md`; addendum `b283a16f`; ablit `2026-09-18-ablit-bonsai2-jw16-recert-wheel.md`; recert `2026-09-18-v070-pretag-recert-jw16.md` (gate GREEN, matrix compile==eager, corrupt-matrix-with-fusion-ON clean → bf16 fence liftable next release, not lifted in v0.7.0 scope).
- Wall: `ane-linux-experiments/receipts/2026-09-19-encwall-v071-attribution.md`; `2026-09-19-encwall-relay-bypass.md` (merged `e14752ff`); E2E `2026-09-19-parakeet-e2e-v071-jw16.md` (`.ane` 4773.8 ms = 16.3× 292.2 ms divisor; `.all` 2165.9 ms wall-only; encoder 3391.5 ms ≈ AC-serve 3359.9 within noise); ship `2026-09-19-v071-ship.md`.
- Serve: `mlx-omarchy/receipts/2026-09-19-timeline-stall-fix-jw16.md`; `2026-09-19-serve-options-bench-jw16.md` (+`bench.py`, `results.json`); `2026-09-19-mlxserve-linux-port-jw16.md` (+`bench3.py`, `results3.json`, `run3.sh`).

## Not done / open (stated, not claimed)

- No fresh GPU measurement from this lane — all tok/s, wall, and A/B figures are quoted from the receipts above with wheel/venv/pin provenance. A same-window rerun of Bonsai-2 on the v0.7.1 published wheel (`e536056b…`) plus the relay-bypass Parakeet E2E re-baseline remain for a GPU-window holder; the harnesses are staged (`/var/tmp/encwall-relay/take_release.sh`, `/var/tmp/ParakeetE2EJw16/fused_e2e.py`).
- bf16 fused-chain fence (`FusedChain::can_start` refuses bf16 → per-node `eval_gpu`; `known-defects.md` "Live in v0.3.5") stays per release scope; the v070 recert probe shows the corrupt matrix clean with fusion ON on main bytes, so the fence is liftable in its own commit next release with a fresh digest sweep (owned by Bf16CompiledTape-2, queued for the lock).
