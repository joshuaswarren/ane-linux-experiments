# H14/T6021 W5 — the RTBuddy-mode doorbell writer decoded from the provider kext: com.apple.driver.RTBuddy, ANEEndpoint1..5 nubs, 48-bit MBI ring word, doorbell bit = endpoint id (2026-09-19)

Verdict: **the W4-fix "gate behind another kext" lane is closed.** The
publisher of the service `EnableRTBuddyEndpoints` waits for is
`com.apple.driver.RTBuddy` 1.0.0 — carved fresh out of
`kernelcache.release.mac14j` this lane (46088 B arm64e kext bundle, now at
`receipts/2026-09-18-t6021-engine-layout-mined/kext-h14j/RTBuddy-1.0.0-mac14j-26A428`).
The TX path K14 reaches through `gate = [svc+0x88]`, `vtable+0x1e8` is the
AKF-mailbox ring send: per message it is the 48-bit word
`{ring cursor [23:0], length [47:24]}` after the command bytes are already
in the shared ring, ending in the AKF `MAILBOX_SET` doorbell write — the
same `write32(1 << bit)` to **ANE+0x1844000** W4-fix pinned from the
sideload-mode setter. Endpoint number **is** the doorbell bit (EP0 =
management, EP1..5 = data). Driver updated: `ane_t6021_csne_submit` now
implements the full sequence (ring copy → msg48 → a2i word → doorbell),
fenced behind a new `mbi_doorbell=1` opt-in; cross-build clean
(aarch64, 0 warnings). No hardware touched.

## 1. Carving the provider kext (kernelcache.release.mac14j)

The W4-fix assumption "the publishing kext is not in the carried binary"
decomposed into three false leads, each closed by evidence before the real
answer:

1. `AppleANELoadBalancer` (the other ANE kext, 16384 B): zero
   endpoint/RTBuddy/mailbox strings — not it.
2. Whole-decompressed-KC byte search for `ANEEndpoint`: exactly one real
   hit (K14's own cstring block @KC 0x4c084c; the other two are
   "IspA**neEndpoint**s" substrings in AppleISP). No personality and no DT
   node carries the name (`dtree-j414c.txt` clean) — the name is built at
   runtime.
3. The publisher builds it from **`"%sEndpoint%u"` @RTBuddy 0x…7cc7d3f**
   with the role string `"ANE"` (K14 personality `RTBuddyBringup`:
   `IOProviderClass = RTBuddyService`, `IOPropertyMatch role = "ANE"`) →
   nubs **ANEEndpoint1..ANEEndpoint5**. RTBuddy.kext is the
   `com.apple.driver.RTBuddy` OSBundleLibrary dependency K14 already
   declared — found via the KC `__PRELINK_INFO.__info` plist
   (374 kexts; `_PrelinkExecutableSize` 46088).

Carve mechanics (new tooling-grade detail for future lanes):
- The decompressed mac14j KC is a fileset Mach-O: 366 load commands, 353 ×
  `LC_FILESET_ENTRY` (`0x80000035`, layout: cmd/cmdsize, vmaddr@+8,
  **KC file offset @+16**, entry_id offset @+24 → inline string @+32).
  `kc_fileset.json` in `/tmp/t6021-mine/` maps all 353.
- Each kext's segments are stored at SEPARATE KC file offsets (RTBuddy:
  `__TEXT` @0xcbdec0, `__TEXT_EXEC` @0x4692860, `__DATA_CONST` @0x1a03508);
  a flat re-assembly (`RTBuddy.flat.bin`) re-bases segment file offsets so
  the W2 `disx.py` works unchanged.
- KC pointers use **chained fixups**: raw = `(tag<<32)|low32`, decoded
  address = `0xfffffe0007004000 + low32` (calibrated against RTBuddy's
  `__mod_init_func` entries landing inside its own `__TEXT_EXEC`, and the
  vtable-slot bucket distribution: `__TEXT_EXEC` fileoff = vm−0x8ae8000
  with `__TEXT_EXEC` vm = base+0x1ae4000).

## 2. The matcher: who K14 waits for

`EnableRTBuddyEndpoints(ANEHWDevice*, const char* name, char n)`
(0x…95feb30, W2 asm) formats `snprintf(buf, 0x40, "%s%d", name, n)`
(`"%s%d"` @0x…74c481f) and calls the wait helper with a **10 s** deadline
(x1 = 0x2_540be400 = 10^10 ns). Callers (`InitializeRTBuddyEndpoints`
0x…95ff824): `EnableRTBuddyEndpoints("ANEEndpoint" @0x…74c484c, n)` for
n = 1..5 in a loop (`cmp w20, #5; b.ls`), or `("ANE1Endpoint" @0x…74c483f, 1)`
on the single-endpoint chip variant. On success: `gate = [svc+0x88]`
(0x…95feccc), PAC-signed rx handler `HandleRTBuddyMessage` (pacia
0x…95feff0, key 0x1810) stored at **gate+0xd0**, 0x…95ff634 at gate+0xd0's
sibling slot, endpoint record written to `dev+0x5c0 + n*0x40`
(`{gate, svc}` at rec+0x28/+0x30, ep num at rec+0x0, wr cursor at rec+0x20).

The RTBuddy classes behind the nubs: **RTBuddyEndpointService** (0x98 B,
metaclass @0xcca8650, class vtable store-base 0x8a127c0) and
**RTBuddyEndpoint** (0xE8 B, metaclass @0xcca8628), over the kernel
IOSlaveEndpoint family (`RTBuddy::endpointForHandle(OSObject*,
IOSlaveEndpoint::Action, ...)` signature string; `RTBuddy::createEndpoint`
@0x…7cc6c57). Management is **RTBuddyManagementEndpoint** (`_handleHello`
0x…7cc934a, `_handleEPRollCall` 0x…7cc95b6, `_handlePowerAck` 0x…7cc94ec),
plus the builtin set (OSLog, Syslog, Kdebug, IOReporting, Crashlog,
CoreAnalytics, TraceKit, Entropy).

## 3. The doorbell writer: exact TX sequence

From K14's own `rtbuddyEndpointSendMessage` (0x…95f3990, W2 asm re-read
this lane and extended to the cursor-advance tail):

1. `len > rec.size` → fail `0xe00002c2` (0x…95f3a24; rec+0x8 = ring size).
2. `cursor = rec.wr (rec+0x20)`; `if (cursor + len >= size) cursor = 0`
   (csel lo @0x…95f3b04 — an exact fit wraps too).
3. `ring = [rec.ringobj(rec+0x18) + 0x38]`;
   `memcpy(ring + cursor, cmd, len)` (0x…95f3b20).
4. `msg48 = (cursor & 0xFFFFFF) | ((len & 0xFFFFFF) << 24)`
   (`and w8, w25, #0xffffff; bfi x8, x21, #0x18, #0x18` @0x…95f3bf4-c).
5. `gate->vtable[0x1e8](&msg48, 0, 1)` (autda'd vtable walk @0x…95f3c04-c30).
6. Only on send success: `rec.wr = cursor + len`, slot snapshot into the
   command state (rec+0x40 / rec+0x58) @0x…95f3c70-c.

The gate send's hardware tail is the AKF mailbox write: RTBuddy's mailbox
dump fn (0x…b69d9c8) prints the register names it guards —
`AKF_KIC_INBOX_CTRL`, `AKF_KIC_MAILBOX_SET`, `AKF_AP_OUTBOX_CTRL`,
`AKF_AP_MAILBOX_SET` — with the error strings `INBOX%d not ready`,
`Inbox%d overflow/underflow`, `Outbox%d ...`, i.e. a per-channel-bit SET
register with a queue-space precondition. On the h14g ANE window that SET
register **is** ANE+0x1844000 (W4-fix §1: K14's doorbell setter
0x…95ebdd0 = `write32(1 << bit)` there; config blob dev+0x498). The
host→fw message register pair from the same config blob: write
0x1850000 / read-peer 0x184c000 (kext echo pair 0x…9606e38 → 0x…9606f0c).

**Channel-bit encoding:** the doorbell bit = endpoint id. EP0 is the
management endpoint; EP1..5 are ANEEndpoint1..5 (K14's loop opens exactly
ids 1..5; the driver's EP table already names them INIT/T2FC/T2FH/T2HS/
T2HC/T2HT at ids 1..6 from the W2 config table). So `CSNE_CMD_PING`
(header-only 0x11) on the INIT channel rings `writel(0x2, ANE+0x1844000)`.
[INFERENCE, flagged in the header: the fw→host doorbell/IRQ bit mirrors
the same numbering — Asahi rtkit semantics; W5-live pins it.]

**fw→host pair shape (+0x1170000/+0x1170004):** live W4-fix captures
`{hi=0x2, lo=ticking}` on every load. Under this decode hi = the MBI
endpoint/channel id of the fw→host notification (2 = T2FC, the first
fw→host command channel) and lo = the fw-side cursor/counter [INFERENCE —
the 48-bit shape cannot hold hi=2 as a length (that reads len=0,
offset=0x216c8e1b > 24 bits), so the i2a pair is the MGMT/notify word
family, not a per-command ring word].

## 4. Preconditions and the fatal class (unchanged)

- SCRATCH0-7 (+0x1840048..+0x1840064) writes remain **machine-fatal** in
  RTBuddy mode (jw14m2 SError 2026-09-19, W4-fix §2); the sideload-mode
  SCRATCH handshake stays read-only in this driver.
- Ring-space bound + wrap before the copy; cursor advances only on send
  success (both now in the driver, mirroring the kext).
- The doorbell stays fenced by default: a wrong-bit ring is the same
  "fw-owned control surface rejects host writes" class.

## 5. Driver delta (omarchy-ane `feat/t6021-ane-driver-w4`)

- `ane_t6021.h`: provider decode documented in the MBI block;
  `ANE_MBI_MSG48_OFF/LEN` + `ane_mbi_msg48_encode()`; the 7-step TX
  sequence in a comment; doorbell comment now says `1 << endpoint id`.
- `ane_t6021_rtkit.c`: `ane_t6021_csne_submit` implements steps 1-7 —
  ring memcpy, `dma_wmb()`, `writeq(msg48, A2I_WR)`,
  `writel(BIT(ep), ANE_MBI_DOORBELL)`, cursor advance — replacing the
  `-EOPNOTSUPP` refusal; fenced by `ane->doorbell` (logs the msg48 it
  would send while fenced). Stale "carve the kernelcache next lane"
  comment replaced.
- `ane_t6021_drv.c`: new `mbi_doorbell` module param (default 0, 0444)
  + warning when armed without `rtkit_transport=1`; probe banner now
  prints `CSNE TX ARMED|fenced`.
- Cross-build: `make KERNELDIR=~/src/omarchy-linux ARCH=arm64
  CROSS_COMPILE=aarch64-linux-gnu-` — 0 errors, 0 warnings,
  `ane_t6021.ko` 124312 B. (On-box insmod still belongs to the jw14m2
  lane; dev-box `struct module` mismatch per W4-fix §3 — no module was
  loaded anywhere this lane.)

## 6. Acceptance vs ticket

- "Carve the provider kext": RTBuddy.kext carved + saved
  (`kext-h14j/RTBuddy-1.0.0-mac14j-26A428`), flat-rebuilt for analysis.
- "Disassemble the vtable+0x1e8 doorbell writer — exact register write
  sequence, channel bit encoding, preconditions": sequence = §3 steps
  1-6 (K14 asm-quoted); encoding = bit 1 << endpoint id (§3,
  fw-side INFERENCE flagged); preconditions = ring space + wrap +
  success-only cursor advance + the SCRATCH no-write rule (§4).
- "Decode the fw→host message shape": §3 last block — i2a pair is the
  MBI notify word (ep id hi / counter lo) [INFERENCE], distinct from the
  48-bit per-command ring word.
- "Update the driver": §5. "Document the full H14G register map as a
  header": `ane_t6021.h` MBI block now carries the complete map with
  provenance (ASCII/SCRATCH/doorbell/msgregs + provider decode).
- "Receipt + push": this file; omarchy-ane branch pushed. No hardware
  contact (jw14m2/jw16/jwm1 untouched; no module loaded).

## 7. Footprint

- `/tmp/t6021-mine/`: `RTBuddy.kext.bin` (raw slice),
  `RTBuddy.flat.bin` (111 MB re-based image), `kc_fileset.json`,
  `kc_prelink_out.json` — left for the follow-up lanes.
- `ane-linux-experiments`: carved kext committed under
  `receipts/2026-09-18-t6021-engine-layout-mined/kext-h14j/` + this
  receipt. No installs, no services, no device contact.
