# Theory: Linux Qwen ANE needs staged old-format programs

## Problem

Linux can map ANE buffers and submit raw task descriptors through a narrow KMD interface.
That path executes older self-contained programs.
It does not reproduce the modern macOS program lifecycle.

The full Qwen decoder exceeds the 3.5 GiB DART virtual address space as one fp16 program.
The runtime must stage bounded programs and keep only active state resident.
CPU code can schedule and copy small inputs.
It cannot compute model tensors.

## Working artifact contract

Correct old-format execution has five linked contracts.

1. Task descriptors must match the target ANE.
2. Every task link must preserve the compiled order.
3. Each buffer index must map to the expected virtual span.
4. Each tensor must use the compiled address, dtype, shape, and value.
5. Kernel content must start at the compiled command-buffer boundary.

Monterey ANECompiler 5.5.0 emits this contract from legacy Espresso XML.
The Linux KMD executes these artifacts without modern program preparation.
Modern macOS HWX files reach the task manager but do not return to idle.

The model therefore uses bounded old-format programs.
A deterministic set covers all decoder matrices with 186 projections and 31 vocabulary-head chunks.
All 217 sources compile to self-contained HWX artifacts.
Eight projection geometries pass Linux M1 numeric comparison.
The maximum absolute error is 0.001220703125.

## Completion semantics

`TM_COMMITTED` records accepted task progress.
It does not record completed compute.

A valid completion requires three results.

1. `TM_STATUS` returns to idle.
2. The submit path returns without timeout.
3. The expected output buffer changes and passes its value check.

The mutable GEMM runtime reserves physical output row 511 for completion polling.
Result programs can use rows 0 through 510.
This prevents a valid infinite result in row zero from looking like an unfinished submit.

## Resident state

DeltaNet recurrent state uses one `(1, 16, 133, 128)` tensor.
Rows 4 through 131 hold the `(16, 128, 128)` state.
The runner alternates two aggregate BOs after each submit.
It overwrites only q, k, v, beta, and the final decay factor before each submit.
Two hardware steps completed without a host state round trip.
The final state maximum error was 0.00004078.

The first KV implementation used one `(1, 8, 259, 256)` tensor.
The ANE shifted each cache and appended new key and value rows.
Two hardware steps preserved both caches without an intermediate host copy.

That graph shape cannot also express full attention reliably through Monterey Espresso.
Espresso pruned dynamic transpose, dynamic matrix multiplication, and complete manual softmax chains.
A successful compiler return was not sufficient evidence.
The exported `net.plist` had to retain the named final output.

## Mutable attention contract

Raw Linux GEMM has a simpler state boundary than Espresso.
The command BO already contains packed GEMM weights.
The host can update one packed row or column without copying prior state.

Each attention head uses two mutable GEMM programs.

1. The score program stores keys as matching packed matrix rows.
2. The value program stores values as matching packed matrix columns.
3. Each token writes one key row and one value column at the same ring position.
4. The score GEMM computes `K @ q`.
5. The value GEMM computes `V^T @ probabilities`.

Physical ring order does not affect attention.
Scores and values share the same physical slot.
After wrap, all 128 slots contain the latest 128 entries.
Before the cache fills, the runtime masks unused score rows.

A 130-token Linux M1 run exercised the full 128-slot ring and two overwritten slots.
The final cursor was 2 and the final length was 128.
The score maximum error was 0.00023142993450164795.
The attended-value maximum error was 0.00016526412218809128.
The control GEMM passed before and after the run.

This route removes the Espresso dynamic-matrix boundary.
It also avoids returning the old KV cache tensor to host memory.

## Reference model

The reference model is `Qwen3.8-2B-Q4_K_M.gguf`.
It has 1,312,164,224 bytes.
Its SHA-256 is `4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff`.

ANEForge runs the complete 24-layer decoder on macOS M1.
The locked reference keeps host embedding gather and fp32 `lm_head` work.
The reference runner records timing, logits, and every decoder layer boundary.

The instrumented two-token run took 0.4380809170015709 seconds after warmup.
Its first-token time was 0.2901463750004041 seconds.
Its prefill rate was 14.91380747661077 tokens per second.
Its decode rate was 15.285986554316986 tokens per second.

The prior Linux hybrid path remains slower than its CPU comparison.
Its one-token ANE timings were 7.515 seconds for steps and 7.821 seconds for logits.
Its CPU timings were 3.114 seconds for steps and 2.568 seconds for logits.
Those results do not satisfy the final performance contract.

## Softmax contract

The raw elementwise program has 64 lanes.
A 128-wide softmax therefore operates on two halves.
Every max, add, multiply, square, reduction, exponential approximation, and reciprocal step uses ANE submissions.
Host code stages the two halves and broadcasts returned scalars.
It does not compute tensor arithmetic.

The exponential path clamps differences to -64.
It divides by 128, evaluates a degree-six Taylor polynomial, then squares seven times.
This range makes masked fp16 lanes underflow to zero.
The reciprocal path starts at 1/128 and runs twelve Newton steps.
This fixed start covers sums from 1 through 128 without host division.

A Linux M1 run used 258 ANE elementwise submissions across random and masked inputs.
One output, two input, and one descriptor BO remained resident across every submission.
The random maximum absolute error was 0.001615367829799652.
The probability-sum error was 0.000038623809814453125.
The argmax matched the fp32 reference.
All 127 masked lanes returned zero probability.
The control GEMM passed before and after the run.

## Normalization contract

RMS and L2 normalization reuse the same four resident elementwise BOs as softmax.
The runtime squares and reduces each 64-lane chunk on ANE.
It applies epsilon, Newton inverse square root, output scale, and RMS weight on ANE.
Host code schedules rows and broadcasts returned scalars.
It does not compute normalization tensors.

The inverse square root multiplies source by estimate twice.
It never squares a large reciprocal estimate directly in fp16.
This order prevents overflow when the RMS input is zero or nearly zero.

A Linux M1 run covered 2,048-, 256-, and 128-wide RMS shapes.
Their maximum absolute errors were 0.004076, 0.004814, and 0.004068.
The scaled 128-wide L2 maximum absolute error was 0.0000303.
The control GEMM passed before and after the run.

## Activation contract

Sigmoid and SiLU reuse the same four resident elementwise BOs.
Each 64-lane chunk uses stable negative and positive sigmoid halves.
Fused variants keep the SwiGLU and attention gate products on ANE.

DeltaNet needs `exp(a_log * softplus(alpha + bias))` as its state multiplier.
The runtime evaluates softplus with a bounded log series and then applies the exponential on ANE.
This fixes the prior contract mismatch, which passed logarithmic decay into a direct multiplier input.

The activation exponential divides by eight and squares three times.
This reduces fp16 rounding error for activation ranges.
The softmax exponential keeps its wider division by 128 and seven squarings.

A Linux M1 run covered beta sigmoid, post-convolution SiLU, and both fused gate products.
It also covered the DeltaNet decay factor.
The five maximum absolute errors were 0.001218, 0.005288, 0.010674, 0.003075, and 0.001461.
The control GEMM passed before and after the full token run.

## Causal convolution contract

Each DeltaNet layer keeps a four-slot ring for 6,144 channels.
Host code advances the ring and copies inputs.
It performs no convolution arithmetic.

The shared elementwise backend multiplies each history slot by one depthwise kernel tap.
It then accumulates the four products on ANE.
The ring removes the old host concatenate, multiply, and reduction path.

Four sequential Linux M1 steps had maximum absolute errors from 0.000467 through 0.001509.
The control GEMM passed before and after the complete token run.

## Tensor operations contract

Every residual addition runs as 64-lane ANE chunks.
RoPE packs each head's two 32-lane halves into one 64-lane submission.
One direct multiply, one swapped-half multiply, and one add produce the rotated head.

The host computes cosine and sine constants for each position.
It packs constants and copies results.
It does not perform RoPE or residual tensor arithmetic.

The residual maximum error was 0.001953125.
Query and key RoPE maximum errors were 0.0018101 and 0.0016057.
The control GEMM passed before and after the complete token run.
## Token-to-logits orchestration

The bounded state runtimes now compose inside the 24-layer Qwen model.
Six full-attention layers own two KV-head states each.
Eighteen DeltaNet layers own separate recurrent runners.
One shared four-BO elementwise backend serves softmax, normalization, activations, and convolution.
It also serves RoPE and residual additions.

A Linux M1 run processed prompt token 32 and produced 248,320 finite logits.
The ANE-resident state path and the host-state control both selected token 369.
The resident path took 8.260 seconds for decoder layers and 6.823 seconds for logits.
The host-state control took 7.400 seconds and 6.774 seconds.
The control GEMM passed before and after both model runs.

A second full-token run moved every model normalization call to that backend.
It selected token 220 and produced 248,320 finite logits.
Decoder layers took 19.740 seconds, and logits took 6.916 seconds.

A third full-token run moved every sigmoid, SiLU, fused gate product, and recurrent decay calculation to ANE.
It selected token 220 and produced 248,320 finite logits.
Decoder layers took 78.420 seconds, and logits took 7.063 seconds.

A fourth full-token run moved every depthwise causal convolution to ANE.
It selected token 220 and produced 248,320 finite logits.
Decoder layers took 80.171 seconds, and logits took 7.028 seconds.
A fifth full-token run moved every RoPE rotation and residual addition to ANE.
It selected token 220 and produced 248,320 finite logits.
Decoder layers took 91.686 seconds, and logits took 7.249 seconds.

Normalization, activations, causal convolution, RoPE, residual additions, and projection accumulation are complete.
ANE mode now requires the token runtime before model execution.
Every model tensor method selects ANE from that explicit backend state.
The CPU reference remains a separate, explicit backend.
No GPU tensor backend exists.

Partial projection tiles previously accumulated in host fp32 arrays.
They now use the same 64-lane ANE addition path as residuals.
A complete hardware token run selected token 220 and returned finite hidden state and logits.
Decoder layers took 86.342 seconds, and logits took 11.893 seconds.
The control GEMM passed before and after the run.

## Current direction

The host may load and dequantize weights, gather embeddings, build constants, pack buffers, and schedule submissions.
It may also reshape, split, copy, and select output tokens.
It cannot compute model tensors in ANE mode.

The fixed 100-prompt corpus is now the next gate.
That paired corpus must establish numeric parity before the final performance comparison.
