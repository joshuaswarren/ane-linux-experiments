#!/usr/bin/env bash
# Runs ON jw16 (Linux). Reboot gate + next-boot-only switch to macOS.
# Gate (rule btrfs-v7-grub-reboot-gate): boot files must live off btrfs.
set -euo pipefail
echo "boot: $(findmnt -no SOURCE,FSTYPE /boot) esp: $(findmnt -no SOURCE,FSTYPE /boot/efi) root: $(findmnt -no SOURCE,FSTYPE /)"
[ "$(findmnt -no FSTYPE /boot)" = ext4 ] && [ "$(findmnt -no FSTYPE /boot/efi)" = vfat ] || { echo "GATE FAIL: /boot not off-btrfs"; exit 2; }
echo "GATE PASS: /boot ext4, ESP vfat"
sudo -n asahi-bless -l
sudo -n asahi-bless -n -y --set-boot 1
echo "next boot: $(sudo -n asahi-bless --get-boot --next) default: $(sudo -n asahi-bless --get-boot)"
[ "$(sudo -n asahi-bless --get-boot --next | tail -1)" = "Macintosh HD" ] || { echo "next-boot not set to Macintosh HD"; exit 3; }
sudo -n systemctl stop llm-inference.service
systemctl is-enabled llm-inference.service
echo "rebooting to macOS (next boot only) at $(date -Is)"
sudo -n systemctl reboot
