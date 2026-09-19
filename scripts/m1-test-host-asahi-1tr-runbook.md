# m1-test-host (T8103 MacBook Pro) — Asahi 1TR boot-object repair runbook

Owner runbook for the machine console. Everything before and after the
console steps is scripted. Forensic context and every claim's receipts:
`receipts/2026-09-18-t8103-divisor-macos27.md` (ADDENDUM 1 + 2) and
`receipts/2026-09-18-m1-test-host-macos-root-deadlock.md` in this repo.

## Situation (why this is needed)

After the m1-test-host macOS 26.6.2 → 27.0 OTA, the Asahi stub chain
(iBoot → stub APFS pair → m1n1 → U-Boot → GRUB → disk0s5) no longer
completes. Reboot #2 on 2026-09-18 18:21 CDT left the box with **neither OS
in userspace** — power-cycling or sitting at a picker/console. The persistent
boot default is currently the Asahi stub pair (NVRAM `boot-volume`
`EF57347C…:8BAAF2FA…:7A64DCB3…`). The Linux rootfs (disk0s5) is believed
intact; the boot objects need re-registration against the macOS 27 boot
policy. The supported repair is a re-run of the Asahi installer's boot-object
step (the `mkboot` equivalent), finalized inside Apple's 1TR (One True
RecoveryOS).

## Phase 0 — console triage (you are at the open machine)

Look at the screen and pick the first matching case:

1. **iBoot picker ("Loading startup options…" or a volume chooser) is up:**
   select **Macintosh HD** (the real macOS, NOT "Asahi Alarm Minimal" /
   any Asahi / stub entry) and press Continue. Go to Phase 1.
2. **Text console (m1n1 logo/framebuffer gibberish, U-Boot or GRUB):** the
   stub chain partially fired. Hold the power button ~10 s to force power-off,
   then press power normally; if it lands in the picker, see case 1; if macOS
   boots on its own, go to Phase 1.
3. **Black screen / spin-up loop:** wait through one cycle (~3 min). If
   nothing settles within two cycles, hold power 10 s to power off, then
   press power and immediately hold it until "Loading startup options…"
   appears, then case 1.

## Phase 1 — get macOS back, then hand the rest to the script

1. Log in to macOS as the administrator account (`joshuawarren`) — the same
   account that authorized the original Asahi install. The post-upgrade
   first-login gate may refuse ssh keys until this GUI login has happened
   once (seen 18:14–18:17 CDT on 2026-09-18; it cleared by itself after
   login).
2. From any fleet Linux box, run:

   ```bash
   bash scripts/recover-m1-test-host.sh --wait 1800
   ```

   This re-adds the agent ssh keys if needed, restores the sane boot default
   (`bless --mount "/Volumes/Macintosh HD" --setBoot`), verifies NVRAM
   `boot-volume` no longer references the stub pair, and stages this runbook
   to the Mac. **One sudo password prompt**, over `ssh -tt`.

## Phase 2 — Asahi boot-object repair (at the machine, in macOS)

1. Open **Terminal** and run the official installer:

   ```bash
   curl https://alx.sh | sh
   ```

2. The installer detects the existing Asahi install. When prompted, choose
   the path that **keeps the existing Linux OS and reinstalls its boot
   objects** (expert mode: answer `y` to expert options if offered; pick the
   existing Asahi/Linux partition, not free space, not resize). Exact menu
   wording varies by installer version — follow what it prints.
3. Let it run to completion. The installer re-writes m1n1 stage 1 / the boot
   object chain and schedules the final authorization step inside **1TR**.
4. When it tells you to shut down: **Shut down** (full power-off).
5. Press and **hold the power button** until the screen shows
   **"Loading startup options…"** (~10–15 s), then release.
6. Complete the final step the installer printed — typically entering the
   recovery environment (gear icon **Options** → Continue, or the Asahi/1TR
   entry it names), opening **Utilities → Terminal** in recovery, and running
   the exact `step2`/finish command it gave you. This is the step that
   registers m1n1 stage 1 with the new boot policy; without it the stub chain
   keeps failing exactly as before.
7. The installer finishes with Linux booting (or tells you to reboot — then
   let it reboot into the Asahi default it sets).
8. Reference check once Linux is up: `bputil -l` (from macOS) should list the
   renewed m1n1 boot object for the stub pair; on Linux,
   `efibootmgr`/GRUB default should point at the ANE/stock entries as before
   (`homelab-infra/docs/jw-m1.md` documents the GRUB preamble).

## Phase 3 — when m1-test-host-linux returns

From any fleet Linux box:

```bash
bash scripts/v070-m1-test-host-arm.sh --wait 86400
```

One command: stages the t6001-test-host-proven gate kit (wheel sha `2def345c…`,
oproj islands, probes, E2E harness) onto m1-test-host-linux and runs the both-host
v0.7.0 gate — packaging 3× transcript-exact (`db501a8c…`), E2E
serve/launch/AC/ACO pins (`38c73261…` / `ef6afd13…`), decode legs
`7fd25a869ff21678` / `7da83f06ec9f001d`, primitive 103/103, runtime 41/41,
capsim 6/6, tape 12/12, venv guard, hwcap + KATs. Ends `GATE GREEN` or names
the red gate. Interrupted polling is safe (`--attach` re-polls); the gate
keeps running on m1-test-host-linux.

## If the repair fails

- Installer errors at the recovery/1TR step with user-database/crypto errors
  → the macOS account that authorized Asahi is gone or the seal chain broke.
  Do NOT delete partitions on instinct. Capture the exact error text and
  stop — clean reinstall (partitioning cheatsheet + fresh `alx.sh`) is an
  owner decision, it re-images the Linux rootfs.
- macOS itself will not boot from the picker → Options → macOS Recovery →
  try "Continue" first; a macOS reinstall is out of scope for this runbook
  and an owner call.

## Sources

- Asahi Linux docs — glossary (1TR = One True RecoveryOS), FAQ,
  m1n1 user guide (stage-1 registration / `Finish Installation` step2 flow):
  asahilinux.org/docs
- Asahi installer entry point: `curl https://alx.sh | sh`
- AsahiLinux/asahi-installer issues #100, #377 (boot-object repair after
  macOS updates; 1TR failure modes)
- Fleet receipts: `receipts/2026-09-18-t8103-divisor-macos27.md` ADDENDUM 1+2
  (stub-pair NVRAM GUIDs, bless mechanism, reboot timeline),
  `receipts/2026-09-18-m1-test-host-macos-root-deadlock.md` (root/deadlock analysis),
  `homelab-infra/docs/jw-m1.md` (asahi-bless, GRUB preamble, NOPASSWD sudo)
