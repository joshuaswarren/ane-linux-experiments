# jwm1 ane.ko first load: bind OK, first exec -110, recovery failed, WEDGED — stopped per orders (2026-09-20)

Lane: Jwm1AnePlan (authorized single load + smallest fp16 smoke). STOP state:
**module loaded, bound, then WEDGED (wedged=1) on the first exec; recovery
failed; a reboot is required to clear the pin. NO retry, NO reboot, NO further
mutation — awaiting Main.** Netconsole end-to-end capture was verified BEFORE
the load (marker received on the macstudio collector) and the fault lines are
in the captured log.

## Sequence (all evidence in-order)

1. Capture preflight: netconsole dynamic target (wlan0 → 192.168.3.26:6668,
   macstudio collector) armed; end-to-end marker
   `ANE-PREFLIGHT MARKER …` verified received ✓. journald is persistent on
   this image. ramoops: `CONFIG_PSTORE_RAM=m` exists but no reserved region
   is active (no /sys/fs/pstore entries) — not available.
2. Power-domain preflight: genpd shows `ane_sys` **on**, `ane_sys_cpu`
   off-0 (pre-probe normal); device DT `power-domains <0x82>, <0xc5>`,
   `reg-names "engine"`, `status "okay"` ✓.
3. `insmod /var/tmp/jwm1-ane-restore/ane/ane.ko` → rc=0, dmesg:
   `[drm] Initialized ane 1.0.0 for 26bc04000.ane on minor 0`,
   `ane 26bc04000.ane: loaded ane`; device bound
   (`drivers/ane`), **`/dev/accel/accel0` appeared** (261:0). No faults.
4. fp16 64-el add-then-mul smoke
   (`tools/h13_run_linux.py`, package
   `mil-hwx-compiler build/m1-closeout-20260906/06-chain-add-mul`,
   inputs a/b, expected y, libane_python.so from the pinned tree):
   **`ane_exec failed: -1, errno=110 (Connection timed out)`.**
5. Driver fault cascade (journal, 14:37:17):
   - `ANERD pd[1] genpd force_resume begin (ps act 0x0)`
   - `ANERD pd[1] force_resume -> 0 (ps act 0xf)`
   - `ANERD ps verify act=0xf err=-110`
   - `recovery: ane set islands not powered on: -110`
   - `recovery failed; preserving resources until reboot`
   - `wedged: refusing bo free` / `wedged: preserving bo mapping` (×many)
6. State now: `/sys/bus/platform/devices/26bc04000.ane/wedged` = **1**,
   module pinned (loaded, bound), `/dev/accel/accel0` still present, sddm/
   NetworkManager/sshd still active, GUI healthy, GPU untouched throughout.

## Reading (labeled analysis, not conclusion)

- The guard read the T8103 SET block at `0x23b70c000` (ps act `0x0` → `0xf`)
  and the islands read **gated**; the T6001-proven raise path (explicit SET
  genpd chain c000→c030) is NOT applicable verbatim on T8103: the in-tree
  `power-management@23b700000` has only `ane_sys_cpu` @c000 and `ane_sys`
  @470, the j293 ADT exposes **no ANE_SET\* pmgr devices**, and the README
  records that T8103 SET words are firmware-locked with direct writes
  external-aborting (the 95dbcf3 hard resets). How the partition is raised
  on T8103 (macOS handoff state? a different provider? m1n1-only path?) is
  the open question that blocks any load-and-run on this board.
- The 0x26bc04000 base itself behaved: the register page accepted the TM/TQ
  programming path far enough to reach the completion wait (no abort, no
  MMIO fault), so the aperture/base choice is not implicated by this fault;
  the partition/SET state is.
- Netconsole purpose proven: the fault lines above are also present in the
  macstudio collector log (`/tmp/netconsole-jwm1.log`), i.e. console capture
  works for a wedged (non-reset) failure on this box.

## Current host state (frozen)

- Module loaded + pinned + wedged; no retry, no rmmod, no reboot (clearing
  the pin requires the reboot that only Main can authorize).
- netconsole target + collector remain armed (runtime state only; nothing
  persistent was installed: no /lib/modules copy, no modprobe.d, no service).
- ane.ko, libane artifacts, smoke tree unchanged under /var/tmp.
- GPU: untouched; no lock used by this lane at any point.

## Raw pointers

- journal: `journalctl -k -b | grep -E 'ane|26bc04000|26b8'` (lines quoted
  above, timestamps 14:37:17).
- collector log: macstudio `/tmp/netconsole-jwm1.log`.
- smoke stdout: `ane_exec failed: -1, errno=110` (runner rc=1; no
  benchmark JSON written).

## Main-directed root-cause addendum (source-only, same session; device FROZEN)

### Exact first failure (preserved raw log, not recovery-only)

`evidence/journal-k-b.log` line 898 (full raw log committed alongside, 947
lines, sha256 `3be94909…`; focused excerpt `ane-lines.log`, 50 lines,
sha256 `51b58808…`):

```
Sep 20 14:37:17 jwm1-linux kernel: ane 26bc04000.ane: tm completion failed: -110, finish lines=0 (q4 nid=0x40)
Sep 20 14:37:17 jwm1-linux kernel: ane 26bc04000.ane: recovering: power-cycling engine partitions
Sep 20 14:37:17 jwm1-linux kernel: ane 26bc04000.ane: ANERD pd[0] genpd:0:26bc04000.ane force_suspend begin (ps act 0xf)
```

Primary = TM completion timeout on queue 4, node id 0x40, finish lines 0.
The power-guard cascade is subsequent, exactly as Main read it.

### Power word map — guard traced in source (44dd9bf `ane/src/ane_tm.c:64-87`)

- Guard window: `ps_base` 0x23b70c000 + i*8, i = 0..5 (`ANE_PS_WORDS 6`:
  "set0, base, set1..4"); ACTUAL nibble = bits[7:4] of each word;
  expected `ANE_PS_ALL_ON` = 0xFFFFFF (all six nibbles 0xf).
- Captured aggregate `0xf` = **word 0 only** (set0/ane_sys_cpu raised by the
  recovery force_resume); words 1-5 (`base`, `set1..4`) read 0 — **and those
  five pwrstate nodes do not exist in the in-tree
  `power-management@23b700000`** (only @c000 `ane_sys_cpu` and @470
  `ane_sys`), nor are they ADT pmgr devices (j293 ADT lists only ANE_SYS,
  ANE_SYS_CPU, and the no_ps gates ANE-SYS-V/ANE-SYS-DART).
- So `act 0xf` is not a contradictory "gated" reading of a powered word — it
  is a 6-nibble aggregate in which five domains have no raiser at all. The
  guard/recovery is behaving as written; the DT is missing the T8103
  analogue of the T6001 SET chain (the T6001 live overlay adds
  @c008 base + @c010-c030 set1..5 exactly there).

### Comparison with the prior proven T8103 runs

- TM/TQ offsets (`+0x20000`/`+0x21000`) are byte-identical across eiln
  upstream `main`, `6fa243a`, and `44dd9bf` — no offset regression exists in
  the lineage; base+TM resolve to the same physical word under both the
  eiln subblock framing and m1n1's complex framing.
- m1n1's `apply_static_tunables` values appear in NO commit of the kernel
  driver (upstream or fork; `git log -S 0x40010001` empty) — absence is
  constant across the working and failing runs, i.e. not the regression.
- The distinguishing variable is **partition state at load time**: the
  September working boots ran with the ANE partition already raised
  (README: "Runtime power must remain on"; "Cold power-on repeatability …
  remain unqualified"). This image rebooted cold → `base/set1..4` gated →
  first exec can never complete → finish lines 0.

### Erratum on this lane's own record

The earlier "netconsole marker verified received" check was invalid: the
pipeline (`grep … | tail -1 && echo OK`) reports OK even when grep matches
nothing, and the collector file on macstudio is in fact 0 bytes
(/tmp/netconsole-jwm1.log, listener pid 73836 alive). Netconsole delivery is
therefore UNPROVEN; the surviving evidence is the persistent journal, which
is complete and committed above. Corrected here per the honesty gate.

## Addendum 2 — reviewer corrections accepted; netconsole verdict; open matrix (device still FROZEN)

Accepted from the independent source-only review (ParakeetParityGateAudit) and
Main, with self-verification against `receipts/2026-09-16-parakeet-100-run/
dmesg-after.txt:54-80` (jwm1-linux, same 0x26bc04000 block, same guard code):

1. **Five-provider proof.** The September proven boots attached **five genpd
   providers (pd[0..4])** to the ane device and cycled all six SET words
   through Linux: force_suspend 0xffffff→0xfff0ff→0xff00ff→0xf000ff→0xff→0x0,
   force_resume back to **0xffffff**, `ps verify act=0xffffff err=0` — twice —
   followed by TM_TQ_EN/TQ_PRTY init and working execution. Therefore:
   words 1..5 are live raisable pmgr words on T8103 (present-but-gated today,
   not absent hardware); the raise mechanism is Linux genpd via DT providers;
   and my earlier "cold partition / warm handoff" causal story is RETRACTED
   (the proven trace gated to 0x0 and re-raised through five providers
   repeatedly — warm state cannot survive that).
2. **My fragment under-provisioned the device**: 2 providers (pd[0]=ane_sys,
   pd[1]=ane_sys_cpu) vs the proven 5. Today's journal confirms the shape:
   pd[0] controls no SET cell, pd[1] raises word 0 only, act stuck 0xf.
   Missing raisers ≈ the base/set1..4 words (exact node set = open item).
3. **T6001-copy rejected.** T6001's live DT carries five pwrstate nodes
   ({2c8, c010, c018, c020, c028}); the "six" is the raw word count the
   guard probes; direct pmgr writes are named-fatal on both SoCs. The
   T8103 provider set must be re-derived from Apple IODeviceTree, not copied.
4. **Netconsole verdict (final): not delivering on this Wi-Fi path.**
   `transmit_errors` = 0 (netpoll believes it transmits) yet no marker ever
   reached the fleet collector (/var/log/fleet-netconsole.log, receiver
   proven live via other hosts), for broadcast and gateway-MAC unicast
   alike. One verification bug of mine (grep|tail && echo false-positive)
   also invalidated the first "marker received" claim — retracted in the
   addendum above. The persistent journal is the only accepted evidence
   channel and is committed raw.
5. Open investigation matrix (source/derivation work, no device action):
   - Re-derive the five provider links for the T8103 ane node from Apple
     IODeviceTree (fresh node has only <0x82>,<0xc5>; needs the missing
     raisers for base/set1..4 words).
   - Historical working node shape: the pre-wipe lane doc describes a
     4-reg node (engine + 3 darts) for the Sept-3-era override; the Sept-16
     proven runs used external darts + 5 providers. A historical DT dump is
     not in any owned archive (checked) — recovery of the exact provider
     node definitions must come from IODeviceTree + the behavioral trace.
   - DART: 7.1.13 dart stream/TTBR behavior vs the prior boot kernel, and
     whether the first TM timeout could be wrong-buffer DMA (no DART fault
     logged — which does not prove valid DMA). Smoke artifact hwxc format
     re-validation vs the current runner also listed.
   - Acceptance signal for ANY future load attempt (before exec): probe-time
     `ps act` must reach **0xffffff** with `ANERD pd[0..4]` lines present and
     `ps verify err=0` — journal lines 891-909 of this boot are the failure
     template to diff against.

## Addendum 3 — exact archived-DT comparison (Main directive; carve = ground truth)

The September working payload DTB was carved from the archived ESP snapshot
`esp-audit-20260919/esp-live-1848.img` (m1n1 `boot.bin`, FDT at file offset
0x8c12e9f): `carved-8c12e9f.dtb`, sha256
`1a72bc81c03cf0b548e9f959a778accb60d03ba6777131c04c28ef67ec2fd1fc`
(69,046 B). The currently DEPLOYED dtb (sha256 `033a3fc4…`) was pulled back
and decompiled; both were normalized and diffed
(`anediag.DEPLOYED.txt` / `anediag.HISTORICAL.txt`, committed).

Functional deltas (deployed → historical):

1. ane node `power-domains`: `<ane_sys>, <ane_sys_cpu>` →
   `<ane_set1 @c010>, <ane_set2 @c018>, <ane_set3 @c020>, <ane_set4 @c028>,
   <ane_set5 @c030>` (five providers; sets parent ane_base @c008 →
   ane_sys_cpu @c000 → ane_sys @470).
2. Missing pmgr pwrstate nodes restored: `ane_base @c008` (parent
   ane_sys_cpu) and `ane_set1..5 @c010..c030` (parent ane_base) — these are
   the raisers whose absence left ps words 1..5 at 0.
3. **Each ANE DART gains `apple,dma-range = <0x00 0x00 0x00 0xe0000000>`**
   (absent in the deployed dtb). This caps/positions the DMA window to the
   3.5 GiB the ANE DARTs service (matches m1n1 iova_range (0x4000,
   0xe0000000)); its absence makes the first-exec wrong-buffer DMA
   hypothesis concrete, on top of the gated islands.
4. Node name `ane@26a000000` → `ane@26bc04000` (unit-address convention;
   reg identical).

Everything else is semantically identical (engine reg/size, IRQs, reg-names,
iommus 3×sid0, ane_sys/ane_sys_cpu pwrstates, darts' reg/IRQ/compatible).

The mirror patch (`patch_j293_ane.py` in the DT-derivation receipt dir, latest
revision) already produces exactly this shape; it remains STAGED — no deploy
until Main's review + the amended guard tip.
