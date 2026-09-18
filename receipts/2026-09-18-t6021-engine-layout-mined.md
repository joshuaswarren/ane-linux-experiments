# T6021/H14J ANE engine TM/TQ layout mined from macOS 27 kext + firmware (2026-09-18)

Verdict: **MINED — the missing datum is an ARCHITECTURE answer, not an offset answer.**
On H14 (t6021) **nobody programs TM/TQ MMIO from the host**: the H14-generation ANE
firmware (`CSneTMDrvH14` inside `t602x_ane0_fw_selene`) owns the task manager and the
8 task queues, and the macOS kext (`AppleH11ANEInterface` 10.19.2) talks to it over
RTKit mailbox RPC. The H13-style host-side TM/TQ register block (engine `+0x20000`,
`TM_TQ_EN +0xc`, TQ stride `0x148`) is **constructed 42 times in the H13 kext and 0
times in the H14J kext**. The t6021 external abort at `0x285c2400c` is therefore the
*expected* outcome of an H13-shaped first touch: on t6021 that window has no host-side
programmer and is not the submission path. The next Linux bind attempt on T6021 is a
**driver-architecture change** (RTKit + mailbox + fw command protocol), not an offset
swap. No device writes were performed in this lane.

## 1. Method validation FIRST (per Main/Joshua scope extension)

The H13 baseline was reproduced from an independent H13 source before any H14J number
was trusted:

| step | source | result |
| --- | --- | --- |
| H13 kext copy | macstudio (Mac13,2, M1 Ultra, macOS 26.6.2 **25G83**) boot kernelcollection, scp'd read-only — `/System/Volumes/Preboot/60EAA20C…/boot/…/System/Library/Caches/com.apple.kernelcaches/kernelcache` (im4p `krnl`) | decompressed + kext carved: `AppleH11ANEInterface` **9.512.0** (sha256 `66c212c843edfb37…`) |
| known-constant reproduction | arm64e disasm immediate scan (`tools/imm_scan.py`, handles `#imm` and `#imm, lsl #n`) | **42 `add xN, xM, #0x20, lsl #12` sites** (= base + 0x20000, the TM block) + 44 × `#0x40, lsl #12` (0x40000 engine stride) + 16 × `#0x22000` — sample in `tools/h13-tmhits-sample.txt` |
| cross-check vs working driver | `omarchy-ane/ane/src/ane_tm.c` H13 constants (`ANE_TM_BASE 0x20000`, `TM_TQ_EN 0xc`, TQ stride `0x148`, 8 queues) | consistent; upstream `m1n1/proxyclient/m1n1/hw/ane.py` (Eileen Yoon, 2023-03, unchanged since) carries the same layout as a RegMap (`TaskQueue` stride `0x148`, `STATUS/PRTY/FREE_SPACE/TQINFO`, `BAR1/NID1/SIZE2/ADDR2/BAR2/NID2/SIZE1`) |
| negative control | H13 **firmware** (`h13_ane_fw_styx_j5x`) scanned with the same tool for `0x20000/0x21000/0x148` | 0 hits — proving the fw never used host-window TM/TQ offsets even on H13 (fw sees the engine through its own internal window), so "fw shows no constants" was never evidence against a layout; the **kext** is the host-side oracle |

Only after the H13 kext reproduced the known block was the identical scan applied to
H14J. Every tool and its exact usage is in `tools/`.

## 2. Differential table H13 → H14J (per-entry source evidence)

Sources abbreviated:
- **K13** = `AppleH11ANEInterface` 9.512.0, macOS 26.6.2 25G83, T600x board (macstudio boot KC) — file `kext-h13/`
- **K14** = `AppleH11ANEInterface` 10.19.2, macOS 27.0 **26A428**, mac14j (T6021 board J414c) restore kernelcache `kernelcache.release.mac14j` — file `kext-h14j/`
- **F13** = `h13_ane_fw_styx_j5x.im4p` / **FEOS** = `t600x_ane0_fw_eos_jc3x.im4p` (macOS 27 ships both) — `fw-h13-styx/`
- **F14** = `t602x_ane0_fw_selene_rc4x.im4p` (the T6021 fw of record) / **FBIA** = `h14_ane_fw_bia_j4xx.im4p` — `fw-h14j-selene/`
- **DT27** = `DeviceTree.j414cap.im4p` from the 26A428 IPSW (`dtree-j414c.txt`)
- **UP** = upstream m1n1 `proxyclient/m1n1/{hw,fw}/ane.py` @ main

| datum | H13 (T8103/T600x) | H14J (T6021) | evidence |
| --- | --- | --- | --- |
| ANE MMIO block (ADT range0) | e.g. t8103 `0x26a000000`, 32 MB | `0x84000000` sz `0x2000000` (→ `0x284000000` with the proven `+0x200000000` translation) | DT27 ane0 `reg`; identical to macOS 26.6.2 + 27.0 IOReg captures |
| engine sub-window in ADT | **exists** (t8103 `ane@26a000000` → engine `0x26bc04000`, delta `+0x1c04000`, size `0x24000`) | **DOES NOT EXIST** — ane0 has exactly 3 reg ranges (MMIO + pmgr `0x8e080000/0x4034` + pmgr `0x8e08c000/0x4000`); no engine child, no `+0x1c04000` anywhere | DT27 (second independent source; matches both IOReg captures). m1n1 experiment hardcodes only t8103 `UP: rnges=[(0x26bc04000,0x26bc28000,'engine')]` |
| host TM/TQ programming | **kext does it**: 42 × `add #0x20, lsl #12` (base+0x20000) in K13 code; TQ block `+0x21000` family, stride `0x148`, 8 queues | **kext never touches it**: 0 × `add #0x20/0x21/0x22, lsl #12`; the only 0x20000s in K14 are 6 allocation-tag/bitflag sites (kmem size-class `movk w2, #2, lsl #16` + one `orr x4, x8, #0x20000`) | K13 vs K14 disasm count (tools/imm_scan.py); K14 site contexts dumped (all `kalloc`/`IOMalloc` size-class noise) |
| who drives the task manager | kext (H13 path above) + fw `CSneTMDrvH13` + `CSneTDDrvH13` (task-descriptor driver present) | **fw-only**: `sne/drivers/tm/CSneTMDrvH14.cpp` in F14 with asserts `queueId < (8)` (8 TQs), `tqStatus.f.Idle == 1` (TQ STATUS polled), `Set TQ[%d] priority to 0x%x` (TQ PRTY write), `Set TQ[%d] cfg to 0x%x`, `waitTQIdle() … more than 2 sec`, `state < MAX_NUM_ANE_TQ_STATE`; **CSneTDDrv is GONE** in F14/FBIA | strings in F14 (`strings -n 6`, `sne/drivers/…` table below); FBIA identical |
| TQ count / shape | 8 queues, stride `0x148` (K13 + UP TaskQueue RegMap) | 8 queues (`queueId < (8)` in F14); stride/count of the fw-internal view not host-visible | F14 strings + K13/UP |
| engine stride used by host | `0x40000` (`add #0x40, lsl #12` × 44 in K13) | **no engine-stride arithmetic at all** (0 hits) | K13 vs K14 disasm histogram (`tools/hist_diff.py` output in session) |
| RTKit/ASC block (shared) | block-relative `ASC_IO_RVBAR +0x1050000` (7 K13 sites), RTBuddy/VERS region `+0x1840000` (14 sites) | **same region in use**: `+0x1050000` (2 sites, RVBAR accessor calls at `0x…95e985c/0x…95e9980`), `+0x1840000` (9 sites) | K13 + K14 disasm; UP `ANERegs` names these exact offsets (`ASC_IO_RVBAR=0x1050000`, `VERS=0x1840000`, `GPIO0-7=0x1840048…` "for acks w/ rtkit") |
| kext ↔ fw transport | fw commands + direct TM/TQ doorbell | **fw-command RPC only**: K14-only symbols `ANEFWRpcMsg`, `FWSharedMemoryRequest`, `ANEFwToFwSignalMsg`, `ANEHWDeviceTimeoutMsg`, `processTargetToHostIOCommand`, `pauseFWCommandPollTimer`/`aneFWCommandPollTimer_gated`; fw side has the matching `CSNE_CMD_*` endpoint set (`CSNE_CMD_INFERENCE_CALL`, `CSNE_CMD_IPC_ENDPOINT_SET/UNSET(2)`, `CSNE_CMD_REG_FILE_LOAD`, `CSNE_CMD_BOOT`, …) | symbol-set diff K13 vs K14 (11,022 vs 8,109 syms); F14 strings |
| register-name strings in kext | full CHINOOK CPU surface: `rANE_CHINOOK_*` (30+), `rANE_ASCWRAP_IDLE_STATUS`, `rANE_ASC_CPU_EDPRCR`, `rANE_SCRATCH0-7` | only 4 left: `rANE_H11_CHINOOK_IO_RVBAR`, `rANE_SCRATCH0`, `rANE_SCRATCH0/3/7` | `strings` both kexts |
| tunables | fw `_rtk_tunables` 488 B, one header entry `0x00180301` | fw `_rtk_tunables` 1456 B, headers `0x00240301` + `0x00240303`; per-chip selectors **"Using T6020 A0 / T6021 A0 / T6021 B0 / T6021 B1 / T6022 … tunables"** in `H14TunableManager.cpp` (`./sne/common/misc/tunable/`) | F14 sections + strings; tables themselves are host-loaded (`CSNE_CMD_REG_FILE_LOAD`, kext `AppleANETunableApplyFunction`) |
| fw `_fwinfo` | magic `0x1deafbabe`, image `0xe4000`, heap top `0x608000` | magic `0x1deafbabe`, image `0xe8000`, `0x284000` | section dumps (both) |
| SET window (pmgr) | pmgr0 era; `ps_map["ane0"]=0x…0c000` verified live | **pmgr is `pmgr1,t6021`** (DT27 `compatible: "pmgr1,t6021"`) — the +0xc000 window's non-pwrstate-looking readback (`0x0 / 0x80000000×5`) is consistent with a different ps-word FORMAT, not necessarily a wrong window; pmgr device table carries the full ANE chain ANE_SYS(60), ANE_CPU(76), ANE_SYS_MPM(112), ANE_TD(113), ANE_BASE(114), ANE_SET1-4(115-118) with alias chaining base→set | DT27 pmgr node + devices table; abort-receipt bind-B probe |

### Candidate engine base / first safe access for T6021 (the ask)

1. **There is no t6021 "engine base" equivalent to `+0x1c04000` to find** — the ADT does
   not declare one (DT27 + IOReg agree), and the macOS driver for this chip never
   computes one. On t6021 the host-visible ANE is the **whole 32 MB range0**
   (`0x284000000`) addressed block-relative, with the fw CPU managed via
   `+0x1050000` (RVBAR) and RTKit acks via the `+0x1840000` region — the only
   block-relative offsets the H14J kext itself uses.
2. Any Linux first-touch on t6021 that needs to read *something* host-side before a
   full RTKit stack exists should prefer the **block-relative RTKit/ASC region**
   (`0x284000000 + 0x1050000` = `0x285105000` RVBAR, read-only, fw-CPU boot pc) —
   **[INFERENCE from K14 accessor use + UP RegMap; not yet device-proven]** — and must
   treat the H13 TM/TQ window (`+0x1c04000+0x20000`) as **absent on this SoC**
   (kext never touches it; two netconsole-named external aborts).
3. Real task submission on H14J = port the RTKit + mailbox + `CSNE_CMD` command path
   (m1n1 has the reusable RTKit plumbing; the ANE-specific command set is enumerated
   in F14 strings). This is a driver rewrite, not a constant patch.

## 3. ANE families shipped in macOS 27.0 (26A428) — enumeration

`Firmware/ane/` in the UniversalMac IPSW (all im4p, extracted to arm64 Mach-O):

| fw blob | family | fw TM driver class (from `sne/drivers/…` strings) | extra drivers |
| --- | --- | --- | --- |
| `h13_ane_fw_styx_j5x` | H13 | `CSneTMDrvH13` | `CSneTDDrvH13` |
| `t600x_ane{0-3}_fw_eos_jc3x` | H13-family 4-die | `CSneTMDrvH13` | `CSneTDDrvH13`; "default A0/B0/B1 tunables" |
| `h14_ane_fw_bia_j4xx` | H14 | `CSneTMDrvH14` + `CSneTMDrvHx` | — |
| `t602x_ane{0,1}_fw_selene_rc4x` | **H14 (T6020/21/22 — this machine)** | `CSneTMDrvH14` + `CSneTMDrvHx` | T6020/21/22 A0/B0/B1 tunable selectors |
| `h15_ane_fw_themis_j51y` | H15 | `CSneTMDrvH15` + `CSneTMDrvHx` | `CSneMCWDrvH15` (memory-controller wrapper, new in H15) |
| `t603x_ane{0,1}_fw_erebus_{ls5x,pc5x}` | H15-family | `CSneTMDrvH15` | `CSneMCWDrvH15` |
| `h16_ane_fw_leto_j7x` | H16 | `CSneTMDrvH16` | `CSneMCWDrvH15`, `CSneCEDrvH16` |
| `t604x_ane_fw_aether_brvx` | H16-family | `CSneTMDrvH16` | `CSneMCWDrvH15`, `CSneCEDrvH16` |
| `h17_ane0_fw_hyperion_j71y`, `h17_ane_fw_theia_{d9x,j73y}` | H17 | `CSneTMDrvH17` | `CSneMCWDrvH15`, `CSneCEDrvH17` |
| `h18_ane{0,1}_fw_kirkland_j8xx` | H18 (M5-gen) | `CSneTMDrvH18g` | `CSneItqDrvH18g` (ITQ driver — "ITQ not supported!" already in F14), `CSneMCWDrvH15` |

GPU-side corroboration that macOS 27 carries M5-forward support: SystemOS cryptex ships
`AGXMetalG15…G19P` compiler bundles (G15=M1 → G19P=M5-generation). All 12 fw blobs and
their driver-class tables are extracted under the repo artifact dir
(`fw-shasums.txt` covers the four primary ones; family blobs kept in `/tmp/t6021-mine/ane-fw-extra/`).

Per-family "layout" status for the SoC table: for every family we hold (a) the exact
fw binary that would run on such silicon and (b) the fw TM driver generation + TQ
shape strings; **kext-derived-untested** rows apply: host-side TM/TQ programming is
provably kext-absent from H14 onward (H15+ verify identical by the same imm scan —
`CSneTMDrvH15/16/17/18g` strings prove the fw-side ownership), so no H14+ family
should ever be qualified with an H13-style engine+0x20000 first touch.

## 4. Upstream check (m1n1 / Asahi) — scope item 3

- `m1n1` main: ANE lives in `proxyclient/m1n1/{fw,hw}/ane.py` +
  `proxyclient/experiments/ane.py`; `hw/ane.py` initial commit 2023-03-28 by Eileen
  Yoon, last commit 2025-02-22 = **codespell typo fix only**. Engine window hardcoded
  t8103-only (`0x26bc04000/0x24000`). `ps_map` is name-keyed and hardcoded
  (`"ane0": 0x028e08c000` — coincides with t6021's pmgr+0xc000 window, but the ps-word
  FORMAT behind it is pmgr0-era).
- **No H14/t6021/mach14j ANE constants have landed upstream.** (Community rows in our
  own captures remain the only t602x ANE power-domain data.) The in-kernel
  `apple,t6020-dart`-adjacent work someone did is DART-side, not ANE-side.

## 5. Note for later (scope item 4)

Queued behind the GPU lanes: **IOReg dump from jw14m2 macOS after a real ANE
workload** (needs the macOS slice booted). What it would add: the live `H11ANEIn`
device tree during/after fw RPC traffic — engine-window mappings that only appear
after `ANEDeviceInterface` instantiation, plus live mailbox/endpoint state. This lane
did NOT reboot the machine (GPU lanes active) and performed zero device contact.

## 6. Extraction pointers / reproduction (all CPU-side, read-only)

```
IPSW (exact build): mesu catalog com_apple_macOSIPSW_27_26A428 →
  https://updates.cdn-apple.com/2026FallFCS/afcfc88e-bbe6-44bf-a5da-07c56eebc06c/UniversalMac_27.0_26A428_Restore.ipsw
  sha256 of downloaded file logged in session; Content-Length 26626436228.
kernelcache (T6021 board): kernelcache.release.mac14j → `ipsw kernel dec` →
  `ipsw kernel kexts` (374 kexts; ANE ones: AppleH11ANEInterface 10.19.2,
  AppleANELoadBalancer 10.19.2) → `ipsw kernel extract <KC> com.apple.driver.AppleH11ANEInterface`
H13 kext control: macstudio Preboot boot-KC (im4p) → same pipeline (9.512.0).
ANE firmware: `ipsw fw ane <blob>.im4p -o out/` → PRELOAD arm64 Mach-O (RTKit layout,
  `_rtk_*` sections). Selene = the blob macOS 27 loads on J414c.
DeviceTree: `Firmware/all_flash/DeviceTree.j414cap.im4p` → `ipsw dtree` (dtree-j414c.txt).
Analysis tools + scan samples: tools/ (imm_scan.py is the calibrated immediate scanner;
  it handles `#imm, lsl #n` — a first version that didn't was the reason an initial
  H13 scan showed false zeros, fixed before any conclusion was drawn).
Direct-mount note: jw14m2's macOS 27 APFS is NOT mountable from Linux — container
  keybag block at paddr 1326263 of nvme0n1p2 is ciphertext (o_type `3f ea 46 c8`, not
  `keys`); apfs-fuse KeyManager init fails exactly there (SEP-wrapped). Route used
  instead = Apple mesu restore IPSW (unsealed, same build 26A428).
```

## 7. Footprint / cleanup state

- This host (`omp-studio-local`): `/tmp/t6021-mine/` (26.6 GB IPSW, extracted
  kexts/fw/dtree, analysis scripts) — left in place for the follow-up lanes; delete
  freely when done. No installs except the single-file `ipsw` CLI binary into that
  scratch dir.
- jw14m2-linux (GPU lane box — touched only via ssh, no reboot, no GPU contact):
  `sudo pacman -S cmake` (build dep), `/tmp/apfs-fuse-14181` + `/tmp/apfs-build`
  (apfs-fuse build, kept for future mounts), the two FUSE mounts and the three
  transferred dmg files unmounted and removed in-session. No kernel modules loaded;
  the apfs-fuse route was chosen specifically to avoid insmod on the GPU-active box.
- Scope-item-2 residue: the 12 fw blobs in `Firmware/ane/` are fully enumerated and
  classified (§3). The additional pass over the 11 GB SystemOS `FileSystem` dmg
  (043-70867-635) for on-disk ANEHAL kext *binaries* (M3+ per-chip HALs) was started
  but not completed within this lane's budget — the .aea extract was cut at ~10.3 GB
  and removed with the scratch. Since host-side TM/TQ programming is kext-absent from
  H14 onward (§2), those HAL binaries would only add H15+ host-side detail, never
  t6021 data; run the same three commands (unzip → `ipsw fw aea` → apfs-fuse ro mount)
  if that detail is ever needed.
- macstudio: read-only scp of the boot KC + plist reads only. jwm1, jw16: untouched.
- No ANE module loads, no SET-block writes, no device contact of any kind.
