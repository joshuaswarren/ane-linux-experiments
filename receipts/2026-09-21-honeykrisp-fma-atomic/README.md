# 2026-09-21 — Honeykrisp FMA contraction + 16-bit atomicOr lane loss

Agent: HoneykrispFmaAtomic. Target: joshuaswarren/mesa-1 `honeykrisp-omarchy`
tip 7faf04c065c (= divverdict-tip on gpu-host-A src/mesa-1 (host A)). Hosts: gpu-host-A
(M1 Max G13C), gpu-host-B (M1 G13G). Both reported driver bugs come back
NOT REPRODUCIBLE at the driver level; **no Mesa commits were needed** and
none were made. Evidence per claim below.

## Harness

- `compute_runner` (from receipts/2026-09-21-mesa-divverdict-gpu-host-A lineage,
  deployed /var/tmp/mesa-divverdict-gpu-host-A/ on gpu-host-A and /var/tmp/mesa-e167-host-B/
  on gpu-host-B). NOTE: runner maps **binding 0 = input buffer, binding 1 = output
  buffer**; the shaders here follow that. (An earlier all-zero false reading
  on both hosts came from a shader/runner binding mismatch — fixed before any
  conclusion was drawn.)
- Drivers: tip.so sha256-16 `09e3527dee4a365e` on BOTH hosts (same binary);
  upstream-base arm built from 728fe700bc0 (origin/upstream/correctness head):
  upbase.so `dd3edee030f11676` on gpu-host-A.
- All GPU runs under `flock /tmp/m1-gpu.lock`.

## Bug A — "FMA contraction ignores NoContraction/precise": NOT A BUG

Reproducer: `fma_contract.comp` + `gen_input.py` + `check_fma.py`.
Inputs a=1+2^-23, b=1-2^-23, c=-1 (exact product 1-2^-46):

- separate rounding → +0.0 (0x00000000)
- contracted (true fma) → −2^-46 (0xa8800000)

Two independent chains (duplicated input regions so CSE cannot merge them):
`precise float p` and unconstrained `q`.

Results (65536 elements, both hosts, tip AND upstream base):

| arm | precise p | unconstrained q |
|---|---|---|
| gpu-host-A tip | +0.0 (all) | 0xa8800000 (all) |
| gpu-host-B tip | +0.0 (all) | 0xa8800000 (all) |
| gpu-host-A upbase | +0.0 (all) | 0xa8800000 (all) |

Disassembly (`dump-fma-tip.txt`, identical for tip and upbase): the precise
chain stays `fmul` + `fadd // exact` in NIR and `fmul`+`fadd` in AGX; the
unconstrained chain becomes `ffma` and produces the correctly-rounded −2^-46
on device (AGX fp32 ffma is a TRUE fused fma).

Mechanism: NoContraction is plumbed SPIR-V → `nir_fp_no_contract`/`nir_fp_exact`
(vtn_alu.c `vtn_handle_fp_fast_math`) and the only fmul+fadd→ffma fusion
(`nir_opt_algebraic` late_optimizations, `fadd@32(contract)` pattern gated on
`float_mul_add32 = has_ffma|fuse`) refuses instructions carrying
`nir_fp_no_contract` (`nir_search.c` `fp_math_ctrl_exclude` match check).
The fork's FP_MATH_CTRL framework is doing its job.

Conclusion: GdnPrefillExact's "explicit-fma and separate-rounding wheels are
bit-identical on device" is explained WITHOUT a driver bug — if both builds
end up fused (or both unfused) they are trivially identical. The 1-ulp
per-token residue vs the ops path is an arithmetic decomposition difference,
not an ignored decoration. No fix; no commit. The reproducer
(result differs between contracted/uncontracted evaluation) is in this
directory and can gate any future regression.

## Bug B — "packed 16-bit atomicOr loses lanes": NOT REPRODUCIBLE

Minimal reproducer: `atomic_lane.comp` (65536 invocations, disjoint-half
`atomicOr` pairs into 16384 words; any missing lane leaves a zero half).

| run | gpu-host-A tip | gpu-host-B tip |
|---|---|---|
| 200 rounds (fresh process each) | **0 failing** | **0 failing** |
| high-pressure `atomic_lane_hi.comp` (4M invocations, 16384 groups, 8 rounds) | **0 bad words** | **0 bad words** |
| upstream base driver (gpu-host-A) | 100 rounds 0 failing; hi 4/4 clean | — |

(One false alarm during bring-up: a "bad 32768 words" reading was a tag
overflow in the high-pressure shader itself — 0x400+i ≥ 0x10000 for
i ≥ 64512 — deterministic and identical on both hosts, fixed to
`(i>>2)&0x3FFF`.)

End-to-end: `ropediag7.py` against the diag.pairfix3 wheel AND the stock
5b18306 wheel shows transposed/partial-shape maxdiff ~3–8 on gpu-host-B — but the
STOCK wheel (which never uses atomicOr rope) shows the same under BOTH the
fork tip driver and the SYSTEM asahi driver, i.e. a pre-existing
rope/reference discrepancy in the harness shapes, not the fork's atomicOr
path. DecodeKvDirect's NO-LAND verdict (atomicOr rope store removed on the
kernel side) stands; nothing to fix in the driver.

## Digest check

Driver code is UNCHANGED (no commits), so the gpu-host-A 2B identity anchor must
hold. Verified live: `ab-tipanchor.json` / `window-anchor.log`
(MesaDivergenceVerdict protocol, 4 rounds, Qwen3.8-2B, ctx1024) —
expected `d655d4c3d1ccb030`.

## Housekeeping

- gpu-host-A llama-server (8002): an orphaned manual copy (not systemd) held the
  GPU lock; stopped it per the standing order before the windows. The anchor
  script's cleanup path restarts `llm-inference.service` and polls /health —
  verify healthy before leaving this receipt.
- Build worktree /var/tmp/mesa-upbase-wt on gpu-host-A can be removed once this is
  reviewed.
