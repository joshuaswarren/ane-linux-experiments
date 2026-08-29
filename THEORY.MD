# Theory: Linux ANE speed and parity

## Problem

The Linux ANE path can execute Apple Neural Engine work, but the usable driver
interface exposes small fixed GEMM tiles. A Qwen token step then pays host work,
weight movement, and one ioctl per tile. The full model can match the CPU result
while still losing on time.

## Operating theory

Correctness depends on three contracts. The descriptor must match the hardware
engine. The packed weight blob must match the descriptor's layout. The host
must write the packed blob to the command BO before each submit. A failure in
any contract can produce finite but wrong values, stale values, or a device
fault.

The ANE driver has a narrow reliable path. The verified old-format descriptor
runs 512 output rows by 256 or 512 input columns. Persistent buffers remove BO
setup from repeated work. A resident 512x256 tile path beats CPU for the tied
head in isolation. The full model still sends thousands of serialized tiles.
The descriptor ceiling and the lack of reliable GEMM task chaining set the
current speed boundary.

Fresh macOS 26 HWX uses a Mach-O container and a different KDMA bank layout.
Parsing sections and scanning aligned task markers is safer than fixed offsets.
The fresh layout maps `RBase0=4`, `WBase=5`, and `KBase0=1`. Linux must bind the
input BO to handle 4 and the output BO to handle 5. A production 3,072-task
image now executes in one submit and matches its dequantized int8 reference.

## Strategy

Use the smallest verified descriptor path first. Preserve numeric parity at
each boundary. Convert fresh HWX with section-derived offsets. Decode KDMA
fields from real task descriptors. Copy the complete command payload. Compare
full output buffers with a CPU reference, not only the first output element.

Optimize host overhead only after the output contract passes. Keep weight
packing vectorized, but keep the packed input contiguous. Preserve the command
BO write after every pack. Reboot and run the ANE bring-up ladder before each
hardware experiment because a poisoned submit can persist across processes.

## Key discoveries

Persistent buffers reduced the per-tile floor below one millisecond and made
the tied output head 2.50x faster than CPU in its isolated benchmark. This did
not produce an end-to-end token crossover because layer projections still move
many blobs and submit them serially.

The fresh compiler path is not blocked by parsing. Its KDMA bank swap and full
command copy allow a production graph to execute on Linux. The production
output matches the int8 reference within fp16 rounding, with maximum error
`0.00047719478607177734` and matching argmax.

Vectorized packing reduces Python packing work and preserves the existing blob
layout. A direct pack of a non-contiguous model slice produced huge incorrect
logits because the packer expects contiguous row-major input. The safe path
keeps the padded contiguous tile and still writes the packed blob to the
command BO.

The current clean-boot Qwen benchmark records ANE `steps=7.515`, `logits=7.821`
and CPU `steps=3.114`, `logits=2.568` for the same prompt and one generated
token. Both paths generate token 11. The ANE path therefore has quality parity
for this check but no end-to-end speed crossover.

## Open questions

The compiler-generated Qwen-shaped SwiGLU graph now compiles and executes as
one ANEForge program with matching CPU argmax and bounded fp16 error.
The remaining speed lever is a compiler-generated full-model graph or chaining
for all Qwen GEMM-family tasks. Hand-built multi-TD GEMM chains are not reliable
on this KMD, while compiler-generated graphs execute. The Linux end-to-end
token path still needs thousands of serialized tiles and remains slower than
CPU.
