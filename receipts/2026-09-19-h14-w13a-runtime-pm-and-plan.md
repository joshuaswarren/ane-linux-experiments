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
   persists across driver binds).

   **Final design (supersedes the intermediate set-suspended recovery):**
   device runtime PM is REMOVED from the driver entirely. The probe
   calls `ane_t6021_first_resume()` explicitly (deterministic single
   execution; error → probe unwinds), the `.pm` ops and every
   `pm_runtime_*` call are gone, and the pmgr islands stay held on by
   the `DL_FLAG_RPM_ACTIVE` supplier links from `attach_genpd()`
   (independent of consumer runtime state). With PM never enabled, no
   `rpm_callback` run can ever cache an error that hides the whitelist —
   the -22 trap class is structurally gone, and the whitelist always
   executes before any engine-window use. An intermediate recovery
   (disable/set-suspended/enable) was built and then removed: it
   restored functionality but kept the fragile error-cache machinery,
   and the SUSPENDED status rationale ("reflects reality") was contest-
   able while the islands are physically on. Diff vs pristine W10
   driver: 18 added / 43 removed lines (net −25).

## 3. Driver source corrections (Main reviews; applied, building clean)

- `runtime_resume`: uninitialized `int err` — MOOT: the callback and all
  device runtime PM are removed (see §2 final design); first_resume
  runs explicitly from probe.
- mbi_boot knob DROPPED: the actual `ane_t6021_mbi_boot()` body is
  read-only (SCRATCH0-7 + message-register dumps + a latch; the
  SCRATCH-wake sideload mode its comment referenced is UNIMPLEMENTED —
  stale comment corrected), so no new opt-in was needed.
  `rtkit_transport=1` performs no writes.
- fwload validator hardened per review: exact-image assertions,
  bounded LC walk, u64 fileoff/filesize, thread-state byte validation,
  shared header `ane_fw_validate.h` + offline regression
  `tools/h14_fwload_regression.c` (7/7, host + target).
- Exact diff vs pristine W10 driver (final): drv sha
  `69c2b1ae82002689ca417abb550ffd7ff2488127de16e47f83cbdabfb8483dc0`,
  ko `30d6f9908539e1cad6120a4aef32936f6e93a670c8483cd62c79ef5e94a95984`
  (835,832 B → check ls), 21 added / 44 removed.
- Failure-path audit (W13 review): probe gotos — pre-rtkit_init errors
  (genpd attach return, irq parse, resource loop, ioremap) go to
  detach_genpd (nothing to free beyond devm); every error AFTER
  rtkit_init (first_resume gate, irq request) routes to `shutdown:`
  which runs `ane_t6021_rtkit_shutdown()` (6-ring free) + genpd detach.
  The ring leak Main flagged (first_resume err → detach_genpd,
  bypassing shutdown) is fixed. remove(): fwload_remove → irq free →
  shutdown → detach.

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
3. insmod (corrected build — runtime PM removed, first_resume runs
   explicitly in probe), params `allow_unqualified=1 rtkit_transport=1
   fw_load=1`: probe performs genpd attach (supplier links hold islands
   on), IRQ/resource parse, 3 ioremaps, EXPLICIT first_resume (read-only
   whitelist, 17 registers), 6 ring dma_allocs (dart-ane0 PTEs),
   fwload: request_firmware (filesystem), sha256, validator, 4 MiB
   coherent alloc (DART PTEs), segment copies. NO SCRATCH/doorbell/RVBAR
   writes (no transport write path exists in the tree — mbi_boot is
   read-only). Expected: bound driver + "fwload: … validated +
   DART-mapped" log; the iova value recorded as DATA.
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

## 8. Reset sequence — fully pinned (addendum 3, offline disasm)

Complete Chinook boot flow (K14 0x95e9420–0x95e9d00; W13a + this pass):

1. `readReg(eng+0x1050000)` — RVBAR; `bit0 == 1` → SKIP (released latch;
   matches live reads 0x1).
2. `writeReg(eng+0x1050000, 0x0081_0000_0000_0001)` — ROM entry (K13 ≡ K14).
3. two config-driven writes with `w2=0` then `w2=0x10` on cfg field
   `[dev+0x4a0]` (clock/PM asserts — identities not yet named).
4. **Poll loop** `0x95e9adc–0x95e9b8c`: ≤1000 iterations of
   `readReg(cfg+[dev+0x454])` until it equals **`0x08042006`** (the
   fw-written "channel table ready" value — same constant the W2-era
   header already recorded for the RTBuddy SCRATCH7 handshake).
   Config flag `[cfg+0x163]` selects a logging variant.
5. Success: state marker `0x0101` → `[dev+0x404]`, boot notify, flags
   `[dev+0x407]/[dev+0x405]` cleared, event 6 raised; failure: error
   path `0xe00002bc` family.

Still the single open datum for a boot attempt: WHERE the image (and
boot-args blob) must be placed before step 2 — iBoot's loader constant.
Everything downstream (poll, doorbell registration, CSNE transport) is
now pinned end-to-end and encoded in `ane/t6021/ane_t6021.h` comments.

### Addendum 3b: the config-driven asserts are now NAMED

The two post-RVBAR "asserts" are CPU_CONTROL register writes, and the
poll register is CPU_STATUS — both offsets come from the SoC config
(object built by `initializeANESoCConfig` per-variant):

- 22 sites store `movz w?,#0x44; movk w?,#0x140,lsl #16` → **0x1400044**
  (h14g CPU_CONTROL) into `[dev+0x4a0]`; 6 sites add
  `orr #0x200000` → **0x1600044** (h16g/h17/h18g variant builders).
- Boot tail: `writeReg(cfg+0x4a0, 0)` then `(…, 0x10)` = clear RUN, set
  RUN — i.e. CPU_CONTROL 0x1400044 ← 0 then ← 0x10 for h14g (W10's live
  read CPU_CONTROL=0 at 0x285400044 = ANE+0x1400044 ✓).
- Poll: `readReg(cfg+[dev+0x454]) == 0x08042006`, ≤1000 iters.
  RESOLVED (W13a review pass): the wake write immediately before the
  loop targets the SAME `[dev+0x454]` register with `0xf7fbdff9`
  (movz 0xdff9 + movk 0xf7fb lsl16 — verified bytes), and `[dev+0x454]`
  = SCRATCH7 = **0x1840064**; the poll identity is therefore
  SCRATCH7 == 0x08042006, not CPU_STATUS. The constant appears twice
  more: the SCRATCH3 host-ack write is also 0x08042006 (site
  0x…95eaee8-0x…95eaef0), and the older W2-era header/comment value
  "0x80402006" is a TRANSCRIPTION ERROR (nibble swap) — corrected in
  the driver header and this receipt. Reset ordering at register level
  is therefore: InitANEScratchRegisters (SCRATCH0-7 ← 0; bl 0x960f2a8
  at boot 0x95e954c, H14DartAudit) → SCRATCH7 mode write (cold 0 /
  warm 1) → RVBAR gate → RVBAR ← entry → CPU_CONTROL 0 → CPU_CONTROL
  0x10 → poll SCRATCH7 == 0x08042006. Page-tables/boot-args/placement/
  stream-mapping remain open separately (§6).

### Addendum 3d: SCRATCH corrections (H14DartAudit cross-review)

- dev+0x438+4n == rANE_SCRATCHn, n=0..9 (SCRATCH8/9 at 0x458/0x45c,
  runtime-only sites); InitANEScratchRegisters (0x960f2a8) zeroes
  SCRATCH0-7 before the boot sequence.
- Direction fix: cfg+0x438/0x43c reads (0x95ea0d4/0x95ea0fc) are
  readReg; the publication WRITE is 0x95eaa94-0x95eab08:
  SCRATCH0=lo32/SCRATCH1=hi32 of (surface->[0x18] + ring_cursor −
  surface->[0x38]) — a per-command surface position with iova-shaped
  arithmetic. The fw learns ring positions from SCRATCH at runtime.
- Consequence for placement: SCRATCH is zeroed before RVBAR/RUN, so
  the ROM's boot-time image source is NOT SCRATCH-published — it is a
  fixed convention only iBoot/ROM knows. Placement constant stays the
  open prerequisite, sourced from the iBoot registration chain.
- ROM entry 0x0081_0000_0000_0001 exceeds the 42-bit dart-ane0 iova
  aperture → ROM fetch is an internal non-DART decode; boot image
  space and runtime DART iova space are distinct domains (runtime fw
  buffer addresses ARE dart-ane0 iovas resolved host-side, W2 §5 +
  H14DartAudit).

### Addendum 3c: iBoot registry trace state (continuation point)

- The fw-descriptor REGISTRY is runtime-populated BSS at VA `0x264720+`
  (beyond the file image, file ends 0x257110): registration code
  `0xe81a4–0xe81f8` stores `{x8+4, x8+4, x8+0x10, &pool}` where the
  pool pointer `0x2254c8` anchors the per-role descriptor strings and
  `x8` comes from `bl 0xe8548` (runtime allocator/lookup) — static
  extraction of populated entries is impossible from the file; the
  allocation constants live in the registration call chain
  (`0xe8548`, and the cluster-0x3f990 constructor family; 0x3f9xx pool
  refs are DESTRUCTORS).
- Continuation: trace `0xe8548` (what allocates the per-role object
  and where its load-address field is filled), and the caller chain at
  `0x75a0c/0xcd820`. Both pure-offline.
- Selene bootargs-parse trace (negative result, documented): the fw
  string "Boot arguments entries : %zu" (VA 0x9e02c in `__TEXT.__cstring`)
  has ZERO static references — no ADRP/ADD xref (fwxref), no literal-pool
  u32/u64 pointing at it (full-payload scan). The fw references log
  strings through a mechanism its relocation scheme hides (PRELOAD
  linked-at-0 but strings not pool-addressed). Bootargs layout must come
  from the HOST side (SetupFWInitBootArgs walk, W13 §6) or the iBoot
  descriptor trace, not selene string xrefs.
- Live-ADT route (jw14m2): the only captured phram data is jw16's
  (`adt` @ 0x10004f70000/0x7c000, `m1n1_stage2.log` @ 0x10fb8458000/0x4000
  — jw16mbp1-linux-adt-exposure.json); jw14m2 has NO captured ADT
  physical address (its FDT memreserve list is empty) and no
  apfs/devmem route (STRICT_DEVMEM blocks System RAM). A live read also
  carries a real risk of null result: W10/W14 evidence (CPU stopped,
  mailbox at origin, domains off at boot) says iBoot likely does NOT
  place/start ANE firmware on chainload boots, in which case the ADT
  would show no ane placement markers and the read proves nothing about
  the macOS-boot placement the ROM uses. Discriminating value therefore
  conditional — the iBoot registration-chain RE (0xe8548) is the
  primary offline lead.

## 9. Complete bootstrap prerequisite table (status close-out)

| # | prerequisite | evidence | status |
| --- | --- | --- | --- |
| 1 | firmware payload staged + validated | W12/W14: sha-pinned, exact-image assertions, on-target checker 15/15, regression 7/7 | DONE |
| 2 | power precondition (8 domains on/clear) | W14 live snapshot + genpd summary | DONE |
| 3 | read-only whitelist path | W14 audit + driver bind, 17 reads, 0 aborts | DONE |
| 4 | driver bind | W14 bound (runtime PM removed; -22 trap structurally gone) | DONE |
| 5 | fw surface DART mapping mechanics | W14 mapped 4 MiB coherent, iova 0x3ffffc00000 recorded as data | DONE (mechanics) |
| 6 | DART stream identity | H14DartAudit: stream 0 across 3 instances, group 6; t6021-direct fault-obs open (owner-gated) | PARTIAL |
| 7 | pinned-iova capability | fw_iova param implemented (475bff0/84a49e6), unexercised | CODE DONE |
| 8 | image placement constant (iBoot) | OPEN — descriptor registry is runtime BSS (VA 0x264720+, addendum 3c); registration fn 0xe81a4-0xe81f8 via bl 0xe8548 | OPEN |
| 9 | page-table patching contract (_rtk_boot_l1/_rtk_page_tables fill) | OPEN — same iBoot trace | OPEN |
| 10 | boot-args field layout | PARTIAL — client walk + strides pinned (W13 §6); field semantics open | PARTIAL |
| 11 | publication variant (fixed iova vs args-carried) | OPEN — depends on 8; DART audit bounds both candidates | OPEN |
| 12 | reset sequence at register level | SCRATCH7 mode (0 cold/1 warm) → RVBAR gate → RVBAR ← 0x0081000000000001 → CPU_CONTROL 0x1400044 ← 0/0x10 → poll SCRATCH7/CPU_STATUS == 0x08042006 | DONE (register level) |
| 13 | post-boot gate reads | SCRATCH7 poll + CPU_STATUS family named; bit semantics fw-defined | DONE (named) |
| 14 | execution gate: collector verified off-host | W14 pre-mutation test | DONE |
| 15 | TX fence (doorbell/a2i) | UNQUALIFIED — historical W5/W6/W9 SError; stays fenced until fw runs AND a handshake proves transport | OPEN (post-boot) |

Next execution gate: items 8-11 (one iBoot-RE pass or one approved live-ADT
phram read) → then ONE netconsole-armed boot probe with abort capture.
No speculative writes; nothing executed since the approved staging probe.
