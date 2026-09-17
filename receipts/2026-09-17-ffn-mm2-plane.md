# FFN MM2 weight-plane layout: decomposition SOLVED, chain program CRT blocked by silu-LUT mixing
# 2026-09-17 (jw16, T6001, module 1fc2e02, map_mode=3)

## Verdict

The FFN family now computes correctly on the ANE — **by decomposition, not by
cracking the 28-task chain program**. The two FFN matmul geometries were
CRT-measured independently, the measured maps were implemented in
`encodeLinearParity` (mil-hwx-compiler branch `ffn-mm2-plane`), and MINTED
bundles device-gate at **rel_l2 0.000208** across rngs {11,33,57} for both
geometries. The chain program (route 1) got a working isolation tool
(silu-gated single-row readout) and a numbers-backed negative: the chain's mm2
readout through the device is a **signed mix of neighboring payload halves**,
not a single-half fetch, so single-position CRT cannot decode it. Next probe:
impulse-response measurement of the mm2 mixing kernel, then deconvolution.

## Route 2 (decomposition): per-geometry CRT fetch maps

Method: identical to probe3's crt4 — fill the packed-constant section with
fp16 `((i mod m)+1)`, one-hot input lane, read output row 0, per-run bias
control from a zeros fill, CRT over mods {3,5,7,11,13,17,19} with {23,29}
verification. Programs compiled with mil-hwxc 5bd7ad5 (identity packing for
these geometries). Const payload localized by two-rng diff: bundle bytes
[8192, 8399232), with a 2432-byte section header at [8192, 10624) that is
load-bearing (patching it makes libane refuse the bundle: "task stream does
not name every surface"). All patterns patched AFTER the header.

### mm1 — (375, 1024, 4096) uniform linear, 256 groups of 16

    P_half(g, c, L) = 16384 · π₂₅₆(g) + c + 16·L
    π₂₅₆(g)         = (g & ~31) | ((g & 15) << 1) | ((g >> 4) & 1)

The SAME inverse permutation as the certified 64-plane oproj case, generalized
to 256 planes: within each 32-plane superblock, group g reads plane
`32·(g>>5) + ((g&15)<<1) + ((g>>4)&1)`. Measured exactly (all 256 bases
aligned, remainder 0; lane delta L=0→1023 is 16368 = 16·1023, no wrap;
verification mods: 0/4096 mismatches on both lanes).

### mm2 — (375, 4096, 1024) uniform linear, 64 groups of 16

    c <  8:  P_half(g, c, L) = 32768 · (2g)     + 8·L + c
    c >= 8:  P_half(g, c, L) = 32768 · (2g + 1) + 8·L + (c − 8)

IDENTITY group order (unlike mm1!) — every group base strictly 65536 halves
apart — but each 16-output group is split across TWO 32768-half planes with
lane stride 8 (measured lane delta 32760 = 8·4095, no wrap). This is exactly
the asymmetry byte-parity cannot see and why per-family CRT was mandatory.

### Emitter fix (mil-hwx-compiler, branch ffn-mm2-plane)

`encodeLinearParity` uniform mode (plugins/H13/H13Program.cpp):
- `(375,1024,4096)`: the existing g_inv permutation loop, now gated on
  (reduction==1024, columns==4096) — the formula is bit-exact for 256 planes.
- `(375,4096,1024)`: new `mm2ColumnSplit` branch writing the 8/8 c-split
  two-plane layout above.
- All other geometries keep identity packing (byte-parity oracles intact).

Gates run on jw16 against the rebuilt compiler (clang 22, gnustep prefix from
jwm1's `~/.local/mil-hwx-gnustep`, binary rebuilt in
`~/src/mil-hwx-compiler/build/mil-hwxc`):

| gate | result |
| --- | --- |
| `build/test_h13_encoding`, `build/test_h13_anec` | OK / OK |
| `tests/test_h13_parity.py build/mil-hwxc` | PASS (874 cases, 1748 artifacts) |
| dev_gate_ffn mm1 rngs 11/33/57 | 0.000208 / 0.000208 / 0.000208 — PASS |
| dev_gate_ffn mm2 rngs 11/33/57 | 0.000208 / 0.000207 / 0.000207 — PASS |

`scripts/dev_gate_ffn.py` compiles real-weight + real-bias programs with the
compiler under test and executes them via libane-strict-fill; budget 0.05,
exit 0 on PASS. Gate is on MINTED bundles (not repacked probes); the mm1
bundle sha is recorded in the gate JSON output. As-emitted (pre-fix) controls
measured rel_l2 1.3704 (mm1) / 1.4166 (mm2) — the oproj-class failure,
reproduced for both new geometries.

Consequence: the FFN bucket can move to the ANE as two linear island programs
(mm1 island + mm2 island) with the already-certified linear placement path —
no chain program needed. Engine wiring (a second placed family, ff1+ff2
per layer) is engine-side follow-up for Main; the compiler side is done.

## Route 1 (chain program): isolation tool built, decode blocked — numbers

Target: island-ffn-L00-f1 (28-task chain, const section 16,837,632 bytes at
bundle offset 25728, located by the 128-byte kFFNChainKernelHeader appearing
exactly 256 times). MM1 tiles: 256 × 32960 B (128 B kernel header + 32 B bias
strip + 32768 B weights); MM2: 160 × 49216 B (6-feat) + 16 × 32832 B (4-feat).

1. **Blanket permutation does not transfer.** Repacking MM1 tiles per the
   standalone π₂₅₆ map (bias strips moving with the group, headers put) moved
   chain rel_l2 only 0.9197 → 0.9145 (ref = fp32 silu-chain; four bias-
   immediate variants 0.9046–0.9145). The chain's per-stage fetch maps are
   properties of ITS task stream, not the standalone linear programs'.
2. **Isolation tool (works).** All MM1 cells 0.0 except one +512 cell; MM1
   bias strips set to −0.2502441 (0xB401) to cancel the folded 0x3401
   immediate → every inactive silu input is exactly 0 (silu(0)=0), and the
   hot cell lights exactly one silu row: `y_j = W2'[j, r_hot] · h` with h
   constant (ones-fill minus zeros-fill = h exactly, frac_within_1 = 1.000).
   Chain output verified linear in W2: halving the whole MM2 payload halves y
   (median ratio 0.5, rel diff 0.5).
3. **The negative.** With that readout, CRT residues are exact integers for
   m=3 (v ∈ {1,2,3}, quant err 0.000) but polluted for every larger modulus:
   near-integer fraction m=4: 0.062, m=5: 0.203 (five distinct non-integer
   values spanning −1.7…7.8, spacing ≈2.4), m=7: 0.031, m=9: 0.000, m=13:
   0.000. The readout is a signed mix of NEIGHBORING payload halves (some
   readings exceed any written pattern value → negative stencil weights),
   i.e. the chain's mm2 fetch does not map one output column to one payload
   half. m=3 alone cannot anchor a CRT (positions span 8.4 M halves).
   Pitfalls ruled out en route (all measured): mm2 region IS live at the
   patched offsets; the 2432-byte section header and the 128-byte per-tile
   headers are load-bearing; silu(−512) is NOT 0 on this ANE (LUT clamp ≈
   −1.7e-3/row, and rows must be gated to exact 0, not approximately 0 — an
   all-zero-input bundle ignores its weights entirely).
4. **Next probe (named).** Measure the mm2 mixing kernel directly: with the
   isolation tool, fill mm2 with a single non-zero half at position p and
   read the per-j response vector k_j(p) for p in a window around an
   arbitrary anchor (the response is linear in the payload, verified by the
   0.5× experiment). Then deconvolve: positions = argmax over shifted
   responses, or CRT on deconvolved residues. Estimated cost: ~2 device runs
   per window position; a 32–64 position window characterizes the stencil.

## Host notes (jw16)

- llm-inference.service stopped before device work (lock inode 12 free);
  **restarted and confirmed active** at close-out.
- Staged on jw16: `~/src/mil-hwx-compiler` (branch source + rebuilt binary +
  gnustep prefix), `/tmp/ffnprobe/*` (all probe bundles, P maps, scripts:
  ffn_crt_probe.py, ffn_repack_gate.py, dev_gate_ffn.py, ffn_chain_probe.py,
  ffn_chain_mm2_crt.py). /tmp had 32 GiB free; scratch cleaned.
- jwm1 was NOT touched (read-only copies of the chain island bundle and the
  gnustep toolchain tarball only).

## Branch

- mil-hwx-compiler `ffn-mm2-plane` (from f122644): encodeLinearParity
  mm1Permutation256 gate + mm2ColumnSplit branch + scripts/dev_gate_ffn.py.
  63c1d3cf not an ancestor (verified at push).
