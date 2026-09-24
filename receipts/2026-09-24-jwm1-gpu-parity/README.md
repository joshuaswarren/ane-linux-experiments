# 2026-09-24 — jwm1 (T8103 M1, Linux/honeykrisp) GPU decode+prefill parity lane

Branch: `agent/jwm1-gpu-parity` (off `agent/jwm1-macos-baselines` cddf0b7).
Host: `jwm1-linux` (Apple MacBook Pro 13" M1, T8103), Omarchy, kernel
`7.1.13-3-2-ARCH` (asahi3-2), ane.ko version `9ad8474`
(`F88565981CD8CAE87A37833`), ANE on DRM minor 0 (`/dev/dri/renderD128`).
ICD `/usr/share/vulkan/icd.d/asahi_icd.json` →
`/usr/local/lib/libvulkan_asahi.so.7faf04c` (honeykrisp fork,
`7faf04c065c` from `joshuaswarren/mesa-1` `honeykrisp-omarchy`,
api 1.4.359).

## Status (this commit): PHASE 0 PREP COMPLETE; EXECUTION BLOCKED on M2FwStart-2

Lane is fully staged (14 tools, branch, worktrees, install script,
run_lane.sh end-to-end script). No GPU/ANE/Vulkan measurements have
been executed yet — they are blocked behind M2FwStart-2's window
announcement per Main's hard rule (jwm1 is the M2 hv proxy host;
reboot/USB/ACM/hang-prone action must be coordinated with
M2FwStart-2). M2 is currently dark and needs a physical power cycle,
so the trace window has not opened. CPU-only prep is complete and
preserved in this commit.

## Goal
Bring M1 Linux GPU decode+prefill to >=1.00x the M1 macOS parity bar
(decode >=47.05 tok/s, pure prefill >=343.73 tok/s, TTFT >=99.12 tok/s,
e2e <=0.79 s for 32 new tokens), with bit-exact exactness.

## Starting state (denominators — receipts `agent/jwm1-macos-baselines` cddf0b7)

| metric | Linux (this host) | macOS M1 parity target | ratio | verdict |
| --- | ---: | ---: | ---: | --- |
| decode tok/s | 17.46 | 47.05 | 0.37x | FAIL |
| pure prefill tok/s (512) | 28.68 | 343.73 | 0.083x | FAIL |
| ttft tok/s | 20.19 | 99.12 | 0.20x | FAIL |
| e2e per 32-tok prompt | 2.4195 s | 0.7898 s | 0.33x | FAIL |

## Mesa defect (preliminary finding for §6)

The stock-mesa `vulkan-asahi 1:26.2.3-1` from the Arch package fails
`vkCreateInstance` with VK_ERROR_UNKNOWN. Traced through
`/var/tmp/mesa-e167-src/src/asahi/vulkan/hk_instance.c`: `hk_CreateInstance`
returns `VK_ERROR_INITIALIZATION_FAILED` at line 130 (or 137) when
`build_id_find_nhdr_for_addr(hk_CreateInstance)` cannot locate the
build-id note in the loaded `.so`. The Vulkan loader renders
`VK_ERROR_INITIALIZATION_FAILED` as `VK_ERROR_UNKNOWN`. Root cause:
**packaging** — the Arch `vulkan-asahi` build was linked without
sufficient build-id metadata (the honeykrisp fork ICD at
`/usr/local/lib/libvulkan_asahi.so.7faf04c` does NOT exhibit this
because the fork uses a longer hash). The defect is upstream
build-config, not `joshuaswarren/mesa-1` source. **The defect does
not block the parity lane** — the system ICD points to the honeykrisp
fork, and every existing mlx-omarchy contract runs cleanly on it.
Recommended: hand off to the homelab-infra lane with the recipe
(rebuild Arch `vulkan-asahi` with longer build-id metadata). Mesa
work goes in `joshuaswarren/mesa-1` only.

## Sections (filled in during measurement windows)
- §1 ANE control (re-confirm) — pending
- §2 Profile: one decode token + one prefill pass on the installed path — pending
- §3 Per-family ranked delta vs macOS (eb1e711) — pending
- §4 SDPA hd256 port: gate + install — staged, pending execution
- §5 Next gap attack (per-launch host cost swarm) — recommendation pending profile
- §6 Mesa defect investigation — see above (does not block)
- §7 Final contract vs macOS — pending

## Acceptance
Receipt with the profile, each change's gate + paired-CI result,
the installed state, and final decode/prefill/TTFT/e2e vs macOS with
PASS/FAIL per metric.

## Constraints
- **jwm1 M2 proxy hard rule (Main, 2026-09-24 ~12:09 CDT):** coordinate
  with M2FwStart-2 BEFORE any jwm1 reboot/USB/ACM/hang-prone action.
  The 12:09 reboot (QwenAneRef, with my prior approval, to clear a
  5h-wedged ANE driver) killed the M2 trace. No further jwm1 reboots
  for this lane. As of this commit M2FwStart-2 confirms they have
  not yet launched a new trace (the M2 is dark, needs physical power
  cycle); I am holding all GPU/ANE/Vulkan work until they announce
  "window start". When they announce, I will execute `tools/run_lane.sh`
  end-to-end under flock; on their "window end" I will stop cleanly
  regardless of phase.
- Owned host: jwm1 only. No sibling touch.
- Work in my own worktree/branch: mlx-omarchy at
  `/var/tmp/jwm1-gpu-parity-wt` on jwm1 (branch
  `agent/jwm1-gpu-parity`, head `f9d7bb21` = rel/v0.7.3 +
  cherry-picked 33d1915b7 + 16df8b6b5 from `agent/sdpa-decode-hd256`,
  port byte-equivalent to the proven M1 Max branch in compute.h,
  shaders/sdpa_decode_native.comp, CMakeLists.txt). Receipt worktree
  on this repo (ane-linux-experiments) at
  `/var/tmp/jwm1-gpu-parity-wt-ane` (branch
  `agent/jwm1-gpu-parity`). Mesa work goes in `joshuaswarren/mesa-1`.
- Build in `/dev/shm` or `/var/tmp`.
- Frozen corpus: `benchmarks/qwen38-2b-contract.json` (sha256 prefix
  `9299a3b2…`). Model snapshot `0867d98b…`.
- Exactness gate: gates x3 at 0 flips, 10-pass digest identity, 10
  paired reps with CI entirely positive. Install only significant
  wins.

## Staged tooling (this commit)
| tool | role |
| --- | --- |
| `tools/run_lane.sh` | Master end-to-end script. Execute once after M2FwStart-2 announces window start. |
| `tools/pre_flight.sh` | Read-only state check (ICD sha, GPU lock, ane.ko, libmlx shas, worktrees). |
| `tools/prof_decode.py` | Mirrors contract bench for one decode + one prefill with host CLOCK_MONOTONIC markers. |
| `tools/profile_analyze.py` | Ingests MLX_OMARCHY_GPU_PROFILE JSONL + markers, emits per-kernel µs/tok, dispatches/tok, GPU busy, host record/submit. |
| `tools/run_profile_window.sh` | Builds diag wheel at f9d7bb21, runs prof_decode under flock. |
| `tools/run_sdpa_hd256_window.sh` | Builds production wheel at f9d7bb21, runs 10 paired reps + 10-pass anchors + microbench. |
| `tools/run_contract_window.sh` | Runs the frozen contract under flock. |
| `tools/run_family_bench.sh` | Per-op-family microbench via `/var/tmp/vprof/family_bench.py`. |
| `tools/family_delta.py` | Renders ranked per-family delta vs macOS reference (eb1e711). |
| `tools/logits_gate.py` | Token-ID flip gate (target: 0 flips across 32 tokens x 100 prompts). |
| `tools/paired_decode.py` | 95% t-CI paired delta on decode tok/s across 10 reps. |
| `tools/microbench_sdpa_hd256.py` | Per-shape bitwise + perf microbench for the SDPA hd256 arm (K_VALUES = [12,13,24,44,128,300,513,2048]). |
| `tools/sdpa_token_counts.py` | Counts scaled_dot_product_attention dispatches per token in real generate_step. |
| `tools/install_sdpa_wheel.sh` | pip install with btrfs-ENOSPC fallback (manual libmlx.so copy), per the proven t6001 sdpa receipt §4. |
