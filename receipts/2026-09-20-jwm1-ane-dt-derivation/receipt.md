# jwm1 T8103 ANE device-tree values derived from Apple ADT — offline, review-ready (2026-09-20)

Lane: Jwm1AnePlan (node-value derivation). Host identity re-verified this lane:
serial `C02DP17UQ05P` (`/proc/device-tree/serial-number`), compatible
`apple,j293 apple,t8103 apple,arm-platform`, BuildManifest identity
`J313AP`/`ApChipID 0x8103`. **Method: offline bounded IPSW range extraction
from the already-pinned Apple CDN archive — no macOS boot, no device access,
no DT write, no reboot.** Same method and archive as
[2026-09-13-t6001-static-adt](2026-09-13-t6001-static-adt) (jw16's j316c
capture); this lane extends it to jwm1's j293ap board.

## Verdict

The ANE node set for jwm1 is now fully derived from primary sources and is
**ready for Main review**. The patched device tree
([t8103-j293.ane.dtb](t8103-j293.ane.dtb), sha256
`4a45f7b3f829d19a92db814e97d2b30cbc43f0e47d4333b4aebd0a7942c89cc9`) is staged
locally only — nothing installed to `/usr/lib/modules`, no `update-m1n1` run.

## Provenance chain (every hop hashed)

1. Archive: `UniversalMac_26.6.2_25G83_Restore.ipsw`
   (`updates.cdn-apple.com/2026SummerFCS/fullrestores/140-75212/A2A24B94-…`,
   19,772,231,540 B — byte-identical URL+size pinned in the t6001 receipt).
2. ZIP64 central directory @ `19772074236` (157,206 B) → member
   `Firmware/all_flash/DeviceTree.j293ap.im4p`, local header `18487081677`,
   stored 44,386 B → inflated 44,482 B.
3. IM4P sha256 `67c0d194347535bfc3a3325e4af5e065e6f0ec94735253c62fca015df44074b8`
   → lzfse-decoded `j293.adt` (312,096 B) sha256
   `db13e238ebf4d65a5d6027ae693c1a6efba035d6959c07222a52d842375b4152`.
   (j313ap sibling also extracted: im4p `82ca4e73…`, adt `dfde304a…`.)
4. Parse: m1n1 v1.6.1 `proxyclient/m1n1/adt.py`; address resolution through
   `/arm-io` ranges (range0: bus 0 → parent +0x2_00000000).

## Derived values (ADT ground truth)

| item | value |
|---|---|
| ANE engine | `0x26a000000` + `0x2000000` (ADT `/arm-io/ane` reg0 `0x6a000000` through range0) |
| ANE SET block | `0x23b700000` + `0x8c000` (reg1) — driver `of_match` pins `0x23b70c000` = `+0xc000`, consistent |
| ANE IRQ | AIC 416 (`0x1a0`), one IRQ, `interrupt-names = "ane"` per driver `platform_get_irq_byname` |
| ANE DARTs | `0x26b800000` / `0x26b810000` / `0x26b820000`, each `0x4000` (ADT `/arm-io/dart-ane` reg0-2); dart IRQ AIC 417 (`0x1a1`) |
| dart-ane reg3 | `0x26b804000` + `0x4000` exists in ADT; **unmodeled** (m1n1 `fw/ane.py` uses three; flagged for reviewer awareness) |
| Power states | **already in-tree**: `ane_sys` (phandle `0x82`, @0x470) and `ane_sys_cpu` (@0xc000, parent `0x82`) in the second PMGR `power-management@23b700000` |

Cross-checks that agree: m1n1 `fw/ane.py` (engine = ADT get_reg(0); three
dart registers; `ps_map["ane"] = 0x23b70c000`); the pinned driver tree
`omarchy-ane @44dd9bf` binding (engine by name, one named IRQ, `iommus`
mandatory, `power-domains` count from DT, per-compatible SET base); the
September working-boot facts (node name `ane@26a000000`, IRQs `0x1a0/0x1a1`).
Known-wrong addresses recorded as dead ends: allbilly dtbo engine
`0x23b100000` (that is the AIC), and the `0x26bc04000` platform name from the
September frozen-dtb (eiln-era address, pre-ADT; **not** this board's engine).

## Staged artifact

- [t8103-j293.ane.dtb](t8103-j293.ane.dtb) — stock `t8103-j293.dtb`
  (66,832 B) + three `iommu@26b8xxxxx` dart nodes + `ane@26a000000` + a
  `phandle 0xc5` on `ane_sys_cpu`; 67,656 B, sha256 above.
- [patch_j293_ane.py](patch_j293_ane.py) (deterministic text patch of the
  decompiled tree; phandles 0xc5-0xc8 verified unused in the original),
  [ane-fragment.dtsi](ane-fragment.dtsi) (fragment for review).
- Verification: dtc round-trip decompile-diff shows **additions only**; all
  values re-read from the compiled blob; no phandle collisions.

Review points (decisions wanted, not blockers to reading): (a) `power-domains`
listed parent-then-child `<ane_sys>, <ane_sys_cpu>` (mirrors the T6001
explicit-list pattern) vs child-only single domain; (b) dart SIDs fixed at 0
(m1n1 ttbr sid 0, T6001 precedent); (c) engine size taken from ADT
(`0x2000000`) rather than the T6001-shaped `0x24000`; (d) dart reg3 left
unmodeled.

## Deployment procedure (NOT executed — gated on review + the already-PASS reboot gate)

1. `sudo cp` the reviewed dtb over
   `/usr/lib/modules/7.1.13-3-2-ARCH/dtbs/t8103-j293.dtb` (keep backup).
2. `sudo update-m1n1` → assert `/boot/efi/m1n1/boot.bin` hash changed and
   `boot.bin.old` appeared.
3. Reboot (boot gate PASS per
   [boot-readiness audit](2026-09-20-jwm1-ane-boot-readiness-audit.md)) →
   `nproc` = 8, CPUs `0-7` online, `find /proc/device-tree -name '*ane*'`,
   compatible readback.
4. Load the pinned `ane.ko` → `/dev/accel/accel0` → the qualification ladder
   (fp16 smoke → compiler packages → schema-4 → islands → soak).
