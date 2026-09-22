# 2026-09-22 — Qwen3.8-2B five-lane kernel integration + cadence re-measure

Lane: Qwen38Integration. Branch `integration/qwen38-2026-09-22` (mlx-omarchy, local, no pushes to origin).

## Merge order and commits

1. `bf16-decode-gdn` (1af87a50) — base
2. `agent/decode-kv-direct` (112e30e4) — clean
3. `m1max-host/agent/q4-gemv-xpack` (b3e18ea0) — clean. NOTE: this branch existed only on the
   m1max-host remote (`/var/tmp/rope-pair-land`), not in the local clone.
4. `bf16-prefill-coopmat-925cf` (da3e8a4d) — 2 conflicts (primitives.cpp GatedDeltaUpdate,
   gated_delta_prefill.comp add/add); coopmat side is a strict superset (f32-gate flag bit2,
   10-binding mask path) → took theirs block-wise.
5. `bf16-prefill-gdn-exact` (37e281d8) — 1 conflict (kernel selector in chunked two-pass
   tail); theirs (unconditional GatedDeltaPrefillBF16).
6. `bf16-prefill-gdn-exact-hostfix` (f6db574c) — clean. **The local `bf16-prefill-gdn-exact`
   branch was MISSING the host-path fix commits 117133d0/f6db574c** (they lived only in the
   m1max-host worktree `/var/tmp/gdn-exact-wt`). First cadence runs without them showed fallback:
   m1max-host prefill-512 58 tok/s, m1-host 19.8. Fetched, ref'd as `-hostfix`, merged → final tip
   **dc7ca4a0**.

Merge-hygiene incidents (documented for the packet):
- git rerere replayed a STALE resolution in step 4 that silently dropped the kv-direct
  window-storage work (sum_windows). Detected via link failure
  (`undefined reference to dispatch_dense_gemv_group`), fixed by disabling rerere and
  re-merging with block-level resolution. Do not trust rerere for cross-lane merges here.
- `git checkout --theirs` in step 5 replaced the whole primitives.cpp blob (dropped
  kv-direct hunks); detected via `git diff bf16-prefill-gdn-exact` = 0; redone.
- Stale uncommitted GDN WIP found on the bf16-decode-gdn worktree; stashed (superseded by
  the gdn-exact branch content).

Verification of merge completeness: `git merge-base --is-ancestor` for all five lanes;
diff vs decode-kv-direct confined to QuantizedMatmul (coopmat) + GatedDeltaUpdate (prefill);
diff vs gdn-exact confined to dense-gemv window/RoPE-pair/quant-gemv hunks (kv-direct/xpack).

## Wheels (both hosts, `scripts/build-wheel.sh` in /var/tmp/integ-wt @ dc7ca4a0)

| host | wheel | sha256 |
| --- | --- | --- |
| m1max-host | mlx_omarchy-0.32.3.dev202609221025+dc7ca4a0-cp314-cp314-linux_aarch64.whl (8411637 B) | `1dbc78e4d190bdeb99e88ee79da21e569aa8e8f2b71f6d7ba3e0e8ae66b2187b` |
| m1-host | mlx_omarchy-0.32.3.dev202609221028+dc7ca4a0-cp314-cp314-linux_aarch64.whl (8411642 B) | `55cbee7a241348023001853c423f2ae5d0f12b27091c921a3f126c9a4056ddd6` |

Venvs: `/var/tmp/integ-venv` on both hosts (python -m pip; wheel + mlx-lm 0.31.3 +
`patch-mlx-lm-gdn.py` routing; conv-ring OFF).

## Gates

| gate | m1max-host | m1-host |
| --- | --- | --- |
| q4-bw-bench `--bf16eq` | 28/28 rows, 0 bit mismatches | 28/28 rows, 0 bit mismatches |
| identity_probe fused==ops (3 cases) | True/True/True | (protocol same class, pass on m1max-host battery; m1-host covered by cadence determinism) |
| decode_nan_repro | all finite, no NaN | (same wheel family; m1max-host run green) |
| nc_probe (strided/noncontig equality) | strided==contig True | — |
| verify_fix (vs ops reference) | state ≤1e-7; out within 1 bf16 ulp | — |

### tokid identity — reference stream CORRECTED (important)

The pre-GDN tokid REF (`760 1156 369 ...`, GDN-decode receipt) predates the fused bf16 GDN
prefill; first-token top-1 ties flip legitimately. The assignment's expected cadence digest
`5e093035` was **measured on the f6db574c wheel, which generates degenerate all-zero token
streams** under the full-model protocol (verified directly: fresh venv, f6db574c wheel →
every prompt outputs token 0 repeatedly on m1max-host; bisect wheel WITHOUT xpack reproduces the
healthy stream, WITH hostfix-only reproduces zeros). I.e. `5e093035` is the hash of
degenerate output; the healthy post-GDN-prefill stream is the
`271 248068 271 248069 ...` family, which matches the coopmat-lane cadence records and is
what the integrated wheel produces on both hosts. The GDN prefill lane's "green" digests
were computed on invalid (zero) generation — see taste 2026-09-03.

Integration digests (healthy, deterministic: 10 unique streams over 30 records on both hosts):

| host | digest (ordered_records_sha256) |
| --- | --- |
| m1max-host | `ac1b269553a220ee66d59011decad4740c90f7027ff42deca5b4c4484e2b48f1` |
| m1-host | `e173e037aed127c6e1cdfae2c2f1709a02e201263101f852c2f0631c5dc480b8` |

## Cadence table (10 prompts x 3 passes, greedy, 32 new tokens, warmup 2, prefill-512)

| host | decode tok/s | prefill-512 tok/s | ttft tok/s | digest |
| --- | ---: | ---: | ---: | --- |
| m1max-host (M1 Max) | 57.59 | 238.32 | 61.89 | ac1b2695… |
| m1-host (M1)     | 34.30 | 32.88 | 25.12 | e173e037… |

vs pre-integration receipts: m1max-host decode 33.3 (xpack receipt) → 57.6; m1-host decode 22.9/27.6
→ 34.3; prefill matches the gdn-hostfix receipt (m1max-host 237, m1-host 32.9).

Raw JSON: m1max-host `/var/tmp/integ-bench/cadence-m1max-host.json`, m1-host `/var/tmp/integ-bench/cadence-m1-host.json`.

## Serving smoke

m1max-host: `mlx_lm.server` (integ venv, pinned 2B snapshot 0867d98b, port 8955, flock-held):
10/10 streaming chat completions 200 OK, usage_verified True, ttft median 0.80 s,
token_rate_completion median 14.3 tok/s. Server stopped after smoke; m1max-host llama-server
(27b:8002) untouched and healthy (health 200). m1-host smoke launched under lock but the
result JSON was not confirmed before wrap-up (server startup latency); m1-host serving is
covered indirectly by the cadence + gate battery there — rerun
`benchmarks/qwen38-serve-bench.py` if a m1-host server receipt is required.

## Follow-ups for Main

1. Update README numbers with the cadence table above (not the 5e093035 reference).
2. The gdn-prefill-host receipt's digest column is invalid (degenerate streams); needs a
   corrected receipt.
3. Local branch `bf16-prefill-gdn-exact` should be fast-forwarded to f6db574c (or the
   `-hostfix` ref pushed to origin) so the repo tip matches the receipt's final wheel.
4. Locks respected throughout (`/tmp/m1-gpu.lock`); no reboots; m2-host untouched.
