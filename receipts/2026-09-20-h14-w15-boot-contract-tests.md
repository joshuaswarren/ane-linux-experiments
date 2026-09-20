# H14/T6021 W15 — boot-state resolution, contract units, probe repairs; CPU-only (2026-09-20)

Lane: M2BootImplementation, isolated worktree
`/home/joshuawarren/src/omarchy-ane/.work/boot-w15`, branch
`feat/t6021-ane-boot-w15`. No device contact, no MMIO, no driver load
from this lane. Main tree untouched (dirty state preserved).

## Shipped

Commits (pushed to `joshuaswarren/omarchy-ane`):

- **4b48ce2** `ane/t6021: W15 boot-state resolution + contract units;
  probe readiness/ownership repairs` — 8 files, +775/−108.
- **5f6892d** `ane/t6021: correct init-suballocation producer fields
  per Main disasm review` — comment-only (decimal/hex fix: `+0x24` →
  `0x18`; `[0x10]` = config size, not a dup).
- **c2f94b9** `ane/t6021: fail fw_boot before ANY MMIO write; shared
  acceptance predicate; template +0xC0=4 resolved` — Main review
  round 3 (see Corrections).
- **d40e65c** `record resolved RVBAR lifecycle in boot state report`
- **2f06caf** `no engine-aperture reads while ANE domain gated;
  unambiguous skip-path note`
- **5b0724e** `sourced init-suballocation fill per corrected audit
  pass5b-5d/6`
- **63d70cf** `FWIM surface 0x500000 per config+0x138; READY->WAKE->DONE
  ack transition` (Main/audit 751caa4)

### New files

- `ane/t6021/ane_t6021_boot.h` — pure boot-contract units, shared
  kernel/userspace: RVBAR entry fold
  (`0x0081000000000001 | (x & 0xff7efffffffff800)`; mask clears bits
  0–10, 48, 55, **retains bit 11**), latch/entry decode
  (`tbnz w0,#0`, ANE_Init 0x95e9878), SCRATCH0/1 u64 split (low32 →
  0x01840048 first, dsb st), closed-field init-suballocation fill
  (`[0x00]` = FWIM DVA legacy branch, `[0x68]` = 64, template zeros +
  template+0xC0 = 4). Anchors: rvbar-width, legacy-init-publication,
  mapper-callchain passes 1–5 (3762aee, 12be074, 04630ef, c364f24).
- `ane/t6021/ane_t6021_boot.c` — boot state resolution behind
  `fw_boot=1`. All reads individually whitelist-cited (W8/W10 live
  RVBAR=0x1; CPU_STATUS 0x1400048 phase-1 S2 + W10 0x2a; mailbox
  controls 0x1408110/4 W10-live 0x00020001; SCRATCH 0x1840048..64
  phase-1 S2 + first_resume re-reads). **Boot write sequence GATED on one
  complete-preflight flag (`boot_preflight_complete = false`):
  preboot engine table (`eng+0xb38/0xb98/0xbf8 ← 0x01ff01ff`), RVBAR
  resolution, CPU_CONTROL release and SCRATCH publication run
  start-to-finish once every named prerequisite closes, or not at
  all — `fw_boot=1` FAILS the probe (-ENODATA) BEFORE any MMIO
  write; `fw_boot=0` binds status-only. No force path exists. The
  pass5 "dev+0x784 bit0 has no writer" claim is itself under review
  (alias/indirect absence not definitive) and gates nothing.
- `ane/t6021_boot.h` sourced fill (5b0724e): ane_t6021_init_sources
  {fw_dva, ipc_dva, cfg_size, pool_dma, pool_word0} → [0x00]/[0x08]/
  [0x10]/[0x18]/[0x58]/[0x60]/[0x68] + template[0x00]=0 +
  template+0xC0=4; open [0x20]/[0x28]/[0x30]/[0x50] and gaps
  [0x34-37]/[0x64-67] stay caller-zeroed; publication fenced.
- `tools/h14_boot_regression.c` — shipped host regression, 39 checks
  (independently generated golden init image):
  fold vectors (bit 9/10/11/47/48/55/56 algebra), latch decode,
  acceptance round-trips (`entry_bits(compose(x)) == x & mask` for
  clean iovas; explicit loss cases), scratch split/join, init-fill
  exact image + fw-consumed-zone fence. **31/31 PASS**, exit 0.

### Repairs (Main review items, all addressed)

1. Honest state split: `booted`-after-status-reads removed →
   `power_gated` / `cpu_started` / `fw_alive` / `booted`; top-comment
   "status-only proves coprocessor alive" removed.
2. Probe order: staging + boot BEFORE any transport use (old order ran
   the EP0/EP1 session pre-fwload — the W10-proven pointless class
   behind the W5/W6 SError aborts; phrased without causal overclaim).
3. fwload return checked; with `fw_boot=1` a staging failure fails the
   probe with the ACTUAL staging error (no deferred-EINVAL masking);
   status-only continues with a log.
4. Single `ane_t6021_cleanup()` for every failure path and remove():
   IRQ freed FIRST (threaded IRQ read MMIO + drained rings it must not
   outlive), then rings + mutex, then fw surface (old shutdown label
   leaked it after a boot_probe error), then genpd.
5. 64-bit coherent DMA mask set once in probe BEFORE `rtkit_init`
   allocations (was set inside fwload, after the rings allocated).
6. Dead code removed: `ane_t6021_mbi_boot` + `mbi_table_ready` (no
   callers repo-wide). MGMT watch moved off the +0x1170000 CNTVCT
   mirror (W10) onto the real ASC mailbox: `i2a_control` EMPTY gate +
   pop-on-read `RECV0/1` (+0x1408830/8). CSNE PING/MGMT fenced on
   `booted` (conservative wording: W5/W6 sends failed with no fw
   staged; cause not isolated).

## Verification receipts

- Host regression: `gcc -Wall -Wextra -O2 -I ane/t6021 -o
  tools/h14_boot_regression tools/h14_boot_regression.c &&
  ./tools/h14_boot_regression` → `PASSED: 31 checks, 0 failures`,
  exit 0 (run in the worktree, 2026-09-20).
- Module: `make KERNELDIR=~/src/omarchy-linux ARCH=arm64
  CROSS_COMPILE=aarch64-linux-gnu-` → builds `ane_t6021.ko`, zero
  warnings/errors (two independent greps + incremental rebuild).
- Push receipt: `4b48ce2..5f6892d feat/t6021-ane-boot-w15 ->
  origin` (GitHub joshuaswarren/omarchy-ane).

## Pass5b-5d/6 incorporation (5b0724e)

- Init field contract corrected: `[0x08]` = 'IPC ' surface DVA
  (dev+0x988 = AllocateSharedMemorySurface out-param, tag 0x49504320);
  `[0x10]` = config+0x138 image byte-count (u32 zext), NOT a dup;
  `[0x18]` = 0x10000000 − 0x500000 = 0x0fb00000; `[0x50]` = zext u32 [x23+4] (object
  open); `[0x58]` = pool DMA base; `[0x60]` = pool word0;
  template+0xC0 = 4 (Main raw anchors, pass5 all-zero withdrawn).
- Ack registers split: first-alive beacon = SCRATCH0 (selene fn 0x86EC
  → index 0; host-side consumer OPEN); init-ack = SCRATCH7 (fn 0x71A4
  0x77cc-0x77f0, the kext-polled register). fw_alive watches SCRATCH0;
  booted requires the SCRATCH7 init ack.
- Linux allocation map (legacy branch): FWIM = config+0x138
  byte-count = 0x500000 (Main, audit 751caa4 — ANE_FW_BUF_SIZE grown
  0x400000 -> 0x500000; the earlier "superset of vmsize" framing
  withdrawn, the config semantic is honored directly); 'IPC ' =
  min(config+4, dev+0x3A70 cap) — cap numeric open; suballoc 0x174
  from a Linux pool (pool total size open); RTBuddy sizes never
  referenced.
- Ack model (751caa4, supersedes pass6 SCRATCH0-beacon reading):
  single register SCRATCH7, transition-based — READY 0x08042006
  pre-wake, host wake 0xf7fbdff9, fw consumes, DONE 0x08042006; a
  bare ==ACK poll is a stale-ack hazard; SCRATCH0 marker not the
  alive gate; fw_alive only on post-wake DONE.

## Exact remaining source-backed hardware gates (owners named)

1. **Provider first-enable equivalence** — kext
   `enableDeviceClock(1,dev+0x8F0)/enableDevicePower(1,&out,…)`
   (0x95d1d48/0x95d1d90); internal gate-ID arrays runtime-populated.
   Linux substitute today: genpd raise + supplier links (islands
   verified ACTUAL=0xf by the W3 gate). Owner: audit lane.
2. **RVBAR lifecycle fork** — live state reads bit0 set + entry 0
   (W8/W10). Candidate readings: (a) entry 0 = ASC boot ROM (kext
   local order continues with CPU_CONTROL 0→0x10, RVBAR untouched),
   (b) programmed/latched state only a reset lifecycle reaches. Owner:
   M2ResetLifecycle (ANE_CleanupForColdReboot_gated, island
   power-cycle RVBAR semantics, dev+0x41f provenance).
3. **Init publication** — fw consumes `[0x08]..[0x68]`; remaining
   Linux-source opens: IPC surface size numeric (min(config+4,
   dev+0x3A70 cap) — cap needs the h14g config blob field map), pool
   total size, `[0x30]`/`[0x50]` semantics, and the SCRATCH0
   first-alive beacon's host-side consumer.

## Hardware step: NOT APPROVED (Main, 2026-09-20)

No hardware command proposed or executed. Boot prerequisites remain
unresolved; the write sequence cannot partially fire for diagnostics
(complete-preflight gate). A future proposal requires the preflight
items closed first.

## Corrections applied during review (Main)

1. `+0x24` in pass5 was DECIMAL 24 = 0x18: init `[0x08]` =
   `*(dev+0x988+0x18)` (Params-pattern DVA of a second surface,
   identity undecoded); `[0x10]` = config size (x9 overwritten before
   the stp), not a dup.
2. Template `+0xC0 = 4` RESOLVED correct by Main raw anchors
   (0x9612b78/7c/80); pass5's all-zeros template read withdrawn by
   Main. Conditional `|=0x10` separate, still unqualified, not set.
3. pass5 header table incomplete: +0x50/+0x58/+0x60 pending pass5b
   (audit lane correcting).
4. No partial mutating boot: preboot table writes removed from the
   blocked path; single complete-preflight gate.
5. Acceptance predicate factored + tested; no-MMIO-before-preflight
   enforced in boot_probe.

MMIO writes from this lane: none.
