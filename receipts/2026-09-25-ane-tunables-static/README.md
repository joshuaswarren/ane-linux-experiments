# ANE tunables in macOS kernelcaches: T8103 extracted, T6001/T6021 absent (2026-09-25)

Owner: Jw16Levers5 (off-device static work on PVE; jw16 itself untouched —
owned by Jw16Levers6). Template: m1n1 2abf3af3 `src/tunables_static.c`.

## Method (validated on T8103 first)

Record format discovered empirically on jwm1's `kernelcache.release.mac13g.macho`
(macOS 13.5 22G74): 16-byte records `{u32 offset, u32 clear, u32 set, u32 pad=0}`
separated by 4-byte zero words, table terminated by `{0xffffffff ×3, 0}` —
with a separator zero before the terminator and before the first record.
Offsets carry flag bits in the top nibble (bit30 observed: `0x40000000|off`).
Backward walk from every terminator; tables ≥ 4 entries.

**Not** the m1n1 layout: m1n1's C `struct entry {u32 off, clear, set}` (12
bytes, AoS) does not occur verbatim; the naive byte search of m1n1's zipped
tables hits nothing (0/8).

## T8103 (jwm1 mac13g) — extraction + m1n1 cross-check

179 tunable tables found, ALL in `__DATA` (0 in every other segment).
The eight m1n1 ANE sequences (`t8103_ane_tunables[]`) identify as follows
(matching = flag-stripped offset-sequence equality; full data in
`results/t8103-ane-tunables.json`):

| m1n1 sequence | m1n1 base PA | copies in cache | clear/set identical to m1n1 |
|---|---|---:|---|
| ane_pmgr | 0x26a000000 | 2 (va 0xfffffe000b8a8614, 0xfffffe000b8a891c) | 0 |
| ane_dart (×3 bases) | 0x26b800000/810000/820000 | **0 — absent** | — |
| ane_dapf | 0x26b804000 | **0 — absent** | — |
| ane_dpe_sys | 0x26b8f0000 | 15 | 0 |
| ane_perf | 0x26b908000 | 4 | 0 |
| ane_dpe_soc | 0x26b8f4000 | 3 | 0 |

Two material findings:

1. **m1n1's published values are normalized, not verbatim.** Every matched
   table has clear/set diffs vs the raw cache data. Examples (ane_pmgr,
   copy va 0xfffffe000b8a891c): raw `{0x38, 0xffffffff, 0x50020}` vs m1n1
   `{0x38, 0xffff, 0x50020}`; raw `{0x900, 0x100, 0x100}` vs m1n1
   `{0x900, 0x1, 0x101}`; raw `{0x600, 0x1ffffff, 0x1ffffff}` matches. The
   raw cache values are the authoritative XNU data; the per-entry diff lists
   are in the JSON.
2. **m1n1's ane_dart/ane_dapf tables are not in this cache at all.** Their
   distinctive values (0x80016100, 0xf0f0f, 0x2b45c000, 0x3b70c033) occur
   NOWHERE in the 96 MB image. m1n1's dart/dapf sequences must derive from a
   different XNU source (older build or hand construction). Also open: no
   reference to the found table VAs exists in any form scanned (adrp+add,
   adrp+ldr, movz/movk absolute, u32/u64 pointer words) — the consumer
   linkage is unresolved (runtime-assembled addresses or an unscored
   relocation form).

## T6001 — absent from both containers

- 22G74 stub `kernelcache.release.mac13j.macho` (the cache AneClockM1
  disassembled AppleT6000PMGR from): 88 terminators, **0 walkable tables** in
  `__DATA`/`__DATA_CONST`/every segment, under the T8103 format AND under
  every (stride 12–36 × lead-word) alternative model. The ANE kext
  (H11ANEIn / AppleH11ANEInterface) IS present (strings + PRELINK_INFO).
- 25G83 live base KC (`kernel.release.adx`, df5ee19f…): the ANE kext is not
  in the base kernel at all (no H11ANEIn/AppleT6000PMGR strings); any
  per-kext tables would live in `BootKernelExtensions.kc` (pull queued for
  the next macOS window).
- Independent corroboration: m1n1 2abf3af3 carries ANE tunable sequences for
  T8103 ONLY — no T600x sequences exist there either.

## T6021 — absent from both containers

- 13.5 22G74 `kernelcache.t6020.13.5-22G74.macho` (sha 9615a486…) and
  27.0 26A428 `kernelcache.t6020.27.0-26A428.macho` (sha 8304156f…): 88 and
  106 terminators respectively, **0 walkable tables in every segment**
  (including the 27.0-only `__DATA_SPTM`).

## Interpretation (consistent across three independent sources)

The tunable-sequence mechanism exists in XNU only where the HOST drives the
ANE (T8103: host TM/TQ, no ANE firmware — hence host-side fabric/DPE/op-point
pokes). On T600x/T602x the ANE runs its own firmware (selene; RTKit boot per
the omarchy-ane findings doc) which configures its own fabric/op-points, so
no hardcoded host tunable sequences exist — in XNU caches (this receipt) or
in m1n1. Consequence for consumers: a static (base PA, offset, clear, set)
list for T6001/T6021 ANE cannot be produced from these kernelcaches; the
fw_start tunable tables for the M2 rtclient leg must come from behavioral
capture (the M2 lane's kext-faithful hv traces), not from cache extraction.

## Reproduction

`tools/scan3.py <cache.macho> [min_entries]` prints every table (file offset,
VA, segment, entries). `tools/identify.py <scan-output>` performs the m1n1
cross-check. `tools/extract_tunables.py` embeds the m1n1 reference tables.
`results/` carries all five scan outputs and the T8103 JSON.
