# H14/T6021 W1 third attempt — amended single-exec protocol executed clean; WALL instance #4: the wedge began BEFORE the gate passed (journald dead 54 s pre-RT2), chain bash ran, first tool exec stalled, zero device contact (2026-09-19)

Verdict: **WALL — evidenced, instance #4.** The amended protocol (retry receipt §4) worked
exactly as designed: all pushes completed in the gate wait window, post-RT2 exposure was
one ssh exec 12 s after the gate round-trip, and the chain's remote bash demonstrably
started — and then the box's already-running wedge swallowed the first tool exec. `python3
-u`'s first unbuffered line never appeared; the MGMT exchange never began; nothing wrote.
Below-kernel reset 65 s after chain start; pstore empty; capture-parked per gate 5, no
retry. The first host<->selene RPC bytes remain unachieved on any H14.

## 1. Gate evidence (all green — and now proven insufficient)

| gate | result |
| --- | --- |
| 1 serviceability | RT1 `07:08:14` (up 3:33, load 0.00, 0.24 s wall), RT2b `07:18:37` (up 3:44, load 0.00, 0.22 s wall) — **Δ10m23s ≥ 10m**. (An earlier RT2 at 07:18:05 hit Δ9m51s — 9 s short — and was discarded per gate; RT2b is the gate pass.) |
| 2 netconsole | receiver `/var/log/fleet-netconsole.log` (omp-studio-local) live: `6668@192.168.3.103/wlan0` → `192.168.10.235:6666`, kts `[12732]` at 07:06:41, kts `[13444]` at 07:18:33 |
| 2 ramoops | reserved `0x10010000000..0x100103fffff (4096 KiB)`, `pstore: Registered ramoops as persistent store backend`, `/sys/fs/pstore/` empty pre-attempt |
| tooling | all three tools scp'd to `/tmp/h14/` **07:08:36, inside the wait window**; md5 both sides: probe `27828b1e…`, hello `7663498f…`, bringup `fe09c678…` (omarchy-ane `feat/t6021-rtkit-w2` @ `6ad26b7`, no tool changes this pass — branch already at origin) |
| chain script | pushed + `bash -n` syntax-checked on-box 07:10 (zero execution); single exec = `timeout -k 10 150 sudo -n bash /tmp/h14/third-chain.sh` |
| captures | remote `journalctl -f` + local netconsole `tail -F` armed (re-armed 07:18:30 without deadline after an initial 300 s tool-timeout kill; master receiver log continuous throughout — the gap 07:13:36→07:18:30 exists only in the local convenience copy) |

## 2. Death timeline (all times CDT 2026-09-19; boot -1 = 03:34:30 → death, boot 0 = 07:19:54 →)

| t | event | evidence |
| --- | --- | --- |
| 07:17:41 | **last kernel journal line of boot -1** (UFW BLOCK) | `journalctl -b -1 -k -n 1` |
| 07:17:43 | **last userspace journal line of boot -1** (tailscaled) — **journald dead here** | `journalctl -b -1 -n 1`; `--since 07:17:43` yields only these 4 tail lines |
| 07:18:33.50 | last old-boot kernel **netconsole** RX (kts `[13444.15]`, UFW) — kernel logging outlived journald by ~50 s | receiver log + local capture, line 16 |
| 07:18:37 | RT2b serviced normally (`hostname`/`uptime`/`date` exec'd, output returned) — **gate passes 54 s into the dying sequence** | session log |
| 07:18:49 | chain launched (12 s after RT2b): remote bash echoed `===CHAIN-BEGIN===` and `===STEP:readonly-probe===` → **sudo+bash demonstrably exec'd** (unlogged — journald already dead) | chain ssh stream |
| ≤07:18:49+ | first pipeline (`timeout … python3 -u h14_readonly_probe.py \| tee third-probe.out`) **stalls**: no probe output within ≥60 s — the probe's first `ane_cpu ps:` line (one pmgr read, unbuffered, sub-second when running) never arrived. Note: pre-reset tee-file existence is unobservable (tmpfs `/tmp/h14` wiped by the reset) — the ssh stream is the evidence | chain ssh stream, 85 s wall |
| 07:19:54 → 07:19:59.67 | below-kernel reset; new boot kts `[0.0]` at 07:19:59.67, ANE pmgr `sync_state` kts `[15.33]` at 07:20:08; **pstore empty** — no panic path | netconsole seam; `ls /sys/fs/pstore/` → 0 entries |
| 07:20:14 | stale chain ssh RST'd by the returning box → exit 255 (reboot instant, same mechanics as instances #1–#3) | chain job log |
| 07:21:58 | capture pass on boot 0 (up 2 min): boots table, sudo trace, pstore, instruments re-verified — ramoops reserved+registered, netconsole flowing. **No retry** | `2026-09-19-h14-w1-third-death-capture.log` |

## 3. What this does and does not prove

- **The amendment was correct and did its job.** Post-gate exposure was one exec 12 s after
  RT2b (vs ~35 s of push+exec last pass), and the chain's bash start is positively proven
  (its echoes returned) — no ambiguity about ssh serviceability this time.
- **Zero device contact, with one honest caveat.** The probe is read-only and its first
  print follows a single pmgr read; that print never appeared, so no completed register
  access occurred in any branch. Whether python3 spawned and stalled pre-main or never
  spawned is indistinguishable (exec of a cold ~30 MB binary is exactly what this wedge
  stalls — see below). No WRITE path was reachable in any branch (probe read-only; hello
  never started — no further step markers). CSNE_CMD_PING 0x11 / BUILDINFO 0x06 was never
  reachable in this pass regardless: the host→fw ring negotiation is still W3-undecoded and
  the pinned tools' write-set ends at MGMT replies (W1 receipt §4) — the app-level RPC was
  a post-MGMT-goal stretch, and the MGMT goal itself never started.
- **New evidence — the wedge order is now three-stage and the gate is structurally blind
  to stage 1.** journald died 07:17:43; the kernel still logged to netconsole 07:18:33;
  sshd still serviced NEW sessions (and page-hot binaries: `uptime` at 07:18:37, `bash`
  + `echo` at 07:18:49) — while cold-binary execs (`timeout`/`tee`/`python3` never
  produced a byte) stalled. The 10-minute two-round-trip gate measures sshd, not the box:
  it passed 54 s after journald death. Same order as instance #3 (journald 03:32:36 →
  sshd services pushes to ~03:33:15 → reset), now confirmed across two gated passes.
- **The push-correlation note from the retry receipt is dead.** This death had no push
  within 70 min of the wedge onset (push 07:08:36, journald death 07:17:43). What remains
  is pure uptime cadence: deaths at 6h10m, 3h05m, 3h43m uptime — a periodic machine fault
  (owner-flagged hardware/firmware class) that fires roughly every few hours, and any
  software pass will straddle one eventually. The amended protocol shrank exposure but
  cannot dodge a wedge already in progress at gate time.
- `[INFERENCE]` exec-path stall (page-in from stalled storage) is consistent with the
  progressive order (journald → cold execs → sshd → kernel RX → below-kernel reset) and
  with a btrfs/storage stall; not directly measured. The W1-retry's journal-gap analysis
  matches: zero journal entries in the chain window because journald was already gone —
  journal ABSENCE is no longer evidence of exec ABSENCE on this box once journald dies.

## 4. Next-pass guidance (honest)

1. **The actual unblock is unchanged: owner/hardware eyes on jw14m2-linux** (Apple
   diagnostics, PMIC/power rail, storage/btrfs check). Three gated software passes have
   now walled the same way; the box resets every few hours on its own cadence.
2. If a fourth software pass is run anyway, the gate must exercise a cold-binary exec
   (e.g. `/usr/bin/env` first-use or a freshly copied binary) rather than round-trips —
   and should still be expected to wall, since the wedge can begin mid-gate.
3. A longer-lived option: run the tooling from a **local** `at`/`systemd-run` job armed
   during the wait window (zero post-gate ssh), so the exec path is the only variable —
   but this changes nothing about a wedge already in progress, and instance #4 says the
   box can pass its own gate while dying.
4. Tooling (u64 mailbox hello, readonly probe, staged bringup) remains field-unexercised
   and statically self-checked (`PROTOCOL-SELFCHECK-OK`); no changes were made this pass
   — the tools never ran.

## 5. Instruments / refs

- Receiver log: omp-studio-local `/var/log/fleet-netconsole.log` (sender
  `192.168.3.103:6668` → `192.168.10.235:6666`); death seam: last old-boot
  `07:18:33.50 kts [13444.15]` → first new-boot `07:19:59.67 kts [0.0]`.
- This repo: `receipts/2026-09-19-h14-w1-third-chain.sh` (the one-shot chain, byte-exact),
  `receipts/2026-09-19-h14-w1-third-capture-journal.log`,
  `receipts/2026-09-19-h14-w1-third-capture-netconsole.log` (seam + new-boot continuation),
  `receipts/2026-09-19-h14-w1-third-death-capture.log` (post-reset evidence pass).
- Journal boots on jw14m2-linux: -3 18:35→00:27:24 (instance #1), -2 00:28:36→03:33:09
  (instance #3), -1 03:34:30→07:17:43 (this instance), 0 07:19:54→ (clean).
- omarchy-ane `feat/t6021-rtkit-w2` @ `6ad26b7` — unchanged, already at origin.
- Prior context: `receipts/2026-09-19-h14-w1-first-rpc.md` (instance #1 + tool fix),
  `receipts/2026-09-19-h14-w1-first-rpc-retry.md` (instance #3 + amended protocol §4),
  `receipts/2026-09-18-h14-w2-protocol-decode.md` (W2 sequence, CSNE table).
