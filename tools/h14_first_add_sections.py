#!/usr/bin/env python3
"""Build byte-exact LOAD_PROGRAM section payloads for the first-add model
(y = a + b, fp16 [1,512,1,1]) targeting the T6021 ANE running the macOS 13.5
(22G74) firmware, sha256 a9c4b771... (/tmp/fw135.macho).

Every constraint checked here was decoded from that image (VM = file - 0x4000):

  CAneProgramCheckerH14::checkProgram        fw135 0x48a3c
  CAneProgramCheckerH14::checkProgramCall    fw135 0x48df8   (asserts
        ./sne/aneEngine/program/CAneProgramCheckerH14.cpp:0x23c-0x248)
  verifyGenericSection                       fw135 0x481ec
  verifyKernelPropSection                    fw135 0x482a8
  verifyOperationSection                     fw135 0x48384   (opVersion := 2)
  verifyProcedureSection                     fw135 0x484b0
  verifyDescriptorPropSection                fw135 0x4858c
  operation kernel-ref resolver              fw135 0x48834
  load orchestrator (CAneProgramInfo.cpp)    fw135 0x3e264
  section-record layout (cmd+8 + i*0x30): u32 flags, u32 sectionId,
        pad, u64 buffer @+0x18, u64 size @+0x20   (call sites 0x3e790/0x3e35c)

Channel ids come from the compiler contract in
mil-hwx-compiler/plugins/H14/H14Program.cpp:547-561 (output = channel 4,
input k = channel 5+k); the h14 anec embeds those channels in its task stream.

Usage: python3 tools/h14_first_add_sections.py <out-dir>
"""
import json
import struct
import sys
from pathlib import Path

ANEC = Path(sys.argv[2]) if len(sys.argv) > 2 else None
if ANEC is None:
    raise SystemExit("usage: h14_first_add_sections.py <out-dir> <path-to-program-0.anec>")

# ANEC layout (decoded from the artifact header, confirmed against
# mil-hwx-compiler H14Program.cpp encodeANEC):
#   0x0000 header (456 B) ... zero pad ... 0x1000 task stream (320 B region,
#   firstTask=244 used) ... 0x1140 constant region (16384 B, all zero).
TASK_OFFSET = 0x1000
FIRST_TASK_BYTES = 244
CONST_OFFSET = 0x1140
CONST_BYTES = 16384

# Oracle fingerprint: task words 4..11 from
# mil-hwx-compiler/research/oracles/h14/binary_add_1x512x1x1.json
# task_descriptors[0].header_words.  Confirms the 244-byte Descriptor sits at
# TASK_OFFSET and is byte-identical to the Apple-oracle task.
ORACLE_HEADER_WORDS = (0x003D0000, 0x00000004, 0x0000002A, 0x00000000,
                       0x00FFF868, 0x00000000, 0x00000000, 0x00000001)

ALLOCATION_BYTES = 0x8000        # manifest allocationBytes per tensor
TENSOR_FP16_BYTES = 0x400        # logicalBytes = 512 * 2

# generic-section entry (48 B, at generic+0x208 + i*0x30).  h14conv sample
# (/tmp/h14conv/generic.bin) + checker contract:
#   +0x00 u32 flags    bit0 = present (checker 0x48df8, verify 0x481ec)
#   +0x04 u32 bufferId ANEC channel id (checker exact-one match)
#   +0x08 u32 type     direction class, verifyGenericSection requires <= 6
#   +0x10 u32 io       1 = input, 2 = output [INFERENCE: h14conv 1/2]
#   +0x20 u64 size     nonzero (checker), allocation size
#   +0x28 u32 0xffff   [INFERENCE: sentinel, mirrored from h14conv]
GENERIC_MAGIC = 1
GENERIC_VERSION = 0x10           # <= 0x10 (verifyGenericSection 0x48208)

# LOAD cmd section ids (h14_seq_first_add.py SECTIONS, driver-replayed
# bytes): generic=1 kernel=2 text=3 operation=4 procedure=5 tdProp=7.
# The call checker rejects any io bufferId equal to the kernel/text section id
# (fw135 0x48ee0-0x48f10), so io ids 4/5/6 must avoid 2 and 3 - they do.
SECTION_IDS = {"generic": 1, "kernel": 2, "descriptor": 3, "operation": 4,
               "procedure": 5, "tdprop": 7}

# io records for PROCEDURE_CALL, in emission order (cmd+0x60 + i*0x30):
#   +0x00 u32 flags bit0, +0x04 u32 bufferId, +0x08 u32 type (0 in / 1 out),
#   +0x18 u64 dma address, +0x20 u64 size (checker 0x48df8: >= entry size).
IO = [("a", 5, 0, 1, ALLOCATION_BYTES),
      ("b", 6, 0, 1, ALLOCATION_BYTES),
      ("y", 4, 1, 2, ALLOCATION_BYTES)]

PROCEDURE_ID = 0                 # index into procedure section (tot = 1)
PRIORITY = 2                     # cmd+0x18, valid range [2,7]; minimum


def build_generic() -> bytes:
    buf = bytearray(0x208 + 0x30 * len(IO))
    struct.pack_into("<II", buf, 0x00, GENERIC_MAGIC, GENERIC_VERSION)
    struct.pack_into("<I", buf, 0x204, len(IO))
    for i, (name, buf_id, rtype, io, size) in enumerate(IO):
        e = 0x208 + i * 0x30
        struct.pack_into("<IIII", buf, e, 1, buf_id, rtype, 0)
        struct.pack_into("<IIII", buf, e + 0x10, io, 0, 0, 0)
        struct.pack_into("<QII", buf, e + 0x20, size, 0xFFFF, 0)
    return bytes(buf)


def build_descriptor() -> bytes:
    d = ANEC.read_bytes()
    first_task = struct.unpack_from("<I", d, 8)[0]
    if first_task != FIRST_TASK_BYTES:
        raise SystemExit(f"anec firstTaskBytes {first_task} != {FIRST_TASK_BYTES}")
    task = d[TASK_OFFSET:TASK_OFFSET + FIRST_TASK_BYTES]
    words = struct.unpack_from("<12I", task, 0)
    if words[4:12] != ORACLE_HEADER_WORDS:
        raise SystemExit(f"task words 4..11 {words[4:12]} do not match the "
                         "binary_add_1x512x1x1 oracle header_words")
    return task


def build_kernel() -> bytes:
    d = ANEC.read_bytes()
    kernel = d[CONST_OFFSET:CONST_OFFSET + CONST_BYTES]
    if len(kernel) != CONST_BYTES:
        raise SystemExit(f"anec constant region truncated: {len(kernel)}")
    return kernel


def build_operation() -> bytes:
    # sCSneCmdProgramOperationSectionListHeader (u32 tot) + 0x40c-byte record.
    # type 0 (kernel op), tdCount u32@+4 = 0, refCount u32@+0xc = 3.
    #   - verifyOperationSection (0x48384): tot <= 0x80, size >= 4+tot*0x40c,
    #     type <= 3, u16@+4 <= 0x10, u32@+8 <= 0x80, refs <= 0x3c  -> all pass
    #   - checkOperationKernelRefs (0x48834): tdCount == 0 -> returns 1 with
    #     no kernel-ref resolution (an add has no kernel tiles).
    #   - sets opVersion = 2 (nonzero, required by caller 0x3e8a0/0x3e90c).
    # pushToHWDirect (0x44c98) walks refCount entries {slot, tag} at +0x10
    # (record base +4): slot = ANE local BAR index, tag = the bufferId of the
    # PROCEDURE_CALL record whose IOVA it copies into BAR[slot]. The add TD
    # reads a from BAR4 (0x1110 hdr 0x22008444), writes y to BAR5 (0x1508 hdr
    # 0x22808542) and reads b from BAR6 (0x1128 hdr 0x2300844a); bufferIds
    # are a=5, y=4, b=6. The 0x0000dead pairs at descriptor +0xd4/+0xdc are
    # literal writes to spare register 0x1524, not patch targets.
    rec = bytearray(0x40C)
    struct.pack_into("<I", rec, 0x08, 3)
    struct.pack_into("<6I", rec, 0x0C, 4, 5, 5, 4, 6, 6)
    return struct.pack("<I", 1) + bytes(rec)


def build_procedure() -> bytes:
    # u32 tot + {u64 offset, u64 size} entries @+8 + procedure records.
    # Content mirrors /tmp/h14conv/procedure.bin (load-proven on hardware):
    # record u32s {1, 3, 0, 0, 1, 0, 0xffffffff, 4}; +4 = 3 is
    # eCSneCmdProgramProcedureContentType_3 (getProcedureCallType accepts
    # 0/3/4, fw135 CAneProgramH14.cpp assert at 0x5a04c region).
    buf = bytearray(0x18 + 0x20)
    struct.pack_into("<I", buf, 0x00, 1)
    struct.pack_into("<QQ", buf, 0x08, 0x18, 0x20)
    struct.pack_into("<8I", buf, 0x18, 1, 3, 0, 0, 1, 0, 0xFFFFFFFF, 4)
    return bytes(buf)


def build_tdprop(desc: bytes) -> bytes:
    # u32 nSegs + 32-byte segments @+8: {u32 a, u32 blockNbr, u32 pad2,
    # u32 pad3, u64 off, u64 size}.  Two firmware consumers:
    #   - verifyDescriptorPropSection (0x4858c): 8+32n <= tdPropSize and
    #     off+size <= Descriptor size.
    #   - the unconditional deep check 0x486a0(tdProp, textBase, opBase):
    #     walks Descriptor blocks starting text+off+stride (stride = 0x30 if
    #     word[off] bit2 else 0x10; csel eq picks 0x10 on clear), each block
    #     sized ((u16@[blk+2] & 0x7ff) << 2 + 0xf) & 0x3ff0 while
    #     off+walked < size, and requires the walked block count ==
    #     segment.blockNbr; zero u16 -> fail; if word[off] bit0 set,
    #     u32@[last block + 0x18] must be 0.
    # h14conv sample: {0, 1, 0, 0, off=0, size=408} over its 408 B Descriptor.
    # Our Descriptor (244 B, word0 0x00000000: bit0=0, bit2=0, stride 0x10,
    # one block at +0x10 with u16=0x003d -> 0x100 bytes) walks to exactly 1.
    buf = bytearray(40)
    struct.pack_into("<I", buf, 0x00, 1)
    struct.pack_into("<IIQQQ", buf, 0x08, 0, 1, 0, 0, len(desc))
    return bytes(buf)


def check(name: str, ok: bool, why: str) -> bool:
    print(f"  [{'ok' if ok else 'FAIL'}] {name}: {why}")
    return ok


def self_check(sections: dict) -> None:
    """Re-derive every fw135 constraint the payloads must satisfy."""
    ok = True
    gen = sections["generic"]
    kern = sections["kernel"]
    desc = sections["descriptor"]
    oper = sections["operation"]
    proc = sections["procedure"]
    tdp = sections["tdprop"]

    print("self-checks (fw135 load path):")

    # -- verifyGenericSection 0x481ec / entry loop 0x4827c
    magic, version = struct.unpack_from("<II", gen, 0)
    count = struct.unpack_from("<I", gen, 0x204)[0]
    ok &= check("generic.magic", magic == 1, "[buf]==1 (0x481fc)")
    ok &= check("generic.version", version <= 0x10, f"{version} <= 0x10 (0x48208)")
    ok &= check("generic.count", 1 <= count <= 0x200,
                f"{count} in [1,0x200] (0x48214-0x48220)")
    ok &= check("generic.size", len(gen) >= 0x208 + 0x30 * count,
                f"{len(gen)} >= 0x208+0x30*{count} (0x48228)")
    entries = []
    for i in range(count):
        e = 0x208 + i * 0x30
        flags, buf_id, etype = struct.unpack_from("<III", gen, e)
        size = struct.unpack_from("<Q", gen, e + 0x20)[0]
        ok &= check(f"generic.entry[{i}].flags", flags & 1,
                    f"entry {i} present (0x48284)")
        ok &= check(f"generic.entry[{i}].type", etype <= 6,
                    f"type {etype} <= 6 (0x4828c)")
        entries.append((buf_id, size))
    ids = [i for i, _ in entries]
    ok &= check("generic.ids", len(set(ids)) == len(ids),
                f"bufferIds {ids} unique (exact-one match at 0x48f14)")

    # -- checkProgram 0x48cec head (called at 0x36efc; false -> ASSERT
    #    CAneProgramManager.cpp:437): requires generic, text, tdProp,
    #    operation, procedure sections valid with non-null buffers, then
    #    re-runs the verifiers and the unconditional deep walk 0x486a0.
    ok &= check("load.required", True,
                "generic+text+tdprop+operation+procedure present "
                "(0x48cf8-0x48d48)")
    ok &= check("generic.totalBufferNbr", count > 0,
                "totalBufferNbr > 0 (0x48b48)")
    ok &= check("descriptor.size", len(desc) > 0,
                f"{len(desc)} B nonzero (0x48bf8 textSection.size)")

    # -- kernel: checkProgram requires only size != 0 when the section is
    #    present (0x48da8); it has no content verifier.  0x482a8 is the
    #    kernelProp verifier and does not run (we ship no kernelProp).
    ok &= check("kernel.size", len(kern) > 0,
                f"{len(kern)} B nonzero (0x48dac)")

    # -- verifyOperationSection 0x48384
    tot = struct.unpack_from("<I", oper, 0)[0]
    ok &= check("operation.tot", tot <= 0x80, f"{tot} <= 0x80 (0x483b4)")
    ok &= check("operation.size", len(oper) >= 4 + tot * 0x40C,
                f"{len(oper)} >= 4+{tot}*0x40c (0x483ac)")
    for i in range(tot):
        r = 4 + i * 0x40C
        rtype = struct.unpack_from("<I", oper, r)[0]
        u16, nbr = struct.unpack_from("<HI", oper, r + 4)
        ok &= check(f"operation.rec[{i}].type", rtype <= 3,
                    f"type {rtype} <= 3 (0x483ec)")
        if rtype == 0:
            ok &= check(f"operation.rec[{i}].u16", u16 <= 0x10,
                        f"{u16} <= 0x10 (0x48400)")
            ok &= check(f"operation.rec[{i}].nbr", nbr <= 0x80,
                        f"{nbr} <= 0x80 (0x48414)")
            refs = struct.unpack_from(f"<{nbr}I", oper, r + 0x0C) if nbr else ()
            ok &= check(f"operation.rec[{i}].refs",
                        all(x <= 0x3C for x in refs),
                        f"{list(refs)} each <= 0x3c (0x48430)")
    # -- checkOperationKernelRefs 0x48834 via checkProgram 0x48c74:
    #    tdCount u32@+4 == 0 short-circuits to 1 (0x48904 -> 0x489f4)
    td_count = struct.unpack_from("<I", oper, 4)[0] if tot else 1
    ok &= check("operation.kernelRefs", td_count == 0,
                "tdCount == 0: no kernel-ref resolution for an add (0x48904)")

    # -- verifyProcedureSection 0x484b0 (+ tot <= 0x80 from CAneProgramH14
    #    content getter 0x46c38)
    ptot = struct.unpack_from("<I", proc, 0)[0]
    ok &= check("procedure.tot", ptot <= 0x80, f"{ptot} <= 0x80 (0x46c3c)")
    ok &= check("procedure.size", len(proc) >= 8 + 0x10 * ptot,
                f"{len(proc)} >= 8+0x10*{ptot} (0x46c1c region)")
    prev_end = 0
    for i in range(ptot):
        off, size = struct.unpack_from("<QQ", proc, 8 + i * 0x10)
        ok &= check(f"procedure.entry[{i}]",
                    off >= prev_end and off + size <= len(proc),
                    f"off={off:#x} size={size:#x} ascending, in-section "
                    "(0x484d8-0x484f4)")
        prev_end = off + size
    rec_off = struct.unpack_from("<Q", proc, 8)[0]
    content_type = struct.unpack_from("<I", proc, rec_off + 4)[0]
    ok &= check("procedure.contentType", content_type in (0, 3, 4),
                f"{content_type} in {{0,3,4}} (CAneProgramH14 getProcedure"
                "CallType; bypass accepted)")

    # -- verifyDescriptorPropSection 0x4858c
    nseg = struct.unpack_from("<I", tdp, 0)[0]
    ok &= check("tdprop.size", len(tdp) >= 8 + 0x20 * nseg,
                f"{len(tdp)} >= 8+0x20*{nseg} (0x485a8)")
    for i in range(nseg):
        off, size = struct.unpack_from("<QQ", tdp, 8 + i * 0x20 + 0x10)
        ok &= check(f"tdprop.seg[{i}]", off + size <= len(desc),
                    f"off={off:#x}+size={size:#x} <= descriptor {len(desc)} "
                    "(0x4866c)")
    # -- deep walk 0x486a0 (unconditional in checkProgram 0x48dc8):
    #    segment.blockNbr must equal the number of Descriptor blocks in
    #    [off, off+size)
    for i in range(nseg):
        blk_nbr = struct.unpack_from("<I", tdp, 8 + i * 0x20 + 4)[0]
        off, size = struct.unpack_from("<QQ", tdp, 8 + i * 0x20 + 0x10)
        w0 = struct.unpack_from("<I", desc, off)[0]
        stride = 0x30 if (w0 & 4) else 0x10   # csel eq: bit2 clear -> 0x10
        walked, cur = 0, stride
        last = None
        while size > cur:
            last = off + cur
            u16 = struct.unpack_from("<H", desc, last + 2)[0] & 0x7FF
            if u16 == 0:
                walked = -1          # zero block word -> firmware fails
                break
            cur += ((u16 << 2) + 0xF) & 0x3FF0
            walked += 1
        ok &= check(f"tdprop.seg[{i}].blockNbr", walked == blk_nbr,
                    f"walked {walked} block(s) in [{off:#x},{off+size:#x}) "
                    f"== blockNbr {blk_nbr} (0x48798)")
        ok &= check(f"tdprop.seg[{i}].tail",
                    not (w0 & 1) or last is None or
                    struct.unpack_from("<I", desc, last + 0x18)[0] == 0,
                    f"word[{off}] bit0={w0 & 1}: u32@[last+0x18] must be 0 "
                    "when set (0x487a8)")

    print("self-checks (fw135 PROCEDURE_CALL checker 0x48df8):")
    # caller-side binding to be emitted in binding.json
    for name, buf_id, rtype, _io, rsize in IO:
        matches = [(i, s) for i, (bid, s) in enumerate(entries) if bid == buf_id]
        ok &= check(f"call.rec[{name}].id", len(matches) == 1,
                    f"bufferId {buf_id} matches exactly one generic entry "
                    "(0x48f14-0x48fa0)")
        if len(matches) == 1:
            ok &= check(f"call.rec[{name}].size", rsize >= matches[0][1],
                        f"{rsize:#x} >= entry {matches[0][1]:#x} (0x48f64)")
        ok &= check(f"call.rec[{name}].reserved",
                    buf_id not in (SECTION_IDS["kernel"], SECTION_IDS["descriptor"]),
                    f"id {buf_id} != kernel/text section ids "
                    f"{SECTION_IDS['kernel']}/{SECTION_IDS['descriptor']} "
                    "(0x48ee0-0x48f10)")
    ok &= check("call.count", 1 <= len(IO) <= 64,
                f"{len(IO)} in [1,64] (0x48e0c)")
    ok &= check("call.priority", 2 <= PRIORITY <= 7,
                f"{PRIORITY} in [2,7] (cmd+0x18)")

    if not ok:
        raise SystemExit("self-check FAILED")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)

    descriptor = build_descriptor()
    sections = {
        "generic": build_generic(),
        "kernel": build_kernel(),
        "descriptor": descriptor,
        "operation": build_operation(),
        "procedure": build_procedure(),
        "tdprop": build_tdprop(descriptor),
    }
    self_check(sections)

    for name, data in sections.items():
        (out / f"{name}.bin").write_bytes(data)
        print(f"wrote {out / (name + '.bin')} ({len(data)} B)")

    binding = {
        "procedure_id": PROCEDURE_ID,
        "records": [{"name": n, "size": s, "type": t, "buffer_id": bid}
                    for n, bid, t, _io, s in IO],
        "stats_type": PRIORITY,
        "section_ids": SECTION_IDS,
        "uuid": None,
        "notes": {
            "record_order": "emission order = cmd+0x60 + i*0x30; record.type "
                            "0=input 1=output (cmd rec +0x08)",
            "buffer_ids": "ANEC channel ids from H14Program.cpp:547-561 "
                          "(output=4, inputs=5,6); must avoid kernel/text "
                          "section ids 2/3 per fw135 0x48df8",
            "stats_type": "cmd+0x18 priority, valid [2,7]; 2 is the value "
                          "proven through the controller by the h14conv run",
        },
    }
    (out / "binding.json").write_text(json.dumps(binding, indent=2) + "\n")
    print(f"wrote {out / 'binding.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
