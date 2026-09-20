# jwm1 T8103 ANE device-tree values derived from Apple ADT — offline, review-ready (2026-09-20)

Lane: Jwm1AnePlan (node-value derivation). Host identity re-verified this lane:
serial `C02DP17UQ05P` (`/proc/device-tree/serial-number`), compatible
`apple,j293 apple,t8103 apple,arm-platform`, BuildManifest identity
`J293AP` (ApBoardID 0x24, ApChipID 0x8103). Correction: an earlier draft
of this receipt cited the `J313AP` identity — that is the MacBookAir
board (ApBoardID 0x26) in the same Universal manifest; both are T8103,
but jwm1's live `compatible` names j293, and every value below was parsed
from `DeviceTree.j293ap.adt`, the j293 board blob. **Method: offline bounded IPSW range extraction
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
| ANE complex (ADT reg0) | `0x26a000000` + `0x2000000` — context only; never claimed by the driver | 
| ANE engine (driver resource) | **`0x26bc04000` + `0x24000`** (complex + `0x1c04000`; the proven T6001 overlay uses the identical +0x1c04000 convention) |
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
Known-wrong address recorded as a dead end: the allbilly dtbo engine
`0x23b100000` (that is the AIC). The `0x26bc04000` platform name from the
September boots is NOT a dead end — see the resolved review points: it is
the engine subblock (complex + 0x1c04000) and is the base this fragment
adopts.

## Staged artifact

- [t8103-j293.ane.dtb](t8103-j293.ane.dtb) — stock `t8103-j293.dtb`
  (66,832 B) + three `iommu@26b8xxxxx` dart nodes + `ane@26a000000` + a
  `phandle 0xc5` on `ane_sys_cpu`; 67,656 B, sha256 above.
- [patch_j293_ane.py](patch_j293_ane.py) (deterministic text patch of the
  decompiled tree; phandles 0xc5-0xc8 verified unused in the original),
  [ane-fragment.dtsi](ane-fragment.dtsi) (fragment for review).
- Verification: dtc round-trip decompile-diff shows **additions only**; all
  values re-read from the compiled blob; no phandle collisions.

## Review points — resolved from source (Main directive, same day)

0. **Resource base corrected to the driver subblock `0x26bc04000`.** The
   first fragment used the ADT complex base `0x26a000000`; that was wrong.
   The T6001 live pattern, parsed from our own j316c ADT, fixes the
   convention on both qualified chips:

   | chip | ADT complex reg0 | proven driver engine base | offset |
   |---|---|---|---|
   | T6001 (jw16, live 104/104) | `0x284000000` + 0x2000000 | `0x285c04000` (t6001-j316c-set-domains.dts) | **+0x1c04000** |
   | T8103 (jwm1, this fragment) | `0x26a000000` + 0x2000000 | `0x26bc04000` | **+0x1c04000** |

   The September jwm1 evidence is therefore retracted as "wrong": the wedge
   dmesg `ane 26bc04000.ane:` and the schema4 `dt_node` were the correct
   subblock base, and the node NAME `ane@26a000000` (complex base, asserted
   by the v0.6.4 installed-state contract) coexists with it exactly as in
   the T6001 overlay (node `ane@284000000`, reg `0x285c04000`). Main's
   independent GPUworker numericbundle reviewed identity pins the same pair
   (`0x26bc04000` / 8 CPUs for jwm1-T8103; `0x285c04000` for jw16-T6001).
   m1n1's `fw/ane.py` TM formula (`complex + 0x1c24000`) is exploratory,
   was never hardware-validated in our receipts, and was not used.

1. **Aperture size: `0x24000` at base `0x26bc04000`.** The driver reaches
   its task manager at engine-relative `+0x20000` and task queues at
   `+0x21000` (`ANE_TM_BASE`/`ANE_TQ_BASE`, stable across eiln `main` →
   `6fa243a` → `44dd9bf`; queues span ≤ ~`0x21a40`), so `0x24000` — the
   proven T6001 overlay size — covers every engine offset the driver
   touches. Claiming the ADT's whole 32 MiB complex would make the ane
   resource contain the three dart resources (`complex+0x1800000..`), the
   exact platform resource-overlap that EBUSYs dart registration on M2
   (h14-w3). The staged dtb uses
   `reg = <0x02 0x6bc04000 0x00 0x24000>`; recompiled sha256
   `7472f4436b227c1fd95f51acb423ef56a369547852713d2e0d71664e91816bab` →
   superseded by `033a3fc4b0fb3f1f4e56315274995fff81c27a8857577fafda5d0b09b5791f23`
   after the base correction.
2. **Domain list: keep the explicit parent-then-child pair** `<0x82>,
   <0xc5>` (`ane_sys`, `ane_sys_cpu`). This exercises the multi-domain
   attach path that the T6001-proven boots used, and `ane_sys_cpu`'s
   pwrstate register is exactly `0x23b70c000` — the word the driver's
   powered-on guard reads — so genpd and the recovery guard observe the same
   bit. The `pd_count == 1` path also exists in the driver but is not the
   proven shape.
3. **SID 0: confirmed.** m1n1 drives the T8103 ANE darts at sid 0 (ttbr0),
   and the T6001 live pairing (`apple,t6000-dart`, `#iommu-cells = <1>`,
   sid 0, same mainline `apple_dart` driver family) is 104/104-qualified on
   jw16. `apple,t8103-dart` carries the same binding shape.
4. **dart reg3 (`0x26b804000` = complex+0x1804000): stays unmodeled.** The
   T6001 live overlay models exactly three darts the same way; the ADT's
   fourth block is unused by driver and m1n1 alike. Recorded so the
   omission is deliberate.

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

## Addendum 2 — staged exact-historical build (Main directive; STAGED, not deployed)

The five providers and DMA ranges are now carved-source-exact (see
[the wedge receipt addendum 3](../2026-09-20-jwm1-ane-first-load-wedge/receipt.md)):
the September working payload DTB (carved `1a72bc81…`) is the template, and
this patch mirrors it node-for-node.

Staged artifact (NOT deployed):

- `t8103-j293.ane.dtb` sha256
  `4ec4b87f36bc9f8f17d3a8213937144277a2197ff6f352ac24482ee20c76f280`
- [patch_j293_ane.py](patch_j293_ane.py) sha256
  `f1970bf14c49575325721601ecc38196e567ec94427856d6bfd14ec8739df3ff`
- [ane-fragment.dtsi](ane-fragment.dtsi) sha256
  `f41a9cbe3bb4883d31629b6afe6bdda62d36748497d2ea2b521b94a4424a34f7`

Reviewer build command (from the stock dtb, byte-identical to the backup):

```sh
dtc -I dtb -O dts -o j293.dts t8103-j293.stock.dtb   # stock = ea32173df3b0f782bf610f38fb390f90a777c16d4a4b2822c58b924bc6088328
python3 patch_j293_ane.py                            # j293.dts -> j293.ane.dts
dtc -I dts -O dtb -o t8103-j293.ane.dtb j293.ane.dts # -> 4ec4b87f…
```

Five provider parent chains (exactly the historical tree):

| provider | reg (pmgr@23b700000) | parent |
|---|---|---|
| ane_set1 @c010 | c010 | ane_base (@c008) |
| ane_set2 @c018 | c018 | ane_base |
| ane_set3 @c020 | c020 | ane_base |
| ane_set4 @c028 | c028 | ane_base |
| ane_set5 @c030 | c030 | ane_base |

ane_base @c008 → parent ane_sys_cpu @c000 → parent ane_sys @470.
ane node `power-domains = <&ane_set1>, …, <&ane_set5>` (five; no direct
sys/sys_cpu entries — mirrors history).

Three DMA ranges (one per ANE DART, all identical):

```
apple,dma-range = <0x00 0x00 0x00 0xe0000000>;   /* iommu@26b800000/810000/820000 */
```

(absent in the deployed dtb — the concrete wrong-buffer DMA candidate).
Deployment remains gated: Main review → dtb install → update-m1n1 → one
reboot → probe acceptance (ps act 0xffffff, ANERD pd[0..4], ps verify
err=0) → guard module 99e8b8b5… load.

## Addendum 3 — reproducible build + machine verification (Main directive)

`patch_j293_ane.py` (hardcoded paths) is superseded by:

- [build_ane_dtb.py](build_ane_dtb.py) sha256
  `31ab0ccaed96a8789b759ee57feddae1239c126765ee490fe9f1657a8afb82bf` —
  argparse CLI (`stock_dtb out_dtb --workdir DIR`); asserts the stock input
  sha256 (`ea32173d…`) and phandle-collision absence (0xc5, 0xc9-0xce
  unused) before any write; refuses output unless it matches the staged
  reviewed hash.
- [verify_ane_dt.py](verify_ane_dt.py) sha256
  `14e9b8ef76d533eefd15f41b1ec287b308a0bcec0c430e68da6eb812dd67194e` —
  canonical property comparison of the built dtb against the carved
  historical tree (ane node + three ANE DARTs + all six SET-word pmgr
  pwrstates; phandle refs resolved, sid-0 cells and node-name cosmetics
  normalized).

Independent verification, executed:

```sh
python3 build_ane_dtb.py t8103-j293.stock.dtb t8103-j293.ane.dtb --workdir work
# -> built … sha256 4ec4b87f… output hash matches the staged reviewed build
python3 verify_ane_dt.py t8103-j293.ane.dtb carved-8c12e9f.dtb
# -> CANONICAL-EQUAL: ane node, 3 ANE DARTs, and all six SET-word pmgr
#    pwrstate nodes match the carved historical working tree (rc=0)
```

Negative control (deployed two-provider dtb vs the same carve): rc=1, four
DIFF blocks (ANE, three darts, pmgr SET nodes) — the verifier discriminates.
`ane-fragment.dtsi` regenerated from the verified build (sha
`f41a9cbe…`). Still STAGED: no deployment until Main's review + the
amended guard tip ride together.

## Addendum 4 — verifier v2 (Main review fixes) + independent-run paths

`verify_ane_dt.py` v2 (sha256
`28d3a6587b3b8cef1c82d7f583292a83e060f1754a98b6dc5ac02283cba0bca1`) fixes the
false positive: the provider regex expected `}` instead of ` {`, so every
provider block was ABSENT on both sides and the earlier CANONICAL-EQUAL was
vacuous for the chains. v2:

- exact node-boundary extraction (`find_block` brace matching) for every
  expected block; ALL blocks required present (absence fails loudly);
- formatting-insensitive canonicalization (whitespace collapsed);
- arity-aware phandle resolution from `#iommu-cells` — SID cells preserved,
  never erased; `interrupt-parent` resolved too;
- negative self-tests (`--selftest`): provider-parent-only mutation and
  DMA-range-only mutation, each must FAIL (verified: 1 and 3 diff blocks).

Independent run (all inputs committed):

```sh
cd receipts/2026-09-20-jwm1-ane-dt-derivation
python3 build_ane_dtb.py evidence/stock-t8103-j293.dtb built.ane.dtb --workdir work
python3 verify_ane_dt.py built.ane.dtb \
  ../2026-09-20-jwm1-ane-first-load-wedge/evidence/carved-8c12e9f.dtb work
python3 verify_ane_dt.py built.ane.dtb \
  ../2026-09-20-jwm1-ane-first-load-wedge/evidence/carved-8c12e9f.dtb work --selftest
```

Executed here: build → `4ec4b87f…` (matches staged); compare →
CANONICAL-EQUAL; selftests → both mutations correctly FAIL. Inputs:
`evidence/stock-t8103-j293.dtb` (`ea32173d…`); historical carve at
`receipts/2026-09-20-jwm1-ane-first-load-wedge/evidence/carved-8c12e9f.dtb`
(`1a72bc81…`). Deployment remains HELD.
