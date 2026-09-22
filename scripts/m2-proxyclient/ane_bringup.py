#!/usr/bin/env python3
"""T6021 ANE ASC bring-up over m1n1 proxyclient (USB) — m2-host single-variable
mode-bit test.

Sequence (one variable vs the 2026-09-21 Linux arms: RVBAR carries the kext
mode bits 0x0081<<48, written from the proper quiesce context):
  (a) dump live ADT ane0 / dart-ane0 / pmgr power state
  (b) ane_cpu power cycle (pmgr ADT disable/enable) + RVBAR write64
      0x0081000000000001 | (DVA & 0xff7eFFFFFFFFFF80) at engine+0x1050000
  (c) map selene at the fw DVA via dart-ane0 SID 0 (+ m1n1 TTBR0 hack)
  (d) CPU_CONTROL 0 -> 0x10 (RUN), poll SCRATCH7 == 0x08042006 (<=1000 x 1 ms)
  (e) on READY: RTKit handshake via m1n1 StandardASC (mgmt EP 0), bounded

Usage:
  python3 ane_bringup.py                # real run over m1n1 USB/uart proxy
  python3 ane_bringup.py --mock         # dry-run against the local stub
  python3 ane_bringup.py --dry-run      # real connect, READS ONLY, no writes

Every proxy command is bounded (alarm), every poll bounded, every step logged.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".work-m1n1-proxyclient"))

import t6021_consts as C

LOG = []
ABORT = "/tmp/ane-bringup.abort"


def log(tag, **kv):
    line = time.strftime("%H:%M:%S") + f" [{tag}] " + " ".join(
        f"{k}={v}" for k, v in kv.items())
    LOG.append(line)
    print(line, flush=True)


def die(tag, msg):
    log(tag, RESULT="ABORT", reason=msg)
    raise SystemExit(1)


class Bounded:
    """alarm() bound on every proxy roundtrip (usb stall == hung lane)."""

    def __enter__(self):
        import signal
        signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(
            TimeoutError("proxy roundtrip exceeded %ss" % C.CMD_TIMEOUT)))
        signal.alarm(C.CMD_TIMEOUT)

    def __exit__(self, *a):
        import signal
        signal.alarm(0)


def poll(name, readfn, match, max_tries, interval, tag=""):
    """Bounded poll; returns (ok, last_value)."""
    last = None
    for i in range(max_tries):
        if os.path.exists(ABORT):
            die("poll", f"abort file {ABORT} present")
        with Bounded():
            last = readfn()
        if last == match:
            log("poll", name=name, tries=i + 1, value=hex(last), MATCH=True)
            return True, last
        time.sleep(interval)
    log("poll", name=name, tries=max_tries, value=hex(last), MATCH=False,
        expected=hex(match), note=tag)
    return False, last


# ---------------------------------------------------------------- hardware --
def connect_real(dry_run):
    """m1n1 proxy over the USB gadget (m2-host stage 2, proxy enabled)."""
    from m1n1.setup import iface, p, u  # noqa: auto-detects M1N1DEVICE
    u.iface = iface
    return u, dry_run


class HW:
    """Thin wrapper: every MMIO access through one place, all logged."""

    def __init__(self, u, dry_run=False, mock=False):
        self.u = u
        self.dry = dry_run
        self.mock = mock
        self.p = u.proxy

    def _addr_ok(self, addr):
        inside = any(a <= addr < a + s for a, s in
                     ((C.ENGINE_BASE, C.ENGINE_SIZE),
                      (C.ASC_BLOCK + 0x8800, 0x100),
                      (C.DART_BASE, 0x400000)))
        if not inside:
            die("guard", f"address {addr:#x} outside ADT windows")

    def r32(self, addr):
        self._addr_ok(addr)
        with Bounded():
            v = self.p.read32(addr)
        log("r32", addr=hex(addr), value=hex(v))
        return v

    def r64(self, addr):
        self._addr_ok(addr)
        with Bounded():
            v = self.p.read64(addr)
        log("r64", addr=hex(addr), value=hex(v))
        return v

    def w32(self, addr, val):
        self._addr_ok(addr)
        if self.dry:
            log("w32", addr=hex(addr), value=hex(val), DRY=True)
            return
        with Bounded():
            self.p.write32(addr, val)
        log("w32", addr=hex(addr), value=hex(val))

    def w64(self, addr, val):
        self._addr_ok(addr)
        if self.dry:
            log("w64", addr=hex(addr), value=hex(val), DRY=True)
            return
        with Bounded():
            self.p.write64(addr, val)
        log("w64", addr=hex(addr), value=hex(val))


# ------------------------------------------------------------------- steps --
def step_a_dump_adt(u):
    log("a", step="adt-dump", begin=True)
    for path in (C.ANE_PATH, C.DART_PATH, "/arm-io/pmgr"):
        try:
            with Bounded():
                node = u.adt[path]
        except Exception as e:
            log("a", path=path, MISSING=str(e).__class__.__name__)
            continue
        log("a", path=path, compatible=getattr(node, "compatible", None))
        for i in range(4):
            try:
                with Bounded():
                    reg = node.get_reg(i)
                log("a", path=path, reg=i, base=hex(reg[0]), size=hex(reg[1]))
            except Exception:
                break
    # pmgr power state of the ane gates, live read from stage-1 pmgr if
    # available (advisory only; never fatal)
    log("a", step="adt-dump", done=True)


def step_b_power_rvbar(hw, fw_phys=None):
    """Power cycle ane_cpu, then RVBAR with mode bits."""
    log("b", step="power-cycle", begin=True)
    if not hw.dry:
        with Bounded():
            hw.p.pmgr_adt_power_disable(C.ANE_PATH)
            time.sleep(0.05)
            hw.p.pmgr_adt_power_enable(C.ANE_PATH)
            hw.p.pmgr_adt_power_enable(C.DART_PATH)
    log("b", pmgr="ane_cpu cycled via ADT gates")

    rvbar = C.rvbar_value()  # 0x0081010000000001
    # lawful skip rule from s22: skip only when bit0 already set AND mode
    # bits already present; the latched value 0x10000000001 lacks them, so
    # we always write here (proxy context, not the Linux-write-ignore case)
    with Bounded():
        pre = hw.r64(C.ASC_RVBAR)
    log("b", rvbar_pre=hex(pre), mode_bits=bool(pre & C.RVBAR_MODE_HI))
    hw.w64(C.ASC_RVBAR, rvbar)
    with Bounded():
        post = hw.r64(C.ASC_RVBAR)
    if post != rvbar:
        die("b", f"RVBAR readback {post:#x} != {rvbar:#x} — write not accepted")
    log("b", step="power-cycle", rvbar=hex(post), done=True)
    return rvbar


def step_c_map_selene(u, hw, fw_blob):
    """Map selene at the fw DVA on DART SID 0 (+ m1n1 ANE TTBR0 hack)."""
    log("c", step="dart-map", begin=True, size=len(fw_blob))
    if hw.dry:
        log("c", DRY=True, step="dart-map", done=True)
        return
    if hw.mock:
        log("c", DRY=True, fw_phys="guest", dva=hex(C.FW_DVA),
            step="dart-map", done=True)
        return
    from m1n1.hw.dart import DART
    with Bounded():
        dart = DART.from_adt(u, path=C.DART_PATH, instance=0,
                             iova_range=(C.VM_BASE, 0xfffffffff000))
        dart.initialize()
        # m1n1 ane.py base-TTBR hack: dart_regs 1/2 need TTBR0 set for DMA
        for prop in range(1, 3):
            addr = u.adt[C.DART_PATH].get_reg(prop)[0]
            dr = DART.from_adt(u, path=C.DART_PATH, instance=prop)
            dr.regs.TTBR[0, 0].val = dart.regs.TTBR[0, 0].val
            del dr
    phys = u.malloc(round_up(len(fw_blob), 0x4000))
    with Bounded():
        u.iface.writemem(phys, fw_blob)
    with Bounded():
        dart.iomap_at(C.DART_SID, C.FW_DVA, phys,
                      round_up(len(fw_blob), C.DART_PAGE_SIZE))
        dart.invalidate_streams(1 << C.DART_SID)
    log("c", fw_phys=hex(phys), dva=hex(C.FW_DVA), step="dart-map", done=True)


def step_d_run_poll(hw):
    log("d", step="cpu-run", begin=True)
    hw.w32(C.CPU_CONTROL, 0)               # kext: clear RUN first
    hw.r32(C.CPU_CONTROL)
    hw.w32(C.CPU_CONTROL, 0x10)            # RUN
    ok, last = poll("SCRATCH7-READY", lambda: hw.r32(C.SCRATCH7),
                    C.READY_MAGIC, C.POLL_A_MAX, C.POLL_INTERVAL, tag="kext Poll A")
    if not ok:
        with Bounded():
            ctl = hw.r32(C.CPU_CONTROL)
            status = hw.r32(C.CPU_STATUS)
        die("d", f"no READY: SCRATCH7={last:#x} CPUCTL={ctl:#x} CPU_STATUS={status:#x} "
                 f"(latched-RVBAR/silent-park signature if CPU_STATUS 0x28)")
    log("d", step="cpu-run", done=True)


def step_e_rtkit(u, hw):
    log("e", step="rtkit", begin=True)
    if hw.dry or hw.mock:
        log("e", DRY=hw.dry, step="rtkit", skipped="mock" if hw.mock else "dry", done=True)
        return
    from m1n1.fw.asc import StandardASC
    asc = StandardASC(u, C.ASC_BLOCK)
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if os.path.exists(ABORT):
            die("e", "abort file")
        with Bounded():
            asc.work()
        if asc.remote_eps:
            break
        time.sleep(0.01)
    log("e", eps=[hex(e) for e in sorted(asc.remote_eps)] if asc.remote_eps else "none")
    if not asc.remote_eps:
        # HELLO is answered by EP0 automatically; no EPMap yet -> report state
        with Bounded():
            s7 = hw.r32(C.SCRATCH7)
            ctl = hw.r32(C.CPU_CONTROL)
        die("e", f"no EPMap within 10 s: SCRATCH7={s7:#x} CPUCTL={ctl:#x}")
    asc.mgmt.ping()
    log("e", step="rtkit", handshake="HELLO/EPMap complete", done=True)


def round_up(x, y):
    return (x + y - 1) & ~(y - 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mock", action="store_true", help="dry-run against stub")
    ap.add_argument("--mock-latched-rvbar", action="store_true",
                    help="mock keeps the s23 latched RVBAR (negative path)")
    ap.add_argument("--dry-run", action="store_true",
                    help="real device, reads only")
    ap.add_argument("--fw", default=os.path.join(
        HERE, "..", "..", "tools", "ane-hunter", "fixtures",
        "t602x_ane0_fw_selene_rc4x.macho"))
    args = ap.parse_args()

    if os.path.exists(ABORT):
        die("init", f"abort file {ABORT} present")

    good, _ = C.validate()
    if not good:
        die("init", "constant validation failed")

    if args.mock:
        sys.path.insert(0, HERE)
        from mock_proxy import make_mock
        u = make_mock(C, mode_bits=not args.mock_latched_rvbar)
    else:
        u, _ = connect_real(args.dry_run)

    hw = HW(u, dry_run=args.dry_run, mock=args.mock)

    step_a_dump_adt(u)

    fw_blob = b""
    if not args.dry_run:
        try:
            fw_blob = open(args.fw, "rb").read()
            log("fw", path=args.fw, size=len(fw_blob))
        except OSError as e:
            die("init", f"selene not readable: {e}")

    step_b_power_rvbar(hw)
    step_c_map_selene(u, hw, fw_blob)
    step_d_run_poll(hw)
    if hw.dry or hw.mock:
        log("dry-run", RESULT="READS-ONLY DONE (no RUN written)")
        return
    step_e_rtkit(u, hw)
    log("done", RESULT="OK", next_step="TQ contract on running selene "
        "(.work/2026-09-21-t6021-host-tm-contract.md)")


if __name__ == "__main__":
    main()
