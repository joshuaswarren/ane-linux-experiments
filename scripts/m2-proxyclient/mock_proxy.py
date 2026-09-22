#!/usr/bin/env python3
"""Mock m1n1 ProxyUtils stub for dry-running ane_bringup.py.

Simulates the T6021 ANE ASC at the register level:
  - RVBAR starts latched at 0x10000000001 (the bad iBoot value); a write
    sticks only if mode bits 0x0081<<48 are present, else keeps the latch
    (mirrors s23 live behaviour so the script's readback check bites)
  - the ASC core "boots" (SCRATCH7 -> READY 0x08042006 after a few poll
    iterations) ONLY when RVBAR holds mode bits before RUN is set;
    with the latched value it parks at CPU_STATUS 0x28 / SCRATCH7 0
    (the silent-park signature)
  - on READY the mailbox answers HELLO / EPMap so step (e) completes

Run:  python3 ane_bringup.py --mock
"""
import time

ADT_NODES = {
    "/arm-io/ane": dict(compatible="ane,t8020",
                        regs=[(0x284000000, 0x2000000),
                              (0x28E004000, 0x4034),
                              (0x28E010000, 0x4000)]),
    "/arm-io/pmgr": dict(compatible="pmgr,t6021", regs=[(0x23B700000, 0x10000)]),
    "/arm-io/dart-ane0": dict(compatible="dart,t8110",
                              regs=[(0x285800000, 0x400000),
                                    (0x285810000, 0x400000),
                                    (0x285820000, 0x400000),
                                    (0x285804000, 0x400000)]),
}


class AdtNode:
    def __init__(self, info):
        self.compatible = info["compatible"]
        self._regs = info["regs"]

    def get_reg(self, i):
        return self._regs[i]


class Adt:
    def __getitem__(self, path):
        return AdtNode(ADT_NODES[path])


class MockProxy:
    def __init__(self, C, mode_bits=True):
        self.C = C
        self.mem = {}                       # addr -> word
        self.rvbar = 0x10000000001          # latched iBoot value
        self.accept_mode_bits = mode_bits   # False = write-ignore stays latched
        self.mode_ok = False
        self.run = False
        self.ready = False
        self.ready_at = None
        self.poll_reads = 0
        self.mailbox_out = []               # (msg0, msg1) waiting for host
        self.eps_mapped = False
        self.hello_done = False
        self.boot_delay_iters = 5           # READY after 5 poll reads

    # --- memory -----------------------------------------------------------
    def read32(self, a):
        a = self._canon(a)
        self._advance(a)
        if a == self.C.SCRATCH7:
            return 0x08042006 if self.ready else 0
        if a == self.C.ASC_CPU_STATUS:
            return 0x08 if (self.run and not self.ready) else (
                0x00 if self.ready else 0x28)  # STOPPED|idle after park
        if a == self.C.ASC_CPU_CONTROL:
            return 0x10 if self.run else 0
        return self.mem.get(a, 0)

    def read64(self, a):
        if a == self.C.ASC_RVBAR:
            return self.rvbar
        return self.mem.get(a, 0)

    def write32(self, a, v):
        a = self._canon(a)
        self.mem[a] = v
        if a == self.C.ASC_CPU_CONTROL:
            was = self.run
            self.run = bool(v & 0x10)
            if self.run and not was:
                # core leaves reset: fetch depends on RVBAR mode bits
                self.mode_ok = bool(self.rvbar & 0x0081000000000000)
                if self.mode_ok:
                    self.ready_at = self.poll_reads + self.boot_delay_iters
                    self._queue_rtkit()

    def write64(self, a, v):
        if a == self.C.ASC_RVBAR:
            # live write sticks ONLY with mode bits (else stays latched)
            if v & 0x0081000000000000 and self.accept_mode_bits:
                self.rvbar = v
            return
        self.mem[a] = v

    def _canon(self, a):
        if self.C.ASC_BLOCK <= a < self.C.ASC_BLOCK + 0x10000:
            return a
        return a

    def _advance(self, a):
        if a == self.C.SCRATCH7 and self.ready_at is not None \
                and not self.ready:
            self.poll_reads += 1
            if self.poll_reads >= self.ready_at:
                self.ready = True

    # --- rtkit mailbox (EP 0 mgmt) ----------------------------------------
    def _queue_rtkit(self):
        mgmt = self.C.ASC_BLOCK + 0x8800 + 0x30   # OUTBOX0
        ver = (16 << 16) | 16                      # HELLO max=min=16
        self.mailbox_out.append((1 | (ver << 12) | (0 << 52) | (1 << 52),
                                 0x00))            # EP 0, TYPE=1 HELLO
        self.mailbox_out.append(
            (8 | (1 << 51) | (0 << 32) | (0x21), 0x00))  # EPMap BASE0 LAST bitmap 0x21

    # pmgr ADT ops are no-ops in the mock (they exist on the real proxy)
    def pmgr_adt_power_enable(self, path):
        pass

    def pmgr_adt_power_disable(self, path):
        pass


class MockIface:
    def writemem(self, addr, data):
        pass


class MockUtils:
    def __init__(self, C, mode_bits=True):
        self.C = C
        self.proxy = MockProxy(C)
        self.iface = MockIface()
        self.adt = Adt()

    def malloc(self, size):
        return 0x100000000  # arbitrary guest phys


def make_mock(C, mode_bits=True):
    u = MockUtils.__new__(MockUtils)
    u.C = C
    u.proxy = MockProxy(C, mode_bits=mode_bits)
    u.iface = MockIface()
    u.adt = Adt()
    return u


if __name__ == "__main__":
    import t6021_consts
    u = make_mock(t6021_consts)
    print("mock ready; rvbar latched:", hex(u.proxy.rvbar))
