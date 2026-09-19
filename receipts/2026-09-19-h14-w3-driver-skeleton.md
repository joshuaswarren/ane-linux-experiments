# H14/T6021 W3 — Linux driver skeleton (static, no device) (2026-09-19)

Verdict: **SKELETON BUILT — `ane_t6021.ko` cross-compiles and links against the
jw14m2 kernel tree on this box; every undefined symbol verified against the
kernel's export list; overlay rebased to the W1 architecture and dtc-clean.**
No device was touched. Compile status detail at §6 (built + linked + symbol
audit; modpost CRC check pending a vmlinux build in this tree, see below).

Branch: omarchy-ane `feat/t6021-ane-driver` (from `feat/t6021-rtkit-w2` @
6ad26b7). Ancestry: 63c1d3cf **absent in omarchy-ane** (W2 receipt noted the
same; N/A for this change).

## 1. What landed

```
ane/t6021/Makefile            out-of-tree module `ane_t6021` (ane/Makefile pattern)
ane/t6021/ane_t6021.h         constants + DT binding contract (see §2)
ane/t6021/ane_t6021_rtkit.c   mailbox ops, MGMT handshake, app-EP rings, doorbell codec
ane/t6021/ane_t6021_drv.c     platform driver: probe/genpd/ioremap/IRQ/PM
ane/t6021-j414c-ane.dts       overlay update (W1 architecture, installed-overlay consistent)
receipts/2026-09-19-h14-w3-driver-skeleton.md   (this file)
```

## 2. Driver (ane/t6021/ane_t6021_drv.c + .h)

- **DT probe** on `apple,t6021-ane` only; repo tier discipline kept: binds
  only behind `ane_t6021.allow_unqualified=1`, gate fires before any
  power-domain/MMIO/IRQ interaction (H13 `ane/src/ane_drv.c` pattern).
- **reg windows** (the ADT's three ane0 ranges, names are the binding):
  `engine` = whole 32 MiB block `0x284000000` (block-relative; the H13
  +0x1c04000 engine delta is GONE — kext never computes it, first touch
  external-aborted twice per the 2026-09-18 bisect), `pmgr` =
  `0x28e080000+0x4034` island words, `set` = `0x28e08c000+0x4000` mapped
  by address outside the resource API, read-only by repo rule (H13 SET
  precedent: direct SET writes external-abort).
- **genpd attach**: multi-domain loop from the H13 driver, consumes the six
  overlay domains (ane_cpu, set1..4, sys_mpm) through supplier links held
  RPM_ACTIVE; probe then holds the device awake for its lifetime.
- **AIC2 IRQ**: `platform_get_irq_byname(pdev, "ane")` (raw 884, level-high)
  requested threaded AFTER the first resume; handler = RTKit drain.
  dart-ane0's 885 is never touched (provider-owned, H13 rule).
- **First resume** = the W1 bisect ladder as read-only named stages: pmgr
  island words (`+0x2e0, +0x4000..0x4030`) + SET word 0, then the ASC
  status block (`RVBAR +0x1050000`, `VERS +0x1840000`, RTBuddy status
  `+0x1840088`, GPIO0, `CPU_CONTROL +0x1600044`, mailbox controls). The
  `dev_info` lines are the netconsole flush points phase1 §3 requires for
  the first live pass (the +0x1600000 block is write-evidenced /
  read-suspect; nothing in this driver writes it).
- **No engine writes anywhere.** There is no TM/TQ code at all: H14 has no
  host-side task manager (W1 §2 — the entire premise of the rewrite).

## 3. RTKit mailbox core (ane_t6021_rtkit.c)

C port of `rtkit/h14_rtkit_hello.py` (6ad26b7) with kernel-API semantics
from `drivers/soc/apple/mailbox.c` (ASC variant: ctrl 0x110/0x114, send
0x800/0x808, recv 0x830/0x838 at block +0x1608000 → ANE+0x1608xxx) and
`drivers/soc/apple/rtkit.c`:

- u64 msg0 as a full `writeq`/`readq` at SEND0/RECV0, ep at SEND1/RECV1
  (the 6ad26b7 u64-semantics fix is structural here, not a bug class to
  re-fix); FULL (bit 16) poll before send, EMPTY (bit 17) poll on recv.
- EPMAP accumulate + reply with the rtkit.c reply shape (LAST bit 51
  echo when the fw says LAST, MORE bit 0 otherwise), then STARTEP (ep
  bits 39:32, FLAG bit 1) for announced system endpoints (crashlog/
  syslog/debug/ioreport/oslog/tracekit); SET_IOP_PWR_STATE (selene
  initiates) → ACK echo; SET_AP_PWR_STATE_ACK incoming → app EPs
  started, `booted = true`.
- **App EP rings**: six `dma_alloc_coherent` rings at the kext config
  table sizes (INIT 64K, T2FC 256K, T2FH 256K, T2HS 64K, T2HC 128K,
  T2HT 64K), allocated at probe so STARTEP can fire from the MGMT path.
  DMA flows through the dart-ane0 providers via dma-iommu (device
  `iommus`); no hand-rolled DART programming.
- **Doorbell codec**: `offset[43:0] | size_code[51:44] | unit[53:52]`
  (W2 §3); encode picks unit 1 (×4K) below 1 MiB / unit 2 (×1M) above —
  the K14 SetupEndpoints size-class encoder. Receive side enforces the
  kext's `offset+size <= ring_size` bound in u64 (the 44-bit offset
  field cannot wrap through the u32 ring size), and a round-trip
  self-check runs at probe (unit-1 class for all three small ring
  sizes), refusing to bind on mismatch.
- **W4 stub, clearly marked**: `ane_t6021_csne_submit()` returns
  `-EOPNOTSUPP` with a dev_warn_once naming W4. CSNE_CMD ids needed by
  W4 (BOOT, PING, BUILDINFO, REG_FILE_LOAD, IPC_ENDPOINT_SET/UNSET,
  PROCEDURE_CALL, INFERENCE_CALL, BACK_CHANNEL_RPC) are in the header
  enum with the full-96 pointer to `fw_cmd_table.json`.
- Open question carried in code as `[INFERENCE]`: how the fw learns each
  app ring's DART address (RTKit-standard STARTEP buffer field is the
  candidate; the kext RTBuddy record decode did not pin it). W1/W4 pins
  it against the live exchange. Nothing here claims it is solved.

## 4. Binding + overlay (ane/t6021-j414c-ane.dts)

- Binding contract documented in `ane_t6021.h` (this repo keeps its
  binding as driver-of_match + overlay; no kernel Documentation tree):
  `compatible "apple,t6021-ane"`, reg-names `engine|pmgr|set`, one
  `ane` interrupt, `iommus` = dart-ane0 streams, six `power-domains`.
- Overlay: ane0 node now carries the three ADT reg ranges verbatim
  (`<0x2 0x84000000 0x0 0x2000000>, <0x2 0x8e080000 0x0 0x4034>,
  <0x2 0x8e08c000 0x0 0x4000>`); node name `ane@284000000` now matches
  its engine base. dart nodes UNCHANGED (installed, b877b87
  boot-proven three-node t8110 split; the ADT quartet's fourth window
  0x285804000 stays unsplit exactly as on T6001 — noted in the header).
- dtc -@ compile: clean exit 0 (remaining warnings are the inherent
  numeric-phandle-to-base-DTB class of any fdtoverlay plugin).
- Deployment coupling: the new driver requires the new overlay (old
  installed overlay has only `engine` reg → probe fails cleanly with
  -EINVAL on the missing `pmgr` resource; nothing half-probes).

## 5. Build verification (this box, `omp-studio-local`)

- Toolchain: `aarch64-linux-gnu-gcc (Debian 12.2.0-14) 12.2.0`; kernel
  tree `/home/joshuawarren/src/omarchy-linux` (Linux 7.1.6, arm64
  omarchy config already present; `modules_prepare` run first — the tree
  had no arm64 generated headers).
- Build: `make KERNELDIR=.../omarchy-linux ARCH=arm64
  CROSS_COMPILE=aarch64-linux-gnu-` → both objects compile warning-free,
  `LD [M] ane_t6021.ko` links (146,832 B).
- Modpost note (honest status): this kernel tree has never had a vmlinux
  build, so `Module.symvers` does not exist and stock modpost cannot
  verify symbols (it flagged even in-tree modules the same way). Two
  compensations:
  1. **Full export audit**: all 31 undefined symbols in the `.ko` were
     checked against the kernel tree's export list — 27 direct
     EXPORT_SYMBOL matches, `_dev_err`/`_dev_info`/`_dev_warn` via the
     `define_dev_printk_level` macro (drivers/base/core.c:5068, exports
     `EXPORT_SYMBOL(func)` per level), `alt_cb_patch_nops`
     (arch/arm64/kernel/alternative.c:305). **All 31 resolve.**
  2. A `make vmlinux` (then `make modules`) was started in this tree to
     produce a real `Module.symvers` and re-run the module build without
     `KBUILD_MODPOST_WARN`; if it lands post-receipt, the follow-up run
     is recorded in the session, not silently assumed.
- Status line: **built + linked + export-audited**; modpost CRC
  verification = recipe-verified (§6 tracks it).

## 6. What is NOT here (scope)

- CSNE_CMD submission (W4): endpoint-open only, submission stubbed
  (-EOPNOTSUPP), ring payload walking (T2F*/T2HT) not implemented.
- No GEM/UAPI/DRM surface: no submission path exists to expose yet; the
  H13 ane module remains untouched and separate.
- No device run of any kind: every on-device expectation (HELLO arrives,
  epmap contents, ASC-block reads) is staged for the W1/W5 windows on
  jw14m2 when its reset loop allows; probe's tier gate keeps the
  skeleton inert unless explicitly forced.

## 7. Footprint

- This box only: omarchy-ane working tree + build artifacts in
  `ane/t6021/` (checked in: sources + Makefile only; .ko/.o ignored by
  the repo pattern), kernel tree build output in
  `/home/joshuawarren/src/omarchy-linux` (modules_prepare + module
  builds; vmlinux attempt logged in /tmp), nothing installed anywhere.
- omarchy-ane push: branch `feat/t6021-ane-driver` → origin.
- ane-linux-experiments: this receipt committed to `receipts/` on main.
