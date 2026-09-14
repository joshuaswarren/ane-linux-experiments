# Omarchy ANE out-of-box install plan

## Goal

Make ANE support an optional, board-proven part of an Apple Silicon Omarchy
install. A supported board receives a packaged device tree and a
kernel-matched `kmod-ane`; every other machine keeps the existing GPU-only
MLX path. This is a packaging plan, not authorization to change firmware,
boot state, a device tree, or a module on a live host.

## Facts that constrain the design

- Stock `t8103-j293.dtb` contains no `apple,t8103-ane` node. The working M1
  (`jwm1`) instead uses a custom `/boot/efi/m1n1/boot.bin` whose packaged tree
  contains that node and an out-of-tree `ane.ko`.
- T6001 on jw16 now has a live `/dev/accel/accel0` (`apple,t6000-ane`), DRM 1.0.0, SET genpd (PMGR window `0x14000`, set1..4), and exact fp16 64-el add-mul (`receipts/2026-09-13-t6001-set-domains.json`, `mlx-omarchy/receipts/2026-09-13-jw16-ane-set-exec.json`). The live overlay is `omarchy-ane` `ane/t6001-j316c-set-domains.dts` (`eb7dfe7`). set5 stays unattached. Do not write SET `0xf` from userspace. Packaging still must put that node in the SoC/board DTS and `update-m1n1` path; a live overlay is not the product.
- The installer already copies Apple firmware, including
  `h13_ane_fw_styx_j5x.im4p`; firmware alone does not create an ANE device.
  It currently installs neither an ANE kernel module nor an ANE-enabled DTB.
- `omarchy-base.packages` has no ANE package. DKMS is ISO-only inventory, not
  the delivery mechanism for a kernel-facing ANE module.
- A GRUB `devicetree` whole-tree override is forbidden. It discards m1n1's
  per-boot patches and previously booted only one CPU core.
- `ane_force_power()` currently hardcodes `apple,t8103-pmgr`. Any driver
  package that can bind non-T8103 hardware must select the PMGR implementation
  from the matched SoC, not from that literal.

The source receipts are `parakeet-mel-exact/docs/boot-and-kernel.md`,
`receipts/2026-09-13-t6000-live-mapping.md`,
`receipts/2026-09-13-t6000-ane-pmgr-cells.md`,
`receipts/2026-09-13-t6001-set-domains.json`, and
`mlx-omarchy/receipts/2026-09-13-jw16-ane-set-exec.json`.

## Package boundaries

| Repository | Change | Purpose |
| --- | --- | --- |
| `joshuaswarren/linux` / the linux-asahi or Borealis kernel packaging branch | `arch/arm64/boot/dts/apple/t8103.dtsi`, `arch/arm64/boot/dts/apple/t8103-j293.dts`, and the kernel package DTB install list | Put the T8103 ANE node in the SoC DTS, disabled by default; enable it only in board DTS files whose complete ANE binding is proven. Install the resulting board DTBs below `/usr/lib/modules/<kernel>/dtbs/`. |
| `joshuaswarren/omarchy-ane` | `ane/src/ane_drv.c` and the package build inputs | Replace the hard-coded T8103 PMGR selection with a compatible-aware T600x/T8103 selection before advertising a non-T8103 package. Keep the driver and its supported DT bindings versioned together. |
| `omarchy-mac/omarchy-pkgs-aarch64` | `pkgbuilds/kmod-ane/PKGBUILD` and its existing `source: local`, `category: compile` package-index entry | Build and publish a kernel-matched `kmod-ane` package. It owns `ane.ko`, modprobe policy, and the udev rule that exposes the accelerator device to the intended local group. It is not DKMS. |
| `omarchy-mac` installer | the code that evaluates `omarchy-base.packages` and the Apple hardware probe | Add a conditional `kmod-ane` install after the packaged-DTB gate. Do not add it unconditionally to `omarchy-base.packages`. |
| `mlx-omarchy` installer/smoke script | the existing install smoke path | Keep GPU smoke mandatory. Run ANE smoke only when `/dev/accel/accel0` exists after boot and module installation. |

`kmod-ane` must depend on the exact packaged kernel ABI and on the matching
DTB-producing kernel package. A DTB without its matched module, or a module
without its matched DTB, is not a supported installation state.

## Kernel and DTB delivery

1. Add each supported ANE node to the SoC DTS with `status = "disabled"`.
   The node must contain the binding required by `ane/src/ane_drv.c`: named
   `engine` MMIO resource, named `ane` IRQ, ordered `power-domains`, and a
   provider-owned IOMMU domain. Do not carry guessed T600x fields.
2. Enable that node only in board DTS files that have the actual hardware and
   a complete, reviewed binding. For the known base M1, the delivery shape is
   `t8103.dtsi` plus `t8103-j293.dts`; a board is not enabled merely because
   its SoC family name starts with `t`.
3. Package every resulting board DTB in
   `/usr/lib/modules/<kernel-version>/dtbs/`. `update-m1n1` concatenates those
   package DTBs into `/boot/efi/m1n1/boot.bin`, then m1n1 applies its live
   per-boot patching. Let the existing pacman hook run it.
4. Never add a GRUB `devicetree` command, a static DTB boot entry, or a
   whole-tree replacement. Do not copy a live FDT into `/boot` as a product
   artifact. The only supported boot update is the normal `update-m1n1`
   payload rebuild from packaged DTBs.

T6001 ANE execute is proven on jw16 with the SET overlay. Product cutover still waits on a packaged board DTB (not a live FDT overlay), set5 policy, and the installer gate. A PMGR supplier name alone remains insufficient; the SET domains are part of the binding.

## Installer gate

The Apple installer must perform this decision after the kernel package and
its DTBs are present, but before it tries to install or load `kmod-ane`:

```text
if machine is not Apple Silicon:
    do not install kmod-ane
elif live FDT has compatible "apple,t*-ane":
    install kmod-ane for the running packaged kernel
elif this board's packaged DTB has compatible "apple,t*-ane":
    install kmod-ane; update-m1n1 will make it live on the next boot
else:
    do not install kmod-ane
```

The implementation must inspect the actual board-compatible packaged DTB, not
search an arbitrary DTB from another board. It must also treat an absent or
unreadable FDT/DTB as false. The gate deliberately skips x86 and Apple systems
without a packaged ANE node, including M3-and-later hardware until a DTS and
binding exist. Those machines still receive the normal GPU-capable
`mlx-omarchy` installation.

The installer must not load `ane.ko` simply because it installed it. The first
boot after `update-m1n1` lets normal device discovery bind the platform device.
A post-boot smoke owns any explicit module policy only after the driver has a
bounded recovery contract.

## Device exposure and smoke checks

`kmod-ane` supplies one narrowly scoped udev rule for the kernel's accelerator
node and group access. The rule must match the actual subsystem and device name
created by the packaged driver; it must not grant broad access to DRM, DART, or
all character devices.

The MLX installation contract stays unchanged:

1. Run the existing GPU smoke on every supported Apple install.
2. Check for `/dev/accel/accel0` after boot.
3. Run the ANE smoke only when that exact node exists. If it does not, record
   the GPU smoke result and report ANE as unavailable; do not open a fallback
   device and do not run CPU tensor work.
4. Non-Apple Omarchy receives no ANE package, udev rule, boot change, or ANE
   smoke. Its existing behavior is unchanged.

## Release checks

Before publishing the kernel and `kmod-ane` pair, verify the package contents
and the decision logic without mutating a host:

The package CI must assert that `t8103-j293.dtb` contains
`apple,t8103-ane`, while a selected no-ANE board DTB does not. It must assert
that `ane.ko` reports the packaged kernel's ABI, then exercise the installer
gate with five fixtures: x86, no-ANE Apple, packaged-T8103 ANE, live-ANE FDT,
and missing FDT. The release receipt must name the kernel package version,
`kmod-ane` version, board DTB, detected compatible, gate result, and whether
GPU-only or ANE smoke ran.

## Cutover order

1. Land and review the driver PMGR compatibility fix and supported bindings in
   `omarchy-ane`.
2. Land the disabled SoC node and only proven board enables in the
   linux-asahi/Borealis kernel packaging branch.
3. Publish the ABI-coupled kernel DTBs and `kmod-ane` through
   `omarchy-pkgs-aarch64`.
4. Add the packaged-DTB installer gate and udev rendering; leave
   `omarchy-base.packages` free of an unconditional ANE dependency.
5. Exercise the five decision fixtures, then install on a supported clean M1.
   Verify GPU smoke always; verify ANE smoke only after
   `/dev/accel/accel0` appears.

No hardware mutation is part of this document.