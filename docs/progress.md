ANE progress.

Status is incomplete.
Linux has not reached full-model ANE parity or the performance targets.

Current verified result.
The reference file is `Qwen3.8-2B-Q4_K_M.gguf`.
The file has 1,312,164,224 bytes.
Its SHA-256 is `4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff`.
The fixed corpus has 100 prompts in ten categories.
The corpus SHA-256 is `9299a3b2fc136a4c0c355f9ad3e211be81823a5fb9eeadbc2e6608fb3e5718a0`.
ANEForge ran the complete 24-layer Qwen decoder on macOS for deterministic greedy output.
The host embedding gather and fp32 lm_head remain the locked macOS reference boundary.
The runner records prefill, decode, first-token, and decoder-submission timings.
The runner can capture every decoder layer boundary.
The optional `--contract` flag validates the model and corpus before compilation.
Direct `ANECCompile` calls exported the decoder as 13-layer and 11-layer HWX files.
The converter found 1,403 and 1,175 linked task descriptors in those files.
It also derived the workspace, input, and output spans from Mach-O sections.

Receipt paths.
The contract is `benchmarks/qwen38-2b-contract.json`.
The corpus is `benchmarks/qwen38-2b-prompts.jsonl`.
The corpus generator is `tools/build-benchmark-corpus.py`.
The macOS runner is `tools/aneforge-qwen-reference.py`.
The runner tests are `tools/test_aneforge_qwen_reference.py`.
The repeatability receipt is `receipts/aneforge-qwen-reference-repeatability.log`.
The timing receipt is `receipts/aneforge-qwen-reference-instrumented.log`.
The layer checkpoint receipt is `receipts/aneforge-qwen-layer-checkpoints.log`.
The ten-prompt macOS receipt is `receipts/aneforge-qwen-reference-10.log`.
The bounded 100-prompt attempt is recorded in
`receipts/aneforge-qwen-reference-100-attempt.log`.
The parity comparator is `tools/compare-qwen-reference.py`.
The comparator tests are `tools/test_compare_qwen_reference.py`.
The Linux custom CPU and ANE receipt is `receipts/ane-qwen-generated-parity.log`.
The synthetic compiler graph receipt is `receipts/aneforge-qwen-graph.log`.
The raw HWX export and conversion receipt is
`receipts/qwen-hwx-export-convert.log`.

The ten-prompt receipt contains one measured run for each of the first ten
corpus prompts. The JSON artifact has 220185 bytes. The logits archive has
292745189 bytes. The receipt records both SHA-256 checksums. The archive
format supports variable prompt lengths and repeated runs without padding.

The comparator maps prompt IDs before it compares logits. It compares all
matching repeated runs. It accepts the earlier one-array-per-prompt archive
format for existing receipts.
The hardware-independent contract tests are
`tools/test_ane_contract.py`.
The no-fallback test confirms that an ANE projection error propagates instead
of switching to host math.

Export pipeline.
`tools/ane-compile-hwx.mm` calls the private macOS `ANECCompile` entry point.
It requires a capture directory with `model.mil` and `weights.bin`.
It writes `model.hwx` for the selected target architecture.
`tools/hwxv2-to-anec.py` parses the Mach-O sections and linked task chain.
It writes an ANEC header plus the complete HWX payload without loading the
multi-gigabyte file into memory.
The exported 11-layer graph has 1,175 tasks and a `0x4b10c000` content payload.
The exported 13-layer graph has 1,403 tasks and a `0x59238000` content payload.

Current performance numbers.
The macOS 32-token reference run took 4.5050186660009786 seconds.
The macOS 2-token instrumented run took 0.4380809170015709 seconds after one warmup.
The macOS instrumented first-token time was 0.2901463750004041 seconds.
The macOS instrumented prefill rate was 14.91380747661077 tokens/second for two prompt steps.
The macOS instrumented decode rate was 15.285986554316986 tokens/second for two generated tokens.
The existing Linux ANE one-token path reports `steps=7.515` and `logits=7.821` seconds.
The existing Linux CPU one-token path reports `steps=3.114` and `logits=2.568` seconds.
These numbers do not satisfy the final Linux performance targets.
The measurements are not yet a matched ten-repetition corpus benchmark.
The ten-prompt macOS run completed one measured run per prompt.
Its compile time was 46.28158112500023 seconds.
The bounded 100-prompt attempt timed out at 900 seconds before it wrote
artifacts. The separate ten-prompt run is the largest completed corpus run.
The performance gap receipt is `receipts/performance-parity-gap.log`.
Measured wall time ranged from 5.373820666998654 to
103.45407875000092 seconds. The mean was 56.34133201670011 seconds.
Mean time to first token was 51.53428760429961 seconds.
Mean decode rate was 16.74448671344259 tokens/second.

Current parity status.
The recorded macOS prompt is repeatable across three runs.
The layer run captured 96 finite arrays across 24 layer boundaries and four steps.
Linux full-model token parity against the macOS reference is not proven.
Linux now proves token-to-logits execution with ANE-resident recurrent state,
attention K/V state, attention scores, softmax, normalization, attended values,
and logits. The remaining host tensor operations prevent an ANE-only parity claim.

Linux graph execution.
The corrected 13-layer artifact contains 1,404 linked tasks.
The probe binds buffer indices 0, 1, 3, 4, and 5.
Buffer index 3 backs the `__DATA,__bss` workspace.
The chained runner validates both artifact hashes, workspace, shapes, and
13-to-11 handoff sizes before it opens the device.
The clean 13-layer submit still returned `-110` before any output changed.
The 11-layer tail did not run.
The host rebooted after the timeout, and ANE bring-up passed its elementwise
self-test.

Failed hypotheses.
Exact task layout, queues 1 and 4, a ten-second poll, and queued interrupt
events do not explain the timeout.
The known-good default-queue control still completes on the same KMD.

Next experiment.
Replace only Qwen task zero's ten-word envelope with the known-good envelope.
Keep Qwen's register body, linked layout, kernel, and buffers.
This isolates descriptor protocol from compiled compute payload.
The independent clean reproduction receipt is
`receipts/clean-reproduction.log`.

MLX compatibility plan, 2026-08-29.
The reviewed plan is
`docs/plans/2026-08-29-mlx-omarchy-ane-compatibility-plan.md`.
The public project is `https://github.com/joshuaswarren/mlx-omarchy`.
Its initial public commit is
`929f4d5a16312277965f81f7b62325fbb1eefa21`.
The repository contains the MIT license, README, agent instructions,
architecture, roadmap, compatibility matrix, security policy, and full plan.
No Omarchy MLX backend is implemented yet.
The public project owns the MLX fork, Vulkan backend, ANE bridge, packages,
tests, and releases.
This repository remains the ANE hardware research and evidence lab.
Stable driver and `libane` changes remain owned by `eiln/ane`.

UNGATED experiment update, 2026-08-30.
Monterey ANECompiler 5.5.0 emits the older self-contained format.
A retained Espresso control compiled to a 32,768-byte HWX and ran on Linux M1.
It returned [28.0, 28.0], which matches the fp16 reference exactly.

A 2,048-by-2,048 Qwen projection also ran on Linux M1.
Its 2,040 nonzero outputs match the CPU reference within 0.00074070 maximum error.
Both paths selected index 555.

The deterministic generator is tools/qwen-espresso-graphs.py.
It emitted 217 projection sources for all 24 decoder layers and 31 tied-head chunks.
The fp16 source weights total 3,762,552,832 bytes.
Monterey compiled all 217 sources to old-format HWX files.
The HWX files total 3,769,663,488 bytes, and all exported hashes match the compile manifest.

The source manifest is receipts/qwen-monterey-source-manifest.json.
The HWX manifest is receipts/qwen-monterey-hwx-manifest.json.
The compiler recovery receipt is receipts/qwen-bigsur-compiler-attempt.log.

The modern program-prepare blocker is removed for staged fp16 projections.
A single full fp16 model cannot fit in the 3.5 GiB Linux ANE DART VM.
The runtime now reuses command, input, output, task-stream, and optional workspace buffers.
It writes logical tensors through the compiled NCHW channel strides.

The converter now accepts non-file-backed virtual sections in old-format HWX files.
Eight converted artifacts cover every unique matrix shape in the 217-graph set.
A 214,619,226-byte bundle contains those artifacts and their fp16 reference weights.
Its SHA-256 is `4976c5b34dfdd13ddf9b3329637214b40134368ccfa6a0b941c36476d850f18b`.

All eight projection geometries passed Linux M1 numeric comparison.
The maximum absolute error was 0.001220703125 with a fixed tolerance of 0.1.
The report is `receipts/qwen-linux-projection-geometry-validation.json`.
Old Espresso programs bind output to buffer index 4 and input to buffer index 5.
The earlier square projection hid the reversed runtime binding because both buffers had equal sizes.

The recurrent graph uses one `(1, 16, 133, 128)` fp16 tensor.
Rows 4 through 131 hold the `(16, 128, 128)` DeltaNet state.
`tools/recurrent-runtime.py` alternates the output and input BO roles after every submit.
The host overwrites three vector rows and two gate columns before the next ANE step.
Two sequential hardware steps completed with no intermediate host state copy.
The second output maximum error was 0.00176867.
The final state maximum error was 0.00004078.
The report is `receipts/qwen-linux-recurrent-state-validation.json`.

The KV state graph uses one `(1, 8, 259, 256)` fp16 tensor.
Rows 2 through 129 hold replicated keys. Rows 130 through 257 hold replicated values.
`tools/kv-runtime.py` alternates the output and input BO roles after every submit.
The host overwrites only the new key and value rows before the next ANE step.
Two sequential hardware steps completed with no intermediate host cache copy.
The final cache matched both source key and value tensors exactly.
The report is `receipts/qwen-linux-kv-state-validation.json`.

Espresso exported only pre-attention slices and cache concats from two attempted attention graphs.
The state-only graph retains `next@output`, compiles, and runs on Linux.

A lower-level mutable GEMM route now bypasses the Monterey dynamic-matrix limit.
The score program keeps keys in packed weight rows.
The value program keeps values in matching packed weight columns.
Each token updates one row and one column at the same ring position.
The cache tensor does not return to host memory.

Eight local tests cover packing, geometry, ring wrap, masking, completion polling, and lifecycle safety.
A Linux M1 hardware run appended 130 tokens into a 128-slot ring.
The final cursor was 2 and the final length was 128.
The score maximum absolute error was 0.00023142993450164795.
The attended-value maximum absolute error was 0.00016526412218809128.
The control GEMM passed before and after the wrap test.
The report is `receipts/qwen-linux-mutable-attention-validation.json`.

The 128-wide softmax runtime composes two 64-lane raw ANE halves.
All tensor arithmetic uses ANE max, add, multiply, and square submissions.
The exponential uses range reduction and a degree-six polynomial.
The reciprocal uses twelve Newton steps from a fixed 1/128 estimate.

A Linux M1 run used 258 elementwise submissions across random and masked inputs.
Four ANE BOs remained resident and were reused across every submission.
The random maximum absolute error was 0.001615367829799652.
The probability-sum error was 0.000038623809814453125.
The argmax matched the fp32 reference.
All 127 masked lanes returned zero probability.
The control GEMM passed before and after the run.
The report is `receipts/qwen-linux-softmax128-validation.json`.

The full token-to-logits path now supports ANE-resident recurrent and attention state.
A Linux M1 run processed prompt token 32 and produced 248,320 finite logits.
The resident path and host-state control both selected token 369.
The resident path took 8.260 seconds for layers and 6.823 seconds for logits.
The host-state control took 7.400 seconds for layers and 6.774 seconds for logits.
The control GEMM passed before and after both model runs.
The report is `receipts/qwen-linux-token-runtime-validation.json`.

Full-model Linux parity remains unproven.
RMS and L2 normalization now use composed ANE elementwise submissions.
The tested RMS shapes were 2,048, 8 by 256, and 16 by 128.
Their maximum absolute errors were 0.004076, 0.004814, and 0.004068.
The scaled 16 by 128 L2 case had 0.0000303 maximum absolute error.
A complete token run selected token 220 with finite hidden state and logits.
Decoder layers took 19.740 seconds, and logits took 6.916 seconds.
The control GEMM passed before and after the hardware runs.
The report is `receipts/qwen-linux-normalization-validation.json`.

Sigmoid, SiLU, fused gate products, and recurrent decay now use composed ANE submissions.
The five model activation cases had maximum errors from 0.001218 through 0.010674.
The recurrent path now passes the final exponential decay factor into its direct multiplier input.
A complete token run selected token 220 with finite hidden state and 248,320 finite logits.
Decoder layers took 78.420 seconds, and logits took 7.063 seconds.
The control GEMM passed before and after the hardware runs.
The report is `receipts/qwen-linux-activation-validation.json`.

Depthwise four-tap causal convolution now uses composed ANE multiply and add submissions.
Four sequential 6,144-channel steps had maximum errors from 0.000467 through 0.001509.
A complete token run selected token 220 with finite hidden state and 248,320 finite logits.
Decoder layers took 80.171 seconds, and logits took 7.028 seconds.
The control GEMM passed before and after the hardware runs.
The report is `receipts/qwen-linux-convolution-validation.json`.

RoPE and residual arithmetic remain on the host.
The next milestone moves both operations to ANE.
