# jw14m2 (T6021 / M2 Max) macOS-side ANE capture, 2026-09-17

Verdict: **CAPTURED.** Deep collector run submitted and verified retrievable; full raw
IORegistry archived; the `ane0` device's own `reg` corroborates a **pmgr+0xc000** window on
t6021 — macOS-side evidence for the SET-base hypothesis, with pwrstate *offsets* still
requiring the Linux/m1n1 side. Parakeet divisor: in scope per owner lift of the no-install
constraint; follows as a separate receipt (owner priority: archive pushed first, host can
reboot to Linux at any time).

## Machine + reachability

- `ssh jw14m2.rhino-beaver.ts.net` (`hostname` → `JW14M2.local` — reachability receipt;
  the `laptop` alias still times out on the sleeping host, MagicDNS name works).
- `Mac14,5`, `Apple M2 Max`, 12 cores, 96 GB (`hw.memsize` 103079215104 = 96 GiB),
  macOS 26.6.2 (25G83), `target-type` J414c, platform `t6021`.
- Label **t6021 everywhere** (t602x family, sibling of the T6020 rows; never t6020, never
  "base M2").

## 1. Collector, deep mode (v0.6.4 = commit 112c32c4)

- Scripts (`collect_common/deep/macos/quick/submit/bench_matrix`) extracted from
  `mlx-omarchy` tag `v0.6.4`, staged in `/tmp/t6021-capture` on the Mac, run with
  `--out t6021-deep.tar.gz --submit https://mlx-omarchy-community-data.joshua-s-warren.workers.dev`
  (exit 0, 10.5 s — no mlx wheel on the host, so correctness/benchmark/profile sections
  self-record as unavailable, exactly as designed).
- Archive sha256 = **`a3e974f8e6f98febee4635fc8c381114d8ad0ecd979b0a29371e7e4bc3b07a0c`**
  (4648 bytes; deterministic bytes verified identical locally).
- Submitted; **row sha256 = `a3e974f8e6f98febee4635fc8c381114d8ad0ecd979b0a29371e7e4bc3b07a0c`**
  (dedup key = archive content hash). Receipt URL:
  `https://mlx-omarchy-community-data.joshua-s-warren.workers.dev/v1/results/a3e974f8e6f98febee4635fc8c381114d8ad0ecd979b0a29371e7e4bc3b07a0c`
  — GET'd back after upload: row reads `kind=deep, model=Mac14,5, chip=Apple M2 Max,
  kernel="Darwin 25.6.0 (macOS 26.6.2 (25G83))"`. UA `mlx-omarchy-collector/1` (collector
  default, kept).
- The row's `quick.json` carries the **untruncated ane0 reg**: all three ranges decoded
  below are in the submitted row. The pmgr node's 1168-byte reg is still capped at 64
  bytes by the collector (`truncated: ["reg_bytes:pmgr"]`) — inherent to v0.6.4's probe;
  the authoritative full pmgr reg is the raw dump in this archive.
- Collector quirk observed (upstream fix candidate, not edited here): `AAPL,phandle` is
  byte-swapped in the row (`ane0` row phandle 0x69010000; actual DT phandle **0x169** —
  the blob is little-endian, collector does `from_bytes(..., "big")`).

## 2. Raw IORegistry / pmgr / DART / ANE (authoritative artifacts)

`ioreg-full.txt.gz` (8.0 MB text), `ioreg-ioservice.plist.gz` (28.1 MB `-a -p IOService -l`
plist), `node-ane0.txt`, `node-dart-ane0.txt`, `node-pmgr.txt`, `h11anein.txt`,
`decoded-nodes.json` (reg arrays decoded u64-LE).

- **ane0 device**: `ane0@84000000 <AppleARMIODevice>`, compatible `ane,t8020`,
  phandle 0x169, `interrupts` = 0x374 (AIC), `iommu-parent` = 0x16b (mapper-ane0).
  **reg = 3 ranges:**
  | range | base | size | meaning |
  |---|---|---|---|
  | 1 | `0x84000000` | `0x2000000` | ANE MMIO |
  | 2 | `0x8e080000` | `0x4034` | pmgr block base window |
  | 3 | `0x8e08c000` | `0x4000` | **pmgr + 0xc000, 16 KB — the SET region window** |
  DT-shaped props captured verbatim: `ane-id`=0, `ane-subtype`=0, `ane-type`=0xa0,
  `die-id`=0, `die-ane-id`=0, `clock-ids`=[0x13e,0x13f,0x140,0x141],
  `clock-gates`/`power-gates`=0x1d9, `segment-names`="__TEXT;__DATA", `segment-ranges`
  (3 segments), `pre-loaded`=1, `uuid` 8782905F-39FA-361B-9884-E61379EBC67E.
- **dart-ane0**: `dart-ane0@85800000`, phandle 0x16a, `dart-id`=0x25, `dart-options`=0x25,
  `interrupts`=0x375, `bypass-15` present (empty), `dapf-instance-0` blob captured.
  **reg = 4 ranges × 16 KB**: `0x85800000`, `0x85810000`, `0x85820000`, `0x85804000`.
  No `#iommu-cells` is surfaced by IORegistry (DT-only prop — record: not available from
  this side); the mapper nub `mapper-ane0@0` (`iommu-mapper`, phandle 0x16b, `reg`=0) is
  the IOMMU frontend.
- **pmgr**: `pmgr@8E080000 <AppleARMIODevice>` — **block base `0x8e080000`**, first reg
  range size `0x80000` (512 KB), 73 reg ranges total (full blob in `ioreg-full.txt.gz`
  / `node-pmgr.txt`). The node carries `voltage-states*` tables and ANE-flavored platform
  knobs (`ane-dpe`, `ane0-{slow,fast}-{bw,af,afr}-bw-dvfs-filter`).
- **ANE driver node**: `H11ANE` (`H11ANEIn`, `com.apple.driver.AppleH11ANEInterface`),
  matched `ane,t8020`, `FirmwareLoaded`=Yes, DeviceProperties: arch string **`h14g`**,
  **16 cores**, ANEVersion=128, MinorVersion=17, HWBoardType=160, CPUSubType=5.
  `AppleH13ANEInterface` / `AppleH16ANEInterface` classes: **empty** on this host (probes
  returned nothing) — the H13/H16 naming does not apply to t6021; it is an
  H11-driver/h14g-generation part.

### The t602x SET-base question — what this capture settles and what it does not

On T8103 and T6001 the SET region announces itself as the `ane_*` pwrstate cluster at/above
`+0xc000` inside the ANE pmgr block, and **base + `0xc000` equals the m1n1 `ps_map`
constant** (verified live: jwm1 `0x23b70c000`, jw16 `0x28e08c000`). The T6020 community
rows show ANE domains at `260/2e0/4000/4008` and **no `0xc000` cluster**, so for t602x
`+0xc000` is a **hypothesis**, not a derivation.

What this macOS capture **does** settle for t6021:

- The pmgr block base is `0x8e080000` (node name + reg range 1) — the candidate SET base
  under the hypothesis is therefore **`0x8e08c000`**.
- Apple's own ANE device node is granted a **16 KB window at exactly pmgr+0xc000**
  (ane0 reg range 3), alongside a partial pmgr-base window. On T8103/T6001 the same
  relative offset is where the ANE pwrstate cluster lives and where `ps_map` points.
  This is macOS-side corroboration that the *address relationship* survives on t6021.

What it **does not** settle:

- **Pwrstate *offsets* are not available from macOS IORegistry.** v0.6.4's finding holds on
  this machine: the pmgr node supplies the block base only; the per-domain
  power-controller children / pwrstate offsets (`260/2e0/4000/4008`-style) simply do not
  appear on this side. Confirming that the `ane_*` cluster actually sits at `0x8e08c000`
  on t6021 (and enumerating its offsets) **requires the Linux/m1n1 side on this same
  machine** (m1n1 `pmgr` adt/tools probe against `0x8e080000+0xc000`).

## 3. ANE compiler backend provenance

Full detail: `ane-compiler-provenance.txt` in this directory. Headlines:

- Live generation string **`h14g`**, 16 cores (IORegistry DeviceProperties).
- `ANECompiler.framework` v**9.509.0** (com.apple.ANECompiler); kext
  `AppleH11ANEInterface` v**9.512.0**; daemons `/usr/libexec/aned`, `/usr/libexec/aneuserd`.
- Framework/kext bundles on disk are plist-only stubs — binaries live in the dyld shared
  cache / boot kernel collection, so no compiler binary strings were extractable read-only
  within scope. No `ANECompilerService.framework` on this build.

## 4. Parakeet macOS divisor — cross-pin fails; T6021 self-golden divisor TAKEN

Owner lifted the no-install constraint mid-run (2026-09-17). The M1-Ultra-methodology
battery ran on this host after the archive push: **the M1-family 104-token / `db501a8c`
guard refused `.ane` and `.all` alike (107 tokens ≠ 104, both at warm0, 0/1 holds
each)** — divergence is universal across compute units on t6021 (first mismatch at
token index 99; dot-run tail + junk token). Per discipline no cross-pin number was
claimed. ADDENDUM (same day, appended to the divisor receipt): a **T6021 self-consistent
golden was minted** (3× byte-identical runs; 107 tokens, transcript `344a28e1…`; `.all`
mint identical), and both batteries then held it **13/13**:
**`.ane` median 215.8 ms (runs 2–10; spread 9.1 ms, no drift), `.all` median 242.9 ms
(runs 2–10; scheduler settles −22.6 ms over the window, thermal clean, AC 65 W)**.
Label: **T6021-ONLY reference — NOT token-for-token comparable to the M1 Ultra
292.2/305.8 ms numbers** (107- vs 104-token golden); does not substitute for the
same-die T8103 divisor; purpose is the macOS reference for this machine's Linux run.
Full detail: `receipts/2026-09-17-jw14m2-t6021-parakeet-divisor.md` (addendum section).

## Gaps — could NOT capture, with reasons

1. **Pwrstate offsets / `ane_*` pwrstate cluster enumeration** — not exposed by macOS
   IORegistry (pmgr supplies block base only). Needs Linux/m1n1 on this machine.
2. **ANE firmware image bytes/version file** — no image on disk under
   `/usr/share/firmware/` or framework/kext Resources; it ships inside
   `BootKernelExtensions.kc`. State recorded via IORegistry (`FirmwareLoaded`=Yes,
   ANEVersion=128, minor 17) only; extracting the KC was out of scope.
3. **Compiler binary h-generation table strings** — binaries are cache-resident
   (dyld shared cache); on-disk framework bundles are stubs. Recorded the versions +
   the live driver's `h14g` instead.
4. **`#iommu-cells`** — DT-only property, not surfaced by IORegistry.
5. **coremltools/Parakeet pre-check** — neither installed at capture time (no mlx wheel
   either), so the collector's correctness/benchmark/profile sections are
   unavailable-by-design in the row; divisor now in scope per owner, pending install.
6. **powermetrics ANE power sample** — requires root; recorded as a clean miss by the
   collector (no passwordless sudo per constraints).

## What the Linux-side follow-up needs (make it mechanical)

When jw14m2 is dual-booted (same machine, so every constant below is directly comparable):

1. m1n1 boot + `pmgr` probe: confirm the `ane_*` pwrstate cluster sits at **`0x8e08c000`**
   (= block base `0x8e080000` + `0xc000`) — hypothesis vs derivation resolved.
2. Enumerate ANE pwrstate offsets/ids in that cluster and compare against the T6020
   community rows (`260/2e0/4000/4008`).
3. Devicetree capture of `ane0`/`dart-ane0`/`mapper-ane0` with this macOS archive open
   side-by-side (reg, interrupts, phandles 0x169/0x16a/0x16b, `dart-id` 0x25).
4. Re-run `collect_quick.py` on Linux so the row's `truncated` caps (`darts/phandles`)
   can be reconciled against the full DT; then deep-run for the community row.
5. DAPF addresses from `dapf-instance-0` (blob captured here) vs Linux DAPF setup.

## Mutations on jw14m2 (complete list)

`/tmp/t6021-capture/` (collector scripts, deep archive, log) — removed after this push.
Nothing else written; no installs, no sudo. (Parakeet installs, if any, are listed in the
follow-up divisor receipt.)
