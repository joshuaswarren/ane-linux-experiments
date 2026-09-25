# 2026-09-22-t8103-divisor — old headline numbers RELABELED as INCORRECTLY ATTRIBUTED

Branch: `agent/jwm1-macos-baselines` · 2026-09-24

The 122.12 ms / 119.56 ms ANE/ALL medians reported in the original
`receipts/2026-09-22-t8103-divisor/README.md` were produced by a harness that
set `cfg.computeUnits` but loaded the model with `MLModel(contentsOf: dest)`,
not `MLModel(contentsOf: dest, configuration: cfg)`. The `cfg` was therefore
unwired: the `.ane` / `.all` labels were cosmetic and the timer was actually
running CoreML's default placement.

Those numbers stand in this README only as a historical record. **They are
NOT ANE timings** and must not be used as the macOS ANE denominator for any
parity calculation.

The harness defect was independently fixed by Joshua at commit
`2bc9112 t8103-divisor: pass MLModelConfiguration to MLModel load; record
load_ms and MLComputePlan per-op placement` (already present in the parent
of `agent/jwm1-macos-baselines` at HEAD `eb1e711`). The fix diff:

    -let model = try MLModel(contentsOf: dest)
    +let tl = Date()
    +let model = try MLModel(contentsOf: dest, configuration: cfg)
    +let loadMs = -tl.timeIntervalSinceNow * 1000
    +// Actual per-op placement from CoreML's own plan (macOS 14.4+),
    +// not the requested label.
    +var placement: [String: Int] = [:]
    +let sem = DispatchSemaphore(value: 0)
    +Task.detached {
    +    defer { sem.signal() }
    +    guard let plan = try? await MLComputePlan.load(contentsOf: dest, configuration: cfg),
    +          case let .program(prog) = plan.modelStructure,
    +          let main = prog.functions["main"] else { return }
    +    for op in main.block.operations {
    +        guard let u = plan.deviceUsage(for: op)?.preferred else { continue }
    +        let k: String
    +        switch u {
    +        case .neuralEngine: k = "ane"
    +        case .gpu: k = "gpu"
    +        case .cpu: k = "cpu"
    +        @unknown default: k = "other"
    +        }
    +        placement[k, default: 0] += 1
    +    }
    +}
    +sem.wait()

This commit (on `agent/jwm1-macos-baselines`) carries the fix forward as
inherited content and does not re-apply it as a fresh diff (the working-tree
file is already the fixed version).

## Corrected macOS denominators (attribution re-established)

Re-measurement with the corrected harness on jwm1 macOS — whole Parakeet
encoder via CoreML, 3 warmups + 10 timed reps, model
`~/.cache/mlx-omarchy/parakeet-reference/)mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c.../encoder.mlpackage`,
inputs `feat_f32.bin` and `mask_i32.bin` (the same tensors used for the Linux
gold), 2026-09-23 01:50-01:53 CDT, caffeinate held, models ready 24.06 s on
first compile, pmset therm clean, load avg 10.07 at start, ANE fw 3600.25.2:

| arm | median ms | min ms | max ms | mean ms | placement (preferred per op) | reps | hidden bit-exact vs gold |
|---|---:|---:|---:|---:|---|---:|---|
| cpuAndNeuralEngine (".ane") | **113.12** | 112.41 | 113.47 | 112.92 | ane 1345 / cpu 29 | 10 | yes (0/240000, max_delta 0) |
| all (".all")              | **113.23** | 112.48 | 113.30 | 112.97 | ane 1345 / cpu 29 | 10 | yes (0/240000, max_delta 0) |
| cpuOnly (".cpu")          | **272.80** | 271.01 | 273.33 | 272.27 | cpu 1374          | 10 | yes (max_delta 0.206, expected for fp32 host path) |

Per-rep arrays (from bench JSONs, copy under `raw/core/`):

- ane: `112.41, 112.49, 112.52, 112.58, 113.00, 113.12, 113.19, 113.23, 113.24, 113.47`
- all: `112.48, 112.48, 112.54, 112.89, 112.97, 113.23, 113.25, 113.25, 113.28, 113.30`
- cpu: `271.01, 271.07, 271.29, 271.41, 272.79, 272.80, 272.82, 272.95, 273.26, 273.33`

Placement is the **MLComputePlan-preferred per-op device** for the SAME
compiled model under the SAME `MLModelConfiguration` (the `cfg` that was
previously ignored). 1345/1374 ops on ANE under both `.ane` and `.all`,
1374/1374 on CPU under `.cpuOnly`. The `.all` arm falls back to ANE
because the encoder is ane-friendly enough that the plan doesn't promote
any op to GPU; this matches the bit-exact timing agreement with `.ane`.
These are the macOS ANE denominators that replace the unattributed
122.12 / 119.56 figures.

## Cross-references

- Original (broken-harness) README: `receipts/2026-09-22-t8103-divisor/README.md`
- Harness fix commit: `2bc9112`
- Original raw timing JSONs (still on disk, now relabeled): `receipts/2026-09-22-t8103-divisor/SHA256SUMS` keeps the encoder_bench.swift hash `938dc559…` (pre-fix)
- Re-measurement raw JSONs: this receipt's `raw/core/bench_{ane,all,cpu}.json`
  (sha256: `9980f20b…`, `c5d14d33…`, `01897557…`)
- Parity table that supersedes the 122.12 ms figure: sibling receipt
  `receipts/2026-09-23-m1-mac-denominator/README.md` (worktree
  `agent/m1-mac-denominator`, commit `1df33f6`).
