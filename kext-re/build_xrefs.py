#!/usr/bin/env python3
"""Index every ADRP/ADD and ADRP/LDR literal-computed pointer in __TEXT_EXEC."""
import sys, struct, bisect
sys.path.insert(0, '/var/tmp/kext-re')
from kextmap import D, TEXT_EXEC, vm_to_file
import capstone

addr0, size, fo = TEXT_EXEC
code = D[fo:fo+size]
md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
md.detail = True

insns = []           # (vma, mnemonic, opstr, id)
adrp = {}            # vma -> page base computed by ADRP
xrefs = {}           # target_vma -> list of insn vma

for insn in md.disasm(code, addr0):
    insns.append((insn.address, insn.mnemonic, insn.op_str, insn))
    if insn.mnemonic == 'adrp':
        try:
            reg = insn.operands[0].reg
            imm = insn.operands[1].imm
            adrp[insn.address] = (reg, imm)
        except Exception:
            pass

# join ADRP + next-instruction ADD/LDR

for idx in range(len(insns)-1):
    vma, mnem, ops, insn = insns[idx]
    if mnem != 'adrp':
        continue
    reg, page = adrp[vma]
    nvma, nmnem, nops, ninsn = insns[idx+1]
    tgt = None
    if nmnem == 'add' and ninsn.operands and ninsn.operands[0].type == 1:
        o = ninsn.operands
        if len(o) >= 3 and o[1].type == 1 and ninsn.reg_name(o[1].reg) == insn.reg_name(reg) and o[2].type == 2:
            tgt = page + o[2].imm
    elif nmnem in ('ldr',) and ninsn.operands and ninsn.operands[1].type == 3:
        m = ninsn.operands[1].mem
        if ninsn.reg_name(m.base) == insn.reg_name(reg):
            tgt = page + m.disp
    if tgt is not None:
        xrefs.setdefault(tgt, []).append(nvma)

import pickle
pickle.dump({'xrefs': xrefs, 'adrp': adrp}, open('/var/tmp/kext-re/xrefs.pkl', 'wb'))
print(f"disassembled {len(insns)} insns, {len(xrefs)} pointer targets")
