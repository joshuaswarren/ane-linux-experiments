# jw14m2-linux MLX/Vulkan decode+prefill baseline — wheel 5b18306, fixed harness, stock Honeykrisp 26.2.3 (2026-09-20)

Verdict: **BASELINE RE-ESTABLISHED (first VALID perf numbers post-invalidation).** All five legs ran under
`/tmp/jw14-bench/gpu.lock` on an otherwise idle box (load ≤0.95), ≤10-min legs, compileON==compileOFF
**bit-exact on both prompts** (ID digests), A/A deterministic. Decode/prefill numbers below are produced by
the v2 fixed harness (`8a821aba…`, summary event excluded from BOTH numerator and denominator), so they
replace the invalidated Phase A/B columns (`2026-09-20-jw14m2-phaseB-a1251-correctness-gate.md`).

## Context

- Mesa sin-FTZ fix `095cb7e1` ("agx: return a flushed signed zero from sin under DenormFlushToZero",
  landed 2026-09-20T16:31:09Z in `joshuaswarren/mesa-1`) is **NOT staged on jw14m2-linux**: no mesa build
  tree, no ICD/loader override, no honeykrisp-omarchy package — host runs stock `mesa 1:26.2.3-1` +
  `vulkan-asahi 1:26.2.3-1` (DRIVER_ID_MESA_HONEYKRISP, API 1.4.354 — the same driver/vintage as the
  2026-09-18 third-device baseline). Per delegation, the existing MLX/Vulkan baseline with exact pins was
  executed instead.
- jw14m2-linux rebooted 2026-09-20 ~16:23 (h14 first-boot fault, boot lane). The wipe took the Phase A/B
  `/tmp/jw14-bench` (venv, lock, harness copies, raw receipt JSONs — committed receipts survive). This
  session rebuilt the bench area from repo-pinned artifacts; **zero downloads, zero system installs**
  (all pip deps were pip-cache hits, `Downloading` count = 0, verified in `logs/pip-deps.log`).

## Exact pins

| item | value |
| --- | --- |
| host | jw14m2-linux, kernel `7.1.13-3-1-ARCH`, M2 Max (G14C B1), `/dev/dri/renderD128` |
| driver | stock mesa/vulkan-asahi `1:26.2.3-1`, Honeykrisp, API 1.4.354, conformance 1.4.0.0, deviceUUID `3bacad71-…` |
| wheel | `mlx_omarchy-0.32.3.dev202609201440+5b18306-cp314-cp314-linux_aarch64.whl`, sha256 `fe51534b1ed658f64f2e16f5ce4709c27cbb1c683388b50a2d04eacf6b362a01` (local worktree build; supersedes Phase B's a1251aaa) |
| installed libmlx.so | sha256 `c28a485f98b55aadf12c68ae6d373f308517177c0cf33ad3c77ea82a796e931e` — byte-equal to the wheel member (fork wheel re-seated LAST after pip pulled upstream `mlx==0.32.2` as mlx-vlm dep; the overwrite hazard is real and must be re-checked after every dep install) |
| venv | `/tmp/jw14-bench/venv` (system python 3.14.7); pins: mlx-omarchy 5b18306, mlx-lm 0.31.3, mlx-vlm 0.7.1, transformers 5.17.0, numpy 2.5.3, tokenizers 0.23.2, huggingface_hub 1.32.0, safetensors 0.8.0 (full freeze in evidence) |
| model | `mlx-community/Qwen3.8-27B-4bit` snapshot `10c35caafbb80f7dc6a7a432cdd11af10a6d4818` (HF cache, offline) |
| harness | `bench_decode_vlm.py` v2 sha256 `8a821aba9b2bb2ed4897eec54020cc7326a5a3677d45ff98a254ce86ad478b05` (repo copy `receipts/2026-09-20-final-harness-bench_decode_vlm.py`; self-test PASS: rate=(n-1)/(last-first) over real decodes, summary event excluded from ids and rate) |
| matrix | `bench_matrix.json` sha256 `df8eb9f3…` (unchanged pin); companions `caps_sim_guard.py`, `mlx_provenance.py` from `.local/ane-v064-wt/scripts/` |
| protocol | `HF_HUB_OFFLINE=1`, temp 0 seed 0, `--warmup-tokens 4`, `--stop-policy ignore-eos`, `--tokens 128`; compileON = `env -u MLX_DISABLE_COMPILE`, compileOFF = `MLX_DISABLE_COMPILE=1`; fresh process per leg; `flock -n` held on `/tmp/jw14-bench/gpu.lock` across each leg |

## Results (fixed harness — VALID; supersedes Phase A/B rate columns)

| leg | prompt | mode | decode tok/s | prefill s | prefill tok/s | prompt_tokens | ids sha256_16 (n=128) | wall |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | long (245) | compileON | 4.485 | 18.55 | 13.21 | 245 | `735b8de2664c8d87` | 81 s |
| 2 | long (245) | compileOFF | 4.3817 | 19.64 | 12.48 | 245 | `735b8de2664c8d87` | 77 s |
| 5 | long (245) | compileON A/A | 4.4949 | 18.90 | 12.97 | 245 | `735b8de2664c8d87` | 75 s |
| 3 | ctx1024 (1036) | compileON | 4.2985 | 76.82 | 13.49 | 1036 | `0e0c0824d8ae2bce` | 194 s |
| 4 | ctx1024 (1036) | compileOFF | 4.1803 | 77.92 | 13.30 | 1036 | `0e0c0824d8ae2bce` | 196 s |

- **ON==OFF bit-exact** on both prompts (`735b8de2664c8d87` ×3, `0e0c0824d8ae2bce` ×2); the bf16
  compiled-tape refusal stays absent on 5b18306. Both digests are identical to the Phase B (a1251aaa)
  digests — the 128-token ID sequences are stable across wheels a1251aaa → 5b18306.
- Compiled path: ~+2.4% decode (long), ~+2.8% (ctx1024); prefill parity. Single-run first-indication only —
  no parity/divisor claim, no cross-host comparison.
- Summary-event semantics: `summary_events=1` on every leg, correctly excluded (engine `bench_decode_vlm_v2`).

## Coordination

- `M2BootImplementation` (sole boot/recovery owner, jw14m2) approved the window in-band ("no collision:
  proceed"); constraints honored: no touch of `/var/tmp/ane-t6021-6be485f`, `/var/tmp/ane-w15-fault-capture/`,
  ANE MMIO/pmgr sysfs, no `ane*`/netconsole module loads. GPU yields at their boot boundary.
- `ServePerformanceAudit` (jw16 window) and `GPUparityroot-causeaudit` (jwm1/jw16 lanes) confirmed zero
  jw14m2 overlap.

## Artifacts

- Host (volatile `/tmp/jw14-bench/`): `logs/leg{1,2,3,4,5}-*.log` (full rtmod traces), `results/all-legs.jsonl`,
  `evidence/env-provenance.txt`, `leg-logs.tgz`, `logs/wheel.sha`, `logs/libmlx.sha`, `logs/pip-deps.log`
  (0 `Downloading` lines).
- Repo (persistent, this dir): `evidence/all-legs.jsonl` (5 result lines, sha256 `a61d604b…`),
  `evidence/env-provenance.txt`, `evidence/leg-logs.tgz` (all five full leg logs), `evidence/wheel.sha`,
  `evidence/libmlx.sha`, `receipt.md`.

## Not claimed / open

- Mesa `095cb7e1` sin-FTZ behavior on jw14m2 is UNTESTED — needs a staged mesa build/ICD override; nothing
  was built or installed here (delegation constraint).
- Single-run rates; no thermal/long-run soak, no cross-driver comparison (stock 26.2.3 vs honeykrisp-omarchy
  devel remains open until the fork package or a loader override lands on this host).
