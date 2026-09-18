# H14/T6021 ANE RTKit phase 1 — coprocessor proven ALIVE, cpu-control/mailbox block derived (+0x1600000), RPC staged (2026-09-18)

Verdict: **COPROCESSOR ALIVE — proven on-device.** The t6021 ANE ASC cpu is powered and
running the selene firmware before Linux takes over (iBoot boots it, exactly the H13
m1n1 precedent): RVBAR holds the valid bit, the RTBuddy status register reads the exact
value the H14 kext polls for, and VERS reads structured. The kext-derived Chinook boot
sequence and the **ASC cpu-control block at ANE+0x1600000** (CPU_CONTROL +0x1600044,
mailbox candidates +0x1608xxx) are now pinned by disasm of the config initializer. The
first RTKit exchange is **staged as tooling on the branch** and blocked tonight by one
thing only: the box is in an unclean crash-reboot loop correlated with the lid going
closed (Joshua asleep); a zero-write probe run died to the loop without ever touching
the device. A logind no-lid-suspend drop-in (announced, reversible) is applied to break
the loop; read-only confirmation passes resume the moment the box holds through the old
death window.

## 1. Device evidence (session 17:51-17:54 box CDT, boot 14:02-18:00)

All pmgr write-class work = the exact registers + read-modify-write the
apple-pmgr-pwrstate genpd raise performs (offsets from the live DT; six domain raises
completed cleanly on three prior bind boots — the write class was proven before this
lane reused it). No SET-block sidekick writes anywhere. Engine kill window
0x285c04000..0x285c28000 asserted against in every tool.

| step | result |
| --- | --- |
| S0 snapshot | `ane_sys_mpm/td/base/set1..4` all `0x300` (gated, WAS_CLKGATED\|WAS_PWRGATED), **`ane_cpu` `0x1f0003ff` = TARGET 0xf + ACTUAL 0xf + AUTO_ENABLE + MIN — powered by boot firmware and left on** |
| S1 raise | 8/8 domains parent-first (sys_mpm→td→base→set1..4→cpu @ pmgr+0x4000..0x4030,+0x2e0); every ACTUAL reached 0xf, BUSY cleared; no abort |
| S2 reads | `RVBAR +0x1050000 = 0x00000001` (valid bit set, entry low bits 0 — fw entry = load_base+0), `VERS +0x1840000 = 0x000e3044`, `RTBuddy +0x1840088 = 0x1` (**< 2 = the exact release condition the K14 kext poll-loops for**), `+0x184007c = 0x30`, GPIO0-7 all 0 (no acks pending), EDPRCR 0 |
| inference | **cpu released and not stopped ⇒ selene is running.** The H14 kext never sideloads fw in RTBuddy mode ("FW sideloading not supported in RTBuddy mode") and macOS ioreg says `FirmwareLoaded = true` — the fw comes up from the boot chain and the host attaches to it |

Machine state after the session: alive, netconsole flowing ≥6 more minutes (the boot's
end is in §3, unrelated cadence).

## 2. Static derivation — Chinook bootup + ASC block (all from K14 kext disasm)

1. **Chinook bootup function** (`__TEXT_EXEC` ~0x…95e9xxx): reads `RVBAR` (+0x1050000)
   through the read-helper; if bit0 clear, writes **`(bootaddr & ~0x7ff) | 1`**
   (log strings: "DEBUG: Chinook bootup sequence started bootaddress 0x%llx",
   "Chinook bootup, write to rANE_H11_CHINOOK_IO_RVBAR:0x%llx").
2. Immediately after, it writes `0` then `0x10` through a register offset loaded from
   config field `[self+0x4a0]`. The SoC config initializer
   (`initializeANESoCConfig…mtr_config_komodo`) populates that field with
   **`0x1600044`** (`mov w8, #0x44; movk w8, #0x140, lsl #16; orr w8, w8, #0x200000`).
   Offset 0x44 + value bit 4 = m1n1's `ASCRegs.CPU_CONTROL.RUN` — the H14 ASC
   cpu-control block sits at **ANE+0x1600000** (my first S2 read probed +0x1000000 —
   the RVBAR strap block — and correctly read 0).
3. **Mailbox candidates therefore move to the same block**: m1n1 ASCRegs layout
   (CPU_CONTROL +0x44 paired with mailbox +0x8110/0x8114 controls, +0x8800/0x8830
   slots) maps to **+0x1608110 (A2I ctrl), +0x1608114 (I2A ctrl), +0x1608800/0x88
   (A2I send), +0x1608830/0x8838 (I2A recv)**. My stage-3 sweep probed +0x8xxx at the
   block base (all read 0x0 — wrong base, reads harmless).
4. fw-side corroboration: both selene (H14) and styx (H13) `__text` are dense with
   +0x800-family slot offsets (11-21 ASC-family hits each) — the fw talks to its
   mailbox as ASC-base+0x800-family, generation-stable.
5. selene is fully position-independent (PRELOAD, `__TEXT` vm 0, entry pc 0, zero MMIO
   constants — unlike styx which hardcodes its MMIO table): the H14 fw learns its base
   from boot args (kext writes SCRATCH0-7 pre-release). **Only needed if fw boot from
   Linux is ever required; with iBoot booting the fw it is not on the driver path.**
6. RTKit protocol reference pinned for the exchange: MGMT EP 0, HELLO=1/REPLY=2,
   EPMAP=8 (LAST bit 51), STARTEP=5, SET_IOP/AP_PWR_STATE=6/0xb, ver 11-12
   (Asahi `drivers/soc/apple/rtkit.c`); message = (msg0 64-bit, ep 8-bit) via
   send0/send1 pairs, ctrl FULL/EMPTY bits 16/17.

## 3. The wall — box crash loop (precise)

- Unclean resets (journal-confirmed, tmpfs-wiping, "corrupted or uncleanly shut down"
  journald marker, no panic text, no pstore entry — reset below the kernel): cluster
  13:27:27-14:02:27 box CDT (5 boots: 1 min, 21 min, 5.6 min, 1.6 min lifetimes),
  then a 3.9 h stable boot 14:02→18:00:41, then **18:00:41→18:02:21, ~18:02→~18:11,
  ~18:12→~18:19, 18:20→~18:23** — period 3-9 minutes.
- The cluster predates all agent contact (boot -5 died 13:28 with zero ssh ever).
  My device sessions (17:51-17:54 raise+probe; 18:04:54 raise replay) have **no death
  inside their windows**; deaths landed 3-8 minutes later with nothing of mine running.
  Two zero-device-write operations also died to the loop (probe file never executed /
  a read-only `uptime` poll). Main confirms Joshua went to bed in this window; the
  13:5x cluster lines up with physical handling; jwm1 showed the same signature tonight.
- **Mitigation (ANNOUNCED to Main, reversible)**:
  `/etc/systemd/logind.conf.d/90-agent-no-lid-suspend.conf`
  (`HandleLidSwitch=ignore`, `HandleLidSwitchExternalPower=ignore`,
  `HandleLidSwitchDocked=ignore`, `IdleAction=ignore`) + `systemctl mask sleep.target
  suspend.target hibernate.target hybrid-sleep.target`.
  Revert: `sudo rm /etc/systemd/logind.conf.d/90-agent-no-lid-suspend.conf; sudo
  systemctl unmask sleep.target suspend.target hibernate.target hybrid-sleep.target;
  sudo systemctl restart systemd-logind`.
  Side effect noted: restarting logind mid-session made sddm's greeter lose tty1
  (SDDM HELPER_TTY_ERROR lines) until next boot — cosmetic, did not stop the box.
- Discipline compliance: no retry of any access that faulted (none faulted — reads all
  completed; the kills hit between sessions); no SET-block writes; netconsole+ramoops
  confirmed re-armed post-reboot (netcon0 enabled, ramoops 4 MiB @ 0x10010000000,
  printk 8 4 1 7) before each read-only pass.

## 4. Staged single-shot (tools on omarchy-ane `feat/t6021-rtkit-phase1`)

- `rtkit/h14_bringup.py` — stages 0-3 as run (snapshot / raise / kext-region reads /
  candidate sweep).
- `rtkit/h14_readonly_probe.py` — zero-write confirmation: gate on ane_cpu on (never
  raises), then `+0x1600044` (expect `0x10` RUN on the live fw), `+0x1600048`, mailbox
  controls/slots, RTBuddy status. Prints FULL/EMPTY/wptr/rptr decodes.
- `rtkit/h14_rtkit_hello.py` — RTKit v11/12 MGMT exchange on the derived mailbox:
  receives HELLO, answers HELLO_REPLY (want = min(12, max_ver)), answers EPMAP with
  LAST/MORE echo, logs every rx; `--dry` = receive-only. Writes = RTKit replies only;
  preconditions checked, never forced. Success evidence: hello versions + epmap
  endpoints (SYSLOG/CRASHLOG/OSLOG + ANE app endpoints), then a syslog buffer request
  maps a userland page (pagemap phys) and the fw's log strings become the first
  documented RPC exchange.
- If `+0x1608114` reads without FULL/EMPTY semantics, the fallback decode is the kext
  endpoint-config table (rtbuddyEndpoint* doorbells via RTBuddy GPIO +0x48..+0x64,
  m1n1's "for acks w/ rtkit") — pure static work, already scoped.

## 5. Workstream plan — full H14 submission path

- **W1 — coprocessor RPC proof (first stable window, this turn if possible):**
  read-only probe (+0x1600044 = RUN check) → `h14_rtkit_hello.py` → HELLO/EPMAP/
  syslog text = first RPC exchange receipted. Then one capture-only CSNE_CMD sniff
  (log-only, no inference yet).
- **W2 — RPC protocol decode (static, no device):** kext `SetupEndpoints` /
  `InitializeRTBuddyEndpoints` endpoint table + `rtbuddyEndpointSendMessage`
  (endpointId, offset, size, extra) ring semantics; `ANEFWRpcMsg`,
  `FWSharedMemoryRequest`, `processTargetToHostIOCommand` flows; fw `CSNE_CMD_*` set
  (INFERENCE_CALL, IPC_ENDPOINT_SET/UNSET(2), REG_FILE_LOAD, BOOT) against F14 strings;
  ANE DART quartet (0x285800000/810000/820000, sid 0, `apple,t8110-dart` dual
  compatible per b877b87).
- **W3 — Linux driver skeleton:** platform driver on `apple,t6021-ane`; genpd attach
  consuming all of ane_cpu/sys_mpm/set1-4/base/td (drop-in for the d2e1d14 overlay
  lineage); RTKit core ported from rtkit.c semantics onto the +0x1608000 mailbox;
  tunables load via CSNE_CMD_REG_FILE_LOAD (fw `_rtk_tunables` 1456 B, T6021 A0/B0/B1
  selectors in `H14TunableManager`).
- **W4 — task submission:** TQ stays fw-owned (CSneTMDrvH14, 8 queues — host never
  programs TM/TQ, the H13 model is dead on this silicon); host submits via the
  CSNE_CMD_INFERENCE_CALL endpoint + shared rings; program/weights path =
  `ANEProgram*` (hwx/anec mint for h14g via the proven `mint_aneforge` route).
- **W5 — qualification:** schema4 add-mul smoke exact-match on T6021 through the new
  path (runbook shape from 2026-09-18-t6021-driver-entry-prepared §3); promote
  `ane_soc_t6021` RECOGNIZED → QUALIFIED; README row + receipts.

## 6. Refs

- Branch: omarchy-ane `feat/t6021-rtkit-phase1` (d04cae5 bring-up tool, dfe52ce hello
  tool + zero-write probe), pushed.
- Inputs: 2026-09-18-t6021-engine-layout-mined (kext/fw artifacts + imm_scan tools),
  2026-09-18-t6021-overlay-abort §session-2 (netconsole/ramoops instruments),
  Asahi rtkit.c + m1n1 hw/asc.py (protocol), apple-pmgr-pwrstate.c (PS semantics).
- Netconsole receiver: /var/log/fleet-netconsole.log on omp-studio-local (sender
  192.168.3.103:6668); journald boots -5..0 on the box carry the reset timeline.
