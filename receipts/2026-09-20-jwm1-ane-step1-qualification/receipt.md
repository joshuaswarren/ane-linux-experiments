# jwm1 ladder Step 1: eight pinned H13 packages + overflow — PASS (2026-09-20)

Lane: Jwm1AnePlan Step 1 (Main-authorized after the GPU 12-round release:
24/24 rc=0). Stack: five-provider DT (payload `41a39ac7…`) + guard v2 module
(`99e8b8b5…`, loaded non-persistent, wedged=0 throughout). Lock held
(`/tmp/m1-gpu.lock`), released after.

## Verdict

**8/8 packages PASS under the pinned referenceCriteria; overflow +inf PASS.**

| package | runner | bit-level verdict |
|---|---|---|
| 01-add-legacy | rc=0 | BIT-IDENTICAL |
| 02-add-runtime-native | rc=0 | BIT-IDENTICAL |
| 03-mul-scalar | rc=0 | BIT-IDENTICAL |
| 04-matvec-k256-n512 | rc=0 | BIT-IDENTICAL |
| 05-softmax-512 | rc=0 | BIT-IDENTICAL |
| 06-chain-add-mul | rc=0 | FLOAT-EQUAL — exactly 1 signed-zero pair (bit-diff 1 byte; 0 true numeric diffs) |
| 07-runtime-matmul-64 | rc=0 | BIT-IDENTICAL |
| 08-mlp-768-1024-768 | rc=0 PASS (chunked envelope) | 109/768 elements ±1 fp16 ULP, max \|Δ\| 9.77e-4 vs envelope ≈4.9e-2 (~50× margin); 0 signed-zero |
| overflow [65504,65504] | rc=0 | all 64 outputs +inf (bits `007c`) ✓ |

Comparison semantics, per Main's signed-zero directive: the runner's internal
compare is float semantics (`+0.0 == -0.0`); every device output was
additionally byte-compared against the pristine reference. Signed-zero-only
differences are reported as such and never called bit-exact. The 08-mlp stop
under my stricter-than-pinned bit bar was resolved by the runner's own
pinned criteria (chunked envelope, the documented Sept-6 qualification
semantics for that package) — runner rc=0 re-captured on the rerun.

## Protocol fidelity

- Pre-run hash manifest committed (`step1-prerun-hashes.json`): runner,
  reference, inspector, h13_td, `libane_python.so` (`76fedabb…`), every
  package manifest/program/fixture.
- Runner limitation found and worked around: on PASS it overwrites the
  `--output` path with device output — pristine references were never used
  as `--output` targets (scratch copies absorbed the device bytes); the
  smoke-1 fixture mutation this caused was restored and is documented as an
  erratum in the paired-recovery receipt.
- Constant/model files (`c.bin`, `mlp-w1/w2/b1/b2.bin`) materialized into
  per-package scratch copies from each package's `models/` — the staged
  package tree was never mutated.
- Device time ~4 s total; the 60-minute authorization bound was never
  approached. No reboot; module stayed loaded; wedged=0 throughout.

## Evidence

`evidence/step1-results.json`, `evidence/step1-prerun-hashes.json`,
`evidence/ov-y-device.fp16` (all 64 outputs +inf, bits `007c`).

## Next (gated on Main)

Step 2 schema-4 add-mul re-earn via the `run-once.sh` recipe — requires the
worker rebuild from the pinned `ane-v064-wt` mlx-omarchy tree (heavy ninja
build, own coordination window; the historical worker binary is not in any
owned archive). Then islands E2E → 100-run soak → Parakeet/Qwen3.8 ANE, per
[the ladder plan](2026-09-20-jwm1-ane-qualification-ladder-plan.md).
