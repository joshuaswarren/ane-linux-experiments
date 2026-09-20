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
