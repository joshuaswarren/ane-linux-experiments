# jw14m2-linux — third mlx-omarchy Vulkan device: F1 cross-silicon proofs, current-gen matrix, collector, Q4 baseline (2026-09-18)

Verdict: **GREEN.** The F1-fixed rtmod wheel installs and runs on the M2 Max
T6021 (G14C B1) Honeykrisp stack; all three TEST_DROP_SUBMIT proofs pass with
the same recovery-ladder behavior observed on jw16's T6001 (cross-silicon F1
verdict: the ladder is not T6001-specific); the five-model generation matrix
runs end-to-end with coherent output; Bonsai-2-27B loads through the schema-2
pack path and decodes 24 greedy steps with finite logits (F7 NaN **not
reproduced** in this probe configuration); the parity-protocol Q4 short/ctx
legs reproduce the pinned native generated-ID digests exactly; the community
collector submitted cleanly (row `5de576fd…`, second Linux ANE host ever
collected).

## 1. Provenance

| item | value |
| --- | --- |
| host | jw14m2-linux (Mac14,5 / M2 Max T6021 / J414c, aarch64), kernel `7.1.13-3-1-ARCH` (now booted; the qualification receipt's `-3` contingency is live) |
| RAM | 94 GB (weights headroom not a constraint in this matrix) |
| GPU | `/dev/dri/renderD128`, `Apple M2 Max (G14C B1)`, `architecture: honeykrisp`, Mesa Honeykrisp Vulkan 1.4.354, `mx.default_device()=Device(gpu, 0)`; no `MLX_OMARCHY_ALLOW_NON_APPLE` needed |
| wheel | `mlx_omarchy-0.32.3.dev202609181953+b744f4dd-cp314-cp314-linux_aarch64.whl`, sha256 `e4e83585f4967521e36af913209cc1a51b549e6777f5515b2dbb7229cf5f0551` — file-copy only from jw16 `~/src/mlx-omarchy-rtmod2/dist/` (14:55 build). F1Chain confirmed `b744f4dd` is the F1-fixed lineage (ladder + cholesky float64 gate + bounded recovery refusals; suites 103/103 + 41/41); `libmlx.so` inside the wheel carries the `MLX_OMARCHY_TEST_DROP_SUBMIT` hook (strings-verified before install) |
| venv | `/tmp/jw14-venv` (python 3.14.7, system `/usr/bin/python3.14`): wheel + `mlx-lm==0.31.3 --no-deps` + `mlx-vlm==0.7.1 --no-deps` + transformers 5.17.0 / numpy / pillow / safetensors / huggingface_hub / jinja2 / requests / starlette / uvicorn / websockets |
| system dep added | `pacman -S openblas` (fresh Omarchy lacked `libopenblas.so.0`; the wheel's CPU backend links it) |
| jw16 | read-only scp of the wheel + harness scripts only; GPU and windows untouched |

## 2. F1 cross-silicon proofs (T6021)

Probes identical to `mlx-omarchy/scripts-local/run-round5.sh`
(`MLX_OMARCHY_TRACE_DISPATCH=1`, `MLX_OMARCHY_HANG_NO_PROGRESS_NS=2000000000`,
timeout 150). Full log: `f1-t6021-proofs.log`.

| proof | env | probe | result |
| --- | --- | --- | --- |
| S0 sanity | (none) | sin f32 | `SIN-OK`, rc=0 |
| S1 drop-1 | `MLX_OMARCHY_TEST_DROP_SUBMIT=1` | sin f32 | `TEST-DROP cv=1` → `STALL target=1 observed=0` → `SUBMIT-RECOVER … (round 1, fresh signals)` → `SIN-OK`, rc=0 |
| S2 drop-1,2 | `MLX_OMARCHY_TEST_DROP_SUBMIT=1,2` | exp+sin | two `TEST-DROP` (cv=1, cv=3) → two STALL/RECOVER rounds → `TWOOP-OK`, rc=0 |

**Cross-silicon F1 verdict: the recovery ladder proves out on second silicon.**
Same never-began drop class, same rung-1 kick+resubmit path, same 2-round
budget, same correct kernel results (values match the fp32 references to
1e-6). No T6001-only behavior surfaced.

## 3. Generation matrix (94 GB M2 Max, MLX_DISABLE_COMPILE=1, greedy temp 0, 96-token cap, chat template, "one sentence on photosynthesis" prompt)

Runner: `/tmp/jw14-matrix.py` (on box), JSONL: `jw14-matrix.jsonl`.

| model | load_s | first-token s | tok/s | tokens | output |
| --- | ---: | ---: | ---: | ---: | --- |
| mlx-community/Qwen2.5-0.5B-Instruct-4bit | 0.79 | 0.205 | **92.97** | 39 (EOS) | coherent single-sentence answer |
| prism-ml/Ternary-Bonsai-8B-mlx-2bit | 1.04 | 1.098 | **6.29** | 33 (EOS) | coherent single-sentence answer |
| mlx-community/Ministral-3-8B-Instruct-2512-4bit | 2.21 | 11.336 | **2.65** | 41 (EOS) | coherent single-sentence answer |
| mlx-community/Qwen3.5-9B-MLX-4bit | 2.44 | 1.296 | **13.04** | 96 (cap) | coherent thinking-channel text |
| mlx-community/gemma-4-31b-it-4bit | 7.70 | 3.711 | **3.21** | 96 (cap) | coherent thinking-channel text |

Notes:
- First pass without `MLX_DISABLE_COMPILE=1` hit the known Honeykrisp gate on
  Ministral and Qwen3.5 (`Compiled tape bfloat16 is refused … Re-run with
  MLX_DISABLE_COMPILE=1`); the whole table above is one uniform pass under the
  compile-disabled protocol. Numbers-only protocol; no parity claims.
- Ministral's 11.3 s first token and 2.65 tok/s decode (mistral3 arch) are the
  weakest leg; recorded as observed.
- gemma-4-E4B (kv-shared) was skipped deliberately: release-0.31.3 loader bug
  documented in `2026-09-18-currentgen-loader-feasibility.md` /
  `2026-09-18-gemma4-e4b-upstream-bug.md`; 31B chosen per assignment ("12B or
  31B, whatever fits").

### Bonsai-2-27B (headline attempt)

- Loader contract per F1Chain (base rev `3f926b41` exact — snapshot on box
  matches): pack's bundled `runtime/vision_artifact.py::load_vl_model`
  (schema-2) builds `mlx_vlm.models.qwen3_5.Model` and installs 402 `Packed`
  modules. **LOAD-OK 2.9 s.** `artifact.load_model` v1 skew (known F5)
  avoided by using the canonical schema-2 entry.
- Probe (`bonsai2-run.log`): 62-token chat prompt, 24 greedy steps, full
  recompute per step (no KV cache — probe is a finiteness check, not a tok/s
  measurement; wall 174.7 s for 24 steps).
- **F7 NaN did NOT reproduce on T6021 in this configuration**: logits finite
  through all 24 steps (`nan_from_step: null`); decoded prefix is plausible
  model reasoning text. Per F1Chain's standing F7 finding this is recorded as
  a cross-silicon observation, NOT a text-trust claim and NOT a clean-room
  contradiction (different probe, short horizon, greedy, short context). F7
  remains the open lane on jw16.

## 4. Qwen Q4 GPU baseline — third SoC (numbers only)

Protocol: the parity-table battery (`bench_matrix.py --mode run`,
`bench_decode.py` sha `f5062d88…` + `bench_matrix.json` sha `df8eb9f3…`, both
hash-identical to the 09-14/09-17 jw16 runs; vendored from jw16
`/var/tmp/qmm-tilem`). Model pinned `a5339a4131f135d0fdc6a5c8b5bbed2753bbe0f3`
(snapshot on box matches). `HF_HUB_OFFLINE=1`, MLX_DISABLE_COMPILE via
manifest env, greedy seed 0, 4 warmup tokens, EOS suppressed, fresh subprocess
per leg, uncontended. Output: `jw14-q4-baseline.json`.

| leg | prompt tok | decode tok/s | prefill tok/s | prefill s | generated-IDs digest |
| --- | ---: | ---: | ---: | ---: | --- |
| qwen25-0.5b-4bit:short-decode-32 | 30 | **182.43** | 224.44 | 0.134 | `7fd25a869ff21678` (**= native pin**) |
| qwen25-0.5b-4bit:long-decode-128 | 262 | **155.35** | 1593.52 | 0.164 | `55215e22d7f1b864` |
| qwen25-0.5b-4bit:longctx-1024-decode-32 | 1053 | **99.66** | 2416.61 | 0.436 | `7da83f06ec9f001d` (**= native pin**) |

- Both native-pinned digests (`7fd25a869ff21678` short, `7da83f06ec9f001d`
  ctx1053) reproduce bit-exact on T6021 — same pinned identity the jw16/jwm1
  tables assert. Provenance gate `verified=match` on every leg.
- For scale (same protocol, jw16 v0.6.1 wheel, 2026-09-17): short decode
  190.63, short prefill 459.73; ctx decode 130.70, ctx prefill 3844.62.
  T6021 decode lands in the same class; short prefill is ~2× lower. **No
  native-macOS parity claims are made for T6021** (numbers-only mandate); a
  native M2 Max Metal divisor run would be needed for percentages.

## 5. Community collector (second Linux ANE host ever)

- `collect_quick.py` from `mlx-omarchy` main `c136912f` (workstation checkout;
  current-main collector with the v0.6.4-era `ane_port_detail` bring-up
  fields), run in the b744f4dd venv so `mlx` probes live
  (`mlx-omarchy-info`, `Device(gpu, 0)` recorded).
- **Submitted and accepted:**
  https://mlx-omarchy-community-data.joshua-s-warren.workers.dev/v1/results/5de576fdb1c3fdb083fd9cc74be1d1b45815936c64c7af95e519883cb049810e
  (`deduplicated=false`; row re-fetched and hash-verified after submit:
  `content_sha256=5de576fd…049810e`). Payload archive:
  `jw14-quick-submit.json` (114,137 B — `ane_port` captures the T6021 DT
  facts: no `apple,*-ane` node, display-only DARTs, ANE pmgr pwrstate
  topology, consistent with the 2026-09-18 qualification receipt).

## 6. Host mutations

- jw14m2: `/tmp/jw14-venv`, `/tmp/prefetch.py` + HF cache `~/.cache/huggingface`
  (~34 GB, 6 models), `/tmp/jw14-bench/**`, `/tmp/jw14-collect/**`,
  `/tmp/jw14-matrix.py`, `/tmp/jw14-bonsai2-probe.py`, `/tmp/*.jsonl|json|log`
  artifacts; `pacman -S openblas` (system package). GPU used for measurement
  only; **no ANE module load, no SET-block write, no device-tree change, no
  reboot**. `/tmp` contents are re-stagable; the HF cache is the only
  substantial artifact.
- jw16: read-only file copies (wheel, harness scripts). jwm1: untouched.
  No gates weakened anywhere; the bf16 compiled-tape refusal was honored, not
  bypassed (compile disabled, the documented operating mode).

## 7. Not claimed

- One locked pass per protocol battery; not a thermally soaked multi-rep
  median. Matrix tok/s are single-run eager-mode numbers.
- Bonsai-2-27B finite-logits result is a 24-step greedy observation, not an
  F7 closure; text output is not trusted per the standing F7 finding.
- Bonsai-2 probe decode time is not a tok/s number (quadratic recompute probe).
- No T6021/native-Metal parity percentages (no native M2 Max divisor run).

## 8. Refs

- `receipts/2026-09-18-t6021-qualification.md` (host state, DT gap, `-3`
  kernel contingency), `receipts/2026-09-18-runtime-modernize-source-bump.md`
  §TEST_DROP_SUBMIT proofs, `receipts/2026-09-17-jw16-gpu-parity-refresh.md`
  (protocol + jw16 comparison column),
  `receipts/2026-09-18-currentgen-loader-feasibility.md` (loader matrix,
  version boundary), `2026-09-18-f1-drift-forensics.md` (F1/V closure
  context). F1Chain coordination: wheel endorsement + Bonsai-2 loader
  contract + F7 warning (this session).
