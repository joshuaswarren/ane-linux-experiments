# m1n1 proxyclient bring-up plan — T6021 ANE ASC on m2-host

Single variable vs every 2026-09-21 Linux arm (`receipts/2026-09-21-t6021-host-tm/`):
RVBAR is written **with the kext mode bits** (`0x0081010000000001`) **before**
the core leaves reset, from the proper quiesce context (m1n1 stage 1 owns the
machine; no Linux kernel, no watchdog). Everything else replays the proven
ANE_Init order: power cycle ane_cpu → RVBAR → map selene → RUN → poll
SCRATCH7 for `0x08042006` → RTKit handshake.

Verified against:
- ADT capture `~/var/tmp/m2-macos-capture-20260921/ane0-dt.txt`
  (`python3 t6021_consts.py` — all 18 checks green)
- `tools/ane-hunter/driver_consts.py` (engine 0x284000000, TM 0x285C00000)
- NIGHT-SUMMARY §3/§4 (RVBAR 0x285050000, CPUCTL 0x285400044, SCRATCH7
  0x285840064, READY 0x08042006, wake 0xF7FBDFF9, mode-bit composition)

## Files

| file | role |
|---|---|
| `t6021_consts.py` | every address + `validate()` cross-check (run standalone) |
| `ane_bringup.py` | the session script (a)–(e); `--dry-run` = reads only |
| `mock_proxy.py` | stub ASC; happy path + `--mock-latched-rvbar` negative path |

## Boot side (one-time, m2-host)

1. **m1n1 stage 2 with the proxy enabled.** m2-host already chainloads through
   the Asahi bootstrap; build/install m1n1 with the default config — the m1n1
   proxy runs on the USB serial gadget as soon as the cable is connected.
   If the current bootstrap is a Linux-only install, boot m1n1 once via
   1TR/USB boot object built with `m1n1/m1n1.macho` + `m1n1/build-uboot.sh`
   is NOT needed (no U-Boot; the bare proxy in `m1n1.macho` is enough).
2. **USB gadget mode:** m1n1 enumerates as a USB serial device on the host
   automatically (`/dev/ttyACM*` on Linux host, cu.usbmodem* on macOS host).
   Nothing to configure on m2-host — the cable IS the switch.
3. **Host-side pip requirements** (any host; this workstation):

   ```sh
   python3 -m pip install --user pyserial construct pyelftools
   # m1n1 proxyclient tree:
   git clone --depth 1 https://github.com/AsahiLinux/m1n1 ~/src/m1n1
   ```

4. Point the script at the tree (it inserts `scripts/m2-proxyclient/.work-m1n1-proxyclient`
   into sys.path):

   ```sh
   ln -sfn ~/src/m1n1/proxyclient scripts/m2-proxyclient/.work-m1n1-proxyclient
   ```

5. Selene comes from the hunter fixtures
   (`tools/ane-hunter/fixtures/t602x_ane0_fw_selene_rc4x.macho`, sha `9f7915c4…`);
   re-fetch from m2-host `/lib/firmware/apple/ane/` if absent.

## The 10-minute checklist (once the cable is in)

```sh
cd <repo>/scripts/m2-proxyclient

# 0. (30 s) constants still valid
python3 t6021_consts.py                       # expect: VALIDATION PASS

# 1. (30 s) device present
ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null      # note the device, export it
export M1N1DEVICE=/dev/ttyACM0                # adjust

# 2. (1 min) reads-only smoke: ADT dump + RVBAR/SCRATCH7/CPUCTL state
python3 ane_bringup.py --dry-run              # expect: READS-ONLY DONE
#   expected live state: RVBAR 0x10000000001 (latched), SCRATCH7 0x0,
#   CPU_STATUS 0x28 — matches every post-watchdog read from the night.

# 3. (2 min) the arm — one variable, mode bits
python3 ane_bringup.py --mock                 # stub sanity (optional)
python3 ane_bringup.py                        # THE RUN
```

Interpreting the run:

| outcome | reading | next step |
|---|---|---|
| `[poll] SCRATCH7-READY MATCH=True` + `[e] handshake complete` | **mode-bit hypothesis CONFIRMED** — first ASC boot ever on this box | TQ contract `.work/2026-09-21-t6021-host-tm-contract.md` on the running selene |
| `[d] ABORT no READY … CPU_STATUS=0x28` | silent-park stands even with mode bits — RVBAR composition still incomplete (FWIM_DVA ≠ 0x10000000000?) | check `SCRATCH1:SCRATCH0` after publish path; consider kext FWIM DVA from `*(dev+0x978)+0x18` |
| `[b] ABORT RVBAR readback … write not accepted` | proxy-context RVBAR also ignores writes pre-reset | abort; do NOT reset/ps-cycle from any host; capture with `--dry-run` and stop |
| USB drop / no READY and box unresponsive | — | reboot m2-host (watchdog will anyway); nothing on the Linux side to clean up |

## Safety

- Every poll bounded (kext bounds: Poll A/B = 1000 × 1 ms); every proxy
  command under `alarm(5)`.
- Abort file: `touch /tmp/ane-bringup.abort` stops any poll instantly.
- `--dry-run` writes nothing (read-only pre-flight).
- m1n1 stage 1 owns the whole machine — the Linux freeze classes (posted
  ioremap, kernel-context ps-cycle) do not exist on this path.
- Log every step; the script's stdout is the receipt (tee to
  `receipts/2026-09-22-m2-proxyclient-prep/`).
