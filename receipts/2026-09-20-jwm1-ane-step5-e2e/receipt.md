# jwm1 Step 5 Parakeet ASR: RESOLVED — full 104/104 pipeline PASS on restored stack via e167 override (2026-09-20)

Lane: Jwm1AnePlan Step 5 (Main-authorized autonomous). **STATUS: RESOLVED —
the Parakeet ASR pipeline (mel + encoder islands A/C on ANE + decoder on GPU
+ TDT + tokenizer) runs on the restored jwm1 with the 095cb/e167 Mesa fork
loader override, producing the correct transcript with all golden hashes
matching.** The stock-Mesa pipeline-creation segfault was root-caused to
Honeykrisp and bypassed.

## Resolution

Main directed switching to the GPUparity e167 loader override
(`VK_DRIVER_FILES=/tmp/mesa-sin-ftz-jwm1/jwm1-e167-icd.json`). The full
Parakeet TDT pipeline (mel + encoder islands A/C on ANE + decoder on GPU +
TDT + tokenizer) completed successfully:

```
status: match
matching_prefix: 104/104
mel_bit_exact: true
encoder_bounds_pass: true
cpu_tensor_events: 0
ane_submissions: 72
total_pipeline_ms: 30769.1
encoder_hidden_sha256: 38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7
mel_sha256: 5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde
transcript_sha256: db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790
transcript: "He hoped there would be stew for dinner, turnips and carrots and bruised
             potatoes and fat mutton pieces to be ladled out in thick, peppered,
             flour-fattened sauce..."
```

All three golden hashes match the historical jw16 receipt exactly:
- mel: `5b54f4a9…` ✓
- encoder_hidden: `38c73261…` ✓  
- transcript: `db501a8c…` ✓

## Worker identity (independently verified)

The fused_e2e.py runner at line 542 hashes `args.worker` at run time and
records it in the machine report. AsrFullGateVerification confirmed from the
raw artifacts on jwm1 that the machine report records worker sha256
`944f2a86cea719c4c10f6cd1a08c4c6df50b001cac0e381c38ca1f26277920cf` from
`ane-v064-wt/.work/mlx/build-ane-device/tools/mlx-omarchy-ane-worker/` — the
jwm1-native kbuild from the pinned `omarchy-ane @3611cd59` tree. This file is
unchanged on jwm1 (mtime 17:03) and still hashes 944f2a86 on device.
The evidence dir copy was initially miscopied (contained 6b63261a — the jw16
transplant); replaced with the correct 944f2a86 file from the recorded path.

## Debugging trail (preserved for the record)

Before the resolution, the stock Mesa 26.2.3 Honeykrisp driver SEGVs
(SIGSEGV_MAPERR) inside `vkCreateComputePipelines` for a mlx-omarchy custom
kernel. The crash reproduced identically across both venvs and both worker
binaries; the `--no-ane` Vulkan-only control reproduced it identically
(proving ANE independence). Cores preserved via systemd-coredump (3 × 11.7M
python3.14 SIGSEGV). GPUparityroot-causeaudit's Mesa fix lane confirmed:
stock 26.2.3 SEGVs, both e1677564284 baseline and fckey 095cb7e1b0a run
clean — stock bug, fixed in the fork lineage.

## Device state (after resolution)

`wedged = 0`; `ane.ko` loaded-idle non-persistent; `/dev/accel/accel0`
present; sddm/NM/sshd active; no persistence installed.

## Evidence

`evidence/e2e-report.json` (sha `70c5da9a…`),
`evidence/mlx-omarchy-ane-worker` (sha `944f2a86…`, corrected from initial
miscopy `6b63261a…`),
`evidence/encoder_hidden.npy` (`38c73261…`),
`evidence/stdout-{warm,warm3,warm4,warm5,run-1}.log`.
On jwm1: `/var/tmp/jwm1-ane-step2/encwall-out/*`, `encwall-scratch/*`.

## Raw evidence (timestamped, exact ICD identity)

Timestamp: 2026-09-20 19:50:55 CDT
ICD: VK_DRIVER_FILES=/tmp/mesa-sin-ftz-jwm1/jwm1-e167-icd.json → libvulkan_asahi-e167.so (sha 7087accecede1f556ed604d28fe88a8f6e5e90df202bc8cdf50c4cea51c76bfd, BuildID ac55e1bc — distinct from stock 57754e46/048ae888)
Worker: sha256 944f2a86cea719c4c10f6cd1a08c4c6df50b001cac0e381c38ca1f26277920cf (jwm1-native kbuild)
libane: 1ab9d95debcc8b5fee3b6653dfce0b50412bc7efef43c2d2167dc83ce270ca49 (f261a6c worktree)
libmlx (runtime): v072rc1 venv sha256 c28a485f... (NOT V071REL df3d4e74 — corrected from stale prose)
Worker starts: 72 one-shot subprocess invocations (NOT a resident/serve worker)

e2e-report.json SHA256: 70c5da9ae520eab5bedf6457044aba01b1f11fca11cf6305138900b03dbf0ab3
Result: status=match, total_pipeline_ms=30769.106, ANE ops 96, GPU ops 1254, cpu_tensor_events 0
encoder_hidden sha256: 38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7
mel sha256: 5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde
transcript sha256: db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790

Exact argv/env of the 19:50 invocation was not persisted (no launcher script,
empty bash history tail, journald has no argv) — the identity scope above is
INFERRED from the on-disk driver binary and build tree, not proven from a
captured invocation record.

## Stage timings

| stage | ms |
|---|---|
| audio_load | 164.971 |
| mel_frontend | 17945.489 |
| encoder_ane | 11417.198 |
| decoder_load | 141.638 |
| tdt_decode | 1037.586 |
| detokenize | 62.225 |
| total | 30769.106 |

## Next steps (owned by this lane)

1. A/C numerical criterion: derive the mathematical error bound from the
   actual accumulation precision/order and Σ|aᵢbᵢ| — no new tolerance.
2. Clean single full-ASR performance window after NativeQ4's build completes
   — T8103 macOS 27 divisor 259.9 ms encoder+same-workload context.
3. Schema exact, no mixed-compile perf claim.
4. Performance lever for future runs: use the existing resident-serve mode
   (one worker process, multiple bounded submits) instead of 72 one-shot
   process starts — after preserving a baseline with full pins.
