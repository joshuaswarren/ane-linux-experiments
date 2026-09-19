#!/usr/bin/env python3
"""W2 protocol decode engine: section/addr utilities + symbol-annotated arm64 disasm.

K14 kext nlist n_value encoding (cracked empirically, 4977/4977 text syms validate):
  __TEXT_EXEC.__text real = text_start + ((n_value >> 16) & 0xFFFFFF)
  __TEXT.__os_log  real = cstring_start + ((n_value >> 16) & 0xFFFFFF)
"""
import struct
import bisect
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN


class Macho:
    def __init__(self, path):
        self.path = path
        self.d = open(path, "rb").read()
        d = self.d
        ncmds = struct.unpack_from("<I", d, 16)[0]
        self.secs = []  # (name, addr, size, bytes)
        off = 32
        for _ in range(ncmds):
            cmd, cs = struct.unpack_from("<II", d, off)
            if cmd == 0x19:
                seg = d[off+8:off+24].rstrip(b"\0").decode()
                n = struct.unpack_from("<I", d, off+64)[0]
                so = off + 72
                for i in range(n):
                    sct = d[so:so+16].rstrip(b"\0").decode()
                    addr, size = struct.unpack_from("<QQ", d, so+32)
                    foff = struct.unpack_from("<I", d, so+48)[0]
                    if size:
                        self.secs.append((f"{seg}.{sct}", addr, size,
                                          d[foff:foff+size] if foff else b""))
                    so += 80
            off += cs
        self.sec_by_name = {s[0]: (s[1], s[2], s[3]) for s in self.secs}
        self.sec_by_name_full = {s[0]: s for s in self.secs}
        self.syms = []      # sorted (addr, name)
        self.sym_by_addr = {}
        self.sym_by_name = {}
        self._load_syms()
        self._load_cstrings()

    def _load_syms(self):
        d = self.d
        ncmds = struct.unpack_from("<I", d, 16)[0]
        off = 32
        symoff = nsyms = stroff = strsize = 0
        for _ in range(ncmds):
            cmd, cs = struct.unpack_from("<II", d, off)
            if cmd == 0x2:
                symoff, nsyms, stroff, strsize = struct.unpack_from("<IIII", d, off+8)
            off += cs
        if not symoff:
            return
        strs = d[stroff:stroff+strsize]
        text = self.sec_by_name.get("__TEXT_EXEC.__text")
        cstr = self.sec_by_name.get("__TEXT.__cstring")
        out = []
        for i in range(nsyms):
            n_strx, n_type, n_sect, n_desc, n_value = struct.unpack_from(
                "<IBBQQ", d, symoff + i*16)
            e = strs.find(b"\0", n_strx)
            nm = strs[n_strx:e].decode(errors="replace")
            if not nm or not n_value:
                continue
            payload = (n_value >> 16) & 0xFFFFFF
            addr = None
            if text and n_sect == 4:      # __TEXT_EXEC.__text (sect idx from header walk)
                addr = text[0] + (payload & ~3)  # low 2 bits are extraction noise
            elif cstr and n_sect == 2:    # __TEXT.__os_log
                addr = cstr[0] + payload
            if addr is None:
                out.append((n_value, nm))   # raw fallback
                continue
            out.append((addr, nm))
        out = sorted(set(out))
        self.syms = out
        self.sym_by_addr = dict(out)
        self._sym_addrs = [a for a, _ in out]
        for a, nm in out:
            self.sym_by_name.setdefault(nm, a)

    def _load_cstrings(self):
        name, addr, size, blob = next(
            s for s in self.secs if s[0] == "__TEXT.__cstring")
        self.cstr_addr, self.cstrings = addr, blob

    def cstr(self, a):
        if not (self.cstr_addr <= a < self.cstr_addr + len(self.cstrings)):
            return None
        i = a - self.cstr_addr
        e = self.cstrings.find(b"\0", i)
        return self.cstrings[i:e].decode(errors="replace")

    def addr_name(self, a):
        i = bisect.bisect_right(self._sym_addrs, a) - 1
        if i >= 0:
            base, nm = self.syms[i]
            if base == a:
                return nm
            if a - base < 0x10000:
                return f"{nm}+{a-base:#x}"
        return None

    def func_range(self, addr):
        """(start, end) of the function containing/starting at addr."""
        i = bisect.bisect_right(self._sym_addrs, addr) - 1
        if i < 0:
            raise KeyError(f"no symbol <= {addr:#x}")
        start, nm = self.syms[i]
        end = self.syms[i+1][0] if i + 1 < len(self.syms) else start + 0x2000
        return start, end, nm

    def text(self):
        return self.sec_by_name["__TEXT_EXEC.__text"]

    def read_at(self, addr, n):
        for name, a, sz, blob in self.secs:
            if a <= addr and addr + n <= a + sz and blob:
                return blob[addr-a:addr-a+n]
        return None

    def disasm(self, start, end=None):
        """Disasm [start, end) with symbol/string annotation."""
        if end is None:
            start, end, _ = self.func_range(start)
        name, taddr, tsz, tblob = self.sec_by_name_full["__TEXT_EXEC.__text"]
        assert taddr <= start < end <= taddr + tsz, f"{start:#x}-{end:#x} not in text"
        code = tblob[start-taddr:end-taddr]
        md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        md.detail = False
        lines = []
        adrp = {}
        for ins in md.disasm(code, start):
            ann = ""
            m = ins.mnemonic
            ops = ins.op_str
            if m == "adrp":
                r, imm = ops.split(", ")
                adrp[r] = int(imm.lstrip("#"), 0)
            elif m in ("add", "ldr", "ldrb", "str", "strb", "ldrsb"):
                parts = ops.replace("]", "").split(", ")
                if m == "add" and len(parts) == 3 and parts[1] in adrp and parts[2].startswith("#"):
                    a = adrp[parts[1]] + int(parts[2].lstrip("#"), 0)
                    s = self.cstr(a)
                    ann = f"  ; ={a:#x}" + (f' "{s[:64]}"' if s else f" <{self.addr_name(a) or 'data'}>")
                elif len(parts) >= 2 and parts[-1] in adrp and "[" in ins.op_str:
                    a = adrp[parts[-1]]
                    s = self.cstr(a)
                    ann = f"  ; ={a:#x}" + (f' "{s[:64]}"' if s else "")
            if m.startswith("b.") or m in ("b", "bl", "cbz", "cbnz", "tbz", "tbnz"):
                tgt = None
                if m in ("b", "bl") or m.startswith("b."):
                    try:
                        tgt = int(ops.lstrip("#"), 0)
                    except ValueError:
                        pass
                else:
                    last = ops.split(", ")[-1]
                    try:
                        tgt = int(last.lstrip("#"), 0)
                    except ValueError:
                        pass
                if tgt is not None:
                    n2 = self.addr_name(tgt)
                    if n2:
                        ann += f"  ; -> {n2}"
            lines.append(f"{ins.address:#x}: {ins.mnemonic:<10s} {ops}{ann}")
        return lines


if __name__ == "__main__":
    import sys
    m = Macho(sys.argv[1])
    a = int(sys.argv[2], 0)
    if len(sys.argv) > 3:
        end = int(sys.argv[3], 0)
    else:
        _, end, nm = m.func_range(a)
    print(f"; {m.addr_name(a)} [{a:#x}-{end:#x})")
    print("\n".join(m.disasm(a, end)))
