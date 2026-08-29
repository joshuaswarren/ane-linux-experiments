# Theory: Linux ANE speed and parity

## Problem

Linux can execute Apple Neural Engine work through a narrow KMD interface.
The current interface exposes small fixed GEMM tiles.
A Qwen token step then pays host tensor work, weight movement, and one ioctl
per tile.
The full model can match a CPU result and still lose on time.

## Operating theory

Correctness has three linked contracts.
The descriptor must match the hardware engine.
The packed weight blob must match the descriptor layout.
The host must write the packed blob to the command BO before each submit.
Breaking one contract can produce finite but wrong values, stale values, or a
device fault.

The verified old descriptor path runs 512 output rows by 256 or 512 input
columns.
Persistent buffers remove buffer setup from repeated work.
The tied output head runs 2.50x faster than CPU in isolation.
The full model still sends thousands of serialized tiles.
The descriptor ceiling and weak task chaining set the current speed boundary.

Fresh macOS 26 HWX uses a Mach-O container and a different KDMA bank layout.
Section parsing and aligned task-marker scans avoid fixed offsets.
The fresh layout maps `RBase0=4`, `WBase=5`, and `KBase0=1`.
Linux must bind the input BO to handle 4 and the output BO to handle 5.
A production 3,072-task image executes in one submit.
Its maximum error against the dequantized int8 reference is
`0.00047719478607177734`, with matching argmax.

## Reference evidence

ANEForge runs the complete 24-layer Qwen decoder on macOS.
The locked reference keeps host embedding gather and fp32 `lm_head` work.
The reference runner records prefill, decode, first-token, and submission
timings.
It also captures decoder layer boundaries and per-step logits.

The real model is `Qwen3.8-2B-Q4_K_M.gguf`.
It has 1,312,164,224 bytes.
Its SHA-256 is
`4aa0fb13c431514262f259d420ecc95a8714df58ac2a2384514e20b93983f0ff`.
The ten-prompt run completed one measured run for each of the first ten
corpus prompts.
Compile time was 46.28158112500023 seconds.
End-to-end time ranged from 5.373820666998654 to 103.45407875000092 seconds.
The mean was 56.34133201670011 seconds.
Mean time to first token was 51.53428760429961 seconds.
Mean decode rate was 16.74448671344259 tokens per second.

The instrumented two-token run took 0.4380809170015709 seconds after warmup.
Its first-token time was 0.2901463750004041 seconds.
Its prefill rate was 14.91380747661077 tokens per second.
Its decode rate was 15.285986554316986 tokens per second.
The recorded prompt is repeatable across three runs.
The layer run captured 96 finite arrays across 24 layer boundaries and four
steps.

## Export boundary

The macOS runner imports `aneforge.qwen35.load_gguf`, warms the model, and
executes the decoder in one process.
Private Espresso E5RT performs MIL-to-HWX compilation inside that process.
The current ANEForge API does not expose raw HWX export.
The cache contains private E5RT bundles and hashes, not Linux-loadable HWX or
ANEC images.
An E5RT bundle passed to the Linux ANEC probe as a control test.
The probe rejected it with `expected one input and output, got 17904/4`.
Therefore the complete Linux graph needs a raw HWX or equivalent
Linux-loadable artifact.
That artifact must be converted to ANEC before the Linux KMD can load it.

## Linux evidence

The current Linux Qwen path uses CPU tensor math outside its linear
projections.
It does not prove ANE-resident recurrent state, KV state, or logits
projection.
Its clean-boot one-token check reports ANE `steps=7.515` and `logits=7.821`
seconds.
The CPU check reports `steps=3.114` and `logits=2.568` seconds.
Both checks generate token 11.
This proves a narrow hybrid quality check, not an ANE-only full model.

The compiler-generated Qwen-shaped SwiGLU graph executes as one ANEForge
program with matching CPU argmax and bounded fp16 error.
This proves multi-operation compiler execution.
It does not prove complete Qwen execution, Linux parity, or end-to-end speed.

## Strategy

Keep the smallest verified descriptor path.
Preserve numeric parity at every boundary.
Convert fresh HWX with section-derived offsets.
Decode KDMA fields from real descriptors.
Copy the complete command payload.
Compare complete output buffers with a CPU reference.

Optimize host overhead only after the output contract passes.
Keep packed inputs contiguous.
Write the packed blob to the command BO after every pack.
Run the ANE bring-up ladder before each hardware experiment.

## Blocking conclusion

The current Linux work has not reached full-model ANE parity or the
performance targets.
No complete Linux ANE-only graph can be claimed without a raw Qwen HWX or
equivalent Linux-loadable artifact.
The export gap is recorded in `receipts/aneforge-export-gap.log`.
