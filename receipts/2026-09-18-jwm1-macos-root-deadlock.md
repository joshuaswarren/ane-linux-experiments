# jwm1 macOS root deadlock — evidence and unblock plan (2026-09-18)

## Goal dependency
Same-die T8103 Parakeet divisor requires macOS with CoreML 3520 (CoreML8 parse).
jwm1 is in macOS 14.8.9 (CoreML 3304). Catalog offers `macOS 27-26A428` (+ Safari 26.6.1, CLT 16.2). Install requires root.

## Evidence (this session, live probes)
- `ssh joshuawarren@192.168.3.66`: user in `admin`, `com.apple.access_screensharing`; `sudo -n -l` → "a password is required" (no NOPASSWD entries at all).
- `softwareupdate --list` works unprivileged; full-upgrade labels visible.
- Linux side `jwm1` (100.84.184.102) connection timed out — Asahi not running; no Linux-side recovery path while the box sits in macOS.
- VNC 5900 OPEN on the macOS slice (Screen Sharing running) — authentication required; no legitimate credential path available to agents.
- `bless`/`pmset`/`softwareupdate --install`/`osascript` restart: all root.

## Deadlock statement
Every macOS-side action (OS upgrade, reboot, one-shot bless) needs root; root needs the
console password or the Linux side; the Linux side needs a reboot. SSV sealing prevents
editing /etc/sudoers on the sealed system volume from an external mount without breaking
boot integrity — not a reversible action, not taken.

## Unblock plan (execute the moment any path opens)
1. If console/VNC access or password ever becomes available:
   `sudo softwareupdate --install -a --restart` (stages macOS 27-26A428) OR targeted
   full-upgrade label, then after upgrade+divisor capture:
   `sudo bless --mount /Volumes/Asahi --setboot --nextonly` style one-shot, reboot to Asahi.
2. The FIRST action on any return to the Asahi side: make this deadlock structurally
   impossible — install an agent-controlled root path under the existing passwordless-sudo
   Asahi account: a persistent boot-selection helper + a macOS-side LaunchDaemon is NOT
   possible without macOS root; instead document a standing pre-reboot checklist item:
   set one-shot bless toward macOS BEFORE any Linux-side reboot when a macOS capture is
   pending, and never let both one-shot entries expire while parked in an OS.
3. If macOS 27 proves CoreML-incompatible with the capture tooling (3304→3520 assumption),
   fall back to macOS 26.x full installer via `installinstallmacos.py`-style fetch, same root bar.

## Status
Not a stop condition: parity lanes continue on jw16/macstudio per project rules; this
receipt records why the T8103 divisor lane is hard-blocked and what fires on unblock.
