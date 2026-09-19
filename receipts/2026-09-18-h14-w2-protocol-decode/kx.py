#!/usr/bin/env python3
"""Kext-wide adrp/add + bl index for string-anchored function discovery."""
import sys, re
sys.path.insert(0, '.')
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from disx import Macho


class KX:
    def __init__(self, path):
        self.m = Macho(path)
        self.tname, self.taddr, self.tsz, self.tblob = \
            self.m.sec_by_name_full["__TEXT_EXEC.__text"]
        self.adrp_targets = {}
        self.insns = {}
        self.calls = {}
        self._scan()

    def _scan(self):
        md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        adrp = {}
        pc = 0
        n = len(self.tblob) // 4
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
                pc = (ins.address - self.taddr) // 4 + 1
            if not got:
                pc += 1

    def refs(self, addr):
        return self.adrp_targets.get(addr, [])

    def string_addrs(self, needle, exact=False):
        blob = self.m.cstrings
        out = []
        start = 0
        ne = needle.encode()
        while True:
            i = blob.find(ne, start)
            if i < 0:
                break
            j = blob.rfind(b"\0", 0, i) + 1     # containing string start
            s = self.m.cstr_addr + j
            if exact and blob[j:blob.find(b"\0", j)] != ne:
                start = i + 1
                continue
            if s not in out:
                out.append(s)
            start = i + 1
        return out

    def show(self, needle, before=40, after=60, exact=False, limit=4):
        addrs = self.string_addrs(needle, exact)
        print(f"'{needle}' strings: {[hex(a) for a in addrs]}")
        for a in addrs:
            rs = self.refs(a)
            print(f"refs to {a:#x}: {[hex(x) for x in rs[:limit*4]]}")
            for pc in rs[:limit]:
                lo = pc - 4*before
                for ad in range(lo, pc + 4*after, 4):
                    if ad in self.insns:
                        mn, ops = self.insns[ad]
                        mark = " >>" if ad == pc else "   "
                        ann = ""
                        if mn in ("bl", "b") and ops.startswith("#"):
                            try:
                                t = int(ops.lstrip('#'), 0)
                                n2 = self.m.addr_name(t)
                                if n2:
                                    ann = f"  ; {n2}"
                            except ValueError:
                                pass
                        s = self.m.cstr(ad)
                        print(f"{mark} {ad:#x}: {mn:<8s} {ops}{ann}")
                    else:
                        print(f"    {ad:#x}: <.long>")
                print()


if __name__ == "__main__":
    k = KX(sys.argv[1])
    k.show(sys.argv[2], exact=("--exact" in sys.argv))
