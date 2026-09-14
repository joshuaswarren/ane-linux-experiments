# Theory: qualify the whole Linux accelerator path

## Current strategy

This repository supplies raw-ANE and compiler evidence for the MLX Omarchy work. The ANE, CoreML, and performance plans remain separate, concurrent workstreams. A passing component does not qualify their composition. Export, bundle validation, installed-library selection, worker startup, device submission, numerical behavior, and measured performance each need evidence from the actual consumer.

Host code may schedule work, prepare constants, copy buffers, and select tokens. The Linux product must use Apple GPU compute for tensor work that cannot run on ANE. The older all-ANE research runner described below has a narrower contract: its explicit ANE mode performs tensor arithmetic on ANE, while its CPU reference is separate. That runner's limitations are not a reason to introduce CPU tensor fallback into MLX Omarchy.

The current evidence makes the remaining boundaries specific:

- The installed combined runtime/frontend at `57cc36a2` still qualifies four exact ANE add/add-mul executions, explicit GPU matmul/add, and 18 bit-exact mel comparisons on the base M1. That wheel is schema 3. mlx-omarchy `main` is at `7f8786b0` (encoder parity with ANE islands A+C, `receipts/2026-09-14-encoder-parity-ane.json`; Parakeet E2E in one Linux process diverges at emission 101 on the decoder LSTM hole, `receipts/2026-09-14-parakeet-e2e.json`; decoder activation stages `receipts/2026-09-14-decoder-activation-stages.md`). mil-hwx-compiler `main` is `27cb730`; the select scratch-arena fix (`7ab3eb5`, `receipts/2026-09-14-h13-select-l2-fix.md`) is on main and mlx-omarchy pins `417554c` (`ane-compiler.lock` at `7f8786b0`). Schema-4 hardware qualification on both SoCs now covers add-mul, tiny select, 1x1 conv, `(1,256,128)` and `(32,256,128)` linear, and the re-exported 1x512 and 1x896 add family (`receipts/2026-09-14-1x896-export-fix.json`, `receipts/2026-09-14-t6001-export-family.json`).
- The native TDT capture now contains 146 actual joint decisions, 42 blanks, 1 decoder reuse, and 104 emissions. The existing Python host controller at `7d893bde` replays that log exactly. Full-tensor decoder and joint goldens still fail unchanged bounds. Aggregate MAE improvements do not close that gap; one FP32 LSTM candidate produced real per-output regressions and was not promoted.
- The composition-exact 256-thread BF16 attention candidate did not improve release decode. The later GEMV matrix used stale staged runner files, so its lifecycle failed. The next launch protocol at `ef6c5cc8ac8fb23f77e633518b4054243adcfccd` now passes independent local lifecycle review, including detached-child cleanup and lease refusal. It is not on mlx-omarchy `main`. No GPU grant or hardware matrix has run under that protocol.

One physical GPU has one owner. Acquire only after staging and preflight, use an absolute deadline, and verify child processes, quarantine, lease removal, and lock release before transfer. A failed status does not prove a worker stopped. Directory enumeration and ANEC table bounds are closed in `57cc36a2`. Schema 4 still required a reverse coverage check: a valid ANEC fixture with an unreferenced physical output previously loaded; that now fails closed.

## Platform and artifact boundaries

Linux can map ANE buffers and submit raw task descriptors through a narrow KMD interface. That executes older self-contained programs; it does not reproduce the modern macOS program lifecycle. A schema-4 parser proves the host contract, not firmware applicability or hardware execution.

The board-matched T6001 firmware DeviceTree and a private live ADT capture were the sourcing inputs. A standard phram read removed the need to reboot into a proxy. The live bind is the 2026-09-13 paragraph below; raw ADT fields alone were never treated as a binding.

2026-09-13: T6001 ANE is bound and executes. `/dev/accel/accel0` DRM 1.0.0; engine slice `0x285c04000+0x24000`; TM `0x285c24000`. The first ABI1 submit doorbell-survived then TM `-110` because SET0 at `0x28e08c000` was gated (`ACTUAL=0`, `receipts/2026-09-13-t6001-test-host-set0-read.json`). T8103-shaped SET genpd (PMGR grown to `0x14000`, set1..4 attached, no userspace `0xf`) raised SET0 to `0x3ff` (`receipts/2026-09-13-t6001-set-domains.json`). The same 64-el schema-4 add-mul is then exact fp16 in 2 ms, y `bade941d` matching T8103 (`mlx-omarchy/receipts/2026-09-13-t6001-test-host-ane-set-exec.json`). set5 stays unattached (ADT range1 ends `0xc02c`). Do not write SET from userspace; SET follows runtime PM (`ACTUAL=0` suspended, `0xf` after open). 2026-09-14: the re-exported 1x512 and 1x896 are exact on T6001 as well (`receipts/2026-09-14-t6001-export-family.json`). Where this lives: omarchy-ane `main` `8554583` carries the T6001 bind and SET genpd and is being rebuilt on the lifecycle-correct base (bring-up scaffolding, GEM/ref bugs); the derived-channel libane the exported family needs is omarchy-ane `ane-parity` `20d24ad`, not on `main`; the packaged T6001 DTS is omarchy-linux `feature/t6001-ane-bind` `9247b41`, unmerged.

Correct old-format execution links five contracts: target-compatible task descriptors; preserved task order; buffer indices mapped to the expected virtual spans; exact compiled tensor address, dtype, shape, and value; and kernel content starting at the command-buffer boundary. Monterey ANECompiler 5.5.0 emits this contract from legacy Espresso XML.

A successful compiler return is insufficient. Inspect the exported graph and its named final output before hardware execution. Parakeet encoder MIL still parses. After 2026-09-13 peels, all 72 encoder matmuls compile as one-program batched matmul and bool-cond runtime-a select compiles; concat, (375,1024,128) linear, GLU silu, affine layer_norm, 375-softmax, and encoder convs remain named H13 holes (`mlx-omarchy` `receipts/2026-09-13-encoder-leftover-now.md`). The private compiler HWX-extraction regression remains a release gate.

## Resident state and numerical contracts

The full fp16 Qwen decoder exceeds the 3.5 GiB DART virtual address space as one program. Bounded programs must preserve active state rather than repeatedly stage the whole model.

Raw mutable GEMM avoids Espresso's dynamic-attention boundary. Each head uses one program with keys packed as matrix rows and one with values packed as matrix columns. Each token updates one matching ring slot; scores compute `K @ q`, and values compute `V^T @ probabilities`. Physical ring order does not matter when scores and values use the same slots. Unused score slots must be masked until the cache fills. The historical 130-token Linux run exercised all 128 slots and two overwrites while preserving the control GEMM.

The shared elementwise path keeps one output, two inputs, and one descriptor buffer resident. It operates in 64-lane chunks; host code schedules chunks and broadcasts returned scalars without performing their tensor arithmetic.

- Softmax clamps differences to -64, divides by 128, evaluates a degree-six exponential polynomial, and squares seven times. Its reciprocal starts at 1/128 and performs twelve Newton steps, covering sums from one to 128.
- RMS and L2 normalization perform square, reduction, epsilon handling, inverse square root, and scaling on ANE. Compute `source * estimate * estimate`; do not square a large reciprocal estimate first in fp16. The native reference uses epsilon as a lower bound on mean square, not an added term.
- Sigmoid and SiLU use stable positive and negative halves. Activation exponentials divide by eight and square three times; they do not use the wider softmax approximation. DeltaNet decay must implement `exp(a_log * softplus(alpha + bias))`, not pass a logarithmic decay directly as a multiplier.
- Causal convolution keeps a four-slot history ring for 6,144 channels. The host advances slots and copies inputs; ANE multiplies taps and accumulates products.
- RoPE uses contiguous half-split NeoX frequencies across 64 rotated dimensions. The earlier multimodal remapping was wrong, and a local oracle copied that error. A frozen independent reference exposed it. Residuals and partial projection tiles also accumulate through ANE operations, not host fp32 arrays.

These operations passed bounded hardware checks individually and composed into full-token runs. That establishes execution coverage, not model parity or acceptable speed.

## Model and performance limits

The historical reference is `Qwen3.8-2B-Q4_K_M.gguf`, 1,312,164,224 bytes, SHA-256 `4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff`. The macOS reference completed 100 prompts with 32 generated tokens each and repeatable token sequences. Its median decode rate was 17.651082866938346 tokens/s. Its host embedding gather and fp32 output projection belong to that reference, not to the Linux product's allowed tensor fallback.

The staged Linux model composes six full-attention layers, eighteen DeltaNet layers, and a shared elementwise backend. Historical full-token runs produced 248,320 finite logits, but moving all tensor operations onto small ANE programs raised decoder time into tens of seconds. Finite logits and a selected token are not parity evidence.

Exact-input attention layers remain close to the macOS checkpoints. DeltaNet diverges first, and correcting epsilon semantics reduced rather than eliminated its error. The staged projections, convolution, recurrence, normalization, gating, and residual operations round differently from the reference's fused graph. A bounded fused old-format program, or an equivalent export preserving convolution and recurrent state, must pass the frozen layer and corpus thresholds before a full performance comparison.

The earlier q4 Vulkan profile in `receipts/2026-09-02-gpu-profile-decode.md` showed roughly 1,585 dispatches per token, 35.7 ms of GPU busy time, and 371.8 ms of join wait on its profiled one-core host. That evidence prioritized submission and synchronization overhead over isolated arithmetic tuning. It is not a current BF16 release benchmark, and overlapping host waits and GPU intervals must not be added as independent costs. Current optimization decisions require phase-isolated, source-identified measurements and an unprofiled release comparison.
