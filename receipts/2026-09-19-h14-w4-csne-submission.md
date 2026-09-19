# H14/T6021 W4 — CSNE_CMD submission path (static, no device) (2026-09-19)

Verdict: **W4 STATIC PORTION LANDED — `ane_t6021_csne_submit()` implemented
(ring slot alloc with K14 wrap semantics, doorbell ring, ceiling size-code
fix), CSNE wire structs pinned against the selene binary itself, and the
module rebuilds clean through full modpost against the jw14m2 kernel tree
(exit 0).** No device touched; 63c1d3cf N/A (absent in omarchy-ane, same as
W2/W3).

Branch: omarchy-ane `feat/t6021-ane-driver-w4` (from
`feat/t6021-ane-driver` @ 26110cd).

## 1. Decode correction — the W2 "u16 id at header offset 0" claim was wrong

Fresh disassembly of the selene fw (W2 tooling `disx.py` + capstone, linear
scan of the whole `__TEXT.__text`, 160,155 instructions) shows **three
independent sites parse the host→fw command id as u16 at wire offset +4**:

- `0x4d244` — preload `ldrh w25, [x28, #4]`, passed as the id to the
  dequeue helper `0x3e5f4`;
- `0x4d264` — the generic CSNE processor's id tree (`cmp #0x20b/#0x203/
  #0x204/#0x209/#0x20a`), x28 = command work item;
- `0x5246c` — LOAD_PROGRAM/CREATE_PROCESS/PROCEDURE_CALL pre-parse
  (`cmp #0x200/#0x202/#0x204`), x1 = command pointer.

W2 §4's "fw-side `sCSneCmdHdr.id` is u16 at header offset 0" came from the
0x4af60/0x58f10 region, which on re-read is a session-object cached-id
compare (x20 carries fields at +0xca0 — a runtime struct, not the wire
block) and an assert-log stub. The kext-side `sCSneControllerCmdHdr`
(u32 id @ +0x8, 0x24 B) is the **fw→host** shape and never rides host→fw
submission. Both stale statements are corrected in `ane_t6021.h` comments;
W2 receipt left as-is with this receipt as the erratum.

## 2. Wire structs (`ane/t6021/ane_t6021.h`)

- `struct ane_csne_hdr` — 8 B: `u32 rsvd0; u16 id@+4 (PROVEN); u8 flags@+6
  (fw writes completion state here, strb @0x4d324 [INFERENCE]); u8 rsvd7`.
  `ane_csne_hdr_init()` zero-fills and sets the id.
- **Header-only commands** — PING (0x11), BUILDINFO (0x06), BOOT (0x10):
  the generic processor's id tree routes every id ≤ 0x203 except 0x2d/0x34
  to the default path (0x4e65c) — carried without field parsing. BOOT's
  surfaces ride SCRATCH0-7 / SetupFWInitBootArgs (phase1 §2.5), not the
  command.
- `struct ane_csne_cmd_reg_file_load` (0x05) and
  `struct ane_csne_cmd_ipc_endpoint_set` (0x15) — header + opaque payload:
  no fw field parse decoded; transport/layout honestly marked [INFERENCE],
  pinned by the W1 live exchange. The REG_FILE_LOAD blob is the fw's own
  `__DATA._rtk_tunables` section (@0x100590, size 0x5b0 = 1456 B — the
  W3 receipt's "1456 B" confirmed against the section header).
- `struct ane_csne_cmd_procedure_call` (0x204, and 0x404 INFERENCE_CALL
  same shape [INFERENCE]) — offsets PROVEN, semantics named only where the
  kext asserts name them: u32 program_id @ +0x08, procedure_id @ +0x0c
  (validated as a pair, `ldp` @0x4d654; kext assert order "program id %d,
  procedureId %d, numIoBuffers %d"), u64 @ +0x10 (validator arg, 0x4d6d4),
  u32 @ +0x18 **required in [8,15]** (@0x4d660-0x4d66c: `sub #8; cmn #7`
  unsigned bound), u64 @ +0x20, u32 num_io_buffers @ +0x28 (loop bound
  @0x524bc), then count × **0x30-byte io records at +0x60** (stride 3×16
  @0x524a8-0x524b4). `ane_csne_cmd_procedure_call_size()` computes the
  wire size; six `static_assert`s pin the offsets.
- Fw-side size bound: the generic processor rejects work items ≥ **0x1b89**
  bytes (@0x4d134-0x4d158 `cmp x2, #0x1b89`; what x2 names beyond "command
  size" is [INFERENCE]). `ANE_CSNE_CMD_MAX_SIZE` (0x1b88) fail-fasts
  oversized commands before they enter the ring.

## 3. Submission (`ane_t6021_csne_submit()` in ane_t6021_rtkit.c)

K14 `rtbuddyEndpointSendMessage` semantics (asm `0x…95f3990-0x95f3cdc`,
W2 artifacts), in order:

1. guards: `cmd` non-null, `size >= sizeof(hdr)`, `size <=
   ANE_CSNE_CMD_MAX_SIZE`, INIT endpoint started (else `-ENOTCONN`);
2. ring size bound `size > ring_size` → `-E2BIG` (kext checks this before
   the wrap, `b.hs` @0x…95f3ac0);
3. **slot alloc with wrap**: cursor kept iff `cursor+size < ring_size`
   (`csel w25, w10, wzr, lo` @0x…95f3b04 — an exact end-fit wraps to 0,
   equality included);
4. `memcpy(ring + cursor, cmd, size)` — ring slot is the coherent DMA
   buffer (driver-side equivalent of the kext `ep_obj+0x38` base);
5. doorbell = `ane_ep_doorbell_encode(cursor, size)`, sent as msg0 on the
   mailbox with msg1 = EP1 (`ane_mbox_send`; its `dma_wmb()` orders the
   ring copy before the doorbell MMIO write);
6. `write_cursor = cursor + size` **only on doorbell success** — the kext
   advances its cursor only after the command gate returns 0
   (@0x…95f3c70-0x95f3c7c).

Locking: the whole sequence runs under `mbox_lock` (cursor update, ring
copy and the 1-deep mailbox FIFO serialize together; submit sleeps, so
process-context only). No synchronous response matching: fw→host answers
arrive on T2F* (EP2/EP3) and T2HT (EP6) and are still capture-only — that
walk is deliberately not in this change.

## 4. Doorbell codec ceiling fix (skeleton bug found by W4)

K14 SetupEndpoints' size-class encoder **rounds the size code UP**
(`cinc w9, w9, ne` on remainder @0x…95fe8b0-0x95fe8ec). The W3 skeleton's
`ane_ep_doorbell_encode()` truncated (`size >> (unit*12)`) — wrong for any
non-multiple size, and invisible to the W3 self-check because all three
ring sizes are exact 4 K multiples. Fixed to `DIV_ROUND_UP`, provenance
commented; the probe self-check now also covers a non-multiple size
(0x1234 → reconstructs 0x2000) and refuses to bind on mismatch.

## 5. Build verification (this box)

- Toolchain: aarch64-linux-gnu-gcc 12.2.0 (Debian); kernel tree
  `/home/joshuawarren/src/omarchy-linux` (Linux 7.1.6 arm64, real
  `Module.symvers` from the W3 vmlinux+modules pass).
- `make KERNELDIR=... ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-` →
  `CC ane_t6021_drv.o`, `CC ane_t6021_rtkit.o`, `LD [M] ane_t6021.ko`,
  **MODPOST Module.symvers with zero unresolved symbols, exit 0,
  warning-free**.
- Host smoke of the exact committed formulas (python mirror): ceiling
  round-trip (0x1234→0x2000), all three ring sizes, unit class switch at
  1 MiB (1 below / 2 at-or-above), and the wrap table (strictly-below
  keeps the cursor; equality wraps to 0) — all green. The same formulas
  are the driver's compile-time code and probe self-check.
- Status: **built, linked, modpost-verified against the jw14m2 kernel
  tree; nothing loaded anywhere — no device in this lane.**

## 6. What is NOT here (scope)

- fw→host response walk (T2FC/T2FH delivery, T2HT polling) and the
  id-match/response-completion path (`this+0x8d0` matcher) — response
  side, needs the live exchange to name the completion shape.
- Shared-memory surface plumbing (IPC_ENDPOINT_SET payload, ANEMessage
  map-op path, FWSharedMemoryRequest fields) — W2 §9 gaps stand.
- Which channel INFERENCE_CALL actually rides on the wire (INIT per the
  W2 inference; the 0x404 id is outside the decoded id tree) — first
  live submission pins it.

## 7. Footprint

- omarchy-ane: `ane/t6021/ane_t6021.h` (+wire structs, +doorbell ceiling
  fix, +write_cursor), `ane/t6021/ane_t6021_rtkit.c` (submit + self-check),
  this receipt; branch `feat/t6021-ane-driver-w4` pushed to origin. Build
  artifacts in `ane/t6021/` not checked in (repo pattern).
- ane-linux-experiments: this receipt copied to `receipts/` on main.
