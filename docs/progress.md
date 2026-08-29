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
The runner now records prefill, decode, first-token, and decoder-submission timings.
The runner can capture every decoder layer boundary.

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
The macOS runner imports `aneforge.qwen35.load_gguf`, disables the host
`ane_lm_head`, warms the model, and runs the full 24-layer decoder. ANEForge
compiles MIL through private Espresso E5RT inside the same macOS process.
The current API exposes no raw HWX export. The cache contains private E5RT
bundles, not Linux-loadable HWX or ANEC images.
The Linux path requires a raw HWX or equivalent Linux-loadable artifact.
That artifact must be converted to ANEC before the Linux KMD probe can load it.

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
Measured end-to-end time ranged from 5.373820666998654 to
103.45407875000092 seconds. The mean was 56.34133201670011 seconds.
Mean time to first token was 51.53428760429961 seconds.
Mean decode rate was 16.74448671344259 tokens/second.

Current parity status.
The recorded macOS prompt is repeatable across three runs.
The layer run captured 96 finite arrays across 24 layer boundaries and four steps.
Linux full-model token parity against the macOS reference is not proven.
Linux performs CPU tensor math outside its linear projections.
Linux does not yet prove resident recurrent state, resident KV state, or ANE logits projection for the complete model.

Export blocker.
The macOS E5RT bundle is not a Linux ANEC image.
The Linux ANEC probe rejected the bundle with `expected one input and output, got 17904/4`.
The Linux runtime needs a raw HWX or an equivalent Linux-loadable graph artifact.
No complete Linux graph can be claimed until that artifact is exported and converted.
The failed export receipt is `receipts/aneforge-export-gap.log`.

Failed hypothesis.
The eight-operation SwiGLU graph proves multi-operation ANE execution.
It does not prove complete Qwen execution, numeric parity, or full-run speed.

Next experiment.
Obtain a raw HWX or equivalent Linux-loadable artifact for the real Qwen decoder.
Then convert it to ANEC and run the Linux graph with token and state bindings.
