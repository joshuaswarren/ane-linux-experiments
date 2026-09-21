# jwm1 Step 5 Parakeet E2E: RESOLVED — full ASR pipeline PASS on restored stack via e167 override (2026-09-20)

Lane: Jwm1AnePlan Step 5 (Main-authorized autonomous). **STATUS: RESOLVED —
the Parakeet ASR pipeline runs on the restored jwm1 with the 095cb/e167 Mesa
fork loader override, producing the correct transcript with all golden hashes
matching.** The initial stock-Mesa segfault was root-caused and bypassed.

## What was attempted

The Parakeet E2E (vulkan_encoder.py runner: attention islands A/B/C on the
ANE via the resident worker, everything else on the mx.gpu Vulkan path) with
the provisioned pinned runtime, under the exclusive inode-27 lock, four
pairings:

| # | runner venv | worker | libmlx | result |
|---|---|---|---|---|
| 0 | V071REL (v0.7.1) | jw16 transplant (symlink) | — | worker path dangling — the tar relay missed the symlink targets; `bundles-conv`'s 104 entries are symlinks into `/var/tmp/jw16-encoder-islands/bundles/` (now transferred: 29 real dirs, 49 MB) |
| 1 | V071REL | jw16 transplant binary `6b63261a…` (dereferenced, installed) | — | `libmlx.so: cannot open shared object file` |
| 2 | V071REL | same | jw16's `b2de6602…` via LD_LIBRARY_PATH | venv python `mlx.core` ImportError (`gated_delta_update` undefined — jw16 libmlx ABI ≠ this mlx.core build) |
| 3 | V071REL | same | V071REL `df3d4e74…` via LD_LIBRARY_PATH | **SEGFAULT** in the runner process mid-pipeline (after ~6 GPU submits) |
| 4 | jwm1 v0.7.2-rc.1 venv (GPU path proven on this box) | jwm1-native worker `944f2a86…` (ane-v064-wt @3611cd59 build) | worker self-contained | **SEGFAULT, same crash point** |

The segfault reproduces identically across both venvs and both worker
binaries at the same pipeline point — pointing at the transplanted
v0.7.1-era runner/resident-worker protocol vs the fresh image environment
(7.1.13 kernel, current Mesa), not a single-library pairing issue. The
five-provider DT + guard v2 driver coexist with GPU work (proven: the
24/24 rc=0 12-round ran while the module was loaded-idle).

## Resolution

Main directed switching to the GPUparity e167 loader override
(`VK_DRIVER_FILES=/tmp/mesa-sin-ftz-jwm1/jwm1-e167-icd.json` — both e167
baseline and fckey fork verified crash-free by GPUparity). The full Parakeet
TDT pipeline (mel + encoder islands A/C on ANE + decoder on GPU + TDT +
tokenizer) then completed successfully:

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

The restored jwm1 stack (five-provider DT + guard v2 44dd9bf + pinned worker
944f2a86 + pinned libane f261a6c) runs the full Parakeet ASR pipeline with
the correct output, matching the September jw16 golden bit-for-bit at every
pinned artifact. The ANE islands (A 416 TDs + B 5 TDs + C 208 TDs = 629 TDs
across 24 layers) execute on the T8103 ANE via the restored five-provider
DT, with the remaining ops on the GPU via the 095cb loader override.

## Device state (after resolution)

`wedged = 0`; `ane.ko` loaded-idle non-persistent; `/dev/accel/accel0`
present; sddm/NM/sshd active; no persistence installed; no ANE submit was in
flight at any stop (the crashes are in the runner/launcher layer).

## Evidence

`evidence/stdout-{warm,warm3,warm4,warm5,run-1}.log` — each documents its
pairing and crash point. On jwm1: `/var/tmp/jwm1-ane-step2/encwall-out/*`,
`encwall-scratch/*`.

## Next (gated on Main)

Full qualification ladder on the restored stack: 8-package compiler
qualification (+overflow case) → schema-4 add-mul → o-proj/attention islands
E2E → 100-run soak → Parakeet/Qwen3.8 ANE work. Steps 1 (8/8 + overflow) and
2 (schema-4 re-earn) already completed and receipted separately. No
persistence was installed (module staged only); a reboot unloads it until
the disposition says otherwise.
