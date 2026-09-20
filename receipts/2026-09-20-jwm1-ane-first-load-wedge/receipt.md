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
