# IOMMU_CACHE + sid 15 bypass — 2026-09-24 21:10 UTC

Ran on jw14m2-linux from insmod (`fw_cache_test=1`), not a platform
bind. The bind path hangs before probe on this boot.

## Map
Both segment-ranges, `IOMMU_READ|IOMMU_WRITE|IOMMU_CACHE` forced.
DATA IOVA corrected to `0x100000c4000` (the live table had an extra 0).
`iommu_iova_to_phys(0x10000000000) = 0x10000848000`.

## PTE
dart-ane0 TCR[15] read back `0x2`.
Leaf PTE `0x000fff1000084801`: valid, bit 1 clear, PA `0x10000848000`.

## Release
ane_cpu ACTUAL `0xf` (`ps=0x1f0003ff`). CPU_STATUS `0x28`.
SCRATCH7 `0` for 5 s. I2A `0x00020001`, recv0 `0`.

Negative. A cached mapping is not the missing fetch step.
