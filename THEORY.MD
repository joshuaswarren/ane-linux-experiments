# Theory: Linux Qwen ANE needs staged old-format programs

## Problem

Linux can map ANE buffers and push raw task descriptors through a narrow KMD interface.
That path executes older self-contained programs.
It does not reproduce the modern macOS program lifecycle.

The complete Qwen goal also needs an MLX-compatible Linux tensor backend.
On M1 Linux, that backend must use the Apple GPU through Vulkan.
CPU code can schedule and copy, but it cannot run tensor primitives.

## Current ANE theory

Correct old-format execution has five linked contracts.

1. Task descriptors must match the target ANE.
2. Every task link must preserve the compiled order.
3. Each buffer index must map to the expected virtual span.
4. Each live tensor must use the compiled address, dtype, shape, and value.
5. Kernel content must start at the compiled command-buffer boundary.

Monterey ANECompiler 5.5.0 emits this self-contained contract from legacy Espresso XML.
The Linux KMD can execute these artifacts without modern program creation or preparation.
The verified 2,048-wide Qwen projection proves the full compile-to-Linux path.

The runtime cannot keep the full fp16 model resident in its 3.5 GiB DART VM.
It must load bounded projection programs, submit them, then release or reuse their mappings.
Recurrent and KV state need stable bounded buffers across those submissions.

## Evidence that removed earlier theories

The converted Qwen payload matches the compiler payload by hash.
The converter preserves original task spacing and `NextPointer` values.
The task headers use the decoded EON, LNID, next-size, and next-pointer protocol.

The 13-layer graph uses buffer indices 0, 1, 3, 4, and 5.
Buffer 0 holds command and constant data.
Buffer 1 starts at the aligned kernel boundary inside buffer 0.
Buffer 3 holds the `__DATA,__bss` workspace.
Buffers 4 and 5 hold aggregate input and output spans.

The exact 32-input padded replay did not move the task-20 failure.
A one-layer graph also failed at task 20.
A QKV-only graph committed its early tasks but did not complete.
A two-task 2048-wide linear graph committed its terminal task but did not complete.

The exact linear graph executes on macOS ANE through ANEForge.
It returns a finite `(1, 2048)` output with 2,040 nonzero values.
This result proves the graph, weights, and input can execute on the same M1 ANE family.

The linear HWX places its kernel at the aligned `0x480` command offset.
The Linux KMD derives that same boundary from the `0x474` task-stream size.
Kernel placement is not the linear failure.

## Completion semantics

`TM_COMMITTED` records accepted task progress.
It does not record completed compute.

A diagnostic KMD returned success after the terminal task appeared committed.
The output stayed unchanged and userspace continued to wait.
That fallback was unsafe and remains diagnostic-only.

A valid completion requires all three results.

1. `TM_STATUS` returns to idle.
2. The submit path returns without timeout.
3. The expected output buffer changes and passes its value check.

Do not use committed count as a completion shortcut.
Do not patch the normal KMD with the diagnostic fallback.

## Compiler boundary

Current physical compiler hosts run macOS 26.
A macOS 12.5.1 virtual machine exposes ANECompiler 5.5.0.
Its direct MIL route rejects the saved iOS 18 program syntax.
Its legacy Espresso XML route emits Linux-compatible old-format HWX files.

Target selection on the modern compiler does not reproduce this format.
The compiler generation and source format select the working artifact contract.
Big Sur loader recovery is no longer on the critical path.

The model must compile as bounded projections rather than one resident fp16 program.
The source and compile manifests preserve every projection name, shape, row range, size, and hash.

## Compatibility direction

Upstream MLX supports Linux through CPU and CUDA backends.
Its Metal backend stays limited to Darwin.
MLX selects complete GPU backends at build time.
It exposes no external GPU plug-in boundary.
The Linux port therefore needs an upstream-following MLX fork.

Omarchy exposes the Apple GPU through Vulkan and OpenCL, not Metal.
Vulkan is the full tensor baseline because Honeykrisp provides it on M1.
The backend must preserve supported MLX graphs, streams, transforms, compilation, dtypes, shapes, and errors.
An unsupported operation must fail by name instead of using CPU tensor code.
Initial exclusions include CPU-stream-only linear algebra, `float64`, and complex dtypes.

ANE remains an internal accelerator behind `mx.gpu`.
The partitioner must run before `mx.compile` fusion.
It replaces an accepted region with an opaque `AneRegion` primitive.
The remaining graph then fuses for Vulkan.

The first hybrid path uses host-staged GPU-to-ANE copies.
Current `libane` exposes mapped GEM buffers but no PRIME or dma-buf API.
Direct sharing remains a later driver gate.
The ANE worker must own the device file descriptor and resident buffers.
The evaluator and worker exchange shared host staging buffers.
Every crossover result must include copy and process IPC cost.

Recurrent ANE state keeps stable worker-owned buffer identities across decode evaluations.
Graph, shape, or stream changes tear down that residency and continue on Vulkan.

## Reference evidence

The real model is `Qwen3.8-2B-Q4_K_M.gguf`.
It has 1,312,164,224 bytes.
Its SHA-256 is `4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff`.

ANEForge runs the complete 24-layer Qwen decoder on macOS M1.
The locked reference keeps host embedding gather and fp32 `lm_head` work.
The reference runner records timing, logits, and each decoder layer boundary.

The ten-prompt run compiled in 46.28158112500023 seconds.
Total wall time ranged from 5.373820666998654 to 103.45407875000092 seconds.
Mean time to first token was 51.53428760429961 seconds.
Mean decode speed was 16.74448671344259 tokens per second.

The instrumented two-token run took 0.4380809170015709 seconds after warmup.
Its first-token time was 0.2901463750004041 seconds.
Its prefill rate was 14.91380747661077 tokens per second.
Its decode rate was 15.285986554316986 tokens per second.

## Export evidence

`ANECCompile` exported two raw HWX files from saved MIL and weight captures.
The first graph contains 13 decoder layers and 1,404 task descriptors.
Its content payload is `0x59238000` bytes.
The final graph contains 11 decoder layers, output normalization, and the output head.
It has 1,176 task descriptors and a `0x4b10c000` content payload.

`tools/ane-compile-hwx.mm` makes the direct compiler call repeatable.
`tools/hwxv2-to-anec.py` derives task and buffer geometry from each HWX file.
The converter streams the multi-gigabyte payload into ANEC format.

The compiler and converter now produce valid Linux input files.
They do not reproduce the macOS program-prepare operation.
A bundle format must record the required preparation contract before MLX lowering can depend on it.

## Linux evidence

A production 3,072-task old-format graph executes in one Linux ANE submit.
Its maximum reference error is `0.00047719478607177734`.
Its argmax matches the reference.
This result proves the old descriptor and submission format.

Fresh modern graphs reach the task manager but do not return to idle.
The smallest proof is the two-task linear graph.
The larger Qwen graph reaches its natural task-20 boundary.
DART reports no active mapping fault in these failures.

The older Linux Qwen path still uses CPU tensor math outside linear projections.
Its one-token check reports ANE `steps=7.515` and `logits=7.821` seconds.
The CPU check reports `steps=3.114` and `logits=2.568` seconds.
Those checks do not satisfy the compatibility or performance contracts.

An ANE timeout can require a reboot and a fresh bring-up.
The current driver does not provide process-grade recovery.
New integration tests must isolate ANE submits in a bounded worker.
Testing must stop until the ANE self-test passes after a timeout.

## Delivery strategy

Stop changing tensor packing and completion polling.
Those experiments no longer test the observed linear failure.

Recover the modern program-prepare contract next.
Use one compiler-consistent source of truth.
A macOS prepared-program capture is preferred.
A complete ANEServices lifecycle implementation is the alternative.
Do not port individual descriptor bits without that source.

Prove the preparation path with the two-task linear graph.
Require idle completion and the known macOS output values.
Then rerun QKV, one-layer, and full 13-layer graphs in that order.

After the first full graph completes, pass its output and state into the 11-layer graph.
Compare both boundaries with the fixed macOS reference.
Then run the ten-prompt parity and performance contracts.

Build the Omarchy Vulkan runtime independently of ANE.
Run matched matmul and attention probes before broad primitive work.
Both must reach 80 percent of the pinned same-machine `llama.cpp` Vulkan reference.
Then pass MLX runtime, primitive, dtype, transform, and compile gates without CPU tensor evaluation.
Prove MLX-LM generation and serving before adding ANE selection to the evaluator.

A Vulkan-only release can ship after the GPU package gate.
That release does not complete the hybrid goal.
Full completion requires one useful ANE region to pass bundle, output, safety, and crossover gates.

The public work has one repository: `https://github.com/joshuaswarren/mlx-omarchy`.
It owns the MLX fork, Vulkan backend, ANE bridge, packages, tests, and releases.
This repository remains the hardware lab.
Stable driver and `libane` changes belong in `eiln/ane`.

## Current conclusion

The modern compiler format was the wrong target for the current Linux KMD.
Monterey ANECompiler 5.5.0 removes that blocker through legacy Espresso XML graphs.
The same old-format artifact contract works for a 2,048-wide linear and a 6,144-by-2,048 projection.

A deterministic graph set now covers every matrix used by the 24-layer decoder.
It uses 186 layer projections and 31 bounded chunks for the tied vocabulary head.
All 217 sources compile to self-contained old-format HWX artifacts.

The 3.5 GiB DART VM prevents full fp16 residency.
The runtime now stages one converted projection with reusable Linux ANE buffers.
It accepts old-format graphs that declare no workspace buffer.
The converter now accepts non-file-backed `__FVMLIB` input and output sections.
All eight prepared projection geometries pass Linux M1 numeric comparison.
The maximum absolute error is 0.001220703125.
The compiler-defined buffer roles are now verified for unequal input and output sizes.
One full token step is the next proof.

The MLX path still has three early proof gates.
The Vulkan runtime and core kernels must meet the fixed performance bar.
The old-format ANE worker must execute the staged Qwen projection set.
A stable worker ABI must land before ANE regions join the Vulkan backend.
