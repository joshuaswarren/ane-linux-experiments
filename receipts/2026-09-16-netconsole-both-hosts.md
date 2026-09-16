# Off-box kernel console for both laptops (2026-09-16)

Why: two ANE recovery-driver builds hard-reset a laptop mid-window and the
last kernel lines died with the box (volatile journal, netconsole off-link,
pstore without console mirror). Bisecting a register write that aborts
the SoC needs the console streamed off-box.

## jwm1 (T8103)

- `jwm1-netconsole.service` retargeted from an off-link receiver to
  `6667@192.168.3.91/bc:d0:74:06:52:dd` (jw16 `wlan0`, same /23 as jwm1
  `wld0`). Backup of the old unit:
  `/etc/systemd/system/jwm1-netconsole.service.bak-20260916`.
- Receiver on jw16: `/usr/local/sbin/jwm1-netconsole-receiver.py`
  (`jwm1-netconsole-receiver.service`, enabled), log
  `/var/log/jwm1-netconsole.log`. `ufw allow from 192.168.3.66 to
  192.168.3.91 port 6667 proto udp`.
- `kernel.printk` was `4 4 1 7`, so only KERN_ERR reached netconsole.
  `/etc/sysctl.d/90-netconsole-loglevel.conf` sets `8 4 1 7`; applied live.
- Round-trip proof: `JWM1_NETCONSOLE_INFO_LEVEL` written to `/dev/kmsg`
  at 06:30:37 arrived at jw16 within 1 s.

## jw16 (T6001)

- `jw16-netconsole.service` already targeted this workstation
  (`192.168.10.235:6666`, `enu1`). `kernel.printk` already `8 4 1 7`.
- Receiver was an ad-hoc `/tmp` script; now
  `/usr/local/sbin/fleet-netconsole-receiver.py`
  (`fleet-netconsole-receiver.service`, enabled), log
  `/var/log/fleet-netconsole.log`. The 09-13 log is copied to
  `receipts/jw16-netconsole-2026-09-13.log`.
- Round-trip proof: `JW16_NETCONSOLE_DURABLE` at 06:32:40 arrived.

## Limits

Wi-Fi netpoll on jwm1 delivered every test line, but a hard SoC stop can
still drop the last packet in the NIC queue. Treat a missing final line
as "died at or after the last received line", the same rule the 09-13
bind receipts used.
