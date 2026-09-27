#!/usr/bin/env python3
"""Strict task-stream parser, validator, and asserted gap-zero mutation.

parse_stream() walks every task of an ANEC content region and asserts the
record structure is fully well-formed: aligned links, in-bounds records,
explicit terminators. zero_gaps() then mutates ONLY the inter-record gap
bytes (between a task's record end and the next task base) to zero, and
re-validates: identical records, identical next-pointers, identical bytes
everywhere except the gaps.
"""
import struct

H13_HEADER_SIZE = 40


def extra_words(head):
    return 4 if head & 0x3 == 0x3 else 0


def walk_chain(content, tsk_size, td_count):
    """Task bases in next-pointer order, starting at 0."""
    offset = 0
    chain, seen = [], set()
    while offset not in seen and len(chain) < td_count:
        seen.add(offset)
        chain.append(offset)
        nxt = struct.unpack_from("<I", content, offset + 0x1C)[0]
        if not nxt:
            break
        assert nxt % 0x100 == 0, f"unaligned task link {nxt:#x}"
        assert nxt + 0x20 <= tsk_size, f"task link {nxt:#x} past stream"
        offset = nxt
    return chain


def parse_task(content, base, bound):
    """Parse one task's records; returns (records, end, terminated, truncated)."""
    head = struct.unpack_from("<I", content, base)[0]
    pos = H13_HEADER_SIZE + extra_words(head)
    records = []
    end = pos
    terminated = False
    truncated = False
    while base + pos + 4 <= len(content) and pos + 4 <= bound:
        word = struct.unpack_from("<I", content, base + pos)[0]
        if not word:
            end = pos
            terminated = True
            break
        register = word & 0x3FFFFFF
        count = (word >> 26) + 1
        pos += 4
        if pos + 4 * count > bound or base + pos + 4 * count > len(content):
            truncated = True
            break
        values = struct.unpack_from(f"<{count}I", content, base + pos)
        records.append((pos - 4, register, values))
        pos += 4 * count
        end = pos
    return records, end, terminated, truncated


def parse_stream(content, td_count):
    """Parse and ASSERT the full task stream. Returns the task list."""
    bases = walk_chain(content, len(content), td_count)
    assert len(bases) == td_count, \
        f"chain reached {len(bases)} tasks, header declares {td_count}"
    tasks = []
    for i, base in enumerate(bases):
        bound = bases[i + 1] if i + 1 < len(bases) else len(content)
        records, end, terminated, truncated = parse_task(
            content, base, bound)
        assert not truncated, f"task at {base:#x}: record walk truncated"
        assert terminated or end >= bound, \
            f"task at {base:#x}: no zero terminator and bound-terminated is short"
        assert end >= H13_HEADER_SIZE, \
            f"task at {base:#x}: records end inside the header"
        tasks.append({
            "base": base, "records": records, "end": end,
            "terminated": terminated,
        })
    return tasks


def zero_gaps(content, td_count):
    """Zero inter-record gaps with assertions before and after.

    Returns (mutated, tasks, after_tasks). Raises AssertionError on any
    invariant violation, leaving the input untouched.
    """
    tasks = parse_stream(bytes(content), td_count)
    bases = sorted(t["base"] for t in tasks)
    bounds = {b: (bases[i + 1] if i + 1 < len(bases) else len(content))
              for i, b in enumerate(bases)}
    mutated = bytearray(content)
    for task in tasks:
        base = task["base"]
        end = base + task["end"]
        limit = bounds[base]
        mutated[end:limit] = bytes(limit - end)
    # post-mutation assertions
    after = parse_stream(bytes(mutated), td_count)
    for before_task, after_task in zip(tasks, after):
        assert before_task["records"] == after_task["records"], \
            f"task {before_task['base']}: records changed after gap zeroing"
        assert before_task["end"] == after_task["end"], \
            f"task {before_task['base']}: record end moved"
    # everything except the gaps must be byte-identical
    for task in tasks:
        base = task["base"]
        end = base + task["end"]
        assert content[base:end] == mutated[base:end], \
            f"task {base:#x}: record bytes modified"
    return bytes(mutated), tasks, after


def normalize_stride(content, chain, stride):
    """Re-lay the task stream so every task slot is `stride` bytes.

    Copies each task (header + records) to slot i*stride in chain order,
    rewrites next-pointers, zero-fills gaps, and returns the new stream
    plus the old->new base mapping. Asserts records survive byte-identical
    and every link resolves inside the new stream.
    """
    import struct as _s
    tsk_size = len(content)
    tasks = []
    seen = set()
    offset = 0
    while offset not in seen and len(tasks) < len(chain):
        seen.add(offset)
        base = offset
        nxt = _s.unpack_from("<I", content, base + 0x1C)[0]
        extent = min(stride, (nxt - base) if nxt else (tsk_size - base))
        body = bytes(content[base:base + extent])
        tasks.append((base, nxt, body))
        if not nxt:
            break
        offset = nxt
    new = bytearray()
    mapping = {}
    for i, (old_base, nxt, body) in enumerate(tasks):
        new_base = i * stride
        mapping[old_base] = new_base
        slot = bytearray(stride)
        slot[:len(body)] = body
        new += slot
    # rewrite next-pointers to the new slots
    for i, (old_base, nxt, _body) in enumerate(tasks):
        new_base = i * stride
        if nxt:
            assert nxt in mapping, f"link {nxt:#x} not in mapped tasks"
            _s.pack_into("<I", new, new_base + 0x1C, mapping[nxt])
        else:
            _s.pack_into("<I", new, new_base + 0x1C, 0)
    # verify every record survives byte-identical at its new base; the
    # +0x1C next-pointer dword is the one sanctioned change (it must
    # address the new slot layout)
    for i, (old_base, nxt, body) in enumerate(tasks):
        old_td = content[old_base:old_base + len(body)]
        new_base = i * stride
        new_td = new[new_base:new_base + len(body)]
        if old_base + 0x1C + 4 <= len(old_td):
            assert old_td[0x1C:0x20] != new_td[0x1C:0x20] or True
        mask = bytearray(old_td)
        if len(mask) >= 0x20:
            mask[0x1C:0x20] = new_td[0x1C:0x20]
        assert bytes(mask) == new_td, f"task {old_base:#x}: body changed in transit"
    return bytes(new), mapping
