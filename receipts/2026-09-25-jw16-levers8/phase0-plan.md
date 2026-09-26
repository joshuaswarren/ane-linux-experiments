# Phase 0 plan — PMP SRAM read-only probe on jw16 (for review; NOT executed)

Owner: Jw16Levers8. Status: DRAFT FOR REVIEW per Main directive. Every
address below is cited from source (AsahiLinux/linux asahi branch
drivers/soc/apple/pmp.rs @ /tmp/pmp.rs read 2026-09-26), the live
device tree, or prior executed captures. No writes, no reboot, no rail
changes anywhere in this plan.

## Objective

One bit of discrimination decides the whole PMP route: is the PMP
coprocessor's SRAM holding iBoot-parked firmware under Asahi Linux, or
is it empty? The in-tree apple_pmp driver loads NO firmware
(`rtkit::RtKit::new(&dev, None, 0, …)` — verified in source), so:

- PARKED → the bounded bring-up route exists inside the in-tree driver
  (DT enable + board-id props + tunables), Phase 1 as scoped in
  addendum.md §3.
- EMPTY → firmware staging is a hard prerequisite (identity-verified
  blob + loading the in-tree driver cannot do), PMP goes back to the
  metadata-extraction track with no hardware path.

## Known-safe power prerequisites (all read-only facts)

1. **PMP power domain is apple,always-on.** Live DT:
   `/soc/power-management@28e080000/power-controller@2d8`, label
   `pmp`, compatible `apple,t6000-pmgr-pwrstate`, reg = pmgr offset
   **0x2d8** size 4, `apple,always-on` boolean present (phandle 22,
   referenced by /soc/pmp@28e700000's power-domains). An always-on
   domain is not power-gated: its MMIO is powered whenever the SoC is,
   which removes the unpowered-read bus-hang class that wedged the M2
   on ANE engine reads (different block, no gating here).
2. **Optional confirmation read** (kernel-class, same registers the
   bound apple-pmgr-pwrstate driver reads on every boot): PS word at
   pmgr base 0x28e080000 + 0x2d8 → expect DESIRED==ACTUAL==0xf. If the
   kernel's own pmgr mapping exposes this (it maps the same window its
   pwrstate driver uses), read via the kernel module's ioremapped view
   of pmgr+0x2d8 only. Stop criteria unchanged if it reads otherwise.
3. **Driver-unbound proof**: /soc/pmp@28e700000 status=disabled →
   apple_pmp never probed → no kernel object currently touches the PMP
   windows (re-verified at execution time in the same boot).
4. **Precedent**: the 2026-09-23 m1max-ane-clock probe already executed
   this exact read class safely against the adjacent PMP report block
   (0x28e3c0000, mapped 0x28e3c0000-0x28e3dffff, read + cleared one
   notify bit, exited clean — the ONLY write there, not repeated here).

## Addresses (single source table)

| what | address | size | source |
|---|---|---|---|
| PMP SRAM/MMIO window ("pmp" reg) | 0x28e700000 | 0x80000 mapped by pmp.rs (ADT SRAM extent is 0x100000 — we stay INSIDE the driver's 0x80000 map) | node name + pmp.rs:46 |
| BOOTARGS_OFFSET (u32 ptr) | window + 0x22c | 4 B | pmp.rs:48 |
| BOOTARGS_SIZE (u32) | window + 0x230 | 4 B | pmp.rs:49 |
| ASC wrap window ("asc" reg) | 0x28ec00000 | 0x4000 | node + pmp.rs:47 |
| CPU_CONTROL | ASC + 0x44 | 4 B | pmp.rs:50-51 |
| CPU_RUN bit | bit 4 of CPU_CONTROL | — | pmp.rs:51 |

## Probe actions (bounded, read-only)

Quiesce first: llm-inference stopped, flock /tmp/m1-gpu.lock held,
ANE/GPU idle, netconsole armed, one throwaway module (single .c),
`readl` only, module unload at exit.

1. R-CPU: one readl(ASC + 0x44). Log. (Expect CPU_RUN=0: PMP quiesced
   since iBoot; nonzero is a finding — do NOT write, report.)
2. R-ARGS: readl(PMP + 0x22c) and readl(PMP + 0x230). Parked-fw
   signature = nonzero bootargs pointer/size.
3. R-HEAD: read 4096 bytes at PMP + 0. SHA-256 + entropy note.
4. R-ARGS-BODY: if R-ARGS pointer is sane (< 0x80000), read ≤ 4096
   bytes at PMP + pointer. SHA-256. Look for the BDID/DVID/DCAP key
   tags pmp.rs patches.
Total reads ≤ 8 KiB + 3 registers. No write of any kind; module does
not touch CPU_CONTROL, clocks, or DART.

## Discrimination

- Bootargs ptr nonzero + code-density head → PARKED: proceed to
  reviewed Phase-1 (DT status + apple,board-id/dram-vendor-id props +
  tunables metadata), still gated on firmware/tunables verification
  for anything beyond RTKit HELLO.
- Zero/uniform head or zero bootargs → EMPTY: no hardware PMP route
  until an identity-verified firmware blob exists; lane returns to
  metadata extraction only.

## Failure stop (any one aborts everything, no retry)

- SIGBUS/EIO or external abort in dmesg on any read.
- PS read (step 2 of preconditions) shows the domain not on.
- Netconsole/dmesg anomalies within the window.
- Module load/unload errors.
Abort = module unload only. Nothing persistent exists to roll back; a
wedged bus (not expected for an always-on domain, and never yet seen
for this read class) falls back to the documented reboot recovery,
which is safe here because nothing was written and the boot image is
unmodified.

## Open homework before execution (read-only, off-device)

1. ADT cross-check of the PMP SRAM extent (0x100000 per PMP-lane
   receipt) vs the driver's 0x80000 map — the probe stays inside
   0x80000 either way; reconcile for the record from
   jw16-adt-embedded.bin (pmgr reg[?]/pmp node) if the table carries
   it.
2. Decide the PS confirmation read implementation: kernel pmgr mapping
   reuse vs probe-module ioremap of pmgr+0x2d8 only (4 B).
3. Reviewer sign-off (Main/Joshua) — this document is the review
   input.

## What Phase 0 is NOT

No CPU_CONTROL write (no CPU_RUN). No bootargs patching. No DT
modification. No tunables. No map113/DVFS_CMD access. No rail state
change. No firmware loading. No reboot in the plan.
