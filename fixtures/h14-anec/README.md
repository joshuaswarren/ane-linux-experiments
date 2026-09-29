# H14 stage 1-4 ANEC fixtures (T6021, fw 13.5)

One directory per program: `model.mil` (the MIL source), `program-0.anec`
(the H14 ANEC package), and for matvec `models/weights.bin` (the constant
weights the MIL reads through BLOBFILE). Every package was compiled with the
mil-hwx-compiler at `feat/h13-m1` (commit recorded in the stage receipt) on
the CT, no Apple tools. The `add` package is the hardware-proven
first-inference ANEC (sha256 `b416b9d14059a091...`, boot 8f468602,
y == a+b 16384/16384 bit-exact).

Compile command (from the repo root of mil-hwx-compiler, GNUstep libs on
LD_LIBRARY_PATH):

```sh
LD_LIBRARY_PATH=$HOME/.local/mil-hwx-gnustep/lib ./build/mil-hwxc \
    --target H14 --format anec --mil <dir>/model.mil \
    --model-root <dir> --output <dir>/pkg
```

matvec also needs `weights.bin` copied to `<dir>/weights.bin` (the compiler
resolves `@model_path/` against `--model-root`).

## Programs

| directory | op | shape | tasks | ANEC bytes | sha256 (first 16) |
|---|---|---|---|---|---|
| add | add(a,b) | [1,512,1,1] | 1 | 20800 | b416b9d14059a091 |
| mul | mul(a,b) | [1,512,1,1] | 1 | 20800 | b32fef9f18eaf2a9 |
| relu | relu(a) | [1,512,1,1] | 1 | 20736 | 429d991a07fcc8a1 |
| add-scalar | add(a, 0.5) | [1,512,1,1] | 1 | 20736 | f601839f49b8904c |
| mul-scalar | mul(a, 0.5) | [1,512,1,1] | 1 | 20736 | a8c5a9441f5313df |
| real-div-scalar | real_div(a, 0.5) | [1,512,1,1] | 2 | 6528 | 05e3a0c1c60ba180 |
| clip-low | maximum(a, 0.5) | [1,512,1,1] | 1 | 4480 | 1b2c143310945eee |
| clip-high | minimum(a, 0.5) | [1,512,1,1] | 1 | 4480 | abe78b1292775e36 |
| matvec | y = x·Wᵀ, x [1,256], W [256,256] const | y [1,256] | 2 | 135744 | cfb057c907695747 |

Full sha256:

```
b416b9d14059a0918f6b05bfcf4a8ba982dd92e7b25f2b042c1a15f1ab2a439a  add/program-0.anec
b32fef9f18eaf2a92bbef1ce14d92c37c430af70f08f6506b0993be9a1e3cc67  mul/program-0.anec
429d991a07fcc8a1a4928390ff782c9351c855cd5e4299703b30799aa675e77d  relu/program-0.anec
f601839f49b8904c076c87a56b2dcc843bf98f8b6840b91aba438d41daf08f42  add-scalar/program-0.anec
a8c5a9441f5313df6a148d43486007205cd32c616c74cd0c0fc8b0d87a7ff998  mul-scalar/program-0.anec
05e3a0c1c60ba18079879a021abba6d7a8c71e18464a6def2ba20bf3aef18e25  real-div-scalar/program-0.anec
1b2c143310945eeebbb4ed8b2bf571d2d826f3b46988a43c3f417b94e7552329  clip-low/program-0.anec
abe78b1292775e365a83e5e98c1aee7baed0eb83d0b165f7b559378755c40495  clip-high/program-0.anec
cfb057c907695747c37aadf4b9e2695fdf7d4916dcc3957289aad487c4712e52  matvec/program-0.anec
e262ec8b61b7bc97dcbd6e06ee354d33aae8c1246e129bb2a550741b1966245b  matvec/models/weights.bin
```

## Tile / channel layout (from each ANEC header, derived by the builder)

- add, mul: channels {4 out, 5 in a, 6 in b}, 2 tiles (0x8000 B) each,
  nchw [1,512,1,1] with plane/row 64; one task; refs {4,5}(a) {5,4}(y)
  {6,6}(b); tdprop blockNbr 1.
- relu, add-scalar, mul-scalar: channels {4 out, 5 in}, 2 tiles (0x8000 B)
  each; one task; refs {4,5} {5,4}; tdprop blockNbr 1. The scalar 0.5 folds
  into the descriptor (add-scalar, mul-scalar keep a 16384 B zero constant
  section; clip-low/high fold through their KernelDMA words with a 128 B
  constant section and a kernel-base ref {1,2}).
- real-div-scalar: two tasks. Task 0 loads the stored 2.0 row from the
  constant section (kernel-base ref {1,2}); task 1 multiplies and writes y
  (refs {4,5} in, {5,4} out). tdprop blockNbr 2.
- clip-low / clip-high: single task, kernel-base ref {1,2}, in {4,5},
  out {5,4}. A full `clip` does NOT lower on H14 (see refusals); these two
  are its lowering halves at the only decoded scalar constant.
- matvec: channels {4 out y, 5 in x}, 1 tile (0x4000) each, surface nchw
  [1,1,1,256,512,512] (dense rows); two tasks: t0 brings x in (ref {5,5}),
  t1 reads weights from the constant section through the kernel base
  (ref {1,2}) and writes y (ref {4,4}). tdprop blockNbr 2. Weights:
  `W[n][k] = ((n%8)-3.5)*0.25 + ((k%4)-1.5)*0.0625`, fp16, row-major [N][K].

## Refusals (compiler, observed)

- `clip` op on --target H14: `h14.outside-parity-envelope: H14 supports only
  the decoded fp16 elementwise, scalar-constant, and unary parity envelope`.
- any two-operation program (maximum+minimum chain, --schedule per-op):
  same `h14.outside-parity-envelope`.
- scalar constants other than fp16 0.5 (probed: maximum with -0.25, mul with
  1.5): `h14.outside-parity-envelope`. 0.5 is the only decoded scalar point.
- `maximum`/`minimum` with a same-shape constant BLOBFILE tensor: refused
  (`h14.outside-parity-envelope`); only add/sub/mul/real_div take constant
  tensors, at the decoded shapes.

## Refusals (tools/h14_sections.py, observed on corrupt inputs)

- header word @0x24 != 1 -> "only the emitted 1 is known".
- inputCount not in {1,2} -> "derives tags for 1..2 runtime inputs".
- task header declaring more words than the stream holds -> "beyond the task
  stream".
- nonzero bytes in a 16-byte task gap -> "task N has nonzero 16-byte
  alignment padding".
- BAR-ref record at a register outside {0x1110, 0x1128, 0x1508,
  0x1900..0x19ff} -> "outside the known roles".
- BAR slot 2 or 3 on a surface base -> "collides with the section-tag
  namespace".
- empty task stream -> "holds no task".

## Reproduce the sections and the sequencer files

```sh
python3 tools/h14_sections.py /tmp/sect-add fixtures/h14-anec/add/program-0.anec
python3 tools/h14_seq_program.py chain /tmp/sect-add <artifacts-dir> /tmp/chain-add
python3 tools/h14_oracle.py all /tmp/oracle     # inputs + expected outputs
```

The add sections reproduce the proven LOAD byte-for-byte (six of six with
`SHA256SUMS` in the fixtures of the installed worktree), and the regenerated
chain 00-04 is byte-identical to the proven `/tmp/faseq7` command files.
matvec needs `--bind 5=x` in h14_sections.py so the CALL record names match
the `x.buffer`/`y.buffer` fill files.
