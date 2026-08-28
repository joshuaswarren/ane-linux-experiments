# Apple Core AI reference

Apple's [coreai-models](https://github.com/apple/coreai-models) repo is a
useful reference for the separate Apple Neural Engine stack on macOS and
iOS 27. It provides export recipes, PyTorch primitives, and Swift runtime
tools. Its
[Neural Engine authoring rules](https://github.com/apple/coreai-models/blob/main/skills/skills/model-authoring/references/neural_engine_rules.md)
confirm several patterns that matter here:

- use fp16 and static shapes for Neural Engine execution;
- use BC1S layout and 1x1 Conv2d for projections;
- split attention per head rather than expecting fused SDPA;
- pass KV cache as readonly functional input/output;
- use `-40000.0` instead of `-inf` for fp16 causal masks.

The
[Qwen3 recipe](https://github.com/apple/coreai-models/tree/main/models/qwen3)
shows Apple's supported export path for Qwen3. It does not yet replace this
Linux KMD runtime or provide a Qwen3.8 export, but its layout and cache
rules are part of the design reference for this project.
