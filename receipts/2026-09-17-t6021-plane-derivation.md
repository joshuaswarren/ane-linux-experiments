# T6021/h14g weight-plane derivation from e5 oracles — known-answer gate FAILS by data absence (2026-09-17)

Verdict: **NO T6021 MAP CLAIMABLE.** The specified offline derivation (parse `H13D.e5`,
match the pair28 watermark to emitted positions, reproduce the three known H13 formulas)
was executed against the macstudio (M1) mints and **failed on all three formulas — by
data absence, not value mismatch**: the e5bundlecache program embeds **no weight payload
and no weight descriptors**, so there are no emitted positions to match against. Per the
acceptance gate, **no t6021 plane map may be claimed** from these artifacts. The script
(`tools/derive_e5_plane_map.py`) reproduces every number in this receipt; machine
verdict in `.local/ane-plane-derive/gate-verdict.json`.

## 1. `H13D.e5` / `H14C.e5` container layout (inferred, macstudio oproj 2320 B canonical)

The e5 program is an Espresso flat typed-object archive (u32-tagged records, u16 field
offset tables, negative i32 back-references for interned sub-objects). Named anchors at
fixed offsets; the only geometry-variant bytes are the four tensor-size fields marked †.

| offset | content |
|---|---|
| 0x000–0x080 | top object: tag + u16 field-offset table; section directory (3 u32 offsets {0x8ec, 0x728, 0x4d0} + more), two negative back-refs |
| 0x080–0x0e2 | `__build_info__` records: `built-for-profiling=false`, `input-file-path=/private/tmp/…/model.mil` (embedded **verbatim — path-salts the whole encoding**), `espressoc-component-ANECompiler=9.509.0`, `espressoc-component-MIL=3520.4.1`, `espressoc-version=3525.1.1`, `on-device-compilation=true` |
| 0x0e2–0x22c | serializer bookkeeping (offset tables, interned refs) |
| 0x22c–0x270 | `main_ane` + `main/main_ane/model.anehash` bundle entries |
| 0x270–0x39c | symbol/section tables (`__build_info__`, sizes {0x194, 0x190, 0xc} …) |
| 0x39c–0x3f8 | **task block A — OUTPUT tensor**: record + u32s `{0x30, byte_count†, 0, 0x38, 0x14, 0x34, 0x48}` |
| 0x3f8–0x440 | output shape dict: `{2, rowbytes†, 0, 2, 0, 0, 2, rows=375, 0, cols†, 0, 0xa4}` |
| 0x440–0x494 | **task block B — INPUT tensor**: same record shape, `byte_count†` |
| 0x494–0x4f8 | input shape dict (rowbytes†, rows, cols†) |
| 0x4f8–0x520 | tail records (offsets {0x220, 0x1ec, 0x190, 0x12c, 0xd0, 0x7c, 0x4c}) |
| 0x520–0x6b0 | symbol records: `main`, `main__block_0`, `main__Op0_AneInference`, `…__arg_frame`, `…__op_attrs` |
| 0x6b0–0x740 | tensor symbols `t1` (input), `t0` (BLOBFILE weights const) |
| 0x740–0x78c | tensor attribute dicts (offsets {0x17c, 0x134, 0xe8, 0x9c, 0x58, 0x14}) |
| 0x78c–0x85c | `__build_info__` / `__extern_out_main__` / `__extern_in_main__` symbols with extern buffer sizes (0xbb800 / 0x2ee000)† |
| 0x85c–0x8e0 | `__const__` (descriptor {…, 0x120}) and `__text__` (descriptor {…, 0x150}) — no weight content |
| 0x8e0–0x8fc | `__sym_desc__` record |
| 0x8fc–0x908 | sym_desc content: `{magic 0x02e4e5, u16 chip_id, u32 0}` — **chip id: macstudio 0x6002 (t6002), jw14m2 0x6021 (T6021)** |

**No weight bytes, no weight byte counts (0x200000/0x800000 absent), no source-offset
table, no plane descriptor table exist anywhere in the container.** `t0` references the
MIL BLOBFILE const — weights stay EXTERNAL (`weights.bin`, consumed by e5rt at load
time). `model.anehash` = 128 ASCII hex chars (64-B digest) — a compile-instance cache
key (provenance-bound, per the k16 duplicate-cache evidence), not program content and
not fp16 data. The compile cache contains ONLY `*.e5` + `model.anehash`
(mint-summary.json file lists confirm; the repo archive trimmed nothing else).

## 2. Known-answer validation — per-formula verdicts (macstudio mints)

Method as specified: parse e5 descriptors, correlate pair28 watermark values with
emitted positions, compare against the H13 maps derived independently via the hwx route
+ device gates.

| geometry | expected H13 map | verdict |
|---|---|---|
| oproj (375,1024,1024) | `g_inv(P) = ((P>>5)<<5)\|((P&1)<<4)\|((P>>1)&15)` | **FAIL — NOT REPRODUCIBLE FROM E5** |
| mm1 (375,1024,4096) | `P_half(g,c,L) = 16384·pi256(g) + c + 16L`, `pi256(g) = (g&~31)\|((g&15)<<1)\|((g>>4)&1)` | **FAIL — NOT REPRODUCIBLE FROM E5** |
| mm2 (375,4096,1024) | identity group order, 16-output group split over two 32768-half planes (`c<8 → 32768·2g + 8L + c`, `c≥8 → 32768·(2g+1) + 8L + (c−8)`) | **FAIL — NOT REPRODUCIBLE FROM E5** |

Per the gate: this is the real finding. It is a third variant of the two the ticket
anticipated: **the e5 container does not pack differently — it packs NO weights**. The
hwx/`.anec` route EMBEDS a permuted weight section (the 2432-B section header regime);
the e5 route eliminates that stage entirely (compile-only; weights stream through the
BLOBFILE external at e5rt load time). The permutation, wherever it is applied (e5rt
load-time DMA staging or firmware), is family-loader behavior that is absent from the
archived bytes. No parsing of these bundles can be "wrong" — there is nothing there to
parse.

What the watermark DID establish (all verified in-script):
- `weights.bin` at rest is **identity-ordered**: 524288/524288 pairs (oproj) and
  2097152/2097152 pairs (mm1, mm2 regenerated via `make_capture.py`; whole-file
  sha256 prefixes `8b4a1451cdb2dbfa` / `60b167f9b0b996fb` match the mints receipt).
- No permutation exists in ANY archived artifact.

## 3. What byte-parity does and does not prove about t6021

Established (all script-verified):
- `h14g ≡ h13` byte-identical per geometry per host (6/6) — TargetArchitecture option
  does not steer these linear programs.
- Cross-host (macstudio vs jw14m2), after removing the path-salt shift (+24 B oproj,
  +16 B mm1/mm2 — the embedded `input-file-path` differs in length and re-offsets the
  serializer): **only the head region 0x000–0xdd (top tag 0x10→0x14 + one extra u32
  field; longer path string; section-offset table shifts; one shifted absolute-offset
  field at 0x780) plus the chip-id byte at 0x908 differ.** 158 of 2320 bytes for oproj
  (154 for mm1/mm2); program content 0xde–0x907 is byte-identical. This independently
  reproduces `insurance/fixed-path-experiment/classification.json` (same-path recompiles
  byte-identical; cross-host delta = exactly 1 byte at 0x908: 2 vs 33 = 0x6002 vs 0x6021).
- Cross-geometry accounting (same host): mm1 vs mm2 differ by **exactly 13 bytes**,
  mm1 vs oproj by 22 — every differing byte is an in/out tensor shape field, extern
  buffer size, or the geometry name inside the provenance path. mm1 and mm2 share a
  byte-identical 8 MiB weight blob yet have radically different known maps — the map
  difference is encoded NOWHERE in their programs.

Consequence, stated precisely: **program-side, the t6021 `H14C.e5` IS the H13
program. But program byte-parity does NOT predetermine the t6021 weight-plane map**,
because the map is not a program property — it lives in the load path (family-specific
runtime/firmware code that consumes identical program bytes). The t6021 weight map is
**UNDETERMINED by all archived artifacts**. The mints receipt's "host-flavored program"
framing is corrected here: the program is host-keyed (provenance + 1 chip-id byte), not
host-flavored; the jw14m2-mints-as-oracles-of-record conclusion survives trivially.

**Retraction of record (Main, 2026-09-17, quoted verbatim so the dead inference cannot
be picked back up):** *"I told you and the sibling lane that 'the H13-derived plane
maps transfer to t6021 program-side unchanged' and that M2 bring-up needs no new
weight-layout reverse engineering. That was wrong, and your refutation is decisive: the
map is not a program property, so program byte-parity cannot predetermine it."* The
same trap was closed in the sibling capture receipt §5.

**Weight-attachment path at load time (evidence-based answer to the open question):**
the e5 carries no weight reference beyond the const symbol `t0` (0x6b0 region) backed by
the `__const__` section descriptor — the BLOBFILE binding lives in the MIL (`model.mil`
names the external blob; `weights.bin` carries its own `0xdeadbeef` record with
`byte_count` + `data_offset=0x80`), and `model.anehash` keys the compiled program to
its weight payload. So the intended attachment is: **e5rt resolves the external BLOBFILE
at load time, keyed by the anehash cache entry, and stages weights into ANE memory
itself** — i.e., the staging descriptors (if any exist beyond trivial linear load) are
generated in the loader, not shipped in the bundle. That is exactly the unobserved
component; capture it on device day if reachable.

## 4. Reconciliation with the cross-host byte classification (T6021MacosCapture)

Fully consistent, no conflicts:
- Their "1 differing byte at 0x908 with identical paths" = my chip-id trailer finding
  (`__sym_desc__` content `{0x02e4e5, chip, 0}`); my head-region deltas are exactly
  their path-length salting (program length = 2320 + (pathlen − 31), confirmed:
  2320/2328/2344 for 31/39/56-char paths).
- Their k16 two-bundle retraction + `anehash`-is-provenance caveat adopted here:
  distinct `.e5` CONTENT was counted throughout; `model.anehash` never used as program
  evidence.
- No arch-derived DMA/plane-map regions exist for me to reconcile against — my
  derivation independently proves the negative (zero geometry-scaled fields outside the
  accounted shape/extern/path ranges).

## 5. The oracles are the device probes — re-priced

With the map undetermined offline, the minted bundles stop being "spare oracles" and
become **the device-side read-out experiments**: every archived program + its
identity-ordered pair28 `weights.bin` is a direct map probe the moment a t602x Linux
host exists — load, run, invert the watermark from observed behavior. Nothing needs
re-minting (re-minting would need macOS we may lose). This includes the
`insurance/` set: the fixed-path pair (`fixed-jw14m2-H14C.e5` / `fixed-macstudio-H13D.e5`,
the clean 1-byte family-delta evidence), the edge geometries (k16/k64/n1000), and the
synthesized H14C-from-H13 one-byte-flip candidate (stale-hashed, unvalidated — serves
as the acceptance test for any future e5 container loader, not as a map source).
Execution detail lives in `docs/t6021-weight-map-day-one-runbook.md`.

## 6. Next step (device verification, once a t602x Linux host exists)

The remaining t602x risk lives in the firmware/load path, not in program bytes:
1. On jw14m2 dual-booted to Linux (m1n1), run the minted e5 program (or the hwx-route
   equivalent) with the pair28 index-encoded weights and decode outputs: if the t6021
   engine applies the H13 interleave, outputs decode to the identity map under the
   known formulas; any deviation yields the t6021 map directly from the watermark.
2. Same session: read-verify the SET window hypothesis at `0x8e08c000` (pmgr base
   `0x8e080000` + 0xc000, per the macOS capture) — the pwrstate offsets needed for
   clock gating during the device run come from there.
3. Optional macOS-side pre-check (no device needed): capture the e5rt load-time weight
   DMA program (ANECompilerService/Espresso staging trace) on BOTH hosts — it should
   show whether the loader, not the program, carries any family-specific weight
   transformation.

## Reproduction

```sh
python3 tools/derive_e5_plane_map.py   # full layout, diffs, watermark, gate verdict
```
Work performed in worktree `~/.config/superpowers/worktrees/ane-linux-experiments/PlaneDerive`
(branch `agent/t6021-plane-derive`), read-only on the archived mints. mm1/mm2
`weights.bin` regenerated (not re-minted) via the archived `make_capture.py`.
