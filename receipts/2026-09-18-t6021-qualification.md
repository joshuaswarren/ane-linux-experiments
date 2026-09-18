# T6021 qualification attempt — DT node absent, halted at gate (a) with capture (2026-09-18)

Verdict: **CAPTURED-FAILURE, no retry.** The runbook's stage step is fully green
(rebuild for the running kernel 7.1.13, smoke stack ported and hash-verified),
but **no bind was ever possible**: jw14m2-linux's live device tree has **no
`apple,t6021-ane` node** (and no ane DARTs). The driver's `of_match_table`
therefore never matches, the probe never runs, the RECOGNIZED-tier refusal
never speaks, and `/dev/accel/accel0` cannot exist. The board overlay the
README row already lists as data-needed is the blocker. **No tier promotion.**
No SET-block write anywhere, no GPU touch, jwm1 untouched, jw16 read-only.

## 1. Stage — all green

| item | value |
| --- | --- |
| host | jw14m2-linux (Mac14,5 / M2 Max / J414c, aarch64), kernel **7.1.13-1-1-ARCH** running |
| root | passwordless sudo live (Joshua), ROOT-OK verified on-box |
| source | `omarchy-ane` `feat/t6021-soc-entry` **3b0d115** — git-bundle from workstation → `/tmp/omarchy-ane`, HEAD verified |
| build | `make -C ane` clean (CC/BTF) against `/usr/lib/modules/7.1.13-1-1-ARCH/build` (headers present; pahole present) |
| ane.ko (running kernel) | sha256 `acae46e62c57fd01acfb6cf26b30aa7b6fe90fe40126d2ba413d4b81ae19eed6`, `modinfo -F version` = `3b0d115`, vermagic `7.1.13-1-1-ARCH SMP preempt mod_unload aarch64` |
| ane.ko (pending kernel) | built per Joshua's heads-up against `/usr/lib/modules/7.1.13-3-1-ARCH/build` (linux-asahi-headers 7.1.13.asahi3-1 already installed) at `/tmp/omarchy-ane-k3/ane/ane.ko`, sha256 `8441546fd2b7a7a7091ba2ba096f133e7678f6de9fee2f34358ee88e20ecdd88`, vermagic `7.1.13-3-1-ARCH SMP preempt mod_unload aarch64` |
| smoke stack | ported jw16 `/var/tmp/jw16-ane-first-exec` → jw14m2 `/tmp/t6021-qual` (jwm1 unreachable — ssh timeout; jw16 is the canonical source per the soc-table receipt), layout per prepared receipt §3 |

Smoke-stack bytes identical on both hosts (sha256 pair-verified after copy):
`a.bin 89f3acad…`, `b.bin 0b61cf15…`, `y.bin abd3b8c9…`, `libane.so
1ab9d95d…`, `mlx-omarchy-ane-worker 575e2acd…`, bundle `manifest
4a9ba229…` / `program-0 9a6a6a9a…` / `program-1 62595e4a…` (same manifest
hashes as the 2026-09-14 control-64el receipts).

## 2. Gate (a) executed — refusal path unreachable (dmesg evidence)

One plain insmod, full capture, then rmmod; **no further loads**:

```
$ sudo insmod ane/ane.ko        → rc=0
  dmesg: [1650.496472] ane: loading out-of-tree module taints kernel.
  (NO probe lines, NO "recognized but unqualified" refusal — of_match never matched)
$ ls /dev/accel                 → No such file or directory
$ lsmod | grep -w ane           → ane 65536 0 (loaded, idle)
$ sudo rmmod ane                → rc=0, module gone
```

Full dmesg snapshot: `/tmp/t6021-qual/dmesg-after-plain-insmod.txt` on the box.
Gate (a)'s expected refusal cannot fire without a DT node. Gates (b)–(e) are
unexecutable for the same reason: a forced bind needs a node to bind; the ps
probe and the exact smoke need `/dev/accel/accel0`. `allow_unqualified=1` was
**not** attempted — with no node it cannot bind anything and would only idle;
that would be a load with no evidentiary value (discipline: no retry-class
loads).

## 3. The DT gap — evidence

- Live FDT: `find /sys/firmware/devicetree/base` → no `ane@` node, no ane
  DART anywhere (only false positive: `dcp…/panel`).
- Collector quick run on-box: `ane_node_present: False`; the listed
  `apple,t6020-dart` iommus are display DARTs (`iommu@1302f…`, disabled).
- Stock `t6021-j414c.dtb` (`/usr/lib/modules/7.1.13-1-1-ARCH/dtbs/`): strings
  carry the **pmgr ANE domain names** (`ane_base ane_cpu ane_set1 ane_set2
  ane_set3 ane_set4 ane_sys ane_sys_mpm ane_td`, `pmp-ane-sys`) but **no
  `ane@` platform node and no ane DART nodes**.
- **Linux-side SET-window corroboration (new, free with this run):** the stock
  DTB instantiates `pmgr@28e080000` with ANE pwrstate children at offsets
  `260, 2e0, 4000, 4008, 4010, 4018, 4020, 4028, 4030` (quick.json
  `pmgr_domains`, all `apple,t6020-pmgr-pwrstate`) — matching the T6020
  community rows (`260/2e0/4000/4008`) and putting the `+0xc000` SET window at
  **`0x28e08c000`**, exactly the descriptor's `ps_base`. The 3b0d115 constant
  now has Linux-side confirmation; only execution proof is missing for
  QUALIFIED.
- `/sys/firmware/fdt` sha256:
  `e5b5489aedee80e20b6d07a3764b015e0da085faa5ce1bea11589c6047d3a7e3`.

## 4. Why the board overlay was not authored here

The overlay needs four inputs; two are not derivable from data in hand:

1. **Engine `reg` (hard gap):** the Linux ane node needs a `0x24000` engine
   window. T6001's `0x285c04000+0x24000` came from jw16's **live ADT**
   (t6001-packaged-dts `9247b41f`, t6000-live-mapping). The t6021 macOS
   captures record only the ANE MMIO *block* `0x84000000/0x2000000` (plus the
   pmgr windows) — no engine sub-window. The t6001 engine sits at
   block+`0x1c04000`; nothing proves that offset on t6021. A guessed engine
   base is the external-abort/brick class the runbook and README fence off.
2. **DART stream IDs:** t6000-cells receipt records the explicit
   missing-symbol STOP (`sids=<0xa001>` is not a Linux cell). jw16's live node
   resolves to three literal-`0` tuples (`<&dart 0>` ×3, od-verified) — the
   candidate for t6021, but it needs the same evidence bar (ADT cross-check).
3. IRQ (candidate only): macOS AIC `0x374` (ane) / `0x375` (dart-ane0) →
   AIC2 4-cell `<0 0 0x374 4>`; family pattern (t8103 source, jw16 live
   flags=4) supports LEVEL_HIGH.
4. pmgr phandles (present, enumerable): the stock DTB already has the ANE
   pwrstate nodes — trivial once dtc/fdtget is installed on the box.

Boot/DTB delivery (for the future install): m1n1 `boot.bin` on the ESP embeds
the t6021 DT (strings match); GRUB has **no** `devicetree` line; stock DTB
lives at `/usr/lib/modules/<ver>/dtbs/t6021-j414c.dtb`. Install path options —
rebuild/re-flash the boot.bin chain, or a merged DTB via a GRUB `devicetree`
line — to be chosen at overlay time; revert path exists (macOS side reachable
over ssh for recovery).

## 5. ane_port_detail (quick mode) — recorded

- On-box: `/tmp/t6021-qual/quick.json`, 105,085 B, sha256
  `2ba2bcf416fb7afad997b1754ec0845b52b14530c30ce532be55374daf3d5228`
  (`collect_quick.py --out`, no submit; modules collect_common/collect_macos/
  bench_matrix copied from mlx-omarchy scripts).
- Bounded payload blob (what a submission would carry):
  `/tmp/t6021-ane_port_detail.json`, 52,226 B, `truncated: ["phandles:3"]`,
  `devicetree.ane_node_present=false`, AIC `apple,t6020-aic`, 9 ANE pmgr
  pwrstate entries as listed in §3, display-only DARTs.

## 6. Next run — mechanical list (then re-run the runbook unchanged)

1. Get the t6021 ADT: m1n1 boot (or ADT exposure from Linux if available) →
   capture `ane0` / `dart-ane0` / `mapper-ane0` nodes; read engine reg
   base+size, dart windows, `sids`, interrupts. Compare side-by-side with the
   macOS archive constants (phandles 0x169/0x16a/0x16b, dart quartet
   `0x85800000/0x85810000/0x85820000/0x85804000`, AIC 0x374/0x375).
2. Author the overlay: template = jw16 live node (below) + t6001-packaged-dts
   source `9247b41f` (disabled-SoC-node + board-enable shape); compatible
   `apple,t6021-ane`; ps_base stays in the driver (already corroborated).
3. Install (boot.bin rebuild or GRUB devicetree + merged DTB), boot, confirm
   the node, then execute the prepared receipt §3 command verbatim (gates a–e,
   promotion rule). Use the `-3` .ko if the box has rebooted onto
   7.1.13-3-1-ARCH by then.
4. h14g backend caveat unchanged: if the M1-compiled smoke bundle does not
   exact, re-mint per prepared receipt §3 (h14g ≡ h13 family invariance
   re-proven on 26.6.2 **and** 27.0).

**Reboot contingency (Joshua, 2026-09-18):** a NEW kernel (`7.1.13-3-1-ARCH`,
pkgrel bump) is already installed on jw14m2 and NOT yet booted. All gates in
this run ran under the RUNNING 7.1.13-1 kernel; no reboot was performed. The
matching `-3` .ko is pre-built (§1) so a post-reboot re-run only needs
`insmod /tmp/omarchy-ane-k3/ane/ane.ko` in place of the `-1` path — **if the
box reboots before the runbook can be completed, the module must be rebuilt
(or the pre-built `-3` .ko used) for the new kernel and the gates re-run from
gate (a)**. Note `/tmp` does not survive reboot: `/tmp/omarchy-ane`,
`/tmp/omarchy-ane-k3` and `/tmp/t6021-qual` are re-stagable in one scp each
(bundle `omarchy-ane-3b0d115.bundle` kept on the workstation at
`/tmp/omarchy-ane-3b0d115.bundle`; stack source jw16
`/var/tmp/jw16-ane-first-exec` unchanged).

## 7. jw16 live-node template (od, 2026-09-18, T6001/J316c — reference for the overlay author)

```
compatible       "apple,t6000-ane"
reg              02 85c04000 00 0024000        (engine 0x285c04000+0x24000)
iommus           <0x10b 0> <0x10c 0> <0x10d 0> (three ane DARTs, stream id 0)
power-domains    <0x108> <0x10e> <0x10f> <0x110> <0x111> (ane_sys_cpu + SET1..4; not set5)
interrupts       <0 0 0x302 4>  interrupt-names "ane"   (AIC2, level-high)
node path        /soc/ane@284000000
```

## 8. Refs

- Driver branch (unchanged, nothing to promote):
  `omarchy-ane` `feat/t6021-soc-entry` @ **3b0d115** —
  https://github.com/joshuaswarren/omarchy-ane/commits/feat/t6021-soc-entry
  (origin ref verified this run).
- This receipt: `ane-linux-experiments` commit recorded in the git log; pushed
  to origin.
- Input receipts: `2026-09-18-t6021-driver-entry-prepared.md` (runbook),
  `2026-09-18-jw14m2-macos26-capture.md` (+27 addendum),
  `2026-09-17-t6021-macos-capture.md`, `2026-09-13-t6001-packaged-dts.md`,
  `2026-09-13-t6000-ane-dart-cells.md`, `2026-09-13-t6000-ane-interrupt-cells.md`,
  `2026-09-17-ane-soc-table.md`.

## Host mutations

jw14m2: `/tmp/omarchy-ane`, `/tmp/omarchy-ane-k3`, `/tmp/t6021-qual/**`
(artifacts listed above), one clean insmod/rmmod cycle (no probe, no device
touch). jw16: read-only scp from `/var/tmp/jw16-ane-first-exec`. Workstation:
git bundle at `/tmp/omarchy-ane-3b0d115.bundle`, quick.json copy +
`/tmp/t6021-ane_port_detail.json`. No ANE device writes on any host; no
SET-block write; no service touched; no GPU use.
