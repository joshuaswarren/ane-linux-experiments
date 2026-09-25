# T8103 macOS ANE encoder divisor — receipt (2026-09-22)

Owner: T8103DivisorMacOS (sub). m1-host (MacBookPro17,1, Apple M1 / T8103) stayed
in macOS the whole session — no reboot, no startup-disk change, no ESP write,
camera agent (`/tmp/camwatch /tmp/m1-host-sees.jpg`) left running and verified
alive after the runs (jpg mtime current at 15:10 CDT).

## Headline

| arm | median (ms) | min / max | mean |
|---|---:|---|---:|
| CoreML computeUnits **cpuAndNeuralEngine** (".ane") | **122.12** | 118.23 / 123.71 | 121.04 |
| CoreML computeUnits **all** (".all") | **119.56** | 117.46 / 123.01 | 120.38 |

15 timed reps each after 3 warmups, synchronous `MLModel.prediction`,
whole Parakeet encoder in one prediction call.

**Divisor ratio vs our Linux T8103 number:** our whole-encoder hwx one-submit
on m1-host Linux measured **141.4 ms** (receipts/2026-09-22-encoder-direct-exec,
p50 of 20 reps, bit-exact hidden). macOS ANE divisor **122.1 ms** →

    141.4 / 122.1 = 1.16

We are at **1.16x the macOS ANE wall** on T8103 — close to parity, not past
it. (Using the .all arm, 1.18.) Compare m1max-host at 2.8x and the old
island-chain T8103 number at 24-31x. The island-chain era "113.0-115.8 ms
native figure" is consistent with this measurement; the "259.9 ms macOS 27
CoreML" figure quoted in receipts/2026-09-21-encoder-wall-decomposition and
.local/encwall-v071/receipt-draft.md is **not** reproduced — see caveats.

## Method

1. The model cache survived the macOS 27 upgrade:
   parakeet cache (m1-host `~/.cache/mlx-omarchy/parakeet-reference/)mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c.../encoder.mlpackage`,
   `shasum -c .sha256sums` → all OK (encoder model.mlmodel
   `2e4e6b54...`, weight.bin `23867a83...`). This is the same HF revision
   `b650695c` our Linux pipeline converts.
2. Swift harness (`encoder_bench.swift`, sha256 in SHA256SUMS) on m1-host:
   `MLModel.compileModel(at:)` on the .mlpackage, load with
   `MLComputeUnits.cpuAndNeuralEngine` / `.all`, feed the real parity inputs
   (features fp32 [1,3000,128] from feat-f16.npy, mask int32 [1,3000] from
   mask-f16.npy — the same tensors used for the Linux gold), synchronous
   prediction, 3 warmup + 15 timed reps, last hidden dumped to disk.
3. Correctness gate: dumped `encoder_hidden` fp32→fp16 is **bit-exact
   (0 mismatches of 240,000 words, max delta 0)** vs
   `gold-f16.npy` (sha256 `fca96f13...`) in BOTH arms; `encoder_mask`
   sum = 375 (correct). The timed thing is the same encoder producing the
   same numbers.

## Environment block (m1-host, measured 14:59-15:10 CDT 2026-09-22)

- macOS 27.0 (26A428), uptime 2h08 at start
- Apple M1 (T8103), MacBookPro17,1
- CoreML framework CFBundleVersion **3600.25.2**
- Espresso (private) **3600.56.2**; AppleNeuralEngine bundle version 1
- Swift 5.10 (swiftlang-5.10.0.13), CommandLineTools, arm64-apple-darwin27.0.0
- `pmset -g therm`: no thermal warning level, no performance warning level,
  no CPU power status recorded
- load average 3.5 → 5.1 (camera agent + our compile; box otherwise idle)
- caffeinate: **not present** in `ps` at 15:10 (observed absent; not killed
  by this session — nothing on m1-host was signalled). Flagging because the
  lane context expected one holding the display awake.

## Comparability caveats — stated plainly

1. **Weights: 4-bit palettized in CoreML vs dense fp16 hwx on Linux.** The
   CoreML package ships `constexpr_lut_to_dense` weights; ANE executes LUTs
   natively on H13. Output is bit-exact vs the dense-fp16 Linux gold, so the
   arithmetic agrees, but the weight-traffic profile differs (LUT+indices vs
   dense fp16 fetch). The macOS number is arguably a *best case* for Apple.
2. **Boundary casts.** CoreML casts fp32 features→fp16 and fp16→fp32
   encoder_hidden at the graph edge (the Linux hwx takes fp16 in/out). This
   adds host-side cast work to the macOS number — it makes the macOS divisor
   slightly *worse*, i.e. our 1.16x ratio is conservative in Apple's favor.
3. **One prediction call vs one submit.** Both are the whole encoder in a
   single device submission; CoreML's prediction includes framework dispatch
   overhead, mirroring how the Linux number includes ane.ko submit overhead.
4. **Compiler provenance.** The mlmodelc was compiled on-device by macOS 27's
   ANECompilerService/Espresso stack — Apple's own path, as required.
5. **The 259.9 ms figure is not reproduced.** receipts/2026-09-21-encoder-
   wall-decomposition cites "259.9 (macOS 27 same-encoder, CoreML context)"
   but no staging receipt, harness, or rep data for that number survives
   (m1-host /tmp was wiped by the OS upgrade; the staging manifest under
   receipt 69975da is gone). This receipt's 122.1 ms is fully receipted,
   bit-exact, and consistent with the independent 113.0-115.8 ms native
   figure. Treat 259.9 as superseded/unexplained until someone produces its
   harness. The m1-host 20.2x ratio in that receipt becomes **141.4/122.1 ≈
   1.16** on this evidence.

## Artifacts

- receipts/2026-09-22-t8103-divisor/encoder_bench.swift (+ SHA256SUMS)
- m1-host:/tmp/t8103-div/{encoder.mlpackage, encoder_bench, feat_f32.bin,
  mask_i32.bin, gold_f16.bin, out_ane.bin, out_all.bin} (raw timing JSON and
  per-rep arrays in the transcript; both output dumps verified vs gold)
- Raw bench lines:
  - ane: `{"units":"ane","reps":15,"median_ms":122.12,"min_ms":118.23,"max_ms":123.71,"mean_ms":121.04}` times `[118.23,118.57,118.83,118.85,119.16,119.32,119.98,122.12,122.13,122.42,122.60,122.92,123.12,123.65,123.71]`
  - all: `{"units":"all","reps":15,"median_ms":119.56,"min_ms":117.46,"max_ms":123.01,"mean_ms":120.38}` times `[117.46,118.38,118.42,118.90,119.17,119.38,119.52,119.56,121.17,121.59,121.63,122.33,122.49,122.69,123.01]`
