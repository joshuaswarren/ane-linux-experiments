# m1-host/m1max-host encoder GPU feeder under the fork driver: ICD parity, coopmat-conv NO-GO, fused_e2e fix (2026-09-22)

Lane: EncoderFeederFork. Branch: `agent/ane-inprocess-submit`
(`ANE-REPO-WORKTREE/.local/ane-v064-wt`), commits `44eecc5b9`,
`2cba4fe36`, `4f3f85dba`, reverted by `2545f85e1` + `5be12c5f1` (net runner
change: zero — see §3). Hosts: m1-host (T8103) and m1max-host (T6001), fork-driver lane aliases per private/hosts.md.

## Task 1 — fused_e2e `import os` fix: DONE, verified green on m1max-host

- Bug: m1max-host's `/var/tmp/ParakeetE2EJm16/fused_e2e.py` read `os.environ`
  (`MLX_OMARCHY_TDT_BATCH`, stage_tdt) with no `import os` — every m1max-host e2e
  crashed after the encoder stage. Fixed in place (backup
  `fused_e2e.py.bak-20260922`); fixed copy committed to the branch at
  `receipts/2026-09-22-encoder-feeder-fork/derivation/fused_e2e-m1max-host.py`
  (commit `44eecc5b9`).
- Verification (osfix-20260922T083505, one full e2e on m1max-host, lock held):
  status **match**, 104/104 prefix, mel `5b54f4a9` / hidden `38c73261` /
  transcript `db501a8c` all gold, total_pipeline 2880.6 ms, tdt_decode
  1150.4 ms — **stage_tdt completes on m1max-host for the first time**.

## Task 2 — m1-host feeder on the system ICD: parity; coopmat-conv NO-GO

### ICD state and switch

- The `*-j1.sh` batteries pinned `VK_DRIVER_FILES=/var/tmp/mesa-e167-m1-host/icd.json`,
  whose `libvulkan_asahi.so` is the OLD build (sha `9fe6ccc6`); the system ICD
  `/usr/share/vulkan/icd.d/asahi_icd.json` is the Honeykrisp tip `7faf04c`
  (sha `09e3527d`, same file as `mesa-e167-m1-host/tip.so`).
- Interleaved A/B on m1-host (icdab-20260922T084045, 1 warm + 3 meas each arm,
  inprocess, persistent-inode lock, per-arm driver env recorded):

| arm | encoder_ane median | total median | pins |
| --- | ---: | ---: | --- |
| OLD (e167 pin) | 3439.3 ms | 4596.1 ms | all green |
| NEW (system 7faf04c) | 3436.4 ms | 4572.9 ms | all green |

  **Parity; pins held in every run.** All `/var/tmp/encwall-decomp/*-j1.sh`
  pins switched to the system ICD (backups `*.bak-20260922-icd`);
  `parakeet-e2e-decomp.sh` included. Mesa-side follow-ups target
  `joshuaswarren/mesa-1` per the migration rule.

### Per-kernel feeder GPU profile (m1-host, system ICD)

proficd-20260922T084358, MLX_OMARCHY_GPU_PROFILE on the diag wheel
(`/var/tmp/wheelx`, `0.32.3.dev202609220722+diag.1b72eb4d3`), status match.
GPU busy 3683.9 ms / 6539.7 ms span = **56.3%**; inter-submission gaps
2762.3 ms dominate (island drains), intra-submission gaps only 93.5 ms.
Kernel identity via `profile_analyze.py --compute-h` against the WHEELX
header — the branch header is 7 entries shorter and mislabels everything
after index 45 (first analysis run labeled Custom as "MatmulVecMultiBF16";
use the wheelx header).

| kernel | n | total ms | share | mean |
| --- | ---: | ---: | ---: | ---: |
| Custom (coopmat linears + LN/GLU/mask customs) | 1092 | 2559.6 | 69.5% | 2.34 ms |
| MatmulF32 (48 pointwise convs via f32 conv2d route + 2) | 50 | 358.9 | 9.7% | 7.18 ms |
| CopyGeneralF16/F32 | 1160 | 289.0 | 7.8% | — |
| ElementwiseF32 | 330 | 147.0 | 4.0% | 0.45 ms |
| ReduceF32 (softmax rowsum + LN) | 264 | 105.5 | 2.9% | 0.40 ms |
| ConvF32 (24 depthwise + 3 subsampling) | 27 | 87.0 | 2.4% | 3.22 ms |
| CastF16F32/F32F16 | 616 | 68.0 | 1.8% | — |
| SelectF32 | 48 | 18.2 | 0.5% | 0.38 ms |
| ReduceF16 (softmax rowmax) | 24 | 15.5 | 0.4% | 0.64 ms |

GFLOPS: the 194 GPU linears are 1524.5 GMAC/pass (30.1 GMAC per layer ×24:
FFN 4×1024↔4096 = 1208 GMAC, q/k/v/o 4×1024² = 302 GMAC, subsampling+projector
14.6 GMAC; T=3000) and the 48 pointwise convs add 18.9 GMAC — **~3087 GFLOP/pass
of dense feeder math**. Attributing ~2400 ms of Custom+MatmulF32+ConvF32 time
to that math gives **~1.3 TFLOPS effective on M1's ~2 TF fp32 path (~65%)**.
The remaining GPU time is copies/casts/reductions around the linears.

### Coopmat pointwise-conv route: measured NO-GO (reverted)

- Root cause found: m1-host's encoder source declares the pointwise convs with
  `pad_type = "valid"`, not `"custom"` — bc6069049's gate never matched, so
  that route has NEVER executed in any prior run (its "identity-exact" claim
  was never exercised). Probe evidence probe-20260922T085504: 0 fastpath
  hits, attrs dump `pad_type valid pad [0, 0]` f16/f16 groups 1.
- With the gate opened (commit `2cba4fe36`) the route fires and the wall
  improves (convfix-20260922T085644: 3357 ms median vs 3439 baseline) BUT
  encoder_hidden = `5c5e519e` vs gold `38c73261` — max abs diff 0.24 over
  237k/240000 elements, mel/transcript still exact.
- f32 partials variant (commit `4f3f85dba`): same divergence
  (convfix-20260922T090011 + 090545, all runs `5c5e519e`). An earlier
  "gold-exact" probe reading was a script error — the probe's RUNNER sed
  never matched, so it reran the inert gate-closed file; corrected here.
  **The divergence is structural: coopmat MMA k-order vs mx.conv2d f32
  accumulation order, independent of partial precision.** Matching would
  require replicating conv2d's order scalar-sequential — not coopmat. NO-GO;
  both commits reverted (`2545f85e1`, `5be12c5f1`). The ~82 ms wall gain is
  real but fails the strict bit-exact pin.
- m1max-host runner restored to `2a886a09` immediately (byte-identical to the
  gold-verified osfix-20260922T083505 configuration — that run IS the pin
  evidence; a fresh re-run was blocked by a sibling's lock window).
- m1-host runner restored from `.bak-20260922-convfix` after the macOS bring-up;
  final-gold-20260922T091746: status **match**, mel/hidden/transcript ALL
  gold on the restored runner + system ICD (enc_ane 4305 ms — reboot-cold,
  warm parity is the icdab table above).

### Softmax full fusion: NO-GO by arithmetic

Already fused around the reductions (exp + div are single custom kernels;
only rowmax ReduceF16 and rowsum ReduceF32 remain). Their combined GPU cost
is ~21 ms/pass (15.5 + half of ReduceF32); a one-kernel fusion saves at most
~15 ms GPU busy (0.4%) on a pass that is 56% GPU-busy and marshal-drain
bound, and the rowsum must reproduce mx.sum's fp32 order exactly to keep
hidden `38c73261`. Not worth the exactness risk.

## Task 3 — mac-host capture bounce: no bounce in this window

ANECompilerService bounce (Joshua-gated `sudo kill`) did not occur during
this lane's window. Poller ownership: EncoderFusionBC (`bounce-poll-encbc`);
agreed handoff — they ping on bounce, this lane picks up the whole-encoder
single-program lowering measure if B->C/C->O stacks them. Nothing decoded;
lever remains capture-gated, unchanged.

## Artifacts

- m1-host: `/var/tmp/encwall-decomp/{icdab-20260922T084045,proficd-20260922T084358,convfix-20260922T085644,convfix-20260922T090011,convfix-20260922T090545,final-gold-20260922T091746,probe-20260922T085504}` , `gpu-prof.ndjson`, `icd-ab-j1.sh`, `convfix-battery.sh`, `probe-j1.sh`
- m1max-host: `/var/tmp/encwall-decomp/osfix-20260922T083505`, `restore-check-*` (incomplete, lock-blocked — superseded by byte-identity to osfix config)
- Branch: commits `44eecc5b9` (kept), `2cba4fe36`+`4f3f85dba` (reverted), reverts `2545f85e1`+`5be12c5f1`
