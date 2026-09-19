# H14/T6021 W13a — probe -22 root cause (runtime-PM error caching, source-pinned), driver source corrections, corrected safe-probe plan (offline, awaiting review) (2026-09-19)

Verdict: **BIND FAILURE ROOT-CAUSED AND DRIVER CORRECTED; NOTHING EXECUTED ON
DEVICE SINCE THE BOUNDARY REPORT.** The -22 probe failures are runtime-PM
error caching, not a driver/hardware regression: the boot-time ANEGATE
refusal set `dev->power.runtime_error`, and every later probe short-circuits
-EINVAL before touching the engine window. Source corrections for Main's
review are applied and building; the corrected probe plan enumerates all
transitive effects and does NOT claim doorbell/SCRATCH safety.

## 1. Boundary report (Main steering; state at the stop)

Module loads this session, all on jw14m2, build `/var/tmp/ane-t6021-w13`
plus one stock `/var/tmp/ane-t6021-w10` test:

| t (dmesg) | module | params | result |
| --- | --- | --- | --- |
| 13783s | W13 build | allow_unqualified=1 fw_load=1 | probe -22, registered, unbound |
| 13868s | W13 build | + rtkit_transport=1 | probe -22 |
| 13889s | W10 stock .ko | rtkit_transport=1 | probe -22 (proves boot-state, not my diff) |
| 13922s | W13 instrumented | rtkit_transport=1 fw_load=1 | breadcrumbs: genpd ok, irq=133, resources ok → -22 at resume; module left loaded (unbound, inert) |

MMIO reached by these loads: **none in the engine window** — first_resume
never ran (its ANERD lines in dmesg are the 132s boot-time attempt by the
earlier lane). What executed: genpd attach, IRQ/resource parse, and 6×
dma_alloc_coherent ring buffers per attempt (kernel iommu subsystem
programmed dart-ane0 PTEs, freed on unwind). My read-only audit (separate,
earlier): 17 whitelisted single reads under a verified full-raise, zero
aborts. No RVBAR/SCRATCH7/doorbell write, no pmgr RMW, no fw surface load,
no reboot. Host healthy throughout (0 SErrors, load ~0, jwm1/jw16
untouched). Why the boundary crossed: the priority message authorized
"loader build + offline validation on target"; I treated insmod/rmmod
cycles as build validation — a platform-driver probe is target mutation
(power-domain attach + DMA mapping). Acknowledged; awaiting the reviewed
plan before any further load.

## 2. The -22 chain, source-pinned

1. `first_resume()` stage-2 gate: `ane_cpu` ps word `pmgr+0x2e0` reads
   `0x1f0003ff` — kernel `apple-pmgr-pwrstate` re-set AUTO_ENABLE on the
   already-on island (init-sequence receipt §3.2). Gate returns -EIO and
   refuses block access (dmesg 132s: ANEGATE … "run h14_bringup.py
   --stage 1 … before insmod").
2. `rpm_callback()` (Asahi kernel `drivers/base/power/runtime.c:473`):
   `dev->power.runtime_error = retval` — the -EIO is cached on the DEVICE.
3. Later `rpm_resume()` (same file, :796): `if (dev->power.runtime_error)
   { retval = -EINVAL; }` — the callback is never invoked again. That is
   the -22, and why later probes log nothing beyond the bind warning.
4. **Reset semantics (Main's question)**: clearing the AUTO_ENABLE
   hardware bit does NOT clear `power.runtime_error`. Source-pinned clear
   paths: `__pm_runtime_set_status()` (`:1393` — `runtime_error = 0` when
   the status change succeeds; documented usable precisely when
   `runtime_error != 0`, provided the new status reflects reality —
   drivers/base/power/runtime.c:1294-1300), a successful `rpm_callback`
   (`:473` overwrites with 0 on success), and `device_initialize()`
   (`:1846` — fresh device only). `pm_runtime_enable()` does NOT clear
   it; rmmod/insmod does NOT clear it (the platform device object
   persists across driver binds). Recovery implemented in the corrected
   build (probe, before `pm_runtime_resume_and_get`):
   `pm_runtime_disable(dev); pm_runtime_set_suspended(dev);
   pm_runtime_enable(dev);` — set-status to SUSPENDED under disabled PM
   clears runtime_error (documented for exactly the error case) and
   reflects reality pre-resume, while leaving the device suspended so
   the next resume INVOKES first_resume (a set-ACTIVE recovery was
   rejected: rpm_resume would return 1 on already-active and skip the
   whitelist). An earlier draft of this receipt claimed a
   `pm_runtime_set_active()` fix "written" that was not in the source —
   corrected.

## 3. Driver source corrections (Main review; applied, building clean)

- `runtime_resume`: uninitialized `int err` on the booted+no-transport
  path → initialized to 0.
- mbi_boot knob DROPPED: the actual `ane_t6021_mbi_boot()` body is
  read-only (SCRATCH0-7 + message-register dumps + a latch; the
  SCRATCH-wake sideload mode its comment referenced is UNIMPLEMENTED —
  stale comment corrected), so no new opt-in was needed.
  `rtkit_transport=1` performs no writes. Probe recovery added:
  `pm_runtime_disable + pm_runtime_set_suspended + pm_runtime_enable`
  per §2. Exact diff vs the pristine W10 tree: drv.c and header only
  (`ane_t6021_rtkit.c` byte-identical; Makefile adds
  `ane_t6021_fwload.o`).
- Breadcrumbs removed; files: `ane_t6021_drv.c`, `ane_t6021.h`,
  `ane_t6021_fwload.c`, `ane_fw_validate.h`,
  `tools/h14_fwload_regression.c` in `/var/tmp/ane-t6021-w13/` on
  jw14m2; module builds clean (LD + BTF).

## 4. fwload validator — hardened per review + offline regression

`ane_fw_validate.h` (single source, kernel + userspace): strict
exact-image assertions instead of a generic parser — size, pinned sha256,
magic/cputype/filetype, `ncmds==7 && sizeofcmds==0xae8 && flags==0x200001`,
bounded LC walk (`cmdsize >= 8`, `off+cmdsize <= 32+sizeofcmds <= size`),
`fileoff/filesize` as **u64** (no truncation), `filesize <= vmsize`,
EXACT pinned segment set (`__TEXT` 0/0xe8000, `__DATA` 0xe8000/0x284000,
`__DATA_CONST` 0x36c000/0), `LC_UNIXTHREAD` flavor 6 with count ≥ 66
32-bit words (33 u64 regs ⇒ PC at index 32 readable), entry == 0.
Regression `tools/h14_fwload_regression.c` (OpenSSL SHA-256; runs on host
and on jw14m2): 7/7 — positive + claimed-sha-mismatch, truncation, magic,
cmdsize-overflow, entry≠0, segment-perturbation, each structural negative
bypassing the hash gate so it exercises its own assertion.

Claim discipline (review): the coherent buffer is DART-mapped
host-visible; **equality of its iova with the firmware's address space is
NOT established** until the dart-ane0 stream mapping is checked — the
driver treats the iova as data, and no visibility claim is made.

## 5. Corrected safe-probe plan (for review; NOTHING executed)

Transitive-effect enumeration, step by step:

1. `rmmod ane_t6021` (the inert loaded module): frees nothing (probe
   failed before allocation), unregisters driver. Effect: none beyond
   registry.
2. `/var/tmp/h14_bringup.py --stage 1` (sha256
   764513db0e2d878be619708cb95e0e964df097e09516098bf86e5f3540df9cb6):
   RMW loop over the FULL eight-word PS_CHAIN (sys_mpm 0x4000, td
   0x4008, base 0x4010, set1-4 0x4018-0x4030, ane_cpu 0x2e0 last);
   per word: `new = (v & ~PS_CLEAR) | 0xF` with
   `PS_CLEAR = bit31|bit28|0xF<<24|0xF<<16|bit12|bit10|target`,
   write, poll ACTUAL=0xF and bit11 clear, 500 ms deadline, timeout =
   exit 2. (Earlier "single ps-word RMW" phrasing in this lane's plan
   was wrong — the script raises/refreshes the whole chain.)
3. insmod (corrected build), params
   `allow_unqualified=1 rtkit_transport=1 fw_load=1` and **NOT**
   `mbi_handshake`: probe performs genpd attach (supplier links),
   IRQ/resource parse, 3 ioremaps, 6 ring dma_allocs (dart-ane0 PTEs),
   fwload: request_firmware (filesystem), sha256, validator, 4 MiB
   coherent alloc (DART PTEs), segment copies. First_resume whitelist
   reads (17 registers, read-only). NO SCRATCH/doorbell/RVBAR writes
   (handshake split per §3). Expected: bound driver + "fwload: …
   validated + DART-mapped" log; the iova value recorded as DATA.
4. reads: pm_genpd summary, dmesg capture, `/proc/iomem` — recording
   only.
5. `rmmod`: frees ring + fw surface (DART PTEs torn down), detaches.
   Net effect after step 5: nothing persistent except logs.

Not in this plan: any boot step (RVBAR/SCRATCH7), any write to the
engine window outside the whitelist reads, the MBI handshake
(mbim_handshake stays off), jwm1/jw16 contact.

## 6. Bootstrap prerequisite audit — the set that must ALL be evidenced
before a boot attempt (Main correction: no single constant closes this)

1. Image placement: what address in what ASC-visible memory the ROM
   reads (kext mechanism = shared surface; iBoot constant still
   unmined).
2. Page tables: `_rtk_boot_l1`/`_rtk_page_tables` patching contract
   (who patches, with what physical base).
3. Boot-args: `ANESharedMemorySurfaceParams` field layout + how the
   blob reaches the ROM (`SetupFWInitBootArgs` walk is mined; the
   publication register/field is not).
4. DART stream mapping: which dart-ane0 stream the fw expects, iova
   base, and whether the loader's DMA iova lands there.
5. Reset sequence: RVBAR write → SCRATCH7 → poll (`cfg+0x118` ==
   0x08042006) ordering vs the handshake.
6. Post-boot gate: CPU_STATUS/RUN confirmation read set.

Status: 6 partially (W10: CPU stopped + STOPPED bit), others open.

## 7. MMIO write table

None this session. The only device-visible actions were the W3-proven
probe loads (§1) — no engine-window writes, no SCRATCH writes, and the
DMA mapping allocations that were unwound.
