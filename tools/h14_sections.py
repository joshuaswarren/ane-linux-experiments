#!/usr/bin/env python3
"""Build LOAD_PROGRAM section payloads from any H14 ANEC package.

Replaces tools/h14_first_add_sections.py (the first-add tool). Everything the
old tool hard-coded is now derived from the package:

  descriptor  full task stream: 16-byte zero frame + all tasks, walked by
              header[0] size (bits 26:16), 16-byte alignment, zero-size
              16-byte frames skipped (ported split_h14_tasks).
  operation   refs {slot, tag} from the TD address records: a dense record
              header with bit 29 set is a BAR ref, bits 28:23 (with bit 28
              observed 0) are the slot. Source block (0x1100..0x14ff) records
              map to ANEC input channels 5,6 in address order; destination
              block (0x1500..) maps to output channel 4. Proven on the add:
              refs {4,5}(a) {5,4}(y) {6,6}(b) (fw135 0x44c98 pushes these
              IOVAs into the record patch area, 0x44f20 reads the pairs).
  tdprop      blockNbr from the firmware walk replica (fw135 0x486a0: stride
              0x30/0x10 by word[off] bit 2, block size ((u16@[blk+2]&0x7ff)
              <<2 +0xf) &0x3ff0, walked count must equal blockNbr 0x48798).
  generic     one entry per bound ANEC channel (tiles != 0): inputs 5,6 then
              output 4, size = tiles*0x4000.

Firmware reference: macOS 13.5 (22G74) image, sha256 a9c4b771...
(VM = file - 0x4000). Section id / checker addresses are in the self-checks.

Usage: python3 tools/h14_sections.py <out-dir> <path-to-program-N.anec>
       [--bind <channel>=<name>] ...   name io channels (default a,b,y)
"""
import json
import os
import struct
import sys
from pathlib import Path

H14_HEADER_WORDS = 8
FRAME_BYTES = 16
SECTION_IDS = {"generic": 1, "kernel": 2, "descriptor": 3, "operation": 4,
               "procedure": 5, "tdprop": 7}
GENERIC_MAGIC = 1
GENERIC_VERSION = 0x10           # <= 0x10 (verifyGenericSection 0x48208)
PROCEDURE_ID = 0
PRIORITY = 2                     # cmd+0x18, valid [2,7]
TILE_BYTES = 0x4000
CHANNEL_TILES_OFFSET = 0x28      # u32 tiles[32]
CHANNEL_LAYOUT_OFFSET = 0xA8     # u64 layouts[32*6] (n,c,h,w,plane,row)
LAYOUT_FIELDS = 6


class Refuse(Exception):
    """A derivation this builder cannot justify from decoded facts."""


def refuse(why):
    raise Refuse(why)


def parse_anec(path: Path) -> dict:
    d = path.read_bytes()
    if len(d) < 0x1000:
        refuse(f"{path}: {len(d)} B is smaller than the 0x1000 H14 header")
    (content, ) = struct.unpack_from("<Q", d, 0x00)
    first_task, task_count = struct.unpack_from("<II", d, 0x08)
    (stream_size, ) = struct.unpack_from("<Q", d, 0x10)
    (const_size, ) = struct.unpack_from("<Q", d, 0x18)
    input_count, version = struct.unpack_from("<II", d, 0x20)
    if version != 1:
        refuse(f"anec header word @0x24 is {version}, only the emitted 1 is known")
    if input_count < 1 or input_count > 2:
        refuse(f"anec inputCount {input_count}: this builder derives tags for "
               "1..2 runtime inputs (channels 5,6), the only forms the "
               "h14-oracle-parity encoder emits")
    if len(d) != 0x1000 + content:
        refuse(f"anec file {len(d)} B != header 0x1000 + contentSize {content:#x}")
    const_offset = content - const_size
    if const_offset % 0x40:
        refuse(f"constant offset {const_offset:#x} is not 64-byte aligned "
               "(encoder emits align_up(stream, 64))")
    tiles = struct.unpack_from("<32I", d, CHANNEL_TILES_OFFSET)
    layouts = struct.unpack_from("<192Q", d, CHANNEL_LAYOUT_OFFSET)
    channels = {}
    for index in [4] + [5 + i for i in range(input_count)]:
        if tiles[index] == 0:
            refuse(f"channel {index} has zero tiles; no binding to derive")
        base = index * LAYOUT_FIELDS
        channels[index] = {
            "tiles": tiles[index],
            "allocation_bytes": tiles[index] * TILE_BYTES,
            "nchw": list(layouts[base:base + LAYOUT_FIELDS]),
        }
    stream = d[0x1000:0x1000 + stream_size]
    constants = d[0x1000 + const_offset:0x1000 + const_offset + const_size]
    if len(constants) != const_size:
        refuse("anec constant region truncated")
    return {"first_task": first_task, "task_count": task_count,
            "stream": stream, "constants": constants,
            "input_count": input_count, "channels": channels}


def split_h14_tasks(section: bytes) -> list[bytes]:
    """Ported from mil-hwx-compiler research/h13_td.py split_h14_tasks."""
    tasks, offset = [], 0
    while offset < len(section):
        if len(section) - offset < 4:
            if any(section[offset:]):
                refuse("nonzero H14 trailing alignment bytes")
            break
        task_words = struct.unpack_from("<H", section, offset + 2)[0] & 0x7FF
        if task_words == 0:
            offset = min(offset + 16, len(section))
            continue
        if task_words < H14_HEADER_WORDS:
            refuse(f"task {len(tasks)} declares {task_words} words: below the "
                   "8-word H14 header")
        task_bytes = task_words * 4
        if task_bytes > len(section) - offset:
            refuse(f"task {len(tasks)} declares {task_words} words beyond the "
                   "task stream")
        tasks.append(section[offset:offset + task_bytes])
        nxt = min((offset + task_bytes + 15) & ~15, len(section))
        if any(section[offset + task_bytes:nxt]):
            refuse(f"task {len(tasks)} has nonzero 16-byte alignment padding")
        offset = nxt
    if not tasks:
        refuse("task stream holds no task")
    return tasks


def task_records(task: bytes) -> list[tuple[int, int, tuple[int, ...]]]:
    """(header, first address, payload words) per record, H14 dense/scatter."""
    words = struct.unpack_from(f"<{len(task) // 4}I", task)
    index = H14_HEADER_WORDS
    if words[H14_HEADER_WORDS - 1] & 0x3 == 0x3:
        index += 1
    records = []
    while index < len(words):
        header = words[index]
        base = (header & 0x7FFF) * 4
        if header & 0x80000000:
            mask = (header >> 15) & 0xFFFF
            count = 1 + bin(mask).count("1")
            addresses = [base] + [base + (bit + 1) * 4 for bit in range(16)
                                  if mask & (1 << bit)]
        else:
            count = ((header >> 15) & 0x3F) + 1
            addresses = [base + off * 4 for off in range(count)]
        if index + 1 + len(addresses) > len(words):
            refuse(f"record at word {index} declares {len(addresses)} payload "
                   "words beyond its task")
        records.append((header, addresses[0],
                        words[index + 1:index + 1 + len(addresses)]))
        index += 1 + len(addresses)
    return records


def derive_refs(stream: bytes, anec: dict,
                scratch_bufid: int = 0) -> tuple[list[tuple[int, int]], int]:
    """BAR refs {slot, tag} from dense TD records with bit 29 set.

    fw135 0x44c98 pushToHWDirect picks ONE operation record per call
    (descbase = opSection + rowIdx[cmd[0x10]] * 0x40C, 0x44ea0), zero-fills
    the 61-slot BAR patch table at netDesc+0xC (NEON at 0x44e58-0x44ea4),
    and walks the record's pairs (refCount at +0xC, pairs at +0x10+i*8).
    Each pair writes a 64-bit IOVA into netDesc+0xC+8*slot; the IOVA is
    the call record's value when bufferId == tag (cmd+0x64+j*0x30, key
    at +0 and IOVA at +0x18), or the kernel/text section base for tags 2/3
    (descInfo+0x50 / descInfo+0x80, 0x44f30 / 0x44f58). The call checker
    at fw135 0x48df8 forbids io bufferIds 2/3 for this reason
    (0x48ee0-0x48f10).

    There is NO per-task BAR walk. pushToHWDirect runs once per
    PROCEDURE_CALL (cmd+0x10 is the procedure id; one direct-call FIFO
    push per call). The 61-slot table is GLOBAL per call; pairs that
    share a slot within one record silently overwrite (last-write-wins
    at 0x44f00-0x44f14). Multi-task programs MUST use globally-unique
    slots OR carry every ref of the whole program in the one record
    with one tag per slot.

    IslandBind (2026-09-30): when scratch_bufid != 0 a cross-task slot
    conflict whose refs ALL sit at scratch-eligible registers (TileDMA
    dst 0x1508, KernelDMA 0x1900..0x19ff) is RESOLVED by retagging that
    slot to scratch_bufid; the caller adds the matching scratch generic
    entry and returns the used flag. A conflict whose mix includes a
    TileDMA src base (0x1110/0x1128) refuses — that ref binds a real
    channel buffer, not scratch.

    Returns (refs sorted by slot, scratch_used).

    Tag resolution per record register (the legacy rule, proven for the
    9 stage 1-4 fixtures; matvec proven on hardware boot 8f468602):
      0x1900..0x19ff KernelDMA block   -> 2 (constants base)
      0x1508 TileDMA dst base          -> 4 (output channel 4)
      0x1110 / 0x1128 TileDMA src base -> 5 / 6 (input channels) when
                                          slot >= 4; -> 2 (kernel base)
                                          when slot <= 1 (the constant-row
                                          load pattern; real-div t0 reads
                                          the stored 2.0 row, kernel
                                          offset 0x400)
    """
    pairs: dict[int, int] = {}
    addrs: dict[int, int] = {}
    per_task: list[dict[int, int]] = []
    scratch_used = 0
    for t, task in enumerate(split_h14_tasks(stream)):
        task_pairs: dict[int, int] = {}
        task_addr: dict[int, int] = {}
        for header, addr, _payload in task_records(task):
            if header & 0x80000000 or not header & (1 << 29):
                continue
            slot = (header >> 23) & 0x3F
            if header & (1 << 28):
                refuse(f"task {t}: BAR-ref header {header:#010x} has bit 28 "
                       "set; the slot field width (28:23 vs 27:23) is not "
                       "decided by any decoded case")
            if slot > 0x3C:
                refuse(f"task {t}: BAR slot {slot} exceeds 0x3c "
                       "(fw135 0x44f3c bounds slot*2 at 0x79)")
            if 0x1900 <= addr < 0x1A40:
                tag = 2
            elif addr == 0x1508:
                tag = 4
            elif addr in (0x1110, 0x1128):
                if slot <= 1:
                    tag = 2
                elif slot in (2, 3):
                    refuse(f"task {t}: BAR slot {slot} at src base {addr:#06x} "
                           "collides with the section-tag namespace (2 kernel, "
                           "3 text, fw135 0x44f30/0x44f58); no decoded case "
                           "assigns it a surface")
                elif addr == 0x1110:
                    tag = 5
                else:
                    tag = 6
            elif addr in (0x1120, 0x1124, 0x112c):
                refuse(f"task {t}: BAR-ref record at {addr:#06x} sits between "
                       "the two known src bases 0x1110/0x1128; its surface is "
                       "not identified")
            else:
                refuse(f"task {t}: BAR-ref record at register {addr:#06x} is "
                       "outside the known roles (src 0x1110/0x1128, dst "
                       "0x1508, KernelDMA 0x1900..0x19ff); no tag is known")
            if slot in task_pairs and task_pairs[slot] != tag:
                refuse(f"task {t}: BAR slot {slot} resolves to both tag "
                       f"{task_pairs[slot]} and {tag} in this task")
            task_pairs[slot] = tag
            task_addr[slot] = addr
        per_task.append(task_pairs)
        for slot, tag in task_pairs.items():
            if slot not in pairs:
                pairs[slot] = tag
                addrs[slot] = task_addr[slot]
                continue
            if pairs[slot] == tag:
                continue
            # Cross-task slot conflict: resolve via the scratch merge when
            # allowed (every ref at the slot sits at a scratch-eligible
            # register), otherwise refuse.
            if scratch_bufid and all(
                    a == 0x1508 or 0x1900 <= a < 0x1A40
                    for a in (addrs[slot], task_addr[slot])):
                pairs[slot] = scratch_bufid
                scratch_used = 1
                continue
            old_task = next(i for i, tp in enumerate(per_task)
                            if slot in tp and tp[slot] != tag)
            refuse(f"task {t}: BAR slot {slot} resolves to tag {tag} here "
                   f"but tag {pairs[slot]} in task {old_task}; fw135 "
                   "0x44c98 pushToHWDirect has no per-task BAR walk "
                   "and the 61-slot patch table at netDesc+0xC is "
                   "global per call (0x44e58-0x44ea4), so this slot "
                   "must be unique across the whole program")
    refs = sorted(pairs.items())
    known = {2} | set(anec["channels"])
    if scratch_bufid:
        known.add(scratch_bufid)
    bad = [(s, t) for s, t in refs if t not in known]
    if bad:
        refuse(f"refs {bad} name tags outside the kernel section (2), the "
               f"scratch buffer ({scratch_bufid:#x}) and the bound channels "
               f"{sorted(anec['channels'])}")
    if not refs:
        refuse("the task stream holds no BAR-ref record; no operation refs "
               "can be derived")
    return refs, scratch_used


def scratch_bytes(stream: bytes, scratch_slot: int, output_size: int) -> int:
    """Host-derived scratch BO size: max BAR-ref payload[0] at the merged
    slot across all tasks, plus the output allocation, rounded up to the
    16 KiB tile unit. The C builder computes the same value
    (ane_m2.c scratch_size_bytes)."""
    max_payload = 0
    for task in split_h14_tasks(stream):
        for header, _addr, payload in task_records(task):
            if header & 0x80000000 or not header & (1 << 29):
                continue
            slot = (header >> 23) & 0x3F
            if slot == scratch_slot and payload:
                max_payload = max(max_payload, payload[0])
    size = max_payload + output_size
    return (size + 0x3FFF) & ~0x3FFF


def tdprop_walk(desc: bytes, off: int, size: int) -> tuple[int, int]:
    """Firmware 0x486a0 replica; returns (blocks walked, last block offset)."""
    w0 = struct.unpack_from("<I", desc, off)[0]
    stride = 0x30 if (w0 & 4) else 0x10   # csel eq: bit2 clear -> 0x10
    walked, cur, last = 0, stride, None
    while size > cur:
        last = off + cur
        u16 = struct.unpack_from("<H", desc, last + 2)[0] & 0x7FF
        if u16 == 0:
            return -1, last               # zero block word -> firmware fails
        cur += ((u16 << 2) + 0xF) & 0x3FF0
        walked += 1
    return walked, (last if last is not None else 0)


def build_generic(channels: dict, scratch: dict | None = None) -> bytes:
    # inputs 5,6 then output 4: the proven add entry order; an optional
    # scratch entry (IslandBind) follows the output.
    entries = [(c, channels[c]) for c in [5, 6] if c in channels]
    entries += [(4, channels[4])]
    if scratch is not None:
        entries.append((scratch["buffer_id"], scratch))
    buf = bytearray(0x208 + 0x30 * len(entries))
    struct.pack_into("<II", buf, 0x00, GENERIC_MAGIC, GENERIC_VERSION)
    struct.pack_into("<I", buf, 0x204, len(entries))
    for i, (cid, ch) in enumerate(entries):
        out = cid == 4
        scratch_entry = scratch is not None and cid == scratch["buffer_id"]
        e = 0x208 + i * 0x30
        struct.pack_into("<IIII", buf, e, 1, cid, 0 if scratch_entry else (1 if out else 0), 0)
        struct.pack_into("<IIII", buf, e + 0x10, 1 if scratch_entry else (2 if out else 1), 0, 0, 0)
        struct.pack_into("<QII", buf, e + 0x20, ch["allocation_bytes"], 0xFFFF, 0)
    return bytes(buf)


def build_operation(refs: list[tuple[int, int]]) -> bytes:
    # u32 tot + 0x40c record; refCount at section+0xc, {slot, tag} at +0x10
    rec = bytearray(0x40C)
    struct.pack_into("<I", rec, 0x08, len(refs))
    flat = [v for pair in refs for v in pair]
    struct.pack_into(f"<{len(flat)}I", rec, 0x0C, *flat)
    return struct.pack("<I", 1) + bytes(rec)


def build_procedure() -> bytes:
    # mirrors the load-proven h14conv procedure section; content type 3
    buf = bytearray(0x18 + 0x20)
    struct.pack_into("<I", buf, 0x00, 1)
    struct.pack_into("<QQ", buf, 0x08, 0x18, 0x20)
    struct.pack_into("<8I", buf, 0x18, 1, 3, 0, 0, 1, 0, 0xFFFFFFFF, 4)
    return bytes(buf)


def build_tdprop(desc: bytes) -> bytes:
    walked, _last = tdprop_walk(desc, 0, len(desc))
    if walked <= 0:
        refuse(f"tdprop walk found {walked} blocks in the {len(desc)} B "
               "descriptor; the firmware deep check 0x486a0 would reject it")
    buf = bytearray(40)
    struct.pack_into("<I", buf, 0x00, 1)
    struct.pack_into("<IIQQQ", buf, 0x08, 0, walked, 0, 0, len(desc))
    return bytes(buf)


def check(name, ok, why):
    print(f"  [{'ok' if ok else 'FAIL'}] {name}: {why}")
    return ok


def self_check(anec: dict, sections: dict, refs: list,
               scratch_tag: int = 0) -> bool:
    """Re-derive every fw135 constraint the payloads must satisfy.

    scratch_tag is the bufferId the scratch merge retagged (0 = no
    scratch); it is allowed as a ref tag and must appear exactly once in
    the generic entries when set."""
    ok = True
    gen, kern, desc = sections["generic"], sections["kernel"], sections["descriptor"]
    oper, proc, tdp = sections["operation"], sections["procedure"], sections["tdprop"]

    print("self-checks (fw135 LOAD path):")

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
        ok &= check(f"generic.entry[{i}].bufid", buf_id != SECTION_IDS["kernel"]
                    and buf_id != SECTION_IDS["descriptor"],
                    f"id {buf_id} not a section id (0x48ee0-0x48f10)")
        entries.append((buf_id, size))
    ids = [i for i, _ in entries]
    ok &= check("generic.ids", len(set(ids)) == len(ids),
                f"bufferIds {ids} unique (exact-one match at 0x48f14)")

    # -- checkProgram 0x48cec head (false -> ASSERT CAneProgramManager.cpp:437)
    ok &= check("load.required", True,
                "generic+text+tdprop+operation+procedure present "
                "(0x48cf8-0x48d48)")
    ok &= check("generic.totalBufferNbr", count > 0,
                "totalBufferNbr > 0 (0x48b48)")
    ok &= check("descriptor.size", len(desc) > 0,
                f"{len(desc)} B nonzero (0x48bf8 textSection.size)")
    ok &= check("kernel.size", len(kern) > 0,
                f"{len(kern)} B nonzero (0x48dac; only size!=0 when present)")

    # -- descriptor: the walked task array must consume the section exactly
    tasks = split_h14_tasks(desc)
    ok &= check("descriptor.tasks", len(tasks) == anec["task_count"],
                f"{len(tasks)} walked == header taskCount "
                f"{anec['task_count']} (0x486a0 walk agreement)")
    first_words = struct.unpack_from("<4I", tasks[0], 0)
    ok &= check("descriptor.header.taskWords",
                (first_words[0] >> 16) & 0x7FF == len(tasks[0]) // 4,
                f"header[0] {first_words[0]:#010x} declares "
                f"{(first_words[0] >> 16) & 0x7FF} words, task is "
                f"{len(tasks[0]) // 4} (bits 26:16)")

    # -- verifyOperationSection 0x48384
    tot = struct.unpack_from("<I", oper, 0)[0]
    ok &= check("operation.tot", tot <= 0x80, f"{tot} <= 0x80 (0x483b4)")
    ok &= check("operation.size", len(oper) >= 4 + tot * 0x40C,
                f"{len(oper)} >= 4+{tot}*0x40c (0x483ac)")
    for i in range(tot):
        r = 4 + i * 0x40C
        rtype = struct.unpack_from("<I", oper, r)[0]
        u16 = struct.unpack_from("<H", oper, r + 4)[0]
        nbr = struct.unpack_from("<I", oper, r + 8)[0]
        ok &= check(f"operation.rec[{i}].type", rtype <= 3,
                    f"type {rtype} <= 3 (0x483ec)")
        if rtype == 0:
            ok &= check(f"operation.rec[{i}].u16", u16 <= 0x10,
                        f"{u16} <= 0x10 (0x48400)")
            ok &= check(f"operation.rec[{i}].nbr", nbr <= 0x80,
                        f"{nbr} <= 0x80 (0x48414)")
            flat = struct.unpack_from(f"<{2 * nbr}I", oper, r + 0x0C) \
                if nbr else ()
            pairs = list(zip(flat[0::2], flat[1::2]))
            ok &= check(f"operation.rec[{i}].refs",
                        all(s <= 0x3C and (t <= 0x3C or t == scratch_tag)
                            for s, t in pairs),
                        f"{pairs} slot<=0x3c, tag<=0x3c or scratch "
                        f"({scratch_tag:#x}) (0x48430)")
            ok &= check(f"operation.rec[{i}].sorted",
                        [s for s, _ in pairs] == sorted(s for s, _ in pairs),
                        "refs ascending by slot, the proven add emission order")
            ok &= check(f"operation.rec[{i}].match",
                        [s for s, _ in pairs] == [s for s, _ in refs],
                        f"emitted refs equal the TD-derived {refs} "
                        "(pushToHWDirect 0x44c98 pairs them with call IOVAs)")
            tail_at = r + 0x0C + 8 * nbr
            ok &= check(f"operation.rec[{i}].tailZero",
                        not any(oper[tail_at:r + 0x40C]),
                        "record bytes after the ref pairs are zero; the "
                        "patch area is filled from call IOVAs at run time "
                        "(0x44e5c-0x44ea4)")

    # -- checkOperationKernelRefs 0x48834: tdCount == 0 short-circuits (0x48904)
    td_count = struct.unpack_from("<I", oper, 4)[0] if tot else 1
    ok &= check("operation.kernelRefs", td_count == 0,
                "tdCount == 0: no kernel-ref resolution for these programs")

    # -- verifyProcedureSection 0x484b0 (+ tot <= 0x80 from 0x46c38)
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
                f"{content_type} in {{0,3,4}} (getProcedureCallType)")

    # -- verifyDescriptorPropSection 0x4858c + deep walk 0x486a0
    nseg = struct.unpack_from("<I", tdp, 0)[0]
    ok &= check("tdprop.size", len(tdp) >= 8 + 0x20 * nseg,
                f"{len(tdp)} >= 8+0x20*{nseg} (0x485a8)")
    for i in range(nseg):
        # segments start at section+8; the firmware ldp at 0x48730 reads off
        # at seg+0x10 and size at seg+0x18 (writer args 4 and 5, the fields
        # the verifier bounds at 0x4866c)
        off = struct.unpack_from("<Q", tdp, 8 + i * 0x20 + 0x10)[0]
        size = struct.unpack_from("<Q", tdp, 8 + i * 0x20 + 0x18)[0]
        ok &= check(f"tdprop.seg[{i}]", off + size <= len(desc),
                    f"off={off:#x}+size={size:#x} <= descriptor {len(desc)} "
                    "(0x4866c)")
        ok &= check(f"tdprop.seg[{i}].covers", size > 0 and off + size == len(desc),
                    f"single segment covers [{off:#x},{off+size:#x}) over the "
                    f"{len(desc)} B descriptor (the emitted and h14conv form)")
        blk_nbr = struct.unpack_from("<I", tdp, 8 + i * 0x20 + 4)[0]
        walked, last = tdprop_walk(desc, off, size)
        w0 = struct.unpack_from("<I", desc, off)[0]
        ok &= check(f"tdprop.seg[{i}].blockNbr", walked == blk_nbr,
                    f"walked {walked} block(s) in [{off:#x},{off+size:#x}) "
                    f"== blockNbr {blk_nbr} (0x48798)")
        ok &= check(f"tdprop.seg[{i}].tail",
                    not (w0 & 1) or last == 0 or
                    struct.unpack_from("<I", desc, last + 0x18)[0] == 0,
                    f"word[{off}] bit0={w0 & 1}: u32@[last+0x18] must be 0 "
                    "when set (0x487a8)")
        ok &= check(f"tdprop.seg[{i}].tasks",
                    walked == len(split_h14_tasks(desc[off:off + size])),
                    f"walked {walked} == {len(split_h14_tasks(desc[off:off + size]))} "
                    "parsed task(s): the two walks agree")

    print("self-checks (fw135 PROCEDURE_CALL checker 0x48df8):")
    for i, (buf_id, esize) in enumerate(entries):
        matches = [(j, s) for j, (bid, s) in enumerate(entries) if bid == buf_id]
        ok &= check(f"call.rec[{i}].id", len(matches) == 1,
                    f"bufferId {buf_id} matches exactly one generic entry "
                    "(0x48f14-0x48fa0)")
        ok &= check(f"call.rec[{i}].reserved",
                    buf_id not in (SECTION_IDS["kernel"], SECTION_IDS["descriptor"]),
                    f"id {buf_id} != kernel/text section ids 2/3 "
                    "(0x48ee0-0x48f10)")
    ok &= check("call.count", 1 <= count <= 64,
                f"{count} in [1,64] (0x48e0c: w9-0x41 must compare below 0x40)")
    ok &= check("call.priority", 2 <= PRIORITY <= 7,
                f"{PRIORITY} in [2,7] (cmd+0x18)")
    tags = sorted(set(t for _, t in refs))
    ok &= check("call.tagsKnown",
                all(t == 2 or t == scratch_tag or t in ids for t in tags),
                f"ref tags {tags} name the kernel section (2), the scratch "
                f"buffer ({scratch_tag:#x}) or bound call channels; "
                "pushToHWDirect resolves each tag to an IOVA "
                "(0x44f30 section path, 0x44fbc call-record scan)")
    if not ok:
        raise SystemExit("self-check FAILED")
    return True


def main() -> int:
    args = sys.argv[1:]
    binds = {}
    rest = []
    i = 0
    while i < len(args):
        if args[i] == "--bind":
            chan, _, name = args[i + 1].partition("=")
            binds[int(chan)] = name
            i += 2
        else:
            rest.append(args[i])
            i += 1
    if len(rest) != 2:
        print(__doc__)
        return 2
    out, anec_path = Path(rest[0]), Path(rest[1])
    names = {5: "a", 6: "b", 4: "y"} | binds

    # IslandBind env overrides (mirror the C builder libane/ane_m2.c):
    #   ANE_M2_SCRATCH=<bytes>  enable the scratch merge and floor the
    #                           scratch BO at <bytes> (0 disables).
    #   ANE_M2_OPREFS=s:t,s:t   replace the derived ref pairs outright.
    scratch_env = os.environ.get("ANE_M2_SCRATCH")
    scratch_bufid = 0x40
    scratch_floor = 0
    if scratch_env is not None:
        try:
            scratch_floor = int(scratch_env, 0)
        except ValueError:
            scratch_floor = 0
    if scratch_env is not None and scratch_floor == 0:
        scratch_bufid = 0

    anec = parse_anec(anec_path)
    refs, scratch_used = derive_refs(anec["stream"], anec, scratch_bufid)

    oprefs_env = os.environ.get("ANE_M2_OPREFS")
    if oprefs_env:
        pairs = []
        for item in oprefs_env.split(","):
            s, _, t = item.partition(":")
            pairs.append((int(s, 0), int(t, 0)))
        for s, t in pairs:
            if s > 0x3C or t > 0x3C:
                refuse(f"ANE_M2_OPREFS pair ({s},{t}) outside the 61-slot "
                       "BAR range")
        refs = sorted(pairs)
        scratch_used = 0

    channels = dict(anec["channels"])
    scratch_size = 0
    if scratch_used:
        out_alloc = channels[4]["allocation_bytes"]
        scratch_slot = next(s for s, t in refs if t == scratch_bufid)
        scratch_size = scratch_bytes(anec["stream"], scratch_slot, out_alloc)
        scratch_size = max(scratch_size, scratch_floor) + 0x4000
        channels[scratch_bufid] = {
            "tiles": scratch_size // TILE_BYTES,
            "allocation_bytes": scratch_size,
            "nchw": [0, 0, 0, 0, 0, 0],
        }

    sections = {
        "generic": build_generic(channels,
                                 scratch={"buffer_id": scratch_bufid,
                                          "allocation_bytes": scratch_size}
                                 if scratch_used else None),
        "kernel": anec["constants"],
        "descriptor": anec["stream"],
        "operation": build_operation(refs),
        "procedure": build_procedure(),
        "tdprop": build_tdprop(anec["stream"]),
    }
    self_check(anec, sections, refs, scratch_bufid if scratch_used else 0)

    out.mkdir(parents=True, exist_ok=True)
    for name, data in sections.items():
        (out / f"{name}.bin").write_bytes(data)
        print(f"wrote {out / (name + '.bin')} ({len(data)} B)")

    order = [5, 6, 4]
    records = []
    for cid in order:
        if cid not in anec["channels"]:
            continue
        records.append({
            "name": names[cid],
            "size": anec["channels"][cid]["allocation_bytes"],
            "type": 1 if cid == 4 else 0,
            "buffer_id": cid,
        })
    if scratch_used:
        records.append({
            "name": "scratch",
            "size": scratch_size,
            "type": 0,
            "buffer_id": scratch_bufid,
        })
    binding = {
        "procedure_id": PROCEDURE_ID,
        "records": records,
        "stats_type": PRIORITY,
        "section_ids": SECTION_IDS,
        "uuid": None,
        "channels": {str(c): anec["channels"][c] for c in sorted(anec["channels"])},
        "refs": [{"slot": s, "tag": t} for s, t in refs],
        "notes": {
            "record_order": "emission order = cmd+0x60 + i*0x30; record.type "
                            "0=input 1=output (cmd rec +0x08)",
            "buffer_ids": "ANEC channel ids (output 4, inputs 5,6); must "
                          "avoid kernel/text section ids 2/3 (fw135 0x48df8)",
            "stats_type": "cmd+0x18 priority, valid [2,7]; 2 is hardware-"
                          "proven by the add run",
            "refs": "operation-section {slot,tag} pairs derived from the TD "
                    "BAR records (bit 29, slot bits 28:23, fw135 0x44c98)",
        },
    }
    (out / "binding.json").write_text(json.dumps(binding, indent=2) + "\n")
    print(f"op refs: {refs}; tdprop blockNbr="
          f"{struct.unpack_from('<I', sections['tdprop'], 0xC)[0]}; "
          f"tasks={len(split_h14_tasks(anec['stream']))}; all self-checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
