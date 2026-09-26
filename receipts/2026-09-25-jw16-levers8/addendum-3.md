# jw16-levers8 addendum 3 — functional Parakeet/ANE parity lane status (2026-09-26)

Owner: Jw16Levers8. Per Main: recovered existing receipts/harness (no
recreation), ran the current installed audio-to-transcript pipeline with
live checks, identified exact unpassed acceptance cases, Qwen ANE
blocker, and the next measured bottleneck. Host jw16, research-exclusive
(llm-inference inactive + disabled per owner override).

## 1. Recovered corpus + harness (not recreated)

- Corpus gate receipt (jwm1, Jwm1Parity10):
  `receipts/2026-09-25-jwm1-parity10-parakeet-tdt-mel/` — fixture.flac +
  0.3s/1s/5s/10s variants + 1089-134686-0000.wav, **6/6 PASS rc=0**
  (tokens/frames/durations true, hidden/cell bitwise; emission counts
  104/0/0/28/101/104 exercise skip, blank-hop, partial and full slot
  schedules). The 6 variant audio files exist only on jwm1; jw16 never
  had them, and re-deriving them here would recreate the harness —
  not done.
- Live checker recovered: `scripts-local/tdt-chain/validate_chain.py`
  (mlx-omarchy) — decodes the saved golden encoder tensor twice (landed
  host path vs one-dispatch chain) and compares token_ids,
  frame_indices, durations, hidden, cell bit-exact.
- Installed-pipeline receipts (this lane): tc pin-1/2/3 + resident
  r1-r4 + warm0 + corrupt + coldcold — all `status: match`, 104/104,
  transcript db501a8c (see receipt.md/addendum tables).

## 2. Live run on the CURRENT installed stack (ccfb97fb1, 2026-09-26)

validate_chain (venv python, GPU lock held, golden encoder tensor
(1,375,640), valid_frames=375):

```
host: 104 emissions (fused run_step callbacks)
check token_ids: PASS
check frame_indices: PASS
check durations: PASS
check hidden: PASS
check cell: PASS
timing best-of-3: host 207.4 ms  chain 118.9 ms (1.74x)
```

Accelerator placement (transcribe-report, pin-1): encoder = ANE worker
process (`parakeet-encoder-whole` bundle, exec_ms **440.35**, zero GPU
submits from the app process); mel_frontend = GPU (1 submit, 6 compute
dispatches); tdt_decode = GPU (4 submissions, 1163 compute dispatches),
decode_control = host loop by default, one-dispatch GPU loop available
via `MLX_OMARCHY_TDT_HOST=0`.

GPU-loop end-to-end probe: total 1126.89 ms, tdt_decode 144.6 ms
(-30 ms vs host loop 174.6) — single paired sample; the saving is
inside encoder boot-variance (±20 ms), so an interleaved A/B is needed
before counting it. All pins green in that mode too.

## 3. Exact acceptance status

| acceptance case | status |
|---|---|
| golden correctness (mel/hidden/transcript/tokens/durations/frames, 104 emissions) | PASS (every run this lane, both wheels) |
| corpus gate 6/6 | PASS on jwm1 (recovered receipt); variants absent on jw16 — not re-run (no harness recreation) |
| chained-TDT bit-exactness + timing | PASS (this addendum §2) |
| same-boundary latency ≤ 1.00x vs macOS | **UNPASSED**: inference-only Linux 579.4 ms (mel 7.8 + enc-exec 440.8 + tdt 130.8) vs macOS 264 → 2.19x; models-ready 634.7 vs 315 → 2.01x |
| warm mel vs macOS 15 ms | PASS at steady state (7.7-7.8 ms); fresh-process 29-31 ms post-translator-cache |
| Qwen ANE decode case | separate lane — see §4 |

## 4. Qwen ANE (separate required case) — current concrete blocker

From `receipts/2026-09-25-qwen-ane-decoder-fix/` (macstudio-rooted
2026-09-25): the ANE decoder compile fails at
`ANECompilerForANE … err=11` because the fused `gated_deltanet` decode
layer exceeds ANECCompile's whole-program ceiling at real Qwen dims —
bisected to the fused outer-product state update (`S1 + k^T @ delta`);
slice/reshape views into batched matmuls fail while dedicated input
ports compile. Independent second blocker in the same path: the
contract GGUF crashes `qwen35.load_gguf` without `n_layers` (tied
embeddings `output.weight` KeyError; `block_count`=25 counts the
trailing MTP block vs the 24-layer decoder the frozen reference used).
The laptops never reached either — they die earlier (no `gguf` module /
ANEForge on-device). Staged fix assets exist per the receipt
(split-series + harness gguf fix, commit e19e9329 lineage); laptop-side
enablement is its own bounded lane.

## 5. Next measured bottleneck

1. **ANE encoder exec 440.8 ms** (vs macOS 146.5): the dominant same-
   boundary gap. Linux-side levers exhausted (CPU boost falsified on
   T6001, poll cadence falsified, dvfs_ane writes falsified — no-op
   with PMP fw not running). The remaining measured path was the PMP
   route: now parked at Main's metadata-only stop (bootargs prepared,
   firmware head resident, identity UNVERIFIED; TUNS convention
   unresolved offline).
2. **TDT 130.8-144.6 ms**: dispatch-latency-bound (parity10 root
   cause: 192 slots × 6 dispatches × ~120 µs submit-sync; ~15 ms real
   exec). Chain mode measures 118.9 decode-only. The program lever is
   queue-depth/batched submission in the runtime (stack-level, shared
   by every custom-kernel pipeline) — a Mesa/runtime lane.
3. **decoder_load 42-45 ms**: per-call in the current consumer; the
   resident path amortizes it.

## 6. Host state

jw16: ccfb97fb1 wheel installed and green; llm-inference inactive +
disabled (research-exclusive, owner override); GPU lock free; ANE
untouched at 5ecff86; no PMP reads beyond the authorized Phase-0 set;
probe modules unloaded.
