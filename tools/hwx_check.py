#!/usr/bin/env python3
# Offline replica of the Linux ane driver H16/H17 HWX load validator.
# Used to test tools/hwx_normalise output: a normalised container must PASS.
"""Offline port of the running kernel's H16/H17 HWX load validator.

Source of truth: drivers/accel/ane/ane_h16_hwx.c + ane_h16_tasks.h at
aurora commit ddd95a7af8fc2 (the tree the M5's 7.3.0-k114c-ARCH-a3m-daily2
was built from). Every check is labeled with the C site that produced it.
The script walks checks in the kernel's order and reports the first one
that fails, with the offending field and value.

Usage: hwx_check.py FILE.hwx [FILE2.hwx ...]
"""

import struct
import sys

SZ_16K = 16 * 1024
SZ_256M = 256 * 1024 * 1024
SZ_1M = 1024 * 1024
SZ_4K = 4096

ANE_H16_SURFACES = 4
ANE_H16_SECTIONS = 8
ANE_H16_REGIONS = 7
ANE_H16_HWX_MAX = SZ_256M + SZ_1M
ANE_HWX_SUBTYPE_H16 = 7
ANE_HWX_SUBTYPE_H17 = 9
HWX_COMMANDS_MAX = 64
HWX_SYMBOLS_MAX = 4096
HWX_SEGMENTS_MAX = 8
ANE_H16_TASK_MAX = 0x60000


class Rejected(Exception):
    def __init__(self, label, detail=""):
        super().__init__(f"{label}: {detail}" if detail else label)
        self.label = label
        self.detail = detail


def le32(b, off):
    return struct.unpack_from("<I", b, off)[0]


def le64(b, off):
    return struct.unpack_from("<Q", b, off)[0]


def fits(start, length, size):
    return start <= size and length <= size - start


def name_at(b, off, name):
    # hwx_name: NUL-padded 16-byte field compare
    n = len(name)
    return n < 16 and b[off:off + n] == name.encode() and b[off + n:off + 16] == b"\0" * (16 - n)


def zero(b, start, end):
    return b[start:end] == b"\0" * (end - start)


def range_add(ranges, max_count, start, size, what):
    if not size or len(ranges) == max_count:
        raise Rejected(f"segment vm ranges: {what} empty or range table full",
                       f"start=0x{start:x} size=0x{size:x} count={len(ranges)}")
    end = start + size
    for r_start, r_size in ranges:
        if start < r_start + r_size and r_start < end:
            raise Rejected(f"segment vm ranges: {what} overlaps an earlier segment",
                           f"start=0x{start:x} size=0x{size:x} prior=0x{r_start:x}+0x{r_size:x}")
    ranges.append((start, size))


REGISTER_BLOCKS = [
    (0x0000, 0x005C), (0x4100, 0x41A4), (0x44D0, 0x44D4),
    (0x4500, 0x453C), (0x4900, 0x4930), (0x4D00, 0x4E44),
    (0x5100, 0x5154), (0x5500, 0x5620), (0x5900, 0x5930),
]


def register_valid(word):
    addr = word * 4
    return any(start <= addr < end for start, end in REGISTER_BLOCKS)


class Section:
    def __init__(self):
        self.vm = self.size = 0
        self.offset = self.reloff = self.nreloc = 0
        self.ordinal = 0


class Surface:
    def __init__(self):
        self.allocation = self.direction = 0
        self.section = Section()
        self.name = ""
        self.symbol_offset = 0
        self.span = 0


class Info:
    def __init__(self):
        self.subtype = 0
        self.text = Section()
        self.constants = Section()
        self.kernel = Section()
        self.scratch = Section()
        self.surfaces = [Surface() for _ in range(ANE_H16_SURFACES)]
        self.surface_count = 0
        self.program_offset = 0
        self.tasks = 0
        self.regions = []


class Parser:
    def __init__(self, b):
        self.b = b
        self.size = len(b)
        self.command_end = 0
        self.info = Info()
        self.vm_ranges = []
        self.file_ranges = []
        self.sections = []
        self.tensors = []
        self.refs = []
        self.symoff = self.nsyms = self.stroff = self.strsize = 0
        self.guard = False
        self.symtab = False
        self.metadata = False


def file_add(p, start, size, what):
    if start < p.command_end or not fits(start, size, p.size):
        raise Rejected(f"file range: {what} outside payload after commands",
                       f"start=0x{start:x} size=0x{size:x} command_end=0x{p.command_end:x} size=0x{p.size:x}")
    range_add(p.file_ranges, HWX_SEGMENTS_MAX + 4, start, size, what)


def hwx_segment(p, c, length, cmd_pos):
    if length < 72:
        raise Rejected("segment: length < 72", f"len={length}")
    vm = le64(c, 24)
    size = le64(c, 32)
    file = le64(c, 40)
    filesz = le64(c, 48)
    prot = le32(c, 60)
    nsects = le32(c, 64)
    info = p.info
    range_add(p.vm_ranges, HWX_SEGMENTS_MAX, vm, size, f"segment at cmd 0x{cmd_pos:x}")
    text = name_at(c, 8, "__TEXT")
    kernel = name_at(c, 8, "__KERN_0")
    scratch = name_at(c, 8, "__DATA")
    surface = name_at(c, 8, "__FVMLIB")
    guard = name_at(c, 8, "__PAGEZERO")
    if not (text or kernel or scratch or surface or guard):
        raise Rejected("segment: unknown segment name",
                       f"name={c[8:24]!r}")
    if guard:
        if p.guard or vm or size != SZ_16K or file or filesz or prot or nsects:
            raise Rejected("segment: __PAGEZERO shape",
                           f"vm=0x{vm:x} size=0x{size:x} file=0x{file:x} filesz=0x{filesz:x} prot={prot} nsects={nsects} seen={p.guard}")
        if le32(c, 68) != 4:
            raise Rejected("segment: __PAGEZERO flags != 4", f"flags=0x{le32(c, 68):x}")
        p.guard = True
        return
    if surface or scratch:
        if file or filesz or vm % SZ_16K or size % SZ_16K or nsects != 1 or size > SZ_256M:
            raise Rejected(f"segment: {'surface' if surface else 'scratch'} shape",
                           f"vm=0x{vm:x} size=0x{size:x} file=0x{file:x} filesz=0x{filesz:x} nsects={nsects}")
    else:
        if not filesz or filesz > size or size > SZ_256M or vm % SZ_16K or file % SZ_16K:
            raise Rejected("segment: text/kernel vm/size/file shape",
                           f"vm=0x{vm:x} size=0x{size:x} file=0x{file:x} filesz=0x{filesz:x}")
        file_add(p, file, filesz, f"segment at cmd 0x{cmd_pos:x} file range")
    want_flags = (6 if surface else (4 if info.scratch.size else 0) if text else 4)
    if le32(c, 68) != want_flags:
        raise Rejected("segment: flags field at +68",
                       f"got=0x{le32(c, 68):x} want=0x{want_flags:x} name={c[8:16].decode(errors='replace')}")
    if (text and (prot != 5 or nsects != 2 or info.text.size)) or \
       (kernel and (prot != 1 or nsects != 1 or info.kernel.size)) or \
       (scratch and (prot != 3 or info.scratch.size)) or \
       (surface and (prot < 1 or prot > 2 or info.surface_count == ANE_H16_SURFACES)):
        raise Rejected("segment: prot/section-count/duplicate",
                       f"name={c[8:16].decode(errors='replace')} prot={prot} nsects={nsects}")

    for i in range(nsects):
        s_off = 72 + i * 80
        s = c
        sec = Section()
        sec.vm = le64(s, s_off + 32)
        sec.size = le64(s, s_off + 40)
        sec.offset = le32(s, s_off + 48)
        sec.reloff = le32(s, s_off + 56)
        sec.nreloc = le32(s, s_off + 60)
        sec.ordinal = len(p.sections) + 1
        alignment = le32(s, s_off + 52)
        task = text and name_at(s, s_off, "__text")
        sec_name = bytes(s[s_off:s_off + 16]).split(b"\0")[0].decode(errors="replace")
        if len(p.sections) == ANE_H16_SECTIONS or not sec.size or \
           s[s_off + 16:s_off + 32] != s[8:24] or alignment > 31 or \
           sec.vm % (1 << alignment) or sec.vm < vm or \
           not fits(sec.vm - vm, sec.size, size) or \
           not zero(s, s_off + 68, s_off + 80) or sec.reloff > p.size:
            raise Rejected(f"section {sec_name}: shape/alignment/zero tail",
                           f"vm=0x{sec.vm:x} size=0x{sec.size:x} align={alignment} seg_vm=0x{vm:x} seg_size=0x{size:x}")
        for a in p.sections:
            if sec.vm < a.vm + a.size and a.vm < sec.vm + sec.size:
                raise Rejected(f"section {sec_name}: vm overlap with section ordinal {a.ordinal}",
                               f"vm=0x{sec.vm:x}+0x{sec.size:x} other=0x{a.vm:x}+0x{a.size:x}")
        if surface or scratch:
            if sec.offset or sec.reloff or sec.nreloc or sec.vm != vm:
                raise Rejected(f"section {sec_name}: surface/scratch section fields",
                               f"offset=0x{sec.offset:x} reloff=0x{sec.reloff:x} nreloc={sec.nreloc} vm=0x{sec.vm:x} seg_vm=0x{vm:x}")
        else:
            if sec.offset < file or sec.offset % (1 << alignment) or \
               not fits(sec.offset - file, sec.size, filesz) or \
               sec.offset - file != sec.vm - vm:
                raise Rejected(f"section {sec_name}: file offset mapping",
                               f"offset=0x{sec.offset:x} file=0x{file:x} align={alignment} filesz=0x{filesz:x}")
        if sec.nreloc:
            if not task or sec.nreloc > ANE_H16_TASK_MAX // 4:
                raise Rejected(f"section {sec_name}: relocations on non-task or too many",
                               f"task={task} nreloc={sec.nreloc}")
            file_add(p, sec.reloff, sec.nreloc * 8, f"section {sec_name} reloc table")
        dest = None
        surface_ref = None
        if text:
            if task:
                dest = info.text
            elif name_at(s, s_off, "__const"):
                dest = info.constants
            else:
                raise Rejected(f"section {sec_name}: unknown __TEXT section", f"task={task}")
        elif kernel and name_at(s, s_off, "__kern_0"):
            dest = info.kernel
            if sec.vm % 64 or sec.size > SZ_256M:
                raise Rejected("section __kern_0: vm alignment or size",
                               f"vm=0x{sec.vm:x} size=0x{sec.size:x}")
        elif scratch and name_at(s, s_off, "__bss"):
            dest = info.scratch
        elif surface and name_at(s, s_off, "__const" if prot == 1 else "__data"):
            surface_ref = info.surfaces[info.surface_count]
            info.surface_count += 1
            surface_ref.allocation = size
            surface_ref.direction = prot
            dest = surface_ref.section
        else:
            raise Rejected(f"section {sec_name}: does not match any expected section",
                           f"seg={s[8:16].decode(errors='replace')} prot={prot}")
        want_type = (0x128 if sec.nreloc else 0x28) if task else \
                    ((0x21 if prot == 1 else 0x23) if surface else (0x25 if scratch else 0x26))
        if le32(s, s_off + 64) != want_type:
            raise Rejected(f"section {sec_name}: type field at +64",
                           f"got=0x{le32(s, s_off + 64):x} want=0x{want_type:x}")
        if dest.size:
            raise Rejected(f"section {sec_name}: duplicate destination section", f"size already set")
        dest.vm, dest.size, dest.offset, dest.reloff, dest.nreloc = \
            sec.vm, sec.size, sec.offset, sec.reloff, sec.nreloc
        dest.ordinal = sec.ordinal
        p.sections.append(sec)
        if surface_ref is not None:
            pass
    if len(info.regions) == ANE_H16_REGIONS:
        raise Rejected("segment: region table full", f"regions={len(info.regions)}")
    info.regions.append((vm, size, file, filesz, prot))


def hwx_program(p):
    info = p.info
    c = p.b
    base = info.program_offset
    length = le32(c, base + 4)
    prologue = 0 if info.subtype == ANE_HWX_SUBTYPE_H17 else 1
    mixed = length == 0x8C0
    if length != 0x8A0 and not mixed:
        raise Rejected("program: length", f"0x{length:x}")
    checks = [
        (f"+0xc == {'0x22a' if mixed else '0x222'}", le32(c, base + 0xC), 0x22A if mixed else 0x222),
        ("+0x820 == 4", le32(c, base + 0x820), 4),
        ("+0x838 == 0xffffffff", le32(c, base + 0x838), 0xFFFFFFFF),
        ("+0x83c == 0xffffffff", le32(c, base + 0x83C), 0xFFFFFFFF),
        ("+0x844 == 0xffff", le32(c, base + 0x844), 0xFFFF),
        (f"+0x848 == {'0x8b8' if mixed else '0x898'}", le32(c, base + 0x848), 0x8B8 if mixed else 0x898),
    ]
    for label, got, want in checks:
        if got != want:
            raise Rejected(f"program: {label}", f"got=0x{got:x} want=0x{want:x}")
    for label, got, want in [
        ("+0x10 == text.vm", le64(c, base + 0x10), info.text.vm),
        ("+0x810 == text.vm", le64(c, base + 0x810), info.text.vm),
        ("+0x20 == constants.vm", le64(c, base + 0x20), info.constants.vm),
    ]:
        if got != want:
            raise Rejected(f"program: {label}", f"got=0x{got:x} want=0x{want:x}")
    if le32(c, base + 0x824) * 4 != info.text.size:
        raise Rejected("program: +0x824 * 4 == text size",
                       f"got={le32(c, base + 0x824) * 4} want={info.text.size}")
    records = le32(c, base + 0x860)
    info.tasks = le32(c, base + 0x830)
    if mixed:
        usable = le32(c, base + 0x858)
        if not info.scratch.size or not usable or usable > info.scratch.size or \
           le64(c, base + 0x40) != info.scratch.vm or le32(c, base + 0x880) != usable:
            raise Rejected("program: mixed-mode scratch fields",
                           f"scratch_size=0x{info.scratch.size:x} usable={usable} +0x40=0x{le64(c, base + 0x40):x} +0x880={le32(c, base + 0x880)}")
    else:
        if info.scratch.size or le64(c, base + 0x40) or le32(c, base + 0x858):
            raise Rejected("program: plain-mode must have no scratch",
                           f"scratch=0x{info.scratch.size:x} +0x40=0x{le64(c, base + 0x40):x} +0x858=0x{le32(c, base + 0x858):x}")
    for i in range(5):
        if i < info.surface_count:
            want_base = info.regions[0][0]  # placeholder, recomputed below
        base_i = info.surfaces[i].section.vm if i < info.surface_count else \
            (info.kernel.vm if i == info.surface_count else 0)
        if le64(c, base + 0x70 + i * 16) != base_i or le64(c, base + 0x78 + i * 16):
            raise Rejected(f"program: base table slot {i}",
                           f"got=0x{le64(c, base + 0x70 + i * 16):x} want=0x{base_i:x} tail=0x{le64(c, base + 0x78 + i * 16):x}")
    work_limit = sum(info.surfaces[i].allocation for i in range(info.surface_count))
    work = le32(c, base + (0x8B0 if mixed else 0x890))
    if work > work_limit:
        raise Rejected("program: work hint exceeds surface allocation total",
                       f"hint={work} limit={work_limit}")
    # Exact trailer expectation (the memcmp in the kernel).
    expected = bytearray(length)
    common = [0, 4, 8, 0xC, 0x10, 0x14, 0x20, 0x24, 0x40, 0x44,
              0x810, 0x814, 0x820, 0x824, 0x830, 0x838, 0x83C,
              0x844, 0x848, 0x858, 0x860]
    for off in common:
        expected[off:off + 4] = c[base + off:base + off + 4]
    for i in range(5):
        expected[0x70 + i * 16:0x70 + i * 16 + 8] = c[base + 0x70 + i * 16:base + 0x70 + i * 16 + 8]
    struct.pack_into("<I", expected, 0x868, 4)
    struct.pack_into("<I", expected, 0x870, 4 if mixed else 2)
    struct.pack_into("<I", expected, 0x878, 2 if mixed else 7)
    struct.pack_into("<I", expected, 0x87C, 8)
    struct.pack_into("<I", expected, 0x880,
                     le32(c, base + 0x858) if mixed else 0x461C4000)
    struct.pack_into("<I", expected, 0x888, 3 if mixed else 9)
    struct.pack_into("<I", expected, 0x88C, 8)
    if mixed:
        struct.pack_into("<I", expected, 0x890, 0x08020004)
        struct.pack_into("<I", expected, 0x894, 8)
        struct.pack_into("<I", expected, 0x898, 7)
        struct.pack_into("<I", expected, 0x89C, 8)
        struct.pack_into("<I", expected, 0x8A0, 0x461C4000)
        struct.pack_into("<I", expected, 0x8A8, 9)
        struct.pack_into("<I", expected, 0x8AC, 8)
    w = 0x8B0 if mixed else 0x890
    expected[w:w + 4] = c[base + w:base + w + 4]
    n = 0x8B8 if mixed else 0x898
    expected[n:n + 5] = b"main\0"
    prog = c[base:base + length]
    if bytes(prog) != bytes(expected):
        for i in range(length):
            if prog[i] != expected[i]:
                raise Rejected("program: fixed trailer mismatch (memcmp)",
                               f"first differing byte at program+0x{i:x}: got=0x{prog[i]:02x} want=0x{expected[i]:02x}")
    limit, final_end = task_stream_validate_limit(
        c[info.text.offset:info.text.offset + info.text.size],
        info.text.size, info.tasks, prologue)
    if not records or records > limit:
        raise Rejected("program: record hint vs task stream limit",
                       f"records={records} limit={limit}")
    if info.subtype == ANE_HWX_SUBTYPE_H16 and final_end != info.text.size:
        raise Rejected("program: H16 final task must end the section",
                       f"final_end=0x{final_end:x} text_size=0x{info.text.size:x}")


def hwx_tensor_for(p, index, used):
    ref = p.refs[index]
    match = ANE_H16_SURFACES
    for i, tpos in enumerate(p.tensors):
        c = p.b
        length = le32(c, tpos + 4)
        shortoff = le32(c, tpos + 0x7C)
        if shortoff >= length:
            raise Rejected(f"tensor {i}: short-name offset >= length",
                           f"shortoff={shortoff} length={length}")
        room = min(length - shortoff, 8)
        # C: strnlen(c+shortoff, room) == room (no NUL inside the window) skips,
        # then strncmp(c+shortoff, ref+0x18, 8) != 0 skips.
        window = c[tpos + shortoff:tpos + shortoff + room]
        no_nul = b"\0" not in window
        s8 = bytes(c[tpos + shortoff:tpos + shortoff + 8])
        r8 = bytes(c[ref + 0x18:ref + 0x18 + 8])
        same = True
        for j in range(8):
            ca = s8[j] if j < len(s8) else 0
            cb = r8[j] if j < len(r8) else 0
            if ca != cb:
                same = False
                break
            if ca == 0:
                break
        if no_nul or not same:
            continue
        if match != ANE_H16_SURFACES or (used & (1 << i)):
            raise Rejected(f"tensor pairing: ambiguous match for ref {index}",
                           f"match={match} used=0x{used:x}")
        match = i
    if match == ANE_H16_SURFACES:
        raise Rejected(f"tensor pairing: no tensor matches ref {index}",
                       f"ref name bytes={bytes(c[ref + 0x18:ref + 0x20])!r}")
    return match


def hwx_tensor(p, index, tensor):
    info = p.info
    b = info.surfaces[index]
    c = p.b
    tpos = p.tensors[tensor]
    ref = p.refs[index]
    length = le32(c, tpos + 4)
    checks = [
        ("+0xc == 0x34a", le32(c, tpos + 0xC), 0x34A),
        ("+0x10 == 3", le32(c, tpos + 0x10), 3),
        ("+0x14 == surface direction", le32(c, tpos + 0x14), b.direction),
        ("+0x18 == 0xd38", le32(c, tpos + 0x18), 0xD38),
        ("+0x20 == 0xd3d", le32(c, tpos + 0x20), 0xD3D),
        ("+0x24 == 5", le32(c, tpos + 0x24), 5),
        ("+0x38 == 1", le32(c, tpos + 0x38), 1),
        ("+0x78 == 1", le32(c, tpos + 0x78), 1),
    ]
    for label, got, want in checks:
        if got != want:
            raise Rejected(f"tensor {tensor}: {label}", f"got=0x{got:x} want=0x{want:x}")
    if length < 0xD48 or length > SZ_4K * 4:
        raise Rejected(f"tensor {tensor}: length", f"0x{length:x}")
    if not zero(c, tpos + 0x1C, tpos + 0x20):
        raise Rejected(f"tensor {tensor}: +0x1c..0x20 not zero")
    if not zero(c, tpos + 0x3C, tpos + 0x50):
        raise Rejected(f"tensor {tensor}: +0x3c..0x50 not zero")
    if le64(c, tpos + 0x68) != 2:
        raise Rejected(f"tensor {tensor}: +0x68 != 2", f"got={le64(c, tpos + 0x68)}")
    if not zero(c, tpos + 0x88, tpos + 0xD38):
        raise Rejected(f"tensor {tensor}: +0x88..0xd38 not zero")
    if c[tpos + 0xD38:tpos + 0xD3D] != b"main\0":
        raise Rejected(f"tensor {tensor}: +0xd38 != 'main'",
                       f"got={bytes(c[tpos + 0xD38:tpos + 0xD3D])!r}")
    n = le32(c, tpos + 0x28)
    channels = le32(c, tpos + 0x2C)
    height = le32(c, tpos + 0x30)
    width = le32(c, tpos + 0x34)
    batch = le64(c, tpos + 0x50)
    plane = le64(c, tpos + 0x58)
    row = le64(c, tpos + 0x60)
    if not (n and channels and height and width):
        raise Rejected(f"tensor {tensor}: zero shape",
                       f"n={n} c={channels} h={height} w={width}")
    minimum = width * 2
    if row < minimum:
        raise Rejected(f"tensor {tensor}: row < 2*width", f"row={row} min={minimum}")
    minimum = height * row
    if plane < minimum:
        raise Rejected(f"tensor {tensor}: plane < height*row", f"plane={plane} min={minimum}")
    minimum = channels * plane
    if batch < minimum:
        raise Rejected(f"tensor {tensor}: batch < channels*plane", f"batch={batch} min={minimum}")
    if le64(c, tpos + 0x70) != batch or le64(c, tpos + 0x80) != batch:
        raise Rejected(f"tensor {tensor}: batch mirrors",
                       f"+0x70={le64(c, tpos + 0x70)} +0x80={le64(c, tpos + 0x80)} batch={batch}")
    b.span = n * batch
    if b.span > b.section.size:
        raise Rejected(f"tensor {tensor}: span exceeds section size",
                       f"span={b.span} section_size={b.section.size}")
    sym_len = c[tpos + 0xD3D:tpos + 0xD3D + min(256, length - 0xD3D)].find(b"\0")
    if sym_len <= 0 or sym_len == min(256, length - 0xD3D):
        raise Rejected(f"tensor {tensor}: symbol name", f"len={sym_len}")
    shortoff = le32(c, tpos + 0x7C)
    if shortoff != 0xD3D + sym_len + 1 or shortoff >= length:
        raise Rejected(f"tensor {tensor}: short-name offset placement",
                       f"shortoff={shortoff} want={0xD3D + sym_len + 1}")
    short_region = c[tpos + shortoff:tpos + length]
    short_len = short_region.find(b"\0")
    if short_len <= 0 or short_len == length - shortoff or short_len >= 8 or \
       not zero(c, tpos + shortoff + short_len + 1, tpos + length):
        raise Rejected(f"tensor {tensor}: short name", f"len={short_len}")
    b.name = c[tpos + shortoff:tpos + shortoff + short_len].decode()
    b.symbol_offset = tpos + 0xD3D
    if le64(c, ref + 8) != 0x18 or le64(c, ref + 0x10) != b.section.vm or \
       c[ref + 0x18:ref + 0x18 + 8] != b.name.encode().ljust(8, b"\0"):
        raise Rejected(f"tensor {tensor}: buffer reference fields",
                       f"+8=0x{le64(c, ref + 8):x} +0x10=0x{le64(c, ref + 0x10):x} want_vm=0x{b.section.vm:x} name={b.name!r}")
    for i in range(index):
        if b.name == info.surfaces[i].name or \
           c[b.symbol_offset:] .split(b"\0")[0] == c[info.surfaces[i].symbol_offset:].split(b"\0")[0]:
            raise Rejected(f"tensor {tensor}: duplicate name/symbol vs surface {i}",
                           f"name={b.name!r}")


def hwx_symbols(p):
    found = 0
    if not p.symtab or not p.nsyms or p.nsyms > HWX_SYMBOLS_MAX or \
       not p.strsize or p.strsize > SZ_4K * 64:
        raise Rejected("symbols: symtab shape",
                       f"symtab={p.symtab} nsyms={p.nsyms} strsize=0x{p.strsize:x}")
    file_add(p, p.symoff, p.nsyms * 16, "symbol table")
    file_add(p, p.stroff, p.strsize, "string table")
    if p.b[p.stroff]:
        raise Rejected("symbols: first string-table byte must be NUL",
                       f"got=0x{p.b[p.stroff]:02x}")
    names = []
    for i in range(p.nsyms):
        s = p.symoff + i * 16
        strx = le32(p.b, s)
        value = le64(p.b, s + 8)
        if strx >= p.strsize or not p.b[s + 5] or p.b[s + 5] > len(p.sections) or \
           (p.b[s + 4] & ~1) != 0xE:
            raise Rejected(f"symbol {i}: strx/section/type fields",
                           f"strx={strx} sect={p.b[s + 5]} type=0x{p.b[s + 4]:02x}")
        name = p.b[p.stroff + strx:p.stroff + p.strsize]
        nul = name.find(b"\0")
        if nul < 0 or nul == 0 or nul == min(256, p.strsize - strx):
            raise Rejected(f"symbol {i}: name not NUL-terminated in string table",
                           f"nul={nul}")
        name = name[:nul].decode(errors="replace")
        if name in names:
            raise Rejected(f"symbol {i}: duplicate name", f"name={name!r}")
        names.append(name)
        section = p.sections[p.b[s + 5] - 1]
        if value < section.vm or value - section.vm >= section.size:
            raise Rejected(f"symbol {i}: value outside its section",
                           f"value=0x{value:x} section_vm=0x{section.vm:x} section_size=0x{section.size:x}")
        for j in range(p.info.surface_count):
            b = p.info.surfaces[j]
            if name != b.name:
                continue
            if found & (1 << j) or p.b[s + 5] != b.section.ordinal or value != b.section.vm:
                raise Rejected(f"symbol {i}: surface symbol mismatch",
                               f"name={name!r} surface={j} sect={p.b[s + 5]} want={b.section.ordinal} value=0x{value:x} want_vm=0x{b.section.vm:x}")
            found |= 1 << j
    if found != (1 << p.info.surface_count) - 1:
        raise Rejected("symbols: not every surface has a symbol",
                       f"found=0x{found:x} want=0x{(1 << p.info.surface_count) - 1:x}")


def task_stream_validate_limit(text, size, expected_tasks, prologue):
    # ane_hx_task_stream_validate_limit
    if not expected_tasks or size < 16 or size > ANE_H16_TASK_MAX or (size & 3) or \
       le32(text, 0) != prologue or text[4:16] != b"\0" * 12:
        raise Rejected("task stream: frame header",
                       f"size=0x{size:x} prologue_word=0x{le32(text, 0):x} want={prologue}")
    pos, last, tasks, limit = 16, 0, 0, 0
    while pos < size:
        if size - pos < 16:
            raise Rejected("task stream: trailing bytes < 16", f"pos=0x{pos:x}")
        words = (le32(text, pos) >> 16) & 0x7FF
        if not words:
            if text[pos:pos + 16] != b"\0" * 16:
                raise Rejected("task stream: zero-words block not all zero", f"pos=0x{pos:x}")
            pos += 16
            continue
        if words < 9 or words > (size - pos) // 4:
            raise Rejected("task stream: word count",
                           f"words={words} pos=0x{pos:x} max={(size - pos) // 4}")
        end = pos + words * 4
        header_words = 9
        if (le32(text, pos + 8 * 4) & 3) == 3:
            header_words += 1
        if words < header_words:
            raise Rejected("task stream: words < header words",
                           f"words={words} header_words={header_words}")
        rec = pos + header_words * 4
        limit += (end - rec) // 8
        while rec < end:
            h = le32(text, rec)
            base = h & 0x7FFF
            mask = (h >> 15) & 0xFFFF
            rec += 4
            if h & (1 << 31):
                count = 1 + bin(mask).count("1")
            else:
                count = ((h >> 15) & 0x3F) + 1
            if count > (end - rec) // 4 or not register_valid(base):
                raise Rejected("task stream: record count or base register",
                               f"header=0x{h:08x} count={count} base=0x{base:x} (word 0x{base * 4:x})")
            if h & (1 << 31):
                for i in range(16):
                    if mask & (1 << i) and not register_valid(base + i + 1):
                        raise Rejected("task stream: mask register invalid",
                                       f"base=0x{base:x} +{i + 1} word 0x{(base + i + 1) * 4:x}")
            else:
                for i in range(1, count):
                    if not register_valid(base + i):
                        raise Rejected("task stream: sequential register invalid",
                                       f"base=0x{base:x} +{i} word 0x{(base + i) * 4:x}")
            rec += count * 4
        padded = end if end == size else (end + 15) // 16 * 16
        if padded > size or text[end:padded] != b"\0" * (padded - end):
            raise Rejected("task stream: padding not zero", f"end=0x{end:x} padded=0x{padded:x}")
        last = end
        pos = padded
        tasks += 1
        if tasks > expected_tasks:
            raise Rejected("task stream: more tasks than expected",
                           f"tasks={tasks} expected={expected_tasks}")
    if tasks != expected_tasks:
        raise Rejected("task stream: task count mismatch",
                       f"tasks={tasks} expected={expected_tasks}")
    return limit, last


def relocations_validate(text, text_size, relocs, count, ordinal, kernel_vm, kernel_size, seen_bits):
    if not count:
        return
    if not ordinal or ordinal > 0xFFFFFF or not kernel_size or \
       text_size > ANE_H16_TASK_MAX or (text_size & 3) or \
       count > text_size // 4 or seen_bits < text_size // 4:
        raise Rejected("relocations: shape",
                       f"count={count} ordinal={ordinal} kernel_size=0x{kernel_size:x} text_size=0x{text_size:x}")
    seen = set()
    for i in range(count):
        patch = le32(relocs, i * 8)
        info_w = le32(relocs, i * 8 + 4)
        if (patch & 3) or text_size < 4 or patch > text_size - 4 or \
           (info_w >> 24) != 7 or (info_w & 0xFFFFFF) != ordinal or (patch // 4) in seen:
            raise Rejected(f"relocation {i}: patch site or info word",
                           f"patch=0x{patch:x} info=0x{info_w:08x} ordinal={ordinal}")
        seen.add(patch // 4)
        addend = le32(text, patch)
        target = kernel_vm + addend
        if addend >= kernel_size or target >= kernel_vm + kernel_size:
            raise Rejected(f"relocation {i}: addend outside kernel section",
                           f"addend=0x{addend:x} kernel_size=0x{kernel_size:x}")


def relocations_in_payload(p):
    text = p.info.text.offset
    size = p.info.text.size
    pos = 16
    while pos < size:
        words = (le32(p.b, text + pos) >> 16) & 0x7FF
        if not words:
            pos += 16
            continue
        end = pos + words * 4
        record = pos + 9 * 4
        if (le32(p.b, text + pos + 8 * 4) & 3) == 3:
            record += 4
        while record < end:
            header = le32(p.b, text + record)
            if header & (1 << 31):
                count = 1 + bin((header >> 15) & 0xFFFF).count("1")
            else:
                count = 1 + ((header >> 15) & 0x3F)
            record += 4
            record += count * 4
        pos = (end + 15) // 16 * 16
    # The kernel clears payload bits from the bitmap and requires it empty;
    # here every relocation site must land strictly inside a record body.
    covered = set()
    pos = 16
    while pos < size:
        words = (le32(p.b, text + pos) >> 16) & 0x7FF
        if not words:
            pos += 16
            continue
        end = pos + words * 4
        record = pos + 9 * 4
        if (le32(p.b, text + pos + 8 * 4) & 3) == 3:
            record += 4
        while record < end:
            header = le32(p.b, text + record)
            if header & (1 << 31):
                count = 1 + bin((header >> 15) & 0xFFFF).count("1")
            else:
                count = 1 + ((header >> 15) & 0x3F)
            record += 4
            for w in range(record // 4, (record + count * 4) // 4):
                covered.add(w)
            record += count * 4
        pos = (end + 15) // 16 * 16
    return covered


def validate(path):
    with open(path, "rb") as f:
        b = f.read()
    p = Parser(b)
    size = len(b)
    c = b
    if size < 32 or size > ANE_H16_HWX_MAX:
        raise Rejected("header: file size", f"{size}")
    if le32(c, 0) != 0xBEEFFACE:
        raise Rejected("header: magic != 0xbeefface", f"0x{le32(c, 0):x}")
    if le32(c, 4) != 0x80:
        raise Rejected("header: +4 != 0x80", f"0x{le32(c, 4):x}")
    if le32(c, 8) not in (ANE_HWX_SUBTYPE_H16, ANE_HWX_SUBTYPE_H17):
        raise Rejected("header: subtype not 7 (H16) or 9 (H17)",
                       f"0x{le32(c, 8):x}")
    if le32(c, 12) != 2:
        raise Rejected("header: +12 != 2", f"{le32(c, 12)}")
    if le32(c, 24) != 0x200000:
        raise Rejected("header: +24 != 0x200000", f"0x{le32(c, 24):x}")
    if le32(c, 28):
        raise Rejected("header: +28 != 0", f"0x{le32(c, 28):x}")
    count = le32(c, 16)
    length = le32(c, 20)
    if not count or count > HWX_COMMANDS_MAX or not fits(32, length, size):
        raise Rejected("header: command count/length",
                       f"count={count} length=0x{length:x} size=0x{size:x}")
    p.command_end = 32 + length
    p.info.subtype = le32(c, 8)
    pos = 32
    for i in range(count):
        if not fits(pos, 8, p.command_end):
            raise Rejected(f"command {i}: header past command area", f"pos=0x{pos:x}")
        cmd = le32(c, pos)
        ln = le32(c, pos + 4)
        if ln < 8 or (ln & 7) or not fits(pos, ln, p.command_end):
            raise Rejected(f"command {i}: length",
                           f"cmd=0x{cmd:x} len=0x{ln:x} command_end=0x{p.command_end:x}")
        if cmd == 0x19:
            hwx_segment(p, c[pos:pos + ln], ln, pos)
        elif cmd == 2:
            if p.symtab or ln != 24:
                raise Rejected(f"command {i}: LC_SYMTAB duplicate or length",
                               f"len={ln} seen={p.symtab}")
            p.symtab = True
            p.symoff = le32(c, pos + 8)
            p.nsyms = le32(c, pos + 12)
            p.stroff = le32(c, pos + 16)
            p.strsize = le32(c, pos + 20)
        elif cmd == 4:
            if ln < 16:
                raise Rejected(f"command {i}: LC_SEGMENT_64 too short", f"len={ln}")
            kind = le32(c, pos + 8)
            if kind == 3:
                if len(p.tensors) == ANE_H16_SURFACES or ln < 0xD48:
                    raise Rejected(f"command {i}: tensor descriptor",
                                   f"len=0x{ln:x} count={len(p.tensors)}")
                p.tensors.append(pos)
            elif kind == 4:
                if p.info.program_offset or (ln != 0x8A0 and ln != 0x8C0):
                    raise Rejected(f"command {i}: program command duplicate or length",
                                   f"len=0x{ln:x} seen={bool(p.info.program_offset)}")
                p.info.program_offset = pos
            else:
                raise Rejected(f"command {i}: unknown LC_SEGMENT_64 kind", f"kind={kind}")
        elif cmd == 0x40:
            if ln != 32 or len(p.refs) == ANE_H16_SURFACES:
                raise Rejected(f"command {i}: buffer reference",
                               f"len={ln} count={len(p.refs)}")
            p.refs.append(pos)
        elif cmd == 8:
            if p.metadata or ln > SZ_4K or ln == 8:
                raise Rejected(f"command {i}: annotation duplicate or length", f"len={ln}")
            ann = c[pos + 8:pos + ln].find(b"\0")
            if ann < 0:
                raise Rejected(f"command {i}: annotation not NUL-terminated",
                               f"len={ln}")
            if ann == ln - 8 or c[pos + 8 + ann:pos + ln] != b"\0" * (ln - 8 - ann):
                raise Rejected(f"command {i}: annotation padding", f"ann={ann} len={ln}")
            p.metadata = True
        else:
            raise Rejected(f"command {i}: unknown opcode", f"cmd=0x{cmd:x} len=0x{ln:x}")
        pos += ln
    if pos != p.command_end:
        raise Rejected("command walk: end mismatch",
                       f"pos=0x{pos:x} command_end=0x{p.command_end:x}")
    if not p.guard:
        raise Rejected("structure: no __PAGEZERO segment")
    if not p.info.program_offset:
        raise Rejected("structure: no program command")
    if not p.info.text.size:
        raise Rejected("structure: no __text section")
    if not p.info.constants.size:
        raise Rejected("structure: no __const section")
    if p.info.surface_count < 2:
        raise Rejected("structure: fewer than 2 surfaces", f"{p.info.surface_count}")
    if len(p.refs) != p.info.surface_count:
        raise Rejected("structure: buffer refs != surfaces",
                       f"refs={len(p.refs)} surfaces={p.info.surface_count}")
    if len(p.tensors) != p.info.surface_count:
        raise Rejected("structure: tensors != surfaces",
                       f"tensors={len(p.tensors)} surfaces={p.info.surface_count}")
    outputs = 0
    used = 0
    for i in range(p.info.surface_count):
        outputs += 1 if p.info.surfaces[i].direction == 2 else 0
        used_bit = hwx_tensor_for(p, i, used)
        used |= 1 << used_bit
        hwx_tensor(p, i, used_bit)
    if outputs != 1:
        raise Rejected("structure: exactly one output surface", f"outputs={outputs}")
    hwx_program(p)
    hwx_symbols(p)
    text = p.info.text
    covered = set()
    if text.nreloc:
        relocs = p.b[text.reloff:]
        relocations_validate(p.b[text.offset:text.offset + text.size], text.size,
                             relocs, text.nreloc, p.info.text.ordinal,
                             p.info.kernel.vm, p.info.kernel.size, text.size // 4)
        covered = relocations_in_payload(p)
        for i in range(text.nreloc):
            patch = le32(p.b, text.reloff + i * 8)
            if patch // 4 not in covered:
                raise Rejected(f"relocation {i}: site not inside a task record payload",
                               f"patch=0x{patch:x} word={patch // 4}")
    return p.info


def main(paths=None):
    if paths is None:
        paths = sys.argv[1:]
    if not paths:
        print("usage: hwx_check.py FILE.hwx [...]", file=sys.stderr)
        return 2
    failures = 0
    for path in paths:
        try:
            info = validate(path)
            subtype = "H17" if info.subtype == ANE_HWX_SUBTYPE_H17 else "H16"
            print(f"PASS {path}: subtype={subtype} tasks={info.tasks} "
                  f"surfaces={info.surface_count} text=0x{info.text.size:x} "
                  f"regions={len(info.regions)}")
        except Rejected as r:
            failures += 1
            print(f"FAIL {path}: first failing check -> {r.label}"
                  + (f" [{r.detail}]" if r.detail else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
