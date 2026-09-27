# 2026-09-27 — KernelDMA 1 MiB boundary probe: jw16 wedge receipt + source-only applicability analysis

Worker: DmaResearch. Window: granted by Jw16WeightBaseTrace (jw16/T6001) and
M1ParityResume (jwm1/T8103, unused — deferred, then hardware stand-down ordered
by Main). Program under test: `program-chunk.anec`
(sha256 `42269f578123402494a4c6a2f5fdc611ef5dbffcadfa02a9296b6ff48d82c2b2`),
a pinned-compiler (a8392e6) minted H13 chunk program: single 628-byte TD,
62-word kernel_dma table, 16 cores x 0x8000 B kernel DMA, 512 KiB kernel blob.
Driver: ane srcversion `9109B200A150B27F484F718` (cachedread branch).

## What ran, in order

1. Baseline submit (unpatched program, S = 0x8000/core): COMPLETED,
   KMD-synchronous, output digest `6b68b00c06fd892e`. The minted-form
   single-TD submission mechanics (cmd BO = TD + blob at 0x280, btsp = TD,
   dst bank 4, src bank 5) are proven on T6001.
2. First patched variant (S = 0xFF000 per core, disjoint slices i*S, weights
   relocated front-of-slice, tail zero — compute still consumes only
   32 KiB/core): submit ioctl returned ETIMEDOUT (errno 110); the KMD's
   synchronous execute never saw terminal completion.
3. Driver state after the timeout (dmesg, t=2774.81):

```
ane 285c04000.ane: recovery failed; preserving resources until module reload or reboot (tm/tq file retained through the cycle: the latched task error parks the TM in place; rmmod+insmod restores service)
ane 285c04000.ane: wedged: refusing bo free
ane 285c04000.ane: wedged: preserving bo mapping
ane 285c04000.ane: wedge pin released (engine state unknown)
```

4. Recovery (t=2930.35, the driver's own documented path):
   `sudo rmmod ane && sudo insmod <module>` — dmesg:
   `Initialized ane 1.0.0 for 285c04000.ane on minor 0`, `loaded ane`,
   `reclaimed 4 wedge-preserved mapping(s) after quiesce`,
   `DART containment armed: 0`. Service restored; /dev/accel/accel0 present.
   Jw16WeightBaseTrace and Main notified; llm-inference (GPU) unaffected.

## Finding (T6001, this incident)

A programmed kernel-DMA transfer size larger than what the task's compute
consumes does NOT complete on T6001: the engine parks the TM with a latched
task error and the driver wedges. Kernel DMA here is consumption-paced —
the article's S(k,x) transfer-size model (eiln 2026-08-10, M3) can only be
probed with workloads where compute == transfer (their whole-weight compiled
forms). Size-field patching alone is NOT a valid probe form. This matches the
frozen t6001 lane receipts' warning class.

## Source-only applicability analysis (complete; no further hardware writes)

Article: https://eiln.github.io/posts/ane-dma.html (eiln, 2026-08-10).
M3 Air measured only: KernelDMA tasks of exactly k x 1 MiB per core
(k x 0x4000 64-byte lines) throttle 45-60 -> 17-19 GB/s, recovering within
+-256 lines (one 16 KiB page); suspected 14-bit prefetch-ring pointer;
performance-only (transfers complete correctly). Applicability to
T8103/T6001/T6021 is UNKNOWN — this analysis does not claim our chips are
clean, only that nothing shipped reaches the erratum class.

Compiler audit (pinned `mlx-omarchy-main/ane-compiler.lock` = joshuaswarren/
mil-hwx-compiler a8392e6; raw decoded tables retained in
`receipts/2026-09-27-kdma-template-decode.json`):

- Whole-weight single-KDMA tasks at EXACT k x 1 MiB per core exist in the
  closed template tables: 32 instances — k=1 x9, k=2 x13, k=4 x7, k=8 x3
  (`H13EnvelopeTemplates.inc`, env_mm/rrmm m in {1,16,32,64,128} x
  k in {2048,4096,8192} x n in {2048,4096,8192} tx-variants; e.g.
  `kEnvelopeTask11` = env_mm_r2rb_m1_k4096_n4096_tx1_ty1, 16 x 0x200000).
- All other families are far below: matvec 0x8000 (H13Program.cpp
  `putFirmwareDMA`, blockBytes=0x8000), linear/FFN chains <= 0x10000, conv
  <= 0x12080, envelope 0x80000 (512 KiB, `kEnvelopeTask6` class).
- The MIL `linear` and `matmul` ops NEVER emit the whole-weight forms: the
  composite lowering chunks to <= 512 KiB kernel per program (32 KiB/core),
  measured by minting k4096 x n2048 both ways (39-71 artifacts, every chunk
  529024 bytes). Reaching a k>=1 emitter requires hand-authored TDs.
- mlx-omarchy live bundles: Parakeet islands default `ABC`
  (docs/ane-encoder-placement.md), O/F opt-in; Qwen staged cells hidden=2048
  -> per-core KDMA 512 KiB (q/o) and 1.5 MiB (gate/up/down, not a multiple).
  NOTHING shipped today is in the erratum class. There is no performance bug
  in the current stack attributable to this erratum.

## Proposed next step (NOT executed — awaits a separately reviewed workload)

Whole-weight compiled workload from the closed template set, compute ==
transfer by construction: EnvelopeTask6 (k2048 n2048, 0x80000/core),
EnvelopeTask9 chain (k4096 n2048, 0x100000/core), EnvelopeTask11
(k4096 n4096, 0x200000/core), EnvelopeTask12-class (k4096 n8192, 0x400000);
weights packed by an exact Python port of `packMatvecInterleave`
(H13Program.cpp:1096); semantic anchor y = x @ W.T (fp32 accumulate) with
rel_l2 gate at the dev-gate budget; sizes limited to real template
geometries (no size-only patching); jwm1 + jw16; M2 excluded.
