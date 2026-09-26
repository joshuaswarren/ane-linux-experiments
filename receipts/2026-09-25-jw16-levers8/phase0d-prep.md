# Phase 0 prep — sourced identity values, running-kernel driver proof, post-HELLO analysis (2026-09-26)

All read-only. No DT enable, reboot, CPU_RUN, extra SRAM, tunable
writes, implementation, or enable.

## 1. Exact board-id / dram-vendor-id values (sourced from this host)

Source: this host's own saved ADT
(receipts/2026-09-25-jw16-levers6/artifacts/jw16-adt-embedded.bin,
341,376 B, J316cAP/MacBookPro18,2), ADT property encoding
name[32] + u32le length + value:

- **board-id = 0** (u32, LE 00000000)
- **dram-vendor-id = 0** (u32, LE 00000000)
- **dram-capacity = 8** (u32, LE 00000008 — units consistent with
  8 GiB × 8 = 64 GB, matching this host)

These are the boot chain's OWN values (iBoot-written), so they are
authoritative for a future DT apple,board-id / apple,dram-vendor-id /
apple,dram-capacity addition. The live DT does NOT carry any of these
properties anywhere (full-tree property-name search: 0 hits) — they
exist only in the ADT, confirming they must be explicitly added to the
pmp node before probe() can pass its `required_by` gates. Whether the
firmware accepts zero board/vendor ids is a firmware-behavior question
we cannot answer offline; the values are nonetheless exactly what this
host's boot chain declares.

## 2. apple_pmp exists in the RUNNING stock kernel (not just source)

- CONFIG_APPLE_PMP=y + CONFIG_APPLE_PMP_REPORT=y (/proc/config.gz).
- /lib/modules/$(uname -r)/modules.builtin lists
  `kernel/drivers/soc/apple/pmp.ko` (built-in; no .ko on disk to load).
- /proc/kallsyms contains 55 pmp-crate Rust symbols
  (`_RNv…pmp…IovaTableEntry`, rtkit Buffer impls, FwNode property
  readers) at live addresses.
- /sys/bus/platform/drivers/apple_pmp/ exists with bind/unbind/uevent
  and NO bound devices — dormant exactly because the DT node is
  disabled.

## 3. Stock driver actions AFTER HELLO (pmp.rs recv_message order)

1. GET_IOVA_TABLE: driver maps the DT `apple,pio-ranges` (4 entries)
   into the pmp DART at PIO_VM_BASE 0xc0000000, granule 0x100000,
   IOMMU_READ|WRITE|MMIO — i.e. immediately after HELLO the firmware
   gains DMA reachability to its PIO (rail-register) ranges.
2. MALLOC / FREE: coherent buffers, sizes chosen by the firmware.
3. SET_BUF: firmware designates the value buffer (u64 read from its
   head).
4. REGISTER_IOREG: firmware names an IOREG (0x30-byte name); driver
   copies DT `apple,tunable-<name>` payload into the value buffer and
   replies (index, size). Missing name → `unknown property` dev_info,
   registered size 0.
5. SET_IOREG: firmware requests application of registered entry
   #index; driver replies with the LENGTH ONLY — the firmware performs
   and interprets the rail write itself.

## 4. Can the handshake safely stop before any rail writes?

**No in-tree gate exists.** The driver never initiates SET_IOREG, but
it cannot refuse one either: once the endpoint is started, every
firmware request is answered. The only source-level lever is the
tunable PAYLOAD (size 0 when the DT table is missing). Whether a
size-0 SET_IOREG is a firmware no-op, a defaults-application, or an
error is UNVERIFIABLE from source — this is the central open risk for
any stock-driver boot, and it is why verified tunable payloads (or an
instrumented driver that refuses SET_IOREG — implementation work,
out of scope now) must precede any CPU start. DVFS itself has no code
path in pmp.rs; the map113/DVFS_CMD surface remains the separately
gated host-driven experiment.

## 5. TUNS observation (from phase0b, feeding the smallest experiment)

The bootargs TUNS entry carries 0x01078a34 — outside the 1 MiB SRAM
extent as a raw address, so it is either a differently-based pointer
or structured value. It is plausibly the boot chain's pointer to ITS
prepared tunables/material. Resolving TUNS is the most promising
read-only route to the missing apple,tunable-* payloads from the most
authoritative source possible (iBoot's own preparation), without any
CPU start.

## 6. Smallest safe remaining experiment (recommendation, not executed)

Bounded read at/around the TUNS target to resolve the boot chain's
tunable material (exact address derivation needs one more look at the
SRAM layout conventions in pmp.rs/RTKit — e.g. whether 0x01078a34 is
PIO-window-relative). This stays pure-read and could yield the exact
tunable name→payload set, converting the "size-0 unconfigured rails"
unknown into verified metadata BEFORE any CPU start is ever
considered. Alternative (weaker): nothing further off-device; all
remaining steps involve CPU start and await the reviewed gate.

## 7. Wording fix applied

phase0c-results.md heading corrected per Main: "coherent ARM64
executable head" — the whole image is NOT validated by the 4 KiB read.
