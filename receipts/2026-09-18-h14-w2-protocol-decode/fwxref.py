#!/usr/bin/env python3
"""Generic PIE xref for position-independent macho (selene fw): adrp/add resolver.

Usage: python3 fwxref.py <needle-string|addr-hex> [context]
Linear-disasms __TEXT.__text once, indexes adrp+add absolutizations, and dumps
code around references to the resolved target(s).
"""
import sys, re
sys.path.insert(0, '.')
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from disx import Macho


class FW:
    def __init__(self, path):
        self.m = Macho(path)
        self.name, self.taddr, self.tsz, self.tblob = \
            self.m.sec_by_name_full["__TEXT.__text"]
        self.adrp_targets = {}     # abs addr -> [pc,...]
        self.insns = {}            # pc -> (mnemonic, op_str)
        self.calls = {}            # call target -> [pc,...]
        self.branches = {}         # branch target -> [pc,...]
        self._scan()

    def _scan(self):
        md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        adrp = {}
        n = len(self.tblob) // 4
        pc = 0
        while pc < n:
            chunk = self.tblob[pc*4:(pc+64)*4]
            got = False
            for ins in md.disasm(chunk, self.taddr + pc*4):
                got = True
                mn, ops = ins.mnemonic, ins.op_str
                self.insns[ins.address] = (mn, ops)
                if mn == "adrp":
                    r, imm = ops.split(", ")
                    try:
                        adrp[r] = int(imm.lstrip('#'), 0)
                    except ValueError:
                        adrp.pop(r, None)
                elif mn == "add":
                    p = ops.replace("]", "").split(", ")
                    if len(p) == 3 and p[1] in adrp and p[2].startswith("#"):
                        try:
                            a = adrp[p[1]] + int(p[2].lstrip('#'), 0)
                        except ValueError:
                            continue
                        self.adrp_targets.setdefault(a, []).append(ins.address)
                elif mn == "bl":
                    try:
                        t = int(ops.lstrip('#'), 0)
                        self.calls.setdefault(t, []).append(ins.address)
                    except ValueError:
                        pass
                elif mn.startswith("b.") or mn in ("b", "cbz", "cbnz", "tbz", "tbnz"):
                    last = ops.split(", ")[-1]
                    try:
                        t = int(last.lstrip('#'), 0)
                        self.branches.setdefault(t, []).append(ins.address)
                    except ValueError:
                        pass
                pc = (ins.address - self.taddr) // 4 + 1
            if not got:
                pc += 1  # skip undecodable word, resync

    def string_addrs(self, needle):
        blob = self.m.cstrings
        out = []
        start = 0
        while True:
            i = blob.find(needle, start)
            if i < 0:
                break
            out.append(self.m.cstr_addr + i)
            start = i + 1
        return out

    def refs(self, addr):
        return self.adrp_targets.get(addr, [])

    def dis(self, start, count):
        out = []
        for pc in range(start, start + 4*count, 4):
            if pc in self.insns:
                mn, ops = self.insns[pc]
                ann = ""
                m2 = re.match(r"(\w+), (\w+)$", ops.replace("[", "").replace("]", "")) if mn in ("ldr",) else None
                out.append(f"{pc:#x}: {mn:<8s} {ops}")
            else:
                out.append(f"{pc:#x}: <.long>")
        return out

    def ctx(self, pc, before=24, after=48):
        lo = pc - 4*before
        lines = []
        for a in range(lo, pc + 4*after, 4):
            if a in self.insns:
                mn, ops = self.insns[a]
                mark = " >>" if a == pc else "   "
                lines.append(f"{mark} {a:#x}: {mn:<8s} {ops}")
            else:
                lines.append(f"    {a:#x}: <.long>")
        return "\n".join(lines)


if __name__ == "__main__":
    fw = FW(sys.argv[1])
    needle = sys.argv[2]
    before = int(sys.argv[3]) if len(sys.argv) > 3 else 24
    after = int(sys.argv[4]) if len(sys.argv) > 4 else 48
    if needle.startswith("0x"):
        addrs = [int(needle, 0)]
    else:
        addrs = fw.string_addrs(needle.encode())
        print(f"strings: {[hex(a) for a in addrs]}")
    for a in addrs:
        rs = fw.refs(a)
        print(f"refs to {a:#x}: {[hex(x) for x in rs]}")
        for pc in rs:
            print(fw.ctx(pc, before, after))
            print()
