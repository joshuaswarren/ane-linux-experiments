# H14 stage 1-4 prep: generalized section builder, ANEC fixtures, oracle

2026-09-29, worker BuilderGeneral on the CT. NO HARDWARE WAS TOUCHED. Every
command below ran on the CT; hardware runs are the lead's.

## Deliverables

- `tools/h14_sections.py` — ANEC -> section builder, replaces
  `tools/h14_first_add_sections.py` (deleted; both self-check reader bugs
  fixed: operation refCount read at record+8 not +6, tdprop size at
  seg+0x18 not +0x10). Derives everything the old tool hard-coded.
- `tools/h14_seq_program.py` — generalized chain/call/cmd builder, replaces
  `tools/h14_seq_first_add.py` (deleted).
- `tools/h14_oracle.py` — fp16 half-away reference generator with a built-in
  self-check (RNE agreement on 200k values, away-from-zero on 20k exact
  ties, negative and subnormal ties).
- `fixtures/h14-anec/*` — nine compiled H14 ANEC packages + MIL + README
  (see that README for compile commands, hashes, layouts, refusals).

## Byte-identity proof (required gate)

Reference bytes: the buffers embedded in the hardware-proven LOAD command
`/tmp/faseq7/02.bin` and the committed copies with SHA256SUMS in the
`omarchy-ane-m2-installed-wt` worktree's `fixtures/` directory (both
checked). `python3 tools/h14_sections.py /tmp/sect-add
fixtures/h14-anec/add/program-0.anec` reproduces:

```
generic     664 B -> IDENTICAL     7470640cb3f1faac...
kernel    16384 B -> IDENTICAL     4fe7b59af6de3b66...
descriptor  260 B -> IDENTICAL     66e25ee11eb4442a...
operation  1040 B -> IDENTICAL     f95d80a3f4dd4120...
procedure    56 B -> IDENTICAL     e1b5d004fbc7d729...
tdprop       40 B -> IDENTICAL     dc00362edb31f75e...
```

`python3 tools/h14_seq_program.py chain /tmp/sect-add <artifacts> /tmp/chain-add`
reproduces `/tmp/faseq7/00.bin` .. `04.bin` byte-identical (all five cmp
clean), including the CALL with its a/b/y buffers.

## What the builder derives, per program (builder output)

| program | tasks | op refs {slot,tag} | tdprop blockNbr | self-checks |
|---|---|---|---|---|
| add | 1 | (4,5)(5,4)(6,6) | 1 | 49 ok |
| mul | 1 | (4,5)(5,4)(6,6) | 1 | 49 ok |
| relu | 1 | (4,5)(5,4) | 1 | 44 ok |
| add-scalar | 1 | (4,5)(5,4) | 1 | 44 ok |
| mul-scalar | 1 | (4,5)(5,4) | 1 | 44 ok |
| matvec | 2 | (1,2)(4,4)(5,5) | 2 | 44 ok |
| real-div-scalar | 2 | (1,2)(4,5)(5,4) | 2 | 44 ok |
| clip-low | 1 | (1,2)(4,5)(5,4) | 1 | 44 ok |
| clip-high | 1 | (1,2)(4,5)(5,4) | 1 | 44 ok |

Derivations: descriptor = full task stream walked by header[0] size,
16-byte alignment, zero frames (ported split_h14_tasks; the walk replica of
fw135 0x486a0 gives blockNbr, cross-checked against the parsed task count).
Operation refs from dense TD record headers with bit 29 set, slot in bits
28:23: src bases 0x1110/0x1128 -> channels 5/6, dst base 0x1508 -> channel
4, KernelDMA block 0x1900..0x19ff and src-base slot 0/1 -> tag 2 (kernel
section base). Generic entries from the ANEC channel table (tiles*0x4000).

## Proven vs inferred

PROVEN (hardware, boot 8f468602 and the canonical fixtures):
- the add sections byte-for-byte; refs {4,5},{5,4},{6,6}; tdprop blockNbr 1
  with size@seg+0x18; the 00-04 command chain; fp16 add with ties away from
  zero; y == a+b 16384/16384.
- section tag semantics {2,3}: Apple's own load-proven conv operation
  section (/tmp/h14conv/operation.bin) carries refs {0,2} {1,3} {4,0}, and
  the call checker forbids io bufferIds 2/3 (fw135 0x48ee0-0x48f10)
  precisely because pushToHWDirect compares tags against the kernel/text
  section bases (0x44f30/0x44f58) before the call-record scan (0x44fbc).

INFERRED (grounded but not hardware-run; each names its evidence):
- real-div-scalar ref {1,2}: task 0 has no TileDMA destination and no PE
  write, and the constant section holds 512 halfwords of 2.0 at offset
  0x400 ("the host stores each reciprocal slice", compiler README); so the
  task-0 src base reads the kernel section. If wrong, the lead sees t0 read
  input a instead.
- matvec ref {1,2}: the t1 KernelDMA record at 0x1908 binds the weight
  section base (same 0x44f30 path as Apple's conv {0,2}).
- clip-low/clip-high refs {1,2}: scalar fold through KernelDMA words
  (0x19f4/0x1a00), same tag-2 path.
- mul rounding mode: products of two fp16 are exact in fp32, so only the
  final rounding matters; assumed half-away like add.

## Expected outputs (tools/h14_oracle.py, `oracle/` in this receipt)

Inputs are seeded and deterministic; the add inputs are byte-identical to
the hardware run (input-a `fdfa450d...`, input-b `205f6833...`, expected
`a0b24aaf...` all match the proven `inputs.json`). Per-op `expected.fp16`
sha256 (also in `oracle/SHA256SUMS`):

```
add              a0b24aaf7e4edaccb380669cf47f579a65050acb06baba35e41dc5e4eff18384
mul              6142a2db8081765fb57452dc632cb02861116059e029aa04d348591e523cc089
relu             1e1d0f34c839fbd4bbfe24372ee1d89dc99283ad27347adc3ca81735181dd1d7
add-scalar       212332ddf5d915e23104f12629a9b9a7a5e5f8cfbd35abafb6c01d1b7512a760
mul-scalar       7783ebc9999ae89f6c1b92358bc980bc93d3f7aa607c039375cf75cc371644d0
real-div-scalar  1ca5c18f93bdf21366a49b8c1b980ec3a5091640dee2141978efee4fec1a843d
clip-low         47a3192c9e0256b22cde10fa96bfd14868f2539969e7fbb5cf61a10e7a4dbf2d
clip-high        541cf1391e48c3c4763e7c8068c605dfcf48239037408fb8cc2376a0d27193ad
matvec           73feac0530bd381b57fe2f5e30343c72dc53d7801468651e39f6b9c1d4a8aaf9
```

Tolerances (state them as UNPROVEN ASSUMPTIONS; the hardware decides):
- add, add-scalar, relu, clip-low/high, mul-scalar, real-div-scalar: exact
  bit match expected. mul-scalar and real-div-scalar scale by a power of
  two (0.5 / 2.0), so no rounding occurs at all.
- mul: exact match expected; if the device rounds ties to even, mismatches
  concentrate on exact half-ulp products (accept 1 ulp there).
- matvec: oracle accumulates each output in fp32 over K=256 and rounds once,
  half-away. The device accumulation width and order are unknown; treat
  exact equality as the hypothesis and 1-2 ulp as the fallback band.

## Refusals

Compiler (H14, observed diagnostics in fixtures/h14-anec/README.md): clip
op, two-op programs, any scalar constant other than fp16 0.5, and
maximum/minimum with constant tensor blobs — all `h14.outside-parity-envelope`.
Builder: corrupt-header, inputCount>2, truncated task, nonzero inter-task
padding, BAR-ref at unknown registers, slot 2/3 on surface bases, empty
stream — each raises with its reason (tested; see README).

## Lead hand-off

Per program: build sections (`tools/h14_sections.py <out>
fixtures/h14-anec/<op>/program-0.anec`, matvec add `--bind 5=x`), make fill
buffers (`tools/h14_oracle.py <op> <dir>` writes packed `input-*.buffer` and
the `output-sentinel.buffer`), emit the chain (`tools/h14_seq_program.py
chain <sections> <artifacts> <out>`), then the proven LOAD/CREATE/CALL
sequence. Kernel sections up to 128 KiB (matvec) pack into the LOAD command
the same way as the 16 KiB add.
