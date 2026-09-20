# jwm1 wedge cleared by one authorized recovery reboot — GPU released, ane lane gated on guard+five-provider DT (2026-09-20)

Lane: Jwm1AnePlan. Main-authorized single recovery reboot solely to clear the
wedged module (receipts/2026-09-20-jwm1-ane-first-load-wedge/) and return GPU
availability. No DT change, no ANE load, no config edits.

## Preflight (all green)

- Fresh `grub-fstest` cmp ×2 PASS (vmlinuz + initramfs).
- Reviewed DT unchanged on disk (`033a3fc4…`), payload unchanged
  (`66604ffa…`).
- ane.ko NOT persistent: absent from `/lib/modules`, no modprobe.d entries,
  staged copy only under `/var/tmp/jwm1-ane-restore/`.

## Reboot (exactly one)

Down ~15:01:5x UTC, back **15:02:18 UTC**, SSH on first poll (~40 s).

## Post-reboot verification (all green)

| check | result |
|---|---|
| serial / kernel | `C02DP17UQ05P` / `7.1.13-3-2-ARCH` unchanged ✓ |
| CPUs | nproc = 8, online `0-7` ✓ |
| ane module | **absent** — `lsmod` empty, no `/dev/accel` (wedge cleared cleanly) ✓ |
| DARTs | all three bound to `apple-dart` ✓ (node set live from the deployed dtb) |
| ane platform device | `26bc04000.ane` present, unbound ✓ (waits for the guard-patched module + five-provider DT) |
| services | sddm / NetworkManager / sshd active — GUI + network intact ✓ |

## Gate state

- GPU released to GPUparityroot-causeaudit for the 12-round window.
- ane lane remains gated on: (1) Main's review of the five-provider DT
  derivation (exact historical node carved from the September payload —
  [DT derivation receipt](2026-09-20-jwm1-ane-dt-derivation/receipt.md), the
  corrected mirror patch staged; NOT deployed), and (2) the pre-submit power
  guard (`guard/pre-submit-ps-check @63d7646`) kbuild + Main review.
- Until both land: no ANE load (the deployed two-provider DT would re-wedge
  identically; the guard turns that into a clean -ENODEV).
