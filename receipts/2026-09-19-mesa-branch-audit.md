# Mesa branch audit — joshuaswarren/mesa → receipts/outcome map

Date: 2026-09-19. Author: MesaBranchAudit (agent).
Method: bare clone of `https://github.com/joshuaswarren/mesa.git`
(`~/src/mesa-audit.git`, fetched 2026-09-19); `git merge-base --is-ancestor`
against `honeykrisp-omarchy` (`d8d4e1c500b`, tip 2026-09-16) for merge state;
receipt search across this repo's `receipts/`, the mesa repo's own
`receipts/` (landed on `honeykrisp-omarchy`), and commit-message verdicts.

## Verdict table (all 21 branches)

| Branch | Tip | Status | Receipt / outcome |
|---|---|---|---|
| `honeykrisp-omarchy` | d8d4e1c500b | integration trunk | Integration receipt `mesa:receipts/2026-09-08-honeykrisp-omarchy-integration.json`; carries merges of byte-extract, precise-math, coopmat-shapes, queue-lifetime, coopmat, cdm-barrier-trim. **Reference branch for jw16/jwm1 installs (`hk5deac1c-2`).** |
| `hk/byte-extract` | 036472a592f | **MERGED** | `mesa:receipts/2026-09-08-byte-extract.json` (+ repro dir). ubfe shift-then-mask miscompile fix; verified jwm1 G13G. |
| `hk/precise-math` | e93242f3a61 | **MERGED** | `mesa:receipts/2026-09-08-precise-math.json`. Correctly-rounded fdiv/frcp, faithful log, Cody-Waite/Payne-Hanek sin/cos. |
| `hk/coopmat-shapes` | 90f925ad770 | **MERGED** | `mesa:receipts/2026-09-08-coopmat-shapes.json`. 16x16x16 + fp16 coopmat shapes on G13 simd_matrix. |
| `hk/queue-lifetime` | daece8ba84e | **MERGED** (diagnostics-only) | `mesa:receipts/2026-09-08-queue-lifetime.json`. Queue-wedge + SIGBUS root-caused to mlx-omarchy, no driver defect. |
| `honeykrisp-coopmat` | 5bb2b28c95c | **MERGED** | Base for all hk/* work (0x6f bit6 simd_matrix exact mask); superseded by trunk. |
| `honeykrisp-miscompile-repros` | 7302d43288b | **MERGED** | Repro-harness hygiene commit ("receipt observations vs hardware verdicts"). |
| `main` | 4a34ded300c | **MERGED** | Fork's main is an ancestor of trunk (magma-gpu-rs buffer bump); stale pointer, no unique work. |
| `hk/cdm-barrier-trim` | 5deac1c8068 | **MERGED** (2026-09-16) | G13X restored to kitchen-sink CDM_BARRIER after jw16 ctx-regression. Reverts the trim; see termA receipt. |
| `hk/cdm-barrier-floor` | 66b5631a950 | Unmerged — **superseded** | `mlx-omarchy:receipts/2026-09-10-dispatch-floor` (per-launch barrier measured no-op; residual is launch latency). Superseded by `hk/cdm-barrier-trim`/`hk/app-barrier` which build on it. Instrumentation only, default emission byte-identical. |
| `hk/app-barrier` | 69c416a6cff | Unmerged — **active instrumentation** | Builds on barrier-floor; adds `HK_CDMBARBITS` runtime bit mask + `HK_APPBAR=1` app-level barrier mode. Used by termA appbar-ab.json (termA receipt `2026-09-16-termA/`). No verdict against it; land-with-a-need candidate. |
| `hk/cdm-g13x-178` | 242e591a853 | Unmerged — **REJECTED family (bit-trim)** | Designed set {4,5,6,8} + USC inval. Probe for the termA decision battery. |
| `hk/cdm-g13x-1f0` | 5cd0e72f32f | Unmerged — **REJECTED family (bit-trim)** | G13G trim set {4,5,6,7,8} on G13X. |
| `hk/cdm-g13x-578` | 49c21f17b18 | Unmerged — **REJECTED family (bit-trim)** | Designed set with unk_7 for unk_6. |
| `hk/cdm-g13x-fffb` | 669557609f6 | Unmerged — **REJECTED family (bit-trim)** | Sink minus unk_2 (pathological: −24% short, −40% ctx). |
| — bit-trim family verdict | | **NO-LAND** | `receipts/2026-09-16-termA/2026-09-16-termA-dispatch-attribution.md` §Addendum 4: known-good sets are exactly the full sink and the designed set; every sampled subset is correctness-broken or hits a −18…−40% cliff. jw16 keeps full sink. |
| `hk/cdm-chain-batch` | ae819e10cb6 | Unmerged — **NO-LAND (screened 2026-09-19)** | `receipts/2026-09-19-q4-chainbatch-jw16.md`: emission reduction works (16 vs ~2500 barriers/2-token run) but generated-ID digests corrupt nondeterministically on jw16. Barrier is load-bearing memory ordering. Closes the amortize-the-barrier lever family with direct evidence. |
| `hk/fma-ceiling-unroll` | c4251875345 | Unmerged — **REJECTED in commit** | `REJECTED: measured regression` — qmm_coopmat 1034→817 GFLOP/s (−21%), digest identical. Do not PR. |
| `termb/device-load-coh7` | f6286e41e63 | Unmerged — **REJECTED** | `receipts/2026-09-16-termB-kv-mechanism.md` §(c): coherency 4→7 on device loads is value-clean but −8% decode throughput (190.18 vs 175.03 tok/s). |
| `hk/trig-invariance` | d1fed280ec2 | Unmerged — **active experiment, no verdict receipt** | Offline Honeykrisp compile harness + evidence: trig windows compile with identical opcode sequences; deltas are plumbing, not fp selection. Suspicion moved off approximation-bit selection. No receipt file in either repo; evidence lives in `~/trigwork` (mesa-xbuild) per commit message. Pending conclusion. |
| `hk/agx-wait-batching` | 14eb6778a69 | Unmerged — **WIP, no receipt** | 11 commits: wait-insertion rewrite + gtest capacity/hazard suite, includes `WIP debug`/`debug2` commits and temporary instrumentation (guard commit for bare test contexts). Never screened; needs debug-commit squash + receipt before any PR. |
| `upstream/correctness` | aa4fee0d5f7 | Unmerged — **active: upstream submission prep** | The landed correctness fixes (ubfe, precise fp, + new flush-to-zero handling in div/log/sin, `nir: pass FP_MATH_CTRL to the builder generator`) re-sequenced for upstream. 6 commits ahead of trunk, includes work not yet in trunk (7c6aa47ce96, aa4fee0d5f7). PR candidate once upstream-style-verified. |

## Topic map (requested keywords)

- **Per-dispatch submit cost** → ANE-side, `receipts/2026-09-17-ane-submit-cost-isolation.md`; no mesa branch.
- **AGX trig lowering invariance** → `hk/trig-invariance` (harness; verdict pending).
- **Prefill throughput** → ANE-side receipts (`2026-09-17-qmm-prefill-ceiling`, `2026-09-16-prefill-driver-inline`); no dedicated mesa branch.
- **Chain-batch** → `hk/cdm-chain-batch` — NO-LAND 2026-09-19.
- **Bit-trim** → `hk/cdm-g13x-{178,1f0,578,fffb}` + `hk/cdm-barrier-trim` (the merge that reverted it) — family NO-LAND per termA addendum 4.

## Actions implied

1. Safe to delete once archived (fully merged, receipts landed): `hk/byte-extract`, `hk/precise-math`, `hk/coopmat-shapes`, `hk/queue-lifetime`, `honeykrisp-coopmat`, `honeykrisp-miscompile-repros`, `main`, `hk/cdm-barrier-floor` (superseded by merged trim).
2. Rejected — keep only as evidence, never PR: `hk/cdm-g13x-178`, `hk/cdm-g13x-1f0`, `hk/cdm-g13x-578`, `hk/cdm-g13x-fffb`, `hk/fma-ceiling-unroll`, `termb/device-load-coh7`, `hk/cdm-chain-batch`.
3. Live: `hk/app-barrier` (instrumentation, verdict-neutral), `hk/trig-invariance` (harness, pending), `hk/agx-wait-batching` (WIP, needs cleanup + screening), `upstream/correctness` (PR prep).
