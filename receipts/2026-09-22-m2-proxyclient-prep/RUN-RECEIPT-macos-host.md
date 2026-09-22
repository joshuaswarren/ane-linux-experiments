# RUN-RECEIPT — T6021 ANE bring-up, macOS-host leg (m1-host) — 2026-09-22

Operator: M2ProxyMacosHost (subagent of Main). Model resolved: zai/glm-5.3-flash.
Topology per plan: m2-host (M2, t6021) parked at the m1n1 proxy (boot.bin.proxy-swuf
6dc0ec5d on its ESP disk0s4; backup boot.bin.proxy-only.bak 9ad08653; original
boot.bin.pre-proxy 153170e0 on m2-host Linux root at /var/tmp/m2proxy-staging/).
Host leg: m1-host (M1 Max, macOS 27.0) at login window, pre-login SSH
`jw-m1-lan`, booted one-shot by FleetMacOSUnattendedAccess on
Main GO (ReleaseV072Finish window confirmed closed; EncoderFeederFork
checkpointed and holding; DecodeDispatchCut2/PrefillCoopmatTile/M2SwufInstallRun/
M2ProxyRun confirmed nothing of theirs on m1-host).

## Outcome: NEGATIVE — the m1n1 USB gadget does not enumerate on the macOS host either

No proxyclient run was possible: there was no device to point `M1N1DEVICE` at.
The bring-up sequence (RVBAR mode-bit write etc.) was never reached.

## Decisive evidence (verbatim, m1-host @ macOS)

1. `system_profiler SPUSBDataType` — EMPTY, exit code 0:

```
% ssh jw-m1-lan 'system_profiler SPUSBDataType 2>&1; echo RC=$?'
RC=0
```

2. `ioreg -p IOUSB -w0` — only the two XHCI controllers, ZERO attached devices
   (polled twice, ~90 s apart):

```
+-o Root  <class IORegistryEntry, id 0x100000100, retain 28>
  +-o AppleT8103USBXHCI@00000000  <class AppleT8103USBXHCI, id 0x1000005c2, registered, matched, active, busy 0 (15 ms), retain 27>
  +-o AppleT8103USBXHCI@01000000  <class AppleT8103USBXHCI, id 0x1000004e6, registered, matched, active, busy 0 (4 ms), retain 27>
```

3. `/dev/cu.usbmodem*` — absent (`zsh: no matches found`). No VID 0x1209
   PID 0x316d (m1n1 gadget), no 05ac:1905 (macOS NCM), anywhere.
4. `log show --last 10m --predicate 'subsystem == "com.apple.iokit.IOUSBHostFamily"'`
   — no attach/enumerate events.
5. Cable topology at time of test: m2-host port0 <-> m1-host port0 (USB-C charge
   cable), charger on m1-host port1 — exactly the proven-good physical path.

## Differential conclusion

- M2ProxyRun (Linux leg): the m2-host m1n1 gadget NEVER presented on any Linux
  host (3+ reboots, 3 cable types, no 1209:316d).
- M2SwufInstallRun (same cable, earlier today): m2-host DID enumerate
  05ac:1905 (macOS NCM) to m1-host while booted to macOS.
- This run (m1-host @ macOS vs m2-host parked at the proxy): nothing at all.

The link and cable are proven good; the failure isolates to the PARKED m1n1
image's USB gadget on m2-host (m1n1 1.6.1 proxy build, boot.bin.proxy-swuf
6dc0ec5d). The gadget never presents on either OS-family host — this is an
m1n1-side (dwc3 gadget / proxy image) defect, not a host-driver issue.

## Consequences

- T6021 ANE bring-up over the proxy: NOT RUN (no transport). Selene fixture
  verified staged on the workstation
  (`tools/ane-hunter/fixtures/t602x_ane0_fw_selene_rc4x.macho`,
  sha256 9f7915c431d288a2bdc2132c399db8cf5574716a3b1e94af76be6a291c2e665b) and
  scripts ready in `scripts/m2-proxyclient/` — the moment a working transport
  exists, the runbook checklist applies unchanged.
- Chainload-over-proxy un-park of m2-host: IMPOSSIBLE (no USB path).
  Un-park now requires physical hands on m2-host: boot-picker (hold power ->
  macOS; pre-login SSH on m2-host-lan then restore ESP per
  RUN-RECEI.md/M2SwufInstallRun: mount disk0s4, cp boot.bin.pre-proxy ->
  /Volumes/.../m1n1/boot.bin, verify sha 153170e0…ad1ff5) — or a cable
  re-seat to re-test the gadget (both are the owner's physical actions; not
  attempted per constraint).
- m2-host state at handoff: UNCHANGED, still parked at the proxy.

## Return actions

- m1-host returned to Linux by FleetMacOSUnattendedAccess (plain reboot) at the
  end of this window; ANE rebind verified post-return (see below).
- EncoderFeederFork notified to restore m1-host's convfix-reverted runner
  (vulkan_encoder_inproc.py.bak-20260922-convfix) and resume their lanes;
  PrefillCoopmatTile's deferred m1-host build+bench unblocked.

## Post-return verification (Linux, m1-host) — DONE

FleetMacOSUnattendedAccess fired the plain return reboot; verified by SSH:

```
% ssh m1-host 'uname -r'            -> 7.1.13-3-2-ARCH
% ssh m1-host 'ls /sys/class/accel' -> accel0
dmesg: ane: loading out-of-tree module taints kernel.
       [drm] Initialized ane 1.0.0 for 26bc04000.ane on minor 0
       ane 26bc04000.ane: loaded ane
% ssh m1-host 'systemctl is-active m1n1-proxy-watcher' -> active
```

ANE rebind confirmed (accel0, ane DRM minor 0). m1n1-proxy-watcher active
again for its own m1-host-side m1n1 duties. EncoderFeederFork and PrefillCoopmatTile
notified at return.

## Final state

- m1-host: back on Omarchy Linux, ANE bound, watcher active. LANES UNBLOCKED.
- m2-host: UNCHANGED, still parked at the proxy (boot.bin.proxy-swuf 6dc0ec5d).
  Un-park = physical boot picker to macOS (Joshua), then ESP restore per
  M2SwufInstallRun handoff; next lane M2M1n1Hook per Main.
- No ESP writes were performed on m2-host this session (impossible: no transport).
