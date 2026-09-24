# ANE FW perf-mode message — RE evidence + Linux client staged (2026-09-24)

Owner: AneBoundaries. Assignment from Main: recover the exact firmware message
that raises the ANE perf state (endpoint, layout, values macOS sends), check
whether the Linux T6001/T8103 driver has the endpoint open, implement the
request in omarchy-ane behind the evidence, stage a build for m1max-host, and hand
over the exact test command. No hardware was run: m1max-host belongs to
Jw16GpuSubmit; the module is staged at `/var/tmp/ane-perf/` **not loaded**.

## 1. The message (evidence-grade)

**CSNE_CMD_CH_PROPERTY_WRITE, channel 0, property `0x10aa`, value `1`.**

20-byte command buffer, sent once during the kext's ANE power-on/init
sequence:

| off | size | field | value |
|-----|------|-------|-------|
| +0x00 | u32 | reserved | 0 |
| +0x04 | u16 | CSNE cmd id | `0x001f` (CH_PROPERTY_WRITE) |
| +0x06 | u16 | flags | 0 |
| +0x08 | u32 | channel | 0 |
| +0x0c | u32 | property | `0x10aa` (FW perf mode) |
| +0x10 | u32 | value | `1` |

Evidence (H13 kext `receipts/2026-09-18-t6021-engine-layout-mined/kext-h13/
AppleH11ANEInterface-9.512.0-t6000-host-25G83`, the t6000-host/T6000-T6001
generation binary):

- cmd id 0x1f: `mov w20,#0x1f; strh w20,[sp,#0x14c]` at
  `__TEXT_EXEC.__text 0xfffffe0009322e14`; send-helper call at
  `0xfffffe0009322e60` with `w2=0x14` (20-byte length).
- channel/property from constant pool `__TEXT.__const 0xfffffe000748fdc8`
  (`{u32 0, u32 0x10aa}`) loaded via `ldr d0,[x8,#0xdc8]` → stored at
  buffer +0x08; value word `mov w8,#1; str w8,[sp,#0x158]` at +0x10.
- the failing-write log string this call site owns:
  `"%s: %s: ERROR: CSNE_CMD_CH_PROPERTY_WRITE for setting FW perf mode
  failed res=0x%x"` — literal at `__TEXT.__os_log 0xfffffe0007473589`,
  code xref `0xfffffe0009322ec8` (single xref; adrp/add pair found by
  full-text scan, receipts/2026-09-18-.../w2 tooling).
- uniqueness: `0x10aa` appears in exactly one pool entry and one send site
  in the binary → macOS writes perf mode **once, value 1** (enable). No
  other values are ever written. The same init function also writes
  cpuLoadScore watermarks (props `0x1803`/`0x1804`, u16 from dev+0x358)
  and fw-log enable (prop `0xa1`, value 0).
- this matches the runtime observation in receipts/2026-09-22-ane-dvfs:
  macOS raises the whole-encoder from 440 ms/iter to a sustained 140 ms
  through AppleH11ANEInterface's "setting FW perf mode"; the ANE clock
  ladder (PLL_ANE0, 300/540/780/1020/1260/1500 MHz) is documented there.

Mechanism: value 1 tells the ANE firmware to enter its CLPC-managed perf
mode and raise its own clock through its power-firmware link. It is not a
frequency request — macOS never sends a frequency; the firmware chooses it.

## 2. Transport (evidence-grade) and endpoint (runtime item)

- **RTBuddy RPC, not the legacy TM path.** The H13 kext contains zero
  TM-queue constants (searched `0x1c40000/0x1c50000` and m1n1's R_TASK
  offsets: no hits) and zero ASC-mailbox constants (`0x1408000/0x1408110/
  0x1408114/0x1400048`: no hits), while carrying the full RTBuddyService/
  RTBuddyEndpoint machinery (52 RTBuddy symbols, ANEHWDevice::
  HandleRTBuddyMessage). Commands are carved from shared-memory rings and
  delivered as 64-bit (offset,size) doorbell words — the W2 decode
  (receipts/2026-09-22-h14-rpc-protocol §1–§4, transport HIGH).
- **Channels** (K14 cfg table mapping, carried in the t6021 client):
  EP1 INIT, EP2 T2F_CMD, EP3 T2F_HIPRI, EP4 T2H_SHMEM, EP5 T2H_CMD,
  EP6 T2H_TERM. The concrete endpoint numbers are not recoverable from the
  ANE kext alone (owned by RTBuddyService) — the firmware's EPMAP answer
  at handshake time is the runtime authority, and the module logs the full
  advertised bitmap verbatim before anything else.
- **RTKit MGMT handshake** mirrored from mainline
  `drivers/soc/apple/rtkit.c`: host HELLO(1) [11..12] → HELLO_REPLY(2);
  fw EPMAP(8, base/bitmap/last) → host EPMAP_REPLY until LAST; host
  STARTEP(5) on the chosen T2F_CMD ep; SetupEndpoints doorbell word
  (`offset[43:0]|size_code[51:44]|unit[53:52]`) then per-command word
  (`cursor[23:0]|len[47:24]`); command replies come back as CSNE cmds
  (res at hdr+0x1c).
- **Linux endpoint state: NOT OPEN.** omarchy-ane `ane/src` has no rtkit/
  mailbox code at all (legacy TM island path only). The t6021 rtclient
  (`ane/t6021`) implements the handshake but binds only `apple,t6021-ane`
  and needs a DT `mboxes` property; m1max-host's DT (checked live:
  `soc/ane@284000000`, compatible `apple,t6000-ane`, one `engine` reg, no
  mailbox child; no `mbox@285408000` under soc) has none, and boot-asset
  changes on m1max-host are forbidden. Hence the new module self-hosts the ASC
  mailbox registers (mainline `soc/apple/mailbox.c` ASC semantics:
  A2I ctrl 0x110/send 0x800+0x808, I2A ctrl 0x114/recv 0x830+0x838,
  FULL=BIT(16), EMPTY=BIT(17), ep in MSG1[31:0]) inside the engine window
  it already maps.

## 3. Implementation — omarchy-ane `agent/ane-boundaries` @ `a481787`

`ane/h13/ane_h13_perf.c` (+ `ane/h13/Makefile`, `ane/h13/test-perf-mode.sh`):

- never binds the platform node — looks up the **already-probed** legacy
  device by name (param `pdev_name`, default `284000000.ane`) and refuses
  if absent: the production driver owning the node is the load-bearing
  safety gate (no probe-order races, cannot steal the node).
- gates: CPU_STATUS (`engine+0x1400048`) must read RUNNING; every wait
  bounded (2 s A2I drain, 5 s handshake, 5 s reply); all MMIO
  `ioremap_np` (the non-posted rule); reads logged before any write.
- `perf_mode=0` (default): handshake + EPMAP capture + logs only — no
  CSNE write. `perf_mode=1`: the exact 20-byte property write above.
- no RTKit power-state writes in either mode (fw already ON, ADT
  "pre-loaded"=1) and nothing on module exit — no quiesce, no reset.
- build (cross, x64 workstation → vermagic `7.1.6-1-1-ARCH SMP preempt
  mod_unload aarch64`, config = m1max-host `/proc/config.gz`, source =
  omarchy-linux 7.1.6 @ 078f865d1 in `/dev/shm/linux716` + O=
  `/dev/shm/k716`; `KBUILD_MODPOST_WARN=1` — no MODVERSIONS on this
  kernel): `ane_h13_perf.ko` sha256 `2d771ec452eabf22…` (16 KB).

Staged on m1max-host at `/var/tmp/ane-perf/` (`ane_h13_perf.ko`,
`test-perf-mode.sh`, `ane_h13_perf.c`), **not loaded**, lock untouched.

## 4. Exact test command (for the m1max-host owner lane, in a GPU-lock window)

```sh
ssh m1max-host
cd /var/tmp/ane-perf && bash test-perf-mode.sh
```

The script (5 stages, all flock'd, every log kept in
`/var/tmp/ane-perf/run-<ts>/`):

1. BEFORE slope — direct worker `--iterations 1` and `--iterations 32`
   (bundle 13c74423, libane d06222a8, smoke inputs): slope =
   (n32−n1)/31 ms/iter; hidden16 must equal `e1e061ab92ef1a61`.
2. `insmod ane_h13_perf.ko perf_mode=0` — capture-only: dmesg must show
   the fw-advertised endpoint bitmap and a completed HELLO. **If the
   mailbox is silent at +0x1408000, stop here** — that falsifies the h14
   mailbox offset on H13 and the receipt gets the log.
3. rmmod; `insmod ane_h13_perf.ko perf_mode=1` — the property write;
   dmesg shows the send + whatever the firmware replies.
4. AFTER slope — same worker measurement; same hidden16 gate (a wrong
   clock must not change outputs; the ANE is synchronous, but the gate
   stays).
5. rmmod — nothing left loaded.

Read-out: before vs after slope. macOS reference 140.1 ms sustained; Linux
fixed-clock baseline 440 ms/iter; a drop anywhere toward 260 or below is
the mechanism working. If the write is accepted (res=0) but the slope does
not move, the next datum is whether the fw's own CLPC uplink is alive on
Linux — capture `dmesg-perf.log` and report; do NOT retry with other
property values (0x10aa has exactly one observed value: 1).

## 5. Not done / open

- T8103 build: same source, needs a 7.1.13-3-2-ARCH prep tree (m1-host's
  config) — one `modules_prepare` run; not staged (m1-host leg is a lower
  priority than the T6001 anomaly and its node is `26bc04000.ane`).
- The SetupEndpoints doorbell bit placement remains [INFERENCE] (flagged
  in the t6021 receipt §3/§6); stage 2's capture-only run confirms ring
  announce semantics before any perf write goes out.
- Reply parsing: the module logs every reply message raw (ep + word);
  the CSNE res extraction (hdr+0x1c) is left to the receipt reader so no
  code path depends on a guessed reply layout.

## 6. Window results (2026-09-24 13:1x CDT, box loaned by Jw16GpuSubmit)

Staging defects fixed first: manifest.json restored to
`/var/tmp/encoder-whole/bundle` (from m1-host's surviving set, sha
`08769793f8ee…`, graph `020428fc`, converter `6a963f9` — the `13c74423`
lineage; also added to the t6000-host durable copy). Module v2
(omarchy-ane `073d0fa`, on-device build sha `2bfd726d…`): auto-discovers
the legacy-bound device by driver name (node address is boot-dependent:
`285c04000.ane` this boot) and maps the whole ane aperture (reg window
base 32 MiB-aligned down → `0x284000000`), with every early exit logged.

Findings:

1. **The perf-mode write is not deliverable from Linux as staged —
   there is no firmware to receive it.** `CPU_STATUS` at
   aperture+0x1400048 reads **`0x2a` (STOPPED|IDLE, RUNNING=0)** on
   T6001 Linux — the ANE ASC coprocessor is not started this boot, the
   same read the T6021 lane got (their §5). The module refuses by
   design and logs it (`dmesg-perf.log`/`dmesg-capture.log` in
   `m1max-host:/var/tmp/ane-perf/run-manual/`).
2. **The legacy island path demonstrably runs without the ASC fw** —
   the whole-encoder worker executed normally during the same window
   (below). So on H13 the engine executes TDs through the hardware task
   manager with the ASC coprocessor stopped; macOS's CSNE conversation
   requires booting that ASC from the iBoot-pre-loaded image first
   (ADT `pre-loaded`=1: image staged, CPU not run by Linux). The clock
   blocker therefore refines to: **Linux never boots the ANE ASC
   firmware; macOS does, then sends CH_PROPERTY_WRITE(0x10aa=1)**.
   Booting it is the t6021 lane's milestone 1 (quiesce-context RVBAR/
   CPU_CONTROL — the hard-reset class on T6021; not attempted here, not
   authorized on m1max-host).
3. **BEFORE slope anchor re-confirmed: 439 ms/iter** (n1=1088 ms,
   n32=14698 ms, pinned artifacts: bundle `13c74423`, libane `d06222a8`,
   worker `84e8cc8f`, on-device .ko `2bfd726d`). AFTER legs are
   meaningless without the write and are retained only as logs.
4. **Input-set re-anchor (honest):** m1-host's surviving "smoke" inputs are
   the golden **capture** inputs, not the purged e1e061ab smoke set.
   The gate leg with them gives hidden16 `fca96f1355485ec3`, and its
   output is **240000/240000 fp16-equal to the certified Apple capture
   `encoder_hidden.npy`** (`7e442034…`) — a strictly stronger
   correctness anchor than e1e061ab. The A/B anchor is now
   capture-inputs/fca96f13; e1e061ab is unrecoverable without the
   original smoke files (purged, no surviving copy).
5. Handback state: module unloaded, `/tmp/m1-gpu.lock` free at 666
   user, llm-inference left stopped for the owner lane's
   restore+verify; `/var/tmp/ane-perf/run-manual/` holds every log.

## 7. ASC boot campaign (2026-09-24, Main-authorized: m1max-host wholly owned)

Module v3 (omarchy-ane `0b1f158`..`a5c0f6c` lineage): runtime PM pin,
`probe_only`/`probe_reg` single-read bisect, `boot=1` M2-measured RUN
sequence. Two hazards found and fixed en route:

- **TM offsets are legacy-window-relative, not aperture-relative.**
  Reading TM_TQ_EN at aperture+0x2000c (unproven page) hard-reset the
  box; correct read is via the legacy reg window (0x285c04000) + 0x2000c
  (= 0x285c24000, m1n1's aperture+0x1c24000) → returns `0x3000`, the
  legacy driver's own TQ-enable state.
- **CPU_CONTROL (+0x1400044) reads are unproven on T6001** and cost a
  hard reset when added to the info line; the register is only touched
  by the boot WRITE itself. An unpinned visit also dies seconds later
  (autosuspend class, m1-host rule) — hence the runtime PM pin.

Results:

1. **The M2 boot sequence works on T6001.** With `boot=1`:
   RVBAR `0102010000a54001` (bit0 latched → never written), mailbox I2A
   already armed `0x00020001`, CPU_CONTROL write32 0 → 0x10, and
   CPU_STATUS **0x2a → 0x28 instantly** — the iBoot-staged ANE ASC
   firmware RUNS. First Linux-side ASC boot on T6001; zero resets from
   the write path (dmesg in `m1max-host:/var/tmp/ane-perf/run-boot/`).
2. **HELLO unanswered (5 s):** the booted fw has none of its macOS boot
   prerequisites — FW_INIT boot args, shared-memory surfaces
   (ANESharedMemorySurfaceParams), DART context (t6021-lane milestones
   4/5). No RTKit session forms without them, so the perf write stays
   undeliverable for now.
3. **Coexistence: NO.** With the ASC running, the legacy island worker
   times out (60 s deadline, no completion) — the booted fw takes over
   engine servicing and stops serving the TM island path. A reboot
   restores the parked-ASC state and the legacy path (verified: gate
   leg rc=0, 14,731 ms/32 iters, hidden16 `fca96f13` bit-exact — the
   440 ms/iter anchor intact).
4. **Consequence for the perf goal:** the encoder cannot be re-measured
   under the perf write through the legacy path — once the fw runs, the
   encoder itself must move to the CSNE path (PROCEDURE_CALL/
   INFERENCE_CALL over T2F_CMD), i.e. the full macOS-style ANE stack.
   The remaining work is exactly the t6021-lane's milestones 4–6
   (boot args + shmem surfaces, ring carve-out bookkeeping, first
   CSNE_CMD), now proven reachable on T6001 hardware: the CPU boots,
   the mailbox arms, and the RUN sequence is safe.

Handback: rebooted, service auto-started then left ACTIVE→stopped once
for the verification leg — final state: **llm-inference stopped** (owner
restores + completion-verifies), module unloaded, lock free. All logs in
`m1max-host:/var/tmp/ane-perf/run-boot/` and `/var/tmp/ane-perf/run-manual/`.

## 8. Q1/Q2 (Main, 2026-09-24): outbox/SCRATCH raw + segment coverage

**Q1 — did the fw HELLO unanswered, or did no word arrive? No word ever
arrived.** After RUN (boot poll clean, CPU_STATUS 0x28), 5 s later with
`scratch_dump=1` (module 0b1f158+scratch_dump build):

```
SCRATCH: i2a=00020001 recv0=0000000000000000 recv1=000a000000000000 a2i=00020001
SCRATCH0..7 = 00000000 ×8   (ap+0x1840048..+0x1840064)
```

I2A control armed+EMPTY (0x20001) the whole time — the outbox never
delivered a word; recv0/recv1 are stale zeros; SCRATCH0-7 all zero (the
kext's boot path publishes handshake words there — the fw never got that
far). The fw CPU runs but stalls before RTKit init: no boot args, no
shmem surfaces, and (Q2) no DATA-segment mapping.

**Q2 — segment coverage: NO.** T6001 ane0 ADT `segment-ranges` (64 B)
decodes as 2×32-B entries `{phys, iova, remap, size}`:

| entry | phys | iova | remap | size | role (T6021 analogy) |
|---|---|---|---|---|---|
| 0 | `0x10000a5c000` | 0 | `0x10000a5c000` (== phys) | `0x3000f4000` | TEXT+rodata, identity remap |
| 1 | `0x10001684000` | `0xf4000` | `0x1f0000f4000` | `0x5f8000` | DATA (cf. T6021 DATA `0x10001400000` → remap `0x100000c4000`) |

The legacy driver maps only its own BOs through its allocator/iommu
domain — neither the identity TEXT window nor the DATA remap
`0x1f0000f4000` is covered, so a booted fw DATA access faults exactly
like the 2020-era M2 fault at DATA+0x18a10.

**Test plan staged (needs one more window):** before RUN, program the
ANE DART instances that Linux does not own (dart-ane has three; m1n1
hacks TTBRs of instances 1 and 2 for exactly this) with PTEs mapping
the two entries phys→remap as above, then RUN and poll outbox +
SCRATCH7 + DART fault regs for 60 s. Direct DART programming is a
m1n1 `dart.py`-style port (~200 lines: TTBR + level-table walk) and is
shared work with M2FwStart-2's T6021 attempt — the decode above is the
T6001 input to that port.

## 9. Pre-RUN island word (AneStaticStart prerun-diff, 2026-09-24)

With write32(0x2e0, 0xf) first in program order (kext 0x95d0e08,
static-confirmed position), CPU_STATUS reads **0x08** instead of 0x2a —
the island word changes the parked-state representation (bit1 STOPPED
and bit5 clear; STOPPED-gate passes). RUN + handshake sequence
completed as before; HELLO still unanswered (hello=0, epmap=0) — the
remaining blockers are the segment mappings and boot-args/shmem
bring-up of §8, not the RUN preamble. Module v3.2
(omarchy-ane agent/ane-boundaries, pre-RUN write commit); box restored
to serving (llm-inference active).

## 10. DART segment-map port spec (AneStaticStart kernelcache diff, STATIC-CONFIRMED)

Apple `_dartMapiBootFirmware` (kext 0xfffffe0008bc8e3c) walks **0x20-byte
records**: `phys@+0x0, iova@+0x10, len@+0x18 (u32), flags@+0x1c (u32,
bit1=skip)`, clamps each record into `[dart_vm_base, dart_vm_base+size)`
(records outside the live VM window are DROPPED, not faulted), then
`iovmInsert(mapType = 3-or-4 by flags bit0, iova, 0, phys,
page-aligned len)` per record.

Layout correction to my §8 table: the kext `iova` is what §8 called
"remap". Corrected T6001 mappings (flags both 0 → mapType 3):

| entry | phys | iova (fw access) | len |
|---|---|---|---|
| TEXT | `0x10000a5c000` | `0x10000a5c000` (identity) | `0x3000f4000` |
| DATA | `0x10001684000` | `0x1f0000f4000` | `0x5f8000` |

Verbatim mapping without the clamp risks parking the fetch with zero
faults — the exact HELLO-silence symptom.

Port notes for T6001: `iommu_map` on the legacy-attached domain programs
all three dart-ane instances (verify the device's iommu group carries
dart1/2 — they sit on ane_cpu). Reaching that domain from a helper
module is the open bit: either export a mapping op from the legacy
driver, or program un-owned instances directly (m1n1 `dart.py` port:
TTBR + level tables, instances 1/2 free of apple-dart ownership).
T6021-symmetric: same record layout, entries from M2FwStart-2's decode.

## 11. Correction: the 0x2e0 write STRUCK (AneStaticStart c33c0d3)

The §9 island word is a **pmgr ps write** (kext PS register control,
phys base 0x28e080000) — genpd already covers it, and reissuing it
wedged the M2. My engine+0x2e0 variant hit a different address but is
struck anyway. The 0x08 CPU_STATUS representation recorded in §9 was
an artifact of that stray write, not a firmware view. Corrected first
missing NON-ps write: **PWGATE+0x159c = 0** (third-window region;
T6001 base unresolved — the T6001 ADT shows only the aperture + pmgr
windows, so the PWGATE resolution is the open item). Module source on
m1max-host updated to the struck sequence.
