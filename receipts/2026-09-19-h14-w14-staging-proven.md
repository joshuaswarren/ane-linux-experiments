# H14/T6021 W14 — staging milestone: reviewed drv 69c2b1ae binds clean on jw14m2, selene PRELOAD validated + DART-mapped (no boot) (2026-09-19)

Verdict: **STAGING PROVEN.** One approved probe run under exact reviewed
sources (drv `69c2b1ae…`, ko `30d6f990…`): module bound to
`284000000.ane`, eight-domain gate passed on live state (stage-1 RMW
skipped — snapshot showed all words already on/clear), read-only ASC
whitelist clean, firmware validated (sha256 + exact-image assertions)
and loaded into a DART-mapped 4 MiB coherent surface, iova recorded as
data. **No firmware boot, no SCRATCH/doorbell/RVBAR write, no retries,
no reboot.** No direct ANE/PMGR MMIO writes occurred; the DART mapping
(kernel iommu subsystem PTE programming for the coherent surface) and
module load/unload lifecycle changes did occur. With
`rtkit_transport=0 mbi_doorbell=0`, no write path is reachable in this
build (doorbell/a2i fenced by params; SCRATCH handshake unimplemented;
boot absent) — fenced write code exists in the tree and stays fenced.

## Execution (one pass, exact params)

- Pre: netconsole collector verified off-host BEFORE mutation —
  `/usr/local/sbin/fleet-netconsole-receiver.py` (pid 1566279, root,
  UDP :6666 → /var/log/fleet-netconsole.log) received plain-UDP and
  kernel-printk test lines from jw14m2 (192.168.3.103:6668 →
  192.168.10.235:6666, gw MAC 04:f4:1c:92:4c:c8).
- PS snapshot (stage 0, read-only): all eight words on/clear —
  `ane_cpu=0x0f0003ff` (ACTUAL=0xf, BUSY=0, AUTO_ENABLE=0), others
  0x1ff/0x2ff. → approved rule: skip stage-1 RMW.
- `rmmod` inert module (from the boundary-report loads), then ONE
  `insmod ane_t6021.ko allow_unqualified=1 fw_load=1 rtkit_transport=0
  mbi_doorbell=0` → **probe success**: gate pass, whitelist reads
  (SET=0, RVBAR=1, EDPRCR=0, VERS=0xe3044, RTB_STATUS=1, SCRATCH0-7=0),
  `loaded ane_t6021 (status-only bring-up, transport deferred; CSNE TX
  fenced)`, then `fwload: selene PRELOAD validated + DART-mapped: 3
  segs, entry 0x0, iova 0x000003ffffc00000 size 0x400000`. Bound
  (driver dir lists `ane@284000000`). All lines captured off-host by
  the fleet collector (18:31:47Z entries).
- `rmmod`: clean unwind (rings + fw surface DART PTEs torn down,
  driver unregistered, genpd detached). SError count 0; host up
  throughout.

## New pinned data

- Runtime-PM trap closed structurally: device runtime PM removed;
  first_resume runs explicitly from probe (18 added / 43 removed lines
  vs W10 drv; failure-path goto audit in W13a §3).
- `dma_alloc_coherent` on this device yields iova `0x3ffffc00000`
  (first data point for the DART stream-mapping question; NOT claimed
  to be the fw address space — stream mapping unverified).
- RVBAR reads `0x1` with CPU_CONTROL=0 and all domains on. The value-1
  observation is pinned; any latch/kext-semantics interpretation is NOT
  established (the kext skip-gate reading is kext-side only).

## Open bootstrap prerequisites (unchanged set, W13a §6)

Image placement constant (iBoot loader trace — in progress), page-table
patching contract, boot-args publication field, DART stream mapping
proof, reset ordering, post-boot gate. NO boot attempt until the full
set is evidenced.

## MMIO write table

No direct ANE/PMGR MMIO writes. Device-observable changes that DID
occur: dart-ane0 PTE programming for the coherent surface and the six
probe rings (kernel iommu subsystem), torn down at rmmod; module
load/unload lifecycle. PS words were read, not written — stage-1
skipped by the approved rule.
