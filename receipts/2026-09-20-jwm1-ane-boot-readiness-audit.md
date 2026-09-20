# jwm1 ANE boot-readiness audit + pinned restore artifacts (2026-09-20, CPU/disk only)

Lane: Jwm1AnePlan (continuation). Host: jwm1-linux (T8103, `C02DP17UQ05P`).
Scope per Main: independently audit the btrfs-v7 GRUB reboot gate, extract the
exact proven DT/module recipe from our repos, prepare build artifacts and
non-destructive checks. **No ANE module load, no DT write, no reboot, no
Wi-Fi/password change.** GPU lane stayed with GPUparityroot-causeaudit
(coordinated; my work is CPU/disk only). Companion to
[2026-09-20-jwm1-ane-restoration-plan.md](2026-09-20-jwm1-ane-restoration-plan.md),
which this receipt corrects on the DT mechanism.

## Verdict

1. **Reboot gate: PASS** — the byte-compare arm of the btrfs-v7 GRUB rule is
   satisfied on the fresh image.
2. **The DT recipe in the earlier plan is corrected**: the eiln-era
   `m1n1 boot.conf overlay=` flow is **obsolete on this image**. The real
   mechanism is the packaged-DTB + `update-m1n1` payload. Exact node values
   are an explicit re-derivation item, not inferred.
3. **Build artifacts exist and are pinned**: the receipt-proven driver tree
   (`omarchy-ane` @ `44dd9bf`) compiles **unmodified** against the running
   kernel's headers — `ane.ko` with exact vermagic, `libane.a`, and the
   Python binding, staged only. Nothing installed, nothing loaded.

## 1. Boot-gate audit (all reads; one `grub-fstest cmp`)

Chain on the fresh image: m1n1 `boot.bin` (ESP `/boot/efi/m1n1/`, with
`boot.bin.old` backup) → U-Boot (embedded; `ubootefi.var` env is effectively
empty — no custom bootcmd to unwind) → `EFI/BOOT/BOOTAA64.EFI` = **GRUB**
(strings confirm; sha256 `fc9ea5c61430562168a62aaca592f8e6721dfe59c404246dc98fc2d35019cb3d`,
pkg `grub 2:2.14-1.1`, 245 modules incl. `btrfs.mod` under `/boot/grub/arm64-efi/`
on the same btrfs) → kernel from `/@/boot` (btrfs, `/dev/nvme0n1p5`).

Because GRUB reads its own modules **and** the kernel from the btrfs subvol,
the gate applies. Check executed with the installed `grub-fstest` (same
package build as the booted `BOOTAA64.EFI`, not a version-string claim):

```
grub-fstest /dev/nvme0n1p5 cmp /@/boot/vmlinuz-linux-asahi    /boot/vmlinuz-linux-asahi    → rc=0
grub-fstest /dev/nvme0n1p5 cmp /@/boot/initramfs-linux-asahi.img /boot/initramfs-linux-asahi.img → rc=0
```

Both boot files read back byte-identical through GRUB's btrfs driver on this
filesystem. Empirical corroboration: the image has booted repeatedly today.
Recovery context verified intact: macOS + Recovery APFS partitions unchanged
([clean-install receipt](2026-09-20-jwm1-clean-install.json)), payload backup
`boot.bin.old` present, U-Boot env clean. **Planned reboots are no longer
blocked by the boot gate.**

## 2. DT recipe — corrected, receipt-pinned

What does NOT work here (documented dead ends, keep them dead):

- **m1n1 `boot.conf` overlay=** (eiln README flow, `ane.dtbo` @ `83103ae`,
  sha `88bdb7cf…`): the running m1n1 1.6.1 ships **no `boot.conf` support**
  (no config parser in the tree), and the payload is m1n1+U-Boot, not a
  direct kernel. The April dtbo is also the **wrong node shape** — it is not
  what ran in September.
- **GRUB `devicetree` / frozen `.dtb` override**: replaces the m1n1-patched
  live tree and drops injected values — produced the documented one-core
  incident ([boot-and-kernel.md](../.local/ane-v064-wt/docs/boot-and-kernel.md),
  "Omarchy ANE test (STALE DT: boots 1 core only)"). Do not resurrect.

What DOES work (the September-proven mechanism):

1. The kernel receives the **m1n1-patched tree from the ESP payload**.
   `update-m1n1` (pkg `asahi-scripts 20260127.1-1`, present on this image)
   bakes DTBs from `/usr/lib/modules/<newest *-ARCH>/dtbs/` into
   `/boot/efi/m1n1/boot.bin`, keeping the old payload as `boot.bin.old`.
2. Therefore: add the ANE node to the t8103 DTB **in-tree in the payload**:
   - node shape as bound on the working September boot: `ane@26a000000`,
     `compatible = "apple,t8103-ane"`, `reg-names = "engine","dart0","dart1","dart2"`
     (four `reg` ranges), `interrupts = <0x1a0 0x1a1>` /
     `interrupt-names = "ane dart"`, plus `power-domains` and `iommus`
     ([boot-and-kernel.md](../.local/ane-v064-wt/docs/boot-and-kernel.md);
     platform device then appears as `26bc04000.ane`).
   - packaged `t8103-*.dtb` does **not** carry the node (verified `0` on the
     old kernel; re-verify on `7.1.13-3-2-ARCH`'s shipped dtbs before any work).
   - **OPEN ITEM (deliberately not inferred):** the exact `reg` /
     power-domain / iommu values for THIS boot chain must be re-derived from
     Apple's IODeviceTree on the intact macOS side (same method the working
     boot used) and cross-checked against the documented shape; the April
     dtbo is a cross-check only. No boot test until this node is written and
     reviewed.
3. Verify per the published checklist after reboot: `nproc` (8),
   `/sys/devices/system/cpu/online` `0-7`, `find /proc/device-tree -name '*ane*'`,
   compatible readback — then the driver ladder.

## 3. Driver/libane pin + build artifacts (this lane)

Pin: `joshuawarren/omarchy-ane` @ **`44dd9bf`** ("ane: tm recovery — T8103
no-reboot proven, T6001 fails safe", 2026-09-16). Ancestry checked in-repo:
`6fa243a` (the receipt-pinned T8103 driver in
[2026-09-15-jwm1-ane-wedge.md](2026-09-15-jwm1-ane-wedge.md)) is an ancestor;
libane at this tree is the schema-4-proven `f261a6cb` state **plus
additions only** (`ane_bind.h`, `ane.h`; `git diff --stat f261a6cb 44dd9bf --
libane bindings`). Current `feat/t6021-ane-driver-w13` checkout was NOT used.

Source archive `omarchy-ane-44dd9bf.tar.gz` sha256
`79e8dbdafe22426cb23e0a5fb1f0c91632e004e185397436d64d69f2eadc08e0`, verified
after scp. On jwm1, prerequisite `linux-asahi-headers 7.1.13.asahi3-2`
installed from the `asahi-alarm` repo (`pacman -S --needed`, no refresh;
kbuild dir verified). Builds (unmodified sources):

| artifact | sha256 | note |
|---|---|---|
| `ane/ane.ko` | `14ff769f899b2b667685f640515040db5c0d080644ac575cf06d7301bc30c310` | vermagic `7.1.13-3-2-ARCH SMP preempt mod_unload aarch64` (exact match) |
| `libane/libane.a` | `9b60216e1754fb9c365b21c8f1cd04149000e1125ec4bbcd3772b507474f6534` | `-Wall -Werror` clean |
| `bindings/python/dylib/libane_python.so` | `76fedabb1617a88f3708c0be237980c285c0b64e62e7adad6338f79756b0cff3` | built against the pinned `libane.a` |

Location: `/var/tmp/jwm1-ane-restore/`. **The module is not copied to
`/lib/modules`, not depmod-ed, not loaded** — the Sept-3 working-tree state
reset the machine on load, and loading belongs to the qualification ladder
below, never to an artifact-prep lane.

## 4. Remaining ladder to live ANE (each step gated, no shortcuts)

1. Re-derive node values (§2 open item), patch the t8103 dts, rebuild the
   dtb into `/usr/lib/modules/7.1.13-3-2-ARCH/dtbs/`, run `update-m1n1`,
   confirm `boot.bin` hash change + `boot.bin.old` backup.
2. Reboot (gate now PASS) → node/CPU verification checklist.
3. Load pinned `ane.ko` → `/dev/accel/accel0` bind → dmesg clean.
4. fp16 64-element exact smoke → H13 compiler packages (8 + overflow) →
   schema-4 add-mul → islands E2E → 100-run soak — same ladder as
   [the plan](2026-09-20-jwm1-ane-restoration-plan.md), re-earned on this
   image, with the v0.6.4 installed-state contract
   (`/proc/device-tree/ane@26a000000`, `/sys/module/ane/version`,
   `/dev/accel/accel0`) as the acceptance harness.
5. Only then: runtime/Parakeet/Qwen3.8 ANE work, GPU-lock protocol as usual.

## Limits

- No ANE execution, no DT mutation, no reboot happened in this lane.
- The open-item node values are a hard prerequisite for step 1; nothing in
  this receipt authorizes a boot test without them.
- Prompt-token discrepancy from the GPU receipt (245 vs jw16's 233) remains
  explicitly unreconciled there; unchanged here.
