ANE progress.

Status is incomplete.
Linux has not reached full-model ANE parity or the performance targets.

Current verified result.
The reference file is `Qwen3.8-2B-Q4_K_M.gguf`.
The file has 1,312,164,224 bytes.
Its SHA-256 is `4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff`.
The fixed corpus has 100 prompts in ten categories.
The corpus SHA-256 is `9299a3b2fc136a4c0c355f9ad3e211be81823a5fb9eeadbc2e6608fb3e5718a0`.
ANEForge ran the complete 24-layer Qwen model on macOS for 32 greedy tokens.
Three repeated macOS runs returned the same token sequence and finite logits.

Receipt paths.
The contract is `benchmarks/qwen38-2b-contract.json`.
The corpus is `benchmarks/qwen38-2b-prompts.jsonl`.
The corpus generator is `tools/build-benchmark-corpus.py`.
The macOS runner is `tools/aneforge-qwen-reference.py`.
The repeatability receipt is `receipts/aneforge-qwen-reference-repeatability.log`.
The Linux custom CPU and ANE receipt is `receipts/ane-qwen-generated-parity.log`.
The synthetic compiler graph receipt is `receipts/aneforge-qwen-graph.log`.

Current performance numbers.
The macOS reference compiled in 33.84838483400017 seconds.
One macOS 32-token run took 4.5050186660009786 seconds.
The existing Linux ANE one-token path reports `steps=7.515` and `logits=7.821` seconds.
The existing Linux CPU one-token path reports `steps=3.114` and `logits=2.568` seconds.
These numbers do not satisfy the final Linux performance targets.
The measurements are not yet a matched ten-repetition corpus benchmark.

Current parity status.
The recorded macOS prompt is repeatable across three runs.
Linux full-model token parity against the macOS reference is not proven.
Linux performs CPU tensor math outside its linear projections.
Linux does not yet prove resident recurrent state, resident KV state, or ANE logits projection for the complete model.

Failed hypothesis.
The eight-operation SwiGLU graph proves multi-operation ANE execution.
It does not prove complete Qwen execution, numeric parity, or full-run speed.

Next experiment.
Compile the real 24-layer Qwen graph for Linux.
Capture layer checkpoints and token logits with fallback disabled.
