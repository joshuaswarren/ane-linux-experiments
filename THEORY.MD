# Theory: qualify the whole Linux accelerator path

## Current strategy

This repository supplies raw-ANE and compiler evidence for the MLX Omarchy work. The ANE, CoreML, and performance plans remain separate, concurrent workstreams. A passing component does not qualify their composition. Export, bundle validation, installed-library selection, worker startup, device submission, numerical behavior, and measured performance each need evidence from the actual consumer.

Host code may schedule work, prepare constants, copy buffers, and select tokens. The Linux product must use Apple GPU compute for tensor work that cannot run on ANE. The older all-ANE research runner described below has a narrower contract: its explicit ANE mode performs tensor arithmetic on ANE, while its CPU reference is separate. That runner's limitations are not a reason to introduce CPU tensor fallback into MLX Omarchy.

The current evidence makes the remaining boundaries specific:

- The installed combined runtime/frontend at `57cc36a2` still qualifies four exact ANE add/add-mul executions, explicit GPU matmul/add, and 18 bit-exact mel comparisons on the base M1. That wheel is schema 3. mlx-omarchy `main` is `c4768af65f1fd263c2ee55b6767291896ee18381`. mil-hwx-compiler `main` is now `83a4434810b0981d1764e6231f6a679df6f35241` (merge of ordered v2 results `f91bc92` and prior main `5271ab0`). The old v1 archive in `ane-compiler.lock` remains the mlx-omarchy release pin until a matching immutable v2 archive exists. Schema-4 hardware qualification is not claimed.
- The native TDT capture now contains 146 actual joint decisions, 42 blanks, 1 decoder reuse, and 104 emissions. The existing Python host controller at `7d893bde` replays that log exactly. Full-tensor decoder and joint goldens still fail unchanged bounds. Aggregate MAE improvements do not close that gap; one FP32 LSTM candidate produced real per-output regressions and was not promoted.
- The composition-exact 256-thread BF16 attention candidate did not improve release decode. The later GEMV matrix used stale staged runner files, so its lifecycle failed. The next launch protocol at `ef6c5cc8ac8fb23f77e633518b4054243adcfccd` now passes independent local lifecycle review, including detached-child cleanup and lease refusal. It is not on mlx-omarchy `main`. No GPU grant or hardware matrix has run under that protocol.

One physical GPU has one owner. Acquire only after staging and preflight, use an absolute deadline, and verify child processes, quarantine, lease removal, and lock release before transfer. A failed status does not prove a worker stopped. Directory enumeration and ANEC table bounds are closed in `57cc36a2`. Schema 4 still required a reverse coverage check: a valid ANEC fixture with an unreferenced physical output previously loaded; that now fails closed.

## Platform and artifact boundaries

Linux can map ANE buffers and submit raw task descriptors through a narrow KMD interface. That executes older self-contained programs; it does not reproduce the modern macOS program lifecycle. A schema-4 parser proves the host contract, not firmware applicability or hardware execution.

The board-matched T6001 firmware DeviceTree and a private live ADT capture are available. A standard phram read removed the need to reboot into a proxy, but loading the external module changed the current boot taint from 4 to 4100, as the original capture receipt records. The module and MTD baseline were restored; full kernel-state restoration is not claimed. The pinned parser translates physical addresses, but named engine/IRQ semantics, reserved-memory requirements, Linux DART stream mapping, and the ordered PMGR supplier list remain unresolved. No hardware binding follows from raw fields alone.

2026-09-13: the T6001 Linux binding is now fully sourced and was driven to a live FDT node on t6001-test-host four times (`receipts/2026-09-13-t6001-test-host-ane-bind.json`). SID 0 comes from `mapper-ane0 reg 0` (apple-knowledge `cabf98e2`); the "missing" ANE-SYS-V PMGR leaf is a `no_ps` virtual device resolving to `ps_ane_sys_cpu` (m1n1 `b4654b3`); the engine span is boundary-derived `0x284000000+0x1800000`, not the whole ADT subsystem range. The ladder fixed three real driver bugs (engine/DART region overlap `-EBUSY`; single-power-domain `pd_dev` NULL oops; `of_node_name_eq` stripping `@unit` so PMGR label lookup never matched — `origin/feature/t6001-ane-bind` 3946f76, 499bae36, 16720f0). With all consumers satisfied, probe reached `iommu ok, powering domains` and ANE power-up HARD-RESET the SoC (~96 s, no oops, no pstore). Binding is therefore blocked at hardware power sequencing, not description: it needs a serial console plus staged `ane_stop_stage` instrumentation (power-only, then dart0-read-only) before any TTBR write. No further bind cycles were attempted after that. m1-test-host (T8103) remains the only bound Linux ANE; its module load and power-on are now persistent via `m1-test-host-ane.service` so reboots no longer silently drop the device — that missing autoload is what made a post-timeout reboot look like ANE loss.

Correct old-format execution links five contracts: target-compatible task descriptors; preserved task order; buffer indices mapped to the expected virtual spans; exact compiled tensor address, dtype, shape, and value; and kernel content starting at the command-buffer boundary. Monterey ANECompiler 5.5.0 emits this contract from legacy Espresso XML.

A successful compiler return is insufficient. Espresso pruned dynamic transpose, dynamic matrix multiplication, and complete manual softmax chains in prior experiments. Inspect the exported graph and its named final output before hardware execution. Textual MIL still preserves the pinned Parakeet encoder through parsing and import. Compiler source `b12b03f` plus `600dc3e` now emit ordered identity views, including differently shaped or reordered splits over one physical output. The next encoder stop is mixed-type terminal conversion, not missing split order. The private compiler HWX-extraction regression remains a release gate.

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
