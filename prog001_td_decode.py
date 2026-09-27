#!/usr/bin/env python3
"""Tile-DMA decoder for prog001 (T6001 state block) with the grammar proven
against the known-good embed program (2026-09-27, Jw16FirstSubmit):

  Task chain: linked by u32 next-pointer at +0x1C (absolute stream offsets),
  first task at stream offset 0. td_size is per-task variable (slice by the
  next task's offset). Record headers: bits 0..25 register address,
  bits 26..31 word count-1. Selector word at +32 of each task: shift 0 =
  SOURCE channel, shift 12 = DEST channel (5-bit fields); shifts 6/18/24 are
  task-class tags, not channels. Tile-DMA counts: 0x13810/0x13814 = source
  run/total, 0x1780C/0x17810 = dest run/total. All host reads start at
  window offset 0.

prog001 port table (HWX selectors == anec selectors byte-identical; the
converter's rewire_surface_channels did not change them):
  reads  ch4 0x40/0x400   ch5 0x40/0x400   ch9 0x100/0x80000 (state)
         ch10 0x1000/0x1000 (staged via ws ch3, td02)  ch11 0x1000/0x1000
  writes ch3 0x400/0x4000 (ws)  ch6 0x8000/0x80000 (state')  ch8 o rows
  OPEN: six header input sections, five reads — no descriptor fetches the
  sixth 4096 B window (q), yet q provably flows to o (zero7 A/B). Kernel
  section of the HWX is all zeros; KDMA disabled."""

import json
import struct
import sys

sys.path.insert(0, "/var/tmp/m1max-embed-recovery/tools")

HDR = 0x1000


def u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def parse_header(buf):
    # ANEC_HEADER: <QIIQQII...>: td_size@8? empirically h[1]=td_size, h[2]=td_count,
    # h[3]=task_stream_size (prog001: 0x1f8/0x37/0xa074). Confirm by chain walk.
    return {
        "f0": u32(buf, 0), "td_size": u32(buf, 4), "td_count": u32(buf, 8),
        "task_stream_size": u32(buf, 12), "f16": u32(buf, 16),
        "src_count": u32(buf, 20), "dst_count": u32(buf, 24),
    }


def extra_header_bytes(td_head):
    # header[9] low bits 0b11 -> one extra word (converter rule)
    return 4 if td_head & 0x3 == 0x3 else 0


def walk_chain(buf, tsk_size):
    """Follow the linked task chain from offset 0 (converter behavior)."""
    order = []
    off = 0
    seen = set()
    while off + 0x20 <= tsk_size and off not in seen:
        seen.add(off)
        order.append(off)
        nxt = u32(buf, HDR + off + 0x1C)
        if not nxt or nxt + 0x20 > tsk_size:
            break
        off = nxt
    return order


def walk_registers(td):
    regs = {}
    off = 40 + extra_header_bytes(u32(td, 0))
    while off + 4 <= len(td):
        h = u32(td, off)
        if not h:
            break
        reg = h & 0x3FFFFFF
        cnt = (h >> 26) + 1
        off += 4
        if off + 4 * cnt > len(td):
            return regs, True  # truncated record
        for i in range(cnt):
            regs[reg + 4 * i] = u32(td, off + 4 * i)
        off += 4 * cnt
    return regs, False


SRC_RUN, SRC_TOT, DST_RUN, DST_TOT = 0x13810, 0x13814, 0x1780C, 0x17810


def decode_tasks(buf, tsk_size, limit=None):
    hdr = parse_header(buf)
    chain = walk_chain(buf, hdr["task_stream_size"])
    out = []
    for n, off in enumerate(chain):
        if limit and n >= limit:
            break
        td = buf[HDR + off: HDR + off + hdr["td_size"]]
        sel = u32(td, 32)
        regs, trunc = walk_registers(td)
        chans = [(sh, (sel >> sh) & 0x1F) for sh in (0, 6, 12, 18)]
        out.append({
            "n": n, "off": off,
            "hdr0": u32(td, 0),
            "sel": sel,
            "chans": {sh: c for sh, c in chans if c},
            "src_run": regs.get(SRC_RUN, 0), "src_tot": regs.get(SRC_TOT, 0),
            "dst_run": regs.get(DST_RUN, 0), "dst_tot": regs.get(DST_TOT, 0),
            "nregs": len(regs), "trunc": trunc,
        })
    return hdr, chain, out


def report(path, label):
    with open(path, "rb") as fh:
        buf = fh.read()
    hdr, chain, tasks = decode_tasks(buf, 0)
    port = [t for t in tasks if t["src_run"] or t["src_tot"] or t["dst_run"] or t["dst_tot"] or t["chans"]]
    print(f"\n=== {label}: {path}")
    print(f" header: td_size={hdr['td_size']:#x} td_count={hdr['td_count']} stream={hdr['task_stream_size']:#x} src={hdr['src_count']} dst={hdr['dst_count']}")
    print(f" chain walk from 0: {len(chain)} tasks reached: {chain[:8]}{'...' if len(chain) > 8 else ''}")
    print(f" tasks with channel refs or DMA counts: {len(port)}")
    for t in port:
        print(f"  td{t['n']:03d} @{t['off']:#06x} sel={t['sel']:#010x} chans={t['chans']} "
              f"src={t['src_run']:#x}/{t['src_tot']:#x} dst={t['dst_run']:#x}/{t['dst_tot']:#x} "
              f"nregs={t['nregs']} trunc={t['trunc']}")
    return hdr, chain, tasks


if __name__ == "__main__":
    report("/var/tmp/m1max-embed-recovery/prog001/model.hwx", "prog001.model.hwx (Apple original)")
    report("/var/tmp/m1max-embed-recovery/prog001/prog001.anec", "prog001.anec (converted)")
    report("/var/tmp/m1max-embed-recovery/embed-mapping.anec", "embed-mapping.anec (known good)")
