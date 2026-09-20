# jwm1 (T8103) Linux ANE restoration plan — plan only, no device actions (2026-09-20)

Lane: Jwm1AnePlan. Scope: restore the qualified `apple,t8103-ane` Linux ANE
stack on jwm1's **fresh Asahi Alarm image of 2026-09-20**. This document is a
plan; **no ANE device action has been taken on the current image**, and none is
authorized by this document alone. Historical T8103 evidence lives in the
receipts cited below and in [omarchy-ane](https://github.com/joshuaswarren/omarchy-ane)
(`main` README chip table, `omarchy-kmd` branch); all of it is dated evidence
from prior jwm1 boots, not a current recert.

## Current image state (verified 2026-09-20, read-only)

| check | result |
|---|---|
| ANE DT node | **absent** — no `ane*` node under `/proc/device-tree/soc`, no `/dev/ane`, no `/dev/accel/accel0` |
| kernel | `linux-asahi 7.1.13.asahi3-2` (kernel `7.1.13-3-2-ARCH`) |
| kernel headers / kbuild | **absent** — no `linux-asahi-headers` package, no `/usr/lib/modules/$(uname -r)/build` ⇒ `ane.ko` cannot be built yet |
| build tools | make 4.4.1, gcc 16.1.1, flex, bison present; `dtc` absent |
| boot chain | ESP `nvme0n1p4` at `/boot/efi` holding `m1n1/`, `ubootefi.var`, `vendorfw` (m1n1 1.6.1, uboot-asahi 2026.07.asahi2); kernel + `/boot/grub` live **under btrfs subvol `@`**; grub 2:2.14-1.1 installed |
| GPU baseline | restored same day — [2026-09-20-jwm1-gpu-v072rc1-restore](2026-09-20-jwm1-gpu-v072rc1-restore/receipt.md) |

The old jwm1 boot exposed `/dev/accel/accel0` with DT node `ane@26bc04000`
([schema-4 smoke](2026-09-13-jwm1-schema4-ane-smoke.json)); that DT state did
not survive the reinstall and must be re-published. **Correction after the
same-day audit:** Gate 1's mechanism below is superseded by the audit — the
m1n1 boot.conf overlay flow is obsolete on this image; the real mechanism is
the packaged-DTB + `update-m1n1` payload. See
[2026-09-20-jwm1-ane-boot-readiness-audit.md](2026-09-20-jwm1-ane-boot-readiness-audit.md)
for the corrected recipe, the passed reboot gate, and the pinned build
artifacts.

## Gate 0 — reboot gate BEFORE anything that needs a reboot

The btrfs-root GRUB hazard applies to this image: kernel and GRUB config sit
under subvol `@`, and grub `2:2.14-1.1` version strings do **not** identify a
safe build (the fleet `GRUBANE.EFI` stamps `2:2.14-1.1` yet died on jwm1's
v7-variant btrfs inode layout on 2026-09-18; stock Arch ARM `2:2.14-1.1`
fstest-passed on jw16's classic layout). Before the first planned reboot of
this image:

- Either move boot files off btrfs (ESP/ext4 path), **or**
- byte-compare (`grub-fstest`) the exact booted GRUB binary against a large
  file on the btrfs root and require a clean read.

libane's contract makes this gate load-bearing, and it is not theoretical on
this host: the 2026-09-15 T8103 run ended in
[`tm completion failed … preserving resources until reboot`](2026-09-15-jwm1-ane-wedge.md)
— an uncertain completion pinned the module and only a reboot cleared it.
The reboot path must already be proven when ANE work starts, not after.

## Gate 1 — DT publication (no execution claims until verified)

Publish the proven `ane.dtbo` (carried on `omarchy-kmd`, the working T8103
overlay; node `ane@26bc04000`, compatible `apple,t8103-ane`) through the
m1n1/U-Boot boot chain of this image. Verify read-only after boot:
compatible string present under `/proc/device-tree/soc/ane@26bc04000`, then
`/dev/accel/accel0` appears on driver bind. Forced platform/DT removal is
unsupported in this driver — verify before, not by teardown.

## Gate 2 — module build against matching headers

Install `linux-asahi-headers` matching `7.1.13.asahi3-2` (plus `dtc` if
overlay work is done on-device). `make -C ane` from a pinned omarchy-ane
checkout. Historical reference: prior jwm1 boots ran libane ABI-1 at commit
`f261a6cb537aca62f267ad3d01beda0d6877544c`; the current fork's `main`
serializes submissions, holds GEM references across execution, waits for
request-tagged last-task finish events, and rejects pre-ABI-1 drivers. T8103
is a **qualified** tier — the driver binds normally, no
`ane.allow_unqualified=1`.

## Gate 3 — userspace library and bindings

`make -C libane && make -C bindings/python/dylib` from the same pinned
checkout. Programs come only from the H13 backend in
`joshuawarren/mil-hwx-compiler` (`feat/h13-m1`); ANEC payload header is
`0x1000` (the `omarchy` branch libane reads it there).

## Gate 4 — qualification ladder (each step a dated receipt)

Reference points from prior T8103 boots, to be re-earned on this image:

1. Bind + exact fp16 64-element smoke (omarchy-ane chip-table confirmation).
2. Eight H13 compiler qualification packages + finite-input `+inf` overflow
   case, every output matched on 3 warmups / 30 measured iterations.
3. Schema-4 add-then-mul smoke — prior pass:
   [2026-09-13-jwm1-schema4-ane-smoke.json](2026-09-13-jwm1-schema4-ane-smoke.json)
   (worker `45a4a267…`, binary `5e315017…`; those bytes are dated evidence,
   not reusable artifacts).
4. o-proj + attention islands E2E (certified 2026-09-17 on the old boot).
5. 100-run warm soak with zero drift (pattern:
   [2026-09-16-parakeet-100-run](2026-09-16-parakeet-100-run)).
6. Only after 5: model-level work (Parakeet encoder pins / Qwen3.8 layers) per
   the standing contracts.

All ANE GPU-adjacent runs follow the host GPU lock protocol established today
(`/tmp/m1-gpu.lock`, single exclusive flock).

## Explicit non-goals until gates land

- No ANE inference claims, no `MLX_OMARCHY_ANE` enablement, no benchmark
  numbers from this image until Gate 4 closes.
- No edits to omarchy-ane in this lane (plan only; implementation lanes pick
  their own pinned commits).
- No reboot, DT, or firmware mutation without Gate 0 satisfied first.
