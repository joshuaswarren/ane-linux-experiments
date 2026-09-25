# 2026-09-25 — t6001-host (M1 Max) decode: launch-count fusion (459 -> 405 dispatches/token, bit-exact, INSTALLED); the "no-split race" is the stack's own rare near-tie class (it reproduced on the installed driver); CPU clock state moves decode ~5%; macOS window NOT run

Lane: Jw16Levers2 (successor of Jw16GpuLevers, receipt 7b72042). Host:
t6001-host (M1 Max T6001/G13C, Omarchy 7.1.6-1-1-ARCH), single GPU owner;
every GPU leg under `/tmp/m1-gpu.lock` with `llm-inference.service` stopped
and restored with a real completion by the window trap
(`artifacts/*/window-*.log`, `completion-*.json`). Driver throughout:
`/usr/local/lib/libvulkan_asahi.so.d3fa18e` (sha `1e912d3e…`), unchanged.
Model `SiddhJagani/Qwen3.8-2B-mlx-4Bit` @0867d98b; contract = 10 prompts,
warmup 3, greedy, 32 new tokens, prefill 512 (`~/bench-scripts/qwen38-mlx-bench.py`).
Denominator (same laptop, macOS, fd8d878 row): decode 180.38 tok/s (5.54 ms/tok),
prefill 1326.05, e2e 0.2081 s.

**Verdict.** Three bit-exact fusions land: the GatedDeltaNet qkv projection
joins its z/a/b GEMV group (four weights per dispatch), mlx-lm's swiglu is
spelled out so the gate/up GEMV store epilogue folds it, and Qwen3-Next's
fused q_proj is split into query and gate projections at load (no strided
copies). Dispatches per decode token 459 -> 405 (-11.8%); decode 77.7 ->
78.6 tok/s median on quiet paired legs (+1.1%, 12.87 -> 12.73 ms/token),
digest `bc519c03` on every candidate arm (12 of 13 legs; the 13th is the
pre-existing near-tie class, section 3). Installed into the serving venv.
Parity is not reached (decode 0.44x macOS). Launch count is NOT where the
remaining time is: 54 fewer launches bought ~0.14 ms of 12.9.

## 1. Per-token launch census (MLX_OMARCHY_TRACE_DISPATCH, steady token, 3 tokens identical)

Before (installed 3232b1f5e wheel), one GDN layer = 19 dispatches, one
attention layer = 18, head = 9: **459/token**. Not 513: the SDPA native
hd256 arm now covers the contract's k <= 60 (the 513 figure predates it).

| kernel | before | after | delta | why |
|---|---:|---:|---:|---|
| QmmVecQ4WordSubgroupBF16 | 19 | 1 | -18 | GDN `in_proj_qkv` was the 4th projection of the normed row; the group cap was 3 weights |
| SwigluBF16 | 24 | 0 | -24 | mlx-lm `swiglu` (and the `nn.silu` inside it) are `mx.compile`d: opaque to the planner, the GEMV store epilogue never fired |
| CopyGeneralBF16 | 24 | 12 | -12 | attention `q_proj` output split into query/gate along the head axis = two strided views, each copied before q_norm / sigmoid |
| QmmVecQ4MultiSubgroupBF16 | 96 | 96 | 0 | 4 group dispatches per layer as before (GDN group now carries 4 weights, attention group q/gate/k/v) |
| FastRmsNorm 79, FastNormGated 36, CastBF16F32 36, FusedChainF32 36, CastF32BF16 18, GatedDeltaDecode 18, GdnConvDecode 18, FusedChainBF16 18, FastRope 12, Sdpa 6, Sigmoid/Multiply 6+6, head 9 | 298 | 296 | -2 | untouched (the 2 are Elementwise/BinaryVec counting noise at the head) |
| **total** | **459** | **405** | **-54** | |

The remaining swarm: 90/token is `_precise_swiglu` (18 x [Cast, FusedChainF32,
Cast, FusedChainF32, Cast]) whose fused form (`rms_norm_gated`, mode 0) is
PARKED on the driver-pipeline exp() bit wall (receipt
2026-09-23-t6001-dispatchcut-fused-norm section 11); 48 are gx=1 RMSNorms
whose GEMV-prologue fold failed the same wall (launch-sink2 ADDENDUM 4).
Neither was retried here.

## 2. What landed (mlx-omarchy branch `agent/jw16-levers2`, pushed)

- `1faf7f00a` — shaders/qmm_vec.comp QMM_VEC_MULTI: fourth weight slot
  (bindings 19-24, `shape[3]`, same Q4_ROWS chain and ROUND_STORAGE store);
  `kComputeBindingBudget` 19 -> 25, `kQmmVecMultiWeights` 3 -> 4 (host loop,
  flag bits and push-constant arrays already covered four). Plus
  `scripts/patch-mlx-lm-swiglu-eager.py` (v1).
- `152a41cd4` — `scripts/patch-mlx-lm-qwen3next-qgate-split.py` (per-head row
  permutation of q_proj weight/scales/biases into q_proj + q_gate_proj at
  sanitize; call/init/shard sites; idempotent) and the swiglu patch v2:
  `(gate * mx.sigmoid(gate)) * x` — v1 only dropped swiglu's decorator and
  left the compiled `nn.silu`, measured on-device as FusedChainBF16 +
  BinaryVecBF16 per MLP layer (465 dispatches, slower).
- Wheel `mlx_omarchy-0.32.3.dev202609252013+1faf7f00-cp314-cp314-linux_aarch64.whl`,
  built natively on the device (incremental, 144 s) in `/var/tmp/levers/mlx`.
  The device clone has no GitHub key; branches reach it by
  `git push 16m1mbp:src/mlx-omarchy <branch>:refs/heads/levers2-incoming`.
- NOT merged to mlx-omarchy main: the standing omarchy battery (27 suites +
  capability-sim) was still building at `/var/tmp/levers/mlx/.work/build-tests`
  when this receipt closed (request budget); the 3-pass digests are in, the
  10-pass pins come out of the battery window's control legs
  (`artifacts/install/contract-bat-ctl-p10-*.json`, expected `dbf70497`).
  Merge = `git merge --ff-only agent/jw16-levers2` after both are green.

Bit-exactness argument, confirmed by digest: every output row of a Q4 GEMV
is one Q4_ROWS dot of the same normed row, independent of which slot or which
weight it sits in and of row order (the q/gate permutation), so the fourth
slot and the split change no arithmetic. The swiglu store epilogue was
already written statement-for-statement against swiglu.comp (b2ff4e585);
this is its first in-model proof: `bc519c03` x6 with the fold firing.

## 3. Contract arms (same venv recipe on both sides: candidate venvs are copies of the serving venv with only the wheel and/or the two mlx-lm patches changed)

| window / arm | wheel | venv patches | decode tok/s (3-pass runs) | prefill-512 | digests |
|---|---|---|---|---:|---|
| cand1 ctl | 3232b1f | none | 77.66, 78.06 | 735 | bc519c03 x2 |
| cand1 ctl + `MLX_OMARCHY_POISON_FREED=1` | 3232b1f | none | 77.88 | 733 | bc519c03 |
| cand1 candA (4-weight group only) | 1faf7f00 | none | 76.65 | 720 | bc519c03 |
| cand1 candB (+ swiglu patch v1, nn.silu still compiled) | 1faf7f00 | swiglu v1 | 75.81, 74.26 | 719 / 710 | bc519c03 x2; census 465 |
| cand2 ctl | 3232b1f | none | 77.98, 77.72, 76.31 (median 77.72) | 737 | bc519c03 x3 |
| cand2 ctlS (swiglu fold on the installed wheel) | 3232b1f | swiglu v2 | 77.93, 77.92, 77.22 | 732 | bc519c03 x3 |
| cand2 candA | 1faf7f00 | none | 77.79, 77.67, 77.76 | 730 | bc519c03 x2, **c12461f2** (r3) |
| **cand2 candC (all three)** | 1faf7f00 | swiglu v2 + qgate | **78.69, 78.12, 78.57 (median 78.57)** | 741 / 723 / 741 | **bc519c03 x3**; census **405** |
| install installed-r1..r3 (quiet box) | 1faf7f00 | swiglu v2 + qgate | 77.34, 78.53, 78.19 | 730 | bc519c03 x3 |
| install installed-r4 / perfgov-r1 (section 5) | 1faf7f00 | same | 82.37 / 82.08 | 748 / 737 | bc519c03 x2 |
| probes on the installed stack: FUSED_GEMV=0, FUSED_CHAIN=0, NO_BUFFER_CACHE=1, FUSED_TRIO=0 | 1faf7f00 | same | 78.36 / 72.22 / 81.58 / 82.34 | | bc519c03 x4 |

Legs are interleaved in order inside each window (`body-cand2.sh`). candC vs
ctl in cand2: every candC rep above every ctl rep, +0.85 tok/s on medians
(+1.1%); ms/token 12.87 -> 12.73. The 4-weight kernel alone (candA) is
within noise of ctl (77.7 vs 77.7 medians): the 18 saved launches and any
cost of the wider kernel cancel. The swiglu fold alone on the installed wheel
(ctlS) is also within noise. Prefill is unchanged within noise (the fold and
the split apply only to the decode row; prefill keeps the swiglu.comp chain
and the coopmat path).

## 4. The "no-split race" (assignment item 2)

Assignment premise: 2 single-record flips in 290 nosplit records mean a
dependency the batch split hides. Measured this session:

1. **`c12461f2` reproduced on the INSTALLED (split) driver** — cand2 candA-r3,
   pass 0, prompt 7, first divergence at token 15, 3 tokens differ then the
   sequence reconverges (`artifacts/cand2/contract-candA-r3.json` vs any
   `bc519c03` run). This is byte-identical to the nosplit "installed-r1"
   flip of the previous receipt. The other nosplit digest, `a483d947`
   (prompt 7 token 19), was already recorded as a control-arm near-tie on
   the installed driver (dispatchcut receipt, ADDENDUM 2, "one near-tie
   a483d947"), and that receipt's control produced 2 non-`bc519c03`
   digests in 10 runs. Both flips the no-split lane saw are therefore the
   stack's own rare class, not evidence of a barrier dependency; whether
   no-split changes its RATE is what the interleaved battery decides
   (below).
2. Every flip on record is **pass 0, prompt 7** (the first time that prompt
   runs in the process): the class is allocation/state-shaped, not
   timing-shaped.
3. Exonerated by digest pin (`bc519c03`): stale reads of recycled buffers
   (`MLX_OMARCHY_POISON_FREED=1`, finite poison), the buffer cache itself
   (`MLX_OMARCHY_NO_BUFFER_CACHE=1`), and fusion-path selection
   (`MLX_OMARCHY_FUSED_GEMV=0`, `FUSED_CHAIN=0`, `FUSED_TRIO=0` each pin the
   same digest, so the fused and unfused paths are bit-identical on this
   contract and a timing-dependent choice between them cannot flip a
   token). No decode kernel uses float atomics (only the unused greedy
   head). Not exonerated: a read that a finite poison cannot expose (a
   garbage lane masked to zero or fed to a running max before masking) —
   the sdpa hd256 kernel bounds every key loop by k_len, so it is not the
   SDPA; a NaN poison variant of POISON_FREED is the next probe.
4. Mesa side (mesa-1, d3fa18e8dd0 vs 41ccf96cc59): `hk_CmdPipelineBarrier2`
   -> `hk_cmd_buffer_end_compute` does nothing but flush `imm_writes`
   (queries, unused by MLX) and `merge_control_streams` re-joins the split
   CDM streams with `agx_cdm_jump`, so the only GPU-visible difference of
   no-split is the absence of one stream-link packet per MLX barrier; MLX
   records no `vkCmdSetEvent2`/`WaitEvents2` inside a batch. There is no
   dependency-carrying packet for no-split to have dropped.
5. **Interleaved 10x10-pass battery, installed driver vs no-split
   (`VK_DRIVER_FILES=/var/tmp/levers/icd/41ccf96.icd.json`), on the
   installed candC stack:** launched in the install window
   (`artifacts/install/window-20260925T203417Z.log`,
   `contract-bat-{ctl,nosplit}-p10-{1..10}.json`); still running when this
   receipt closed. The window trap restores `llm-inference` and takes a
   completion when it ends; nothing is installed by it. Read it with
   `python3 artifacts/summ.py /var/tmp/levers2/install/contract-bat-*.json`
   on the device: control must pin `dbf70497` (also the 10-pass pin the
   candC merge needs), and the no-split arm qualifies only if its
   divergence count is not above the control's.

## 5. CPU clock state moves GPU decode (~5%, bit-exact) — confounded, needs a clean A/B

With the tests build (`nice -n 10 cmake --build -j4`) running beside the
window, decode jumped from 77.3-78.5 to 82.1-82.4 tok/s on the same stack
(`installed-perfgov-r1` with all three cpufreq policies on `performance`:
82.08; `installed-r4` back on `schedutil` but with the compile still
running: 82.37; probes nocache/trio0 81.6/82.3; TTFT 84 vs 75, e2e 0.53 vs
0.57 s). Same mechanism Jwm1Parity7 found for the T8103 ANE
(omarchy-ane 5a22ee3, `ane_boost.c`): schedutil parks the idle clusters
between GPU completions and the host side of every submission pays. The
governor A/B here is confounded by that background load; a clean paired
run (quiet box, governor toggled) is the next lever with measured
headroom, and it is free.

## 6. Installed state (assignment item 3)

- Serving venv `/var/tmp/v072-venv-fused`: wheel
  `0.32.3.dev202609252013+1faf7f00` (single dist-info; libmlx sha
  `9e7c03b2a6bf030a…`), mlx-lm 0.31.3 with raw-route (2 refs) +
  rms_norm_scaled (3) as before, plus swiglu-eager (1) and qgate-split (4
  refs); gated-norm mode 0 still unrouted. Census 405/token.
  Pre-install snapshot for revert: `/var/tmp/levers2/venv-fused-pre-levers2/`
  (`mlx/`, the 3232b1f dist-info, and the three mlx_lm model files).
- ICD unchanged: `asahi_icd.aarch64.json -> libvulkan_asahi.so.d3fa18e`.
- Installed default, quiet box, 3-pass x3: decode 77.34 / 78.53 / 78.19
  tok/s (12.73-12.93 ms/token), prefill 730-732, TTFT rate 74.7-76.5, e2e
  median 0.569-0.578 s, `bc519c03` x3. Pass rule vs macOS: decode 0.44x,
  prefill 0.55x, TTFT 0.21x, e2e 2.7x — FAIL, as before.
- Service: `llm-inference` active with `/health` ok and a real completion
  after windows census, cand1, cand2 (logs in artifacts); the install
  window's trap does the same when its battery ends.

## 7. Not done

- **macOS window (item 4) NOT executed** — request budget. Prepared and
  staged: `artifacts/mac-run.sh` (runs `run-core.sh` under `sudo -n` and
  `run-parakeet.sh` with the swift-hidden fallback the jwm1 window needed,
  tars `out/`); bundle `mac-reference-bundle-full.tar.gz` sha
  `82c1a70198fd…` is at `ane-linux-experiments/.stage/`; reboot gate is
  live-verified PASS (`/boot` is ext4 nvme0n1p5, ESP nvme0n1p4, root btrfs
  nvme0n1p6[/@]); switch `sudo asahi-bless -n -y --set-boot <Macintosh HD>`,
  mac side `16m1mbp-macos` (LAN) or its tailnet node; stop llm-inference
  first, and on return: health poll + completion.
- mlx-omarchy main merge pending the standing battery (section 2).
- The `_precise_swiglu` swarm (90/token) and the gx=1 norms (48/token) stay
  on the parked exp()-lowering wall; the KV SliceUpdate pair merge and the
  RoPE/values direct-cache windows exist for f16 only (`fused_chain.cpp`)
  and were not extended to bf16 (12 launches/token).

## Artifacts

`artifacts/{census,cand1,cand2,install}/`: contract JSONs, censuses
(`*.trace`, `census.py`), window logs with service restore + completion
probes; `*.out` window consoles; `body-*.sh`, `window.sh`, `summ.py`,
`build-cand.sh`, `mac-run.sh`. Device: `/var/tmp/levers2/` (venvs
`venv-cand`, `venv-candA`, `venv-ctlS`, snapshot, outputs),
`/var/tmp/levers/mlx` worktree on `agent/jw16-levers2` with `dist/` wheel and
`.work/build-tests`.
