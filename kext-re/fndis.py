#!/usr/bin/env python3
"""Function map + annotated disassembler for the AppleH11ANEInterface 9.512.0 slice."""
import sys, bisect, pickle
sys.path.insert(0, '/var/tmp/kext-re')
from kextmap import D, file_to_vm, vm_to_file, TEXT_EXEC
from parse_syms import load_syms

SYMS = load_syms('receipts/'
                 '2026-09-18-t6021-engine-layout-mined/w2/kext13.syms')

TEXT_TAGS = {0x40f, 0x40e}
# all text function starts (file offsets)
FN_FO = sorted({fo & ~3 for fo, t, n in SYMS if 0x48000 <= fo < 0x13c000 and t in TEXT_TAGS})
FN_VM = [file_to_vm(fo)[0] for fo in FN_FO]
FN_NAME = {file_to_vm(fo & ~3)[0]: n for fo, t, n in SYMS
           if 0x48000 <= fo < 0x13c000 and t in TEXT_TAGS}

# data symbols by tag (bytes[6:8]) — keep everything mappable
DATA_SYMS = {}
for fo, t, n in SYMS:
    vma, seg = file_to_vm(fo)
    if vma is not None:
        DATA_SYMS.setdefault(vma, n)

def fn_of(vma):
    i = bisect.bisect_right(FN_VM, vma) - 1
    return FN_VM[i] if i >= 0 else None

def fn_size(vma):
    i = bisect.bisect_right(FN_VM, vma) - 1
    if i < 0:
        return 0
    end = FN_VM[i+1] if i+1 < len(FN_VM) else file_to_vm(TEXT_EXEC[2] + TEXT_EXEC[1])[0]
    return end - FN_VM[i]

def demang(v):
    """light demangle: strip leading __Z, keep readable"""
    return v

_cache = {}
def disasm(vma, count=200, until=None):
    """Disassemble from vma; returns list of (addr, mnem, ops, raw_bytes)."""
    import capstone
    key = (vma, count)
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    fo, _ = vm_to_file(vma)
    code = D[fo:fo+count*4+64]
    out = []
    for insn in md.disasm(code, vma):
        out.append((insn.address, insn.mnemonic, insn.op_str, insn.bytes))
        if until and insn.address >= until:
            break
        if len(out) >= count:
            break
    return out

def show(vma, count=200, label=None, xrefmap=None):
    if label:
        print(f"=== {label} @ {hex(vma)} (fn {hex(fn_of(vma))} {FN_NAME.get(fn_of(vma),'')}) ===")
    prev_adrp = {}
    for a, m, o, b in disasm(vma, count):
        note = ''
        if m == 'adrp':
            try:
                reg, imm = o.split(', ')
                prev_adrp[reg] = int(imm, 0) & 0xFFFFFFFFFFFFFFFF
            except Exception:
                pass
        elif m == 'add' and '#' in o:
            parts = [p.strip() for p in o.split(',')]
            if len(parts) == 3 and parts[1] in prev_adrp and parts[2].startswith('#'):
                tgt = (prev_adrp[parts[1]] + int(parts[2][1:], 0)) & 0xFFFFFFFFFFFFFFFF
                nm = DATA_SYMS.get(tgt)
                if nm:
                    note = f"  ; {nm[:60]} @{hex(tgt)}"
                elif 0xfffffe000744c648 <= tgt < 0xfffffe00074826a9:
                    from kextmap import OSLOG
                    fo2 = tgt - OSLOG[0] + OSLOG[2]
                    s = D[fo2:fo2+64].split(b'\x00')[0][:70]
                    note = f'  ; oslog "{s.decode(errors="replace")}"'
                elif 0xfffffe00074826a9 <= tgt < 0xfffffe000748f630:
                    from kextmap import CSTRING
                    fo2 = tgt - CSTRING[0] + CSTRING[2]
                    s = D[fo2:fo2+64].split(b'\x00')[0][:70]
                    note = f'  ; cstr "{s.decode(errors="replace")}"'
        elif m in ('bl', 'b') and o.startswith('#'):
            try:
                tgt = (a + int(o[1:], 0)) & 0xFFFFFFFFFFFFFFFF
                nm = FN_NAME.get(tgt) or DATA_SYMS.get(tgt, '')
                note = f'  ; {nm[:80]}'
            except ValueError:
                pass
        print(f"{a:#x} {a-FN_VM[bisect.bisect_right(FN_VM,a)-1]:+#6x}" if FN_VM and FN_VM[0] <= a else f"{a:#x} ", end='')
        print(f"  {m:8s} {o:40s}{note}")

if __name__ == '__main__':
    print(f"functions: {len(FN_FO)}")
    pickle.dump({'FN_FO': FN_FO, 'FN_VM': FN_VM,
                 'FN_NAME': {hex(k): v for k, v in FN_NAME.items()}},
                open('/var/tmp/kext-re/fnmap.pkl', 'wb'))
