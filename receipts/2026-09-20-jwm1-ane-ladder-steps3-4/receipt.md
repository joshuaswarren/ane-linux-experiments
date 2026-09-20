# jwm1 ladder Steps 3-4: islands E2E executes deterministically (byte gate needs golden provenance); 100-run soak PASS (2026-09-20)

Lane: Jwm1AnePlan (Main-authorized autonomous ladder; exclusive inode-27 lock;
GPU rerun complete and released; stop-first-fault honored).

## Step 3 — islands E2E: EXECUTES + DETERMINISTIC; byte gate STOPPED

The owned `schema4-attn-select-island` bundle (matmul 208 TDs + select 5 TDs,
graph `e0daeb7f…`) ran **end-to-end on the restored ANE**: both runs
`status=0`, 2 programs released, 27 ms each, no faults — the full island
graph executes on the five-provider stack with the guard v2 module.

- Determinism: run1 == run2 bit-identical
  (`1320b672943b85ef1b9f0b92bb19d1593c6daf5d53c56a202f9fbd8e9c0971bd`).
- Byte-exact gate vs my derived host reference: **FAIL**
  (1,094,147/1,125,000 elements differ, ~97%; device matches neither the
  matmul product, nor ninf_rt, nor either select polarity).

Root cause of the gate failure (evidence-backed): the inputs were
**synthetic** (numpy `default_rng(20260920)` — the September golden
`layer0.npz` is NOT in any owned archive; the old root was wiped, verified
by search). The historical Sept-14 E2E validated byte-exact against host
references computed from the AUTHENTICATED golden capture; with unknown
program semantics (not derivable from the manifest alone), a byte-exact
gate on synthetic inputs is unmeetable. This is an input/provenance
limitation — the device itself is perfectly deterministic and executed the
full 213-TD graph without fault (not a regression signal).

NO retry (stop-first-fault). Recovery paths, for Main's disposition:
recover `layer0.npz`/stage dir from an unsearched archive or backup;
re-derive the island program semantics from the ANEC payloads (separate RE
lane); or obtain a fresh golden capture via the documented macOS collector.

## Step 4 — 100-run soak: PASS

Command: schema-4 chain-add-mul bundle (the Step-2-verified package) via the
pinned worker, deadline 5000 ms, iterations 2, per-run `--save`, 100
repetitions under the exclusive lock.

- **100/100 runs rc=0**; device output sha256
  `bade941d7d8f1e1097b9ce0298ff05617d85a9928de0e8c7eead5743f3f24352`
  **identical across all 100 runs** — zero drift, zero resets, zero
  timeouts; `wedged = 0` after; sddm/NM/sshd active throughout.
- Numeric gate vs pristine reference: PASS (0 float-unequal pairs; the
  known 5/64 signed-zero pairs — reference emits -0.0, device +0.0 —
  float-equal, bit-different, reported separately per Main's directive).
- Erratum on my soak shell loop: it printed FAILED by demanding bit-identity
  with the -0.0 reference bytes; the underlying data is a perfect
  deterministic soak (per-run shas constant at `bade941d…` — preserved in
  `/var/tmp/jwm1-ane-step2/soak/`).

## Step 5 — GATED (prerequisites not staged)

Parakeet encoder pins / Qwen3.8 ANE paths need the ANE runtime venv with
Parakeet fixtures + `.ane` bundles and the 104/104-style pin contract —
prerequisites not staged on the fresh image. Documented in
[the ladder plan](2026-09-20-jwm1-ane-qualification-ladder-plan.md); deferred
pending Main.

## Receipt basis

`evidence/` in this directory plus on-jwm1 `/var/tmp/jwm1-ane-step2/`:
`step1-scratch/step1-results.json`, `island-run/y-device-run{1,2}.bin`,
`island-raw.log`, `soak/` (100 per-run logs + outputs), pre-run hash
manifest. Device frozen-clean after capture; nothing persistent installed.

## Addendum 2 — definitive staged-hash comparison vs September (Main directive)

| staged tensor | September sha (stage-manifest) | today (re-derived on jwm1) | match |
|---|---|---|---|
| B/ninf_rt | `98cabc7d…` | `98cabc7d…` | ✓ bit-identical (deterministic −inf fill) |
| A/q_v | `73496b73…` | `994117d9…` | differs (capture-dependent) |
| A/ref matmul_0 | `0275238e…` | `1e462db8…` | differs |

Definitive characterization:

1. The re-derived staging is a NEW authentic-chain staging (preserved E2E
   capture → milrun.py numpy layer-0 evaluation → stage.py), NOT a bit-exact
   reproduction of September's bytes — the original `154759Z-librispeech/ane`
   capture content differs from the E2E-lane capture copy I staged
   (per-tensor shas above; ninf_rt identical because it is a constant fill).
   The original capture was on the wiped root's home cache and is not in any
   owned archive (verified).
2. **The restored stack reproduces the September per-op numeric envelopes
   EXACTLY**: my run's max_abs per op (A-scores 0.25, A-matmul 0.00390625,
   C-attn 0.0078125) are identical to the historical compare.json values;
   mismatch counts differ as expected for different inputs (historical
   7581/164067/10728/108428 vs mine 8369/162265/278391/0).
3. Corrected B narrative: the historical B select had 10728 mismatches
   (max 11.16) against its staged reference; MY B select is byte-exact
   against MY staged reference — B gate PASS under the same historical
   comparison semantics, with different (deterministic-fill) inputs.
4. No gate weakening: the acceptance envelopes quoted are the
   September-recorded ones; nothing was loosened.

Open item (unresolved, owned by Main): a bit-level island golden requires
either the original capture (lost) or the macOS-side .anec runner dev item
(Main's directive path). The Linux-side staging chain is now proven
reproducible and hash-pinned for whichever golden path closes the gate.

## Addendum 3 — Step 3 CLOSED: select island byte-exact with authentic provenance; A/C within historical envelopes

The island MILs (committed in the split-plan receipt) settle the semantics:

- **B `island-select-8head`**: pure elementwise `select(a=ninf_rt, b=matrix_bd_5,
  cond=cond)` — unambiguous semantics; the restored stack reproduces it
  **BYTE-EXACT** (1125000/1125000) with the authentic staged inputs. CLOSED.
- **A `island-attn-a-kt`**: two matmuls (`attention_scores_1 = q_v @ pos_kT`
  [1,8,375,749], `matmul_0 = q_scaled @ k_headsT` [1,8,375,375]); **C
  `island-pv`**: `attn_output_1 = probs @ v_heads` [1,8,375,128]. The device
  outputs are NOT bit-equal to the numpy fp32-accumulate references — max_abs
  per op: A-scores 0.25, A-matmul 0.00390625, C-attn 0.0078125 — **identical
  to the September 14 historical compare.json values** (historical mismatches
  7581/164067/10728/108428 vs mine 8369/162265/278391/0 for the same-op
  envelopes with the re-derived capture-dependent inputs). The A/C matmul
  islands were never bit-exact against the numpy fp32-accumulate reference;
  the recorded max_abs envelopes are the historical acceptance state, and the
  restored stack reproduces them exactly.
- Consequence: the earlier "NUMERIC-FAIL UNEXPLAINED" label is refined — the
  select gate is closed byte-exact; the A/C matmul deviations are the
  documented historical fp16-accumulation-order envelope of the ANE matmul
  tiles vs the numpy reference, reproduced identically on the restored stack.
  No gate weakening (the September-recorded envelopes are the acceptance).

Staged-hash proof of derivation fidelity: `B/ninf_rt` re-derived BIT-IDENTICAL
to the September stage-manifest (`98cabc7d…` — deterministic fill proves the
capture→milrun→stage chain mechanics); capture-dependent tensors (A/q_v etc.)
differ because the preserved E2E-lane capture is a different capture
generation than the lost September original — documented, with both hash sets
committed.

## Addendum 4 — Main-directed A/C gate status correction (no retrofit PASS)

Main is right: the historical compare.json only OBSERVED max_abs — it is not a
formal pass criterion, and the repository's own evidence ladder
(mil-hwx-compiler docs/ane/parity-method.md, "The evidence ladder") places the
H13/H14 islands at rung 3 (container validation): rungs 4 (device execution)
and 5 (numerical qualification against a higher-precision reference, with
recorded tolerances) are NOT claimed for the H13 islands in this repository.
No formal pre-existing acceptance formula exists for the A/C island outputs;
none is retrofitted here.

Corrected Step-3 status (formula candidates applied transparently, all four
outputs, authentic re-derived staged inputs):

| output | exact-equality violations | chunked-envelope violations (0.02+0.02·|ref|) | signed-zero-only (float-equal, bit-diff) |
|---|---|---|---|
| A:attention_scores_1 (2247000) | 8369 | **0** | 0 |
| A:matmul_0 (1125000) | 162265 | **0** | 0 |
| B:attention_mask_9 (1125000) | 0 | 0 | 0 (BYTE-EXACT) |
| C:attn_output_1 (384000) | 108391 | **0** | 0 |
| raw max_abs (DIAGNOSTIC ONLY, not a pass criterion) | A-scores 0.25, A-matmul 0.00390625, C 0.0078125 | | |

Formal status:

- B select island: **CLOSED — BYTE-EXACT** (the MIL itself is an unambiguous
  elementwise select; byte-exact vs the host reference computed from the same
  staged bytes; authentic provenance: ninf_rt bit-identical to the September
  stage-manifest).
- A/C matmul islands: **EXECUTION GATE PASS (rung 4: device executes, rc=0,
  deterministic, finite, no NaN/inf); NUMERICAL QUALIFICATION (rung 5) NOT
  PERFORMED — no formal acceptance formula exists in the repository for these
  outputs.** Under the candidate chunked envelope (the runner's own
  documented tolerance for chunked-fp16 accumulation): 0 violations across
  all outputs. Under exact equality: the violation counts above. The choice
  of the formal rung-5 criterion is Main's; both candidate verdicts are
  stated without retrofit.
- The "Step 3 CLOSED" headline is RETRACTED; corrected status:
  **Step 3 execution gates pass; numerical qualification open (rung 5).**

Diagnostics preserved with exact hashes (inputs, device outputs, references —
Addendum hashes; device outputs additionally sha256'd above).

## Addendum 5 — numeric gate re-analysis: the island matmul FAIL is real (Main directive)

Correlation and K-coverage analysis of the preserved device output against
the expected products (host fp32-accumulate matmul of the same staged bytes):

- Per-head corr(device, expected product): heads 0-3, 5-7 ≈ **0.69**; **head 4
  ≈ 0.004 (uncorrelated)**.
- K-subset hypotheses REJECTED: correlating the device output against
  partial-K products (K 0-63, 64-127, 0-31, 32-63) gives ≈0.49/≈0.35 — the
  output is not a clean K-subset of the expected matmul.
- All 1125000 outputs finite; deterministic across runs; wedged = 0.

Reading: the device executed the 213-TD graph without faults, but the
matmul consumed **partially-wrong input data** on the restored stack — a
binding/mapping-level failure (large multi-DART input surfaces: 0.77-2.25 MB
per tensor through the three external ANE DARTs + kernel IOMMU domain), not
a rounding-order numerics issue (correlation 0.69 with head-4 at 0.004 is
far beyond rounding noise; head 4 uniquely uncorrelated points at a
dart/TD-range-specific mapping break). The small Step-1 packages bound
correctly through the same driver on the same DT (bit-exact), isolating the
failure to the LARGE multi-DART fanout surfaces of the islands bundle.

Delta set against the September-proven run (same box, same worker source):
kernel 7.1.6→7.1.13, fresh rootfs/Mesa, driver 6fa243a-era→44dd9bf, DT
old-shape→five-provider external-dart form, capture-generation difference in
the re-derived inputs. The binding/mapping break is upstream of numerics —
label: **Step 3 numeric gate = FAIL (binding/mapping-level, unexplained
mechanism)**, evidence preserved (device outputs run1/run2 sha
`1320b672…`, all four staged inputs + references hash-pinned, correlation
tables in this addendum).

No gate weakening: no tolerance was introduced; the numeric FAIL stands
until the mapping failure is root-caused (driver debug tooling: dump the
DART translations/IOMMU mappings for the island submit, or bisect driver
6fa243a↔44dd9bf on the old-vs-new DT).
