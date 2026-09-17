# Day-one runbook: t6021 weight-plane map device verification (t6021-test-host dual-boot)

Status it acts on (2026-09-17): program side of t6021 linear is **settled** —
`H14C.e5` ≡ H13 program (1 chip-id byte 0x6002→0x6021 + path-salted provenance;
`receipts/2026-09-17-t6021-plane-derivation.md`). The **weight-plane map is open**:
it is not a program property (mm1 vs mm2 differ by 13 shape bytes yet need different
maps), so it must be measured on the device. Everything below runs on t6021-test-host booted
to Linux with m1n1/omarchy-ANE tooling; no macOS needed after the artifacts listed
here are in hand.

## 0. Artifacts in hand (all archived; nothing to re-mint)

| item | path | note |
|---|---|---|
| oproj watermark weights | `receipts/2026-09-17-t6021-h14g-oracle-mints/t6021-test-host-t6021-host/oproj/weights.bin` | identity-ordered pair28 payload at 0x80; sha256 8b4a1451… |
| mm1/mm2 watermark weights | regenerate: `python3 make_capture.py mm1 OUT` (same dir) | whole-file sha 60b167f9… (ANEForge-wrapped); payload watermark verified in-script |
| t6021 e5 programs | same tree, `cache_h14g/**/H14C.bundle/H14C.e5` (+ h13 twins) | program content ≡ H13; chip id 0x6021 |
| fixed-path pair | `…/insurance/fixed-path-experiment/fixed-{t6021-test-host-H14C,studio-host-H13D}.e5` | clean 1-byte family delta |
| synthesized H14C | `…/insurance/fixed-path-experiment/synthesized-H14C-from-H13/H14C.bundle/H14C.e5` | one-byte flip of H13D; **stale-hashed, unvalidated** — acceptance test for an e5 loader only |
| H13 known maps | receipts 2026-09-17-encoder-ane-{probe3,oproj-channel-derive,ffn-mm2-plane}.md | formulas below |

Known H13 comparison targets (emitted-position → source arrangement):
- oproj (375,1024,1024), 64 planes × 16384 halves: group at packer plane
  `g_inv(P) = ((P>>5)<<5) | ((P&1)<<4) | ((P>>1)&15)`; within plane `data[c + 16L]`.
- mm1 (375,1024,4096), 256 planes × 16384 halves:
  `P_half(g,c,L) = 16384·pi256(g) + c + 16L`, `pi256(g) = (g&~31)|((g&15)<<1)|((g>>4)&1)`.
- mm2 (375,4096,1024), identity group order, each 16-output group split over two
  32768-half planes: `c<8 → 32768·2g + 8L + c`, `c≥8 → 32768·(2g+1) + 8L + (c−8)`.

## 1. Primary route (existing tooling, no new loader): H13-encoded .anec on t6021

1. Build programs with the mlx-omarchy exporter exactly as for m1-test-host (its
   `encodeLinearParity` implements the three H13 maps for these geometries) using the
   **pair28 watermark payload as weights** — it is non-uniform, so any engine
   misread is identifiable per weight index. Produce `oproj.anec`, `mm1.anec`,
   `mm2.anec` for (375,1024,1024), (375,1024,4096), (375,4096,1024).
2. Load with the repo's libane stack (`patches/libane-ane.c`:
   `ane_init("oproj.anec")` → `ane_bind_kernel` → `__ane_send` → `ane_exec` →
   `__ane_read`), following the established m1-test-host gate procedure.
3. Probe per the CRT method (receipt 2026-09-17-encoder-ane-probe3): for each
   geometry, sweep one source index j at a time (or per-group with per-group
   rel_l2 scoring against fp32 reference), record which output positions each
   source index influences.
4. Interpret:
   - All groups rel_l2 ≈ 0.01-level (the m1-test-host post-fix level) → **H13 maps hold on
     t6021**. Record as: t6021 weight map = H13, device-verified.
   - Any group wrong → the failure pattern IS the t6021 map: for each observed
     (engine-read position P → source pair index p from the watermark,
     `p = (even−0x0400) | ((odd−0x8400)<<14)`), tabulate `P_half`, then fit the
     closed form (expect the same shapes: bit-permutation / pi256-style / column
     split). Emit explicit table if no closed form fits — do not force one.

## 2. Secondary route: archived e5 oracles (only if an e5 container loader exists)

The e5 route needs a Linux e5→DMA translator, which is **not built** — that is a
prerequisite, not a given. If built, its acceptance test is the synthesized
H14C-from-H13 candidate: loader must consume it and produce output identical to the
H13D program on the same weights (they differ by one byte). Only then are the
archived `H14C.e5` oracles + watermark weights a map probe on their own.

## 3. SET window / power bring-up (same session, before §1 step 2)

1. m1n1 pmgr probe at block base `0x8e080000` (macOS capture: ane0 reg range 1;
   full 73-range pmgr dump in the capture archive). Check whether the `ane_*`
   pwrstate cluster sits at **`0x8e08c000`** (= base + 0xc000) — hypothesis on
   t602x, derivation on T8103/T6001. Compare enumerated offsets against the T6020
   community rows (`260/2e0/4000/4008`).
2. Clock/power gates for bring-up come from the macOS IORegistry capture:
   `clock-ids=[0x13e,0x13f,0x140,0x141]`, `power-gates`/`clock-gates=0x1d9`,
   ANE MMIO `0x84000000` size 0x2000000, dart-ane0 at `0x85800000` (4×16 KB).

## 4. Optional staging capture (before dual-boot, macOS side)

The weight-attachment point is the e5rt loader (MIL BLOBFILE external keyed by
`model.anehash`; staging descriptors are generated at load, not shipped in the
bundle). If reachable, capture the load-time weight DMA staging on BOTH hosts
(ANECompilerService/Espresso trace) — a family difference there would explain a
t6021 map deviation found in §1 without any program bytes changing.

## Known failure modes

- **Map applied at load, not firmware**: if §1 shows a t6021-specific map, do not
  assume firmware — the libane Linux path performs its own staging; bisect by
  capturing the tile-channel contents after `ane_bind_kernel` (are weights permuted
  in memory, or does the engine read them permuted?). Distinguishes loader vs engine.
- **Segmentation differences**: count programs by distinct `.e5` content, never by
  bundle-dir count or `anehash` (addendum-3 lesson).
- **Path salting**: any re-compilation for comparison must use byte-identical
  absolute MIL paths (mint_aneforge v3 canonical workroot rule).
- **Do not re-derive offline**: receipts 2026-09-17-t6021-plane-derivation.md and the
  mints addendum 4 mark the e5-descriptor correlation route dead — no weight payload
  or descriptors exist in the container.
