# T6021 (M2 Max) cold-boot CSNE command path: firmware alive, no reply (2026-09-24)

Kernel 7.1.13-ARCH-m2mbox (asahi-7.1.13-3 + mailbox poll-TX fix). All
engine offsets are relative to the ANE aperture 0x284000000.

## Result

On a cold boot the firmware runs: its list builder fills the BSS with a
0x28-stride linked list (3504 and 3512 non-zero words across
vm 0x4ac000..0x4fc000 on two boots). Every host-to-firmware command
attempt produced no reply:

| attempt | transport | reply |
|---|---|---|
| SET_SNE_PMU_BASE2 id 0x2a, 8 B, header only | A2I_SEND0 setup + cmd doorbell, bit 0x2 @ +0x1844000 | none in 60 s |
| PRINT_ENABLE 0x04 / START 0x00 / SET_SNE_PMU_BASE2 0x29 (u64 0x28e08c000) / CONFIG_GET 0x03 | same, one per 15 s | none |
| same boot, SCRATCH0 = 0x1fb08000, SCRATCH1 = 0, SCRATCH7 = WAKE 0xf7fbdff9 | SCRATCH bank | none in 60 s |

Across all three, IRQ53 (mailbox-recv) stayed at 0, I2A_CTRL stayed at
0x00020001, and I2A_RECV0 stayed at 0. Cmd-buffer slot bytes and the
SCRATCH values were never modified by the firmware. SCRATCH7 read 0
before every host write, so the firmware never wrote phase-1 READY.

Verdict: the host-side writes land (A2I_SEND0 reads back the written
word), but the firmware never consumes them. The kext's ANE_Init polls
SCRATCH7 == READY before it publishes a table or wakes the firmware
(static receipt 2026-09-24-t6021-macos-start-sequence §28). The KextRe
round-2 decode (lane/kext-re-clean) says the kext sends only after the
second ANECPU interrupt ("channel description table ready"). This
firmware reaches neither state, so the gate is upstream of any command.

## Exact bytes

Cmd buffer: IOVA 0x1fb08000, 256 KiB, mapped with IOMMU_CACHE.

```
slot 0x00 PRINT_ENABLE      00 00 00 00 04 00 00 00 00 00 00 00
slot 0x10 START             00 00 00 00 00 00 00 00 00 00 00 00
slot 0x20 SET_SNE_PMU_BASE2 00 00 00 00 29 00 00 00 00 c0 08 8e 02 00 00 00
slot 0x30 CONFIG_GET        00 00 00 00 03 00 00 00 00 00 00 00 00 00 00 00
doorbell words (A2I_SEND0)  0x0c000000, 0x0c000010, 0x10000020, 0x10000030
earlier setup doorbell      0x001400001fb08000 (IOVA | size_code 0x40 << 44 | unit 1 << 52)
```

## Setup that reproduces the running firmware (cold boot)

1. VENC parent +0x2902803e0 <- 0x1000000f (AUTO_ENABLE, bit 28). With
   the parent set this way, the leaves 0x8000/0x8008/0x8010/0x8018 grant
   to 0x3ff on a plain 0xf write. Without bit 28 they latch 0x30f.
2. TCR15 = 2 on all three dart-ane instances (+0x180103c/+0x181103c/+0x182103c).
3. Map TEXT/DATA through the rtclient map-only path (fw_cache_test=1 fw_map_only=1).
4. Clear SCRATCH 0x1840050..0x184006c to 0, then CPU_CONTROL 0 -> 0x10.
   CPU_STATUS reads 0x28 after release. In the later command runs it
   read 0x08 (bit 5 clear); that transition is not decoded yet.

Scripts: autoenable.sh, split_release.sh, send_cmd4.sh, scratch_ring.sh.
Module: ane_csne_pmu.c.

## Driver bug fixed

ane_t6021_rtclient_main.c, ane_cache_test(): `eng` was used at the
mailbox read without being mapped. insmod segfaulted (NULL + 0x1408114),
the CPU was never released, and the module was left pinned. The fix is
to ioremap_np(0x284000000, 32 MiB) before first use, with an unwind on
failure (rtclient-null-eng-fix.patch). After the fix, the module's own
release path runs cleanly (insmod rc 0, status 0x2a -> 0x28).

## Page-table walk (no defect)

For IOVA 0x10000000000 the live descriptor sits at pgd[16]. The leaf PTE
0x000fff1000084801 points at PA 0x10000848000. That is the same on every
boot and matches iova_to_phys. The rtclient's own `L1[0]` print uses
the wrong index, so the zero it reports is a logging artifact.

## Warm vs cold

The 19:41 boot that produced the series2 captures was warm: its PMGR
pw32 writes from 18:08 were never cleared by a reboot. On a cold boot,
pw32 0xd2cc <- 3 reads back 0.

## Next blocker

Phase-1 READY: SCRATCH7 is never written by the firmware. Per §27/§28,
its preconditions are the boot-subsystem inits 0..4 and the endpoint
config object ([x19,#0x98] != 0). The command path cannot be tested
until the firmware announces readiness.
