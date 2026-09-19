# H14/T6021 W1 first RPC retry — WALLED again: third below-kernel reset of the class, gates green, zero device contact, probe never exec'd (2026-09-19)

Verdict: **WALL — evidenced, instance #3.** The serviceability gate passed (two ssh
round-trips 10m18s apart), netconsole and ramoops were verified flowing/armed, the
corrected u64-mailbox tools were pushed with matching checksums — and the box wedged
and reset below the kernel inside the probe launch window, **before sudo ever exec'd
python and before a single `/dev/mem` open**. Per gate 5 (capture, no retry) nothing
was re-attempted; the box rebooted clean and was left healthy with instruments
re-armed. The first host<->selene RPC bytes remain unachieved on any H14.

## 1. Gate evidence (all pre-device, all green)

| gate | result |
| --- | --- |
| 1 serviceability | RT1 `03:22:43.37` (up 2:54, load 0.04), RT2 `03:33:01.31` (up 3:04, load 0.00) — **Δ10m18s ≥ 10m**, both serviced normally |
| 2 netconsole | receiver `/var/log/fleet-netconsole.log` (omp-studio-local) carried live sender `6668@192.168.3.103/wlan0` lines at `03:25:07` (kts `[10591.9]`) |
| 2 ramoops | `reserved mem: 0x10010000000..0x100103fffff (4096 KiB) ramoops`, `pstore: Registered ramoops as persistent store backend`, `/sys/fs/pstore/` **empty** (clean) |
| tooling | `h14_readonly_probe.py` + `h14_rtkit_hello.py` scp'd to `/tmp/h14/`; md5 match both sides (`27828b1e…`, `7663498f…`); omarchy-ane `feat/t6021-rtkit-w2` HEAD `6ad26b7` (u64 mailbox fix) already at origin |

dmesg err/warn scan pre-probe: 39 lines, all `[UFW BLOCK]` network noise. Boot history
matched the W1 receipt (-1: 18:35→00:27:24; 0: 00:28:36→).

## 2. Death timeline (all times CDT, 2026-09-19, boot -1 = the death boot)

| t | event | evidence |
| --- | --- | --- |
| 03:32:36 | **last userspace journal line of boot -1** (tailscaled route monitor) — journald stops recording here | `journalctl -b -1 -n 6` |
| 03:33:01–03:33:15 | RT2 + push window: sshd still **servicing** — `mkdir`/`scp`/`ls`/`md5sum` outputs all returned | session log, `/tmp/h14` listing |
| 03:33:09 | **last kernel line of boot -1** (UFW BLOCK, kts `[11074.14]`); also the last netconsole RX of the old boot | journal -b -1 + receiver log (same second) |
| 03:33:35 | probe launched: `sudo -n timeout -k 5 25 python3 -u /tmp/h14/h14_readonly_probe.py` → ssh **black-holed**, wall 60 s, no output | bg job bg_3 |
| 03:33:00→03:34:40 | **zero sudo/sshd/session/python journal lines in the probe window** → sudo never exec'd → python never started → `/dev/mem` never opened | `journalctl -b -1 --since 03:33:00 --until 03:34:40` (empty of those units) |
| probe log | **0 bytes** — unbuffered (`python3 -u`) per-address flush produced not even the first `ane_cpu ps:` line, consistent with no exec | `receipts/2026-09-19-h14-w1-retry-probe.log` |
| ≤03:34:30 | below-kernel reset; **pstore/ramoops empty** — no panic path, reset below the kernel | new-boot pstore listing |
| 03:34:30 | boot 0 begins (clean); netconsole kts `[0.0]` at receiver 03:34:35.8, ANE pmgr `sync_state` lines kts `[15.33]` at 03:34:44 | journal + receiver log |
| 03:39:45 | capture window open (up 5 min, load 0.00) — journal -b -1 / pstore / boots captured; **no retry** | `receipts/2026-09-19-h14-w1-retry-death-capture.log` |
| 03:41 | new boot re-verified: ramoops reserved+registered, netconsole sender up (`03:34:34`), pstore clean | journal -b 0 -k |

## 3. What this does and does not prove

- **Zero device contact is journal-proven for this instance** (stronger than W1's
  inference): no sudo line exists for the probe — the death struck during the push
  phase, between the last serviced ssh (03:33:15) and the refused one (03:33:35).
  The wedge→reset class on jw14m2-linux is machine-level and fires with gates green.
- **Wedge order is new evidence**: journald stopped recording at 03:32:36 while sshd
  was still servicing sessions through ~03:33:15 (push outputs received); sshd stopped
  servicing new sessions by 03:33:35; kernel RX last line 03:33:09 (event-driven UFW —
  kernel death second is bounded, not pinned). Userspace services do not die
  simultaneously: a progressive userland stall (journald first) ending in a
  below-kernel reset. Root cause remains hardware/firmware class; the progressive
  order is consistent with a storage/systemd stall rather than an instant power cut —
  `[INFERENCE]`, not measured.
- **Correlation note for the owner** (correlation, not cause): both agent-session
  deaths (00:27:24 and ≤03:34:30) fell within ~40–60 s of a scripted scp+ls push
  burst to the box; yesterday evening's deaths (18:19/18:21 loop) had no pushes.
  n=2 vs n=2 — too small to act on, recorded so the next pass can break the pattern.
- Death cadence: 18:19, 18:21, 18:33 (loop), 6h10m run, 3h05m run. The box resets
  every few hours regardless of agent activity; today's pass landed inside a dying
  window with only ~9 s between gate-pass (RT2 03:33:01) and push (03:33:12) — the
  10-minute gate cannot see a wedge that begins seconds after it passes.
- The corrected u64 tooling was NOT exercised in the field (again). It remains
  statically self-checked only (`PROTOCOL-SELFCHECK-OK`).

## 4. Next-pass protocol amendment (evidence-driven, cheap)

1. **Move all pushes into the gate WAIT window.** scp the tools before round-trip 2,
   so post-RT2 traffic is exactly one ssh exec (the probe). Any death after RT2 is
   then pre-exec-provable by journal with zero ambiguity, and the exposure window
   between gate-pass and device work shrinks from ~35 s to ~2 s.
2. Keep gates 1–6 unchanged otherwise. The readonly probe (per-address flush) is
   still the right first device touch — the +0x1600000 block remains read-suspect,
   and the probe remains the instrument that would pin it.
3. The actual unblock is still owner/hardware eyes on the box (Apple diagnostics,
   PMIC/power, storage/btrfs check on jw14m2). A third software pass on an unexamined
   box should be expected to wall the same way; treat any post-gate window as a race
   against a machine that resets every few hours.

## 5. Instruments / refs

- Receiver log: omp-studio-local `/var/log/fleet-netconsole.log` (sender
  `192.168.3.103:6668`); death seam: last old-boot `03:33:09 kts [11074.14]`, first
  new-boot `03:34:35.79 kts [0.0]`.
- jw14m2-linux journal boots -1 (death; ends 03:33:09) and 0 (clean; starts 03:34:30).
- Companion evidence: `receipts/2026-09-19-h14-w1-retry-probe.log` (0 bytes),
  `receipts/2026-09-19-h14-w1-retry-death-capture.log`.
- omarchy-ane `feat/t6021-rtkit-w2` @ `6ad26b7` — no tooling changes this pass (tools
  worked as designed; the death pre-executed them); branch already in sync with
  origin. W1 context: `receipts/2026-09-19-h14-w1-first-rpc.md`.
