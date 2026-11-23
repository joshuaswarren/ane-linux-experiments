"""Regression tests for tools/hwx_normalise.cpp (issue #12 review fixes).

Containers are synthesised with the field layout the normaliser and the
kernel validator parse (see the H16/H17 header contract in hwx_check.py).
Fixes covered: command-area and per-command bounds checks, text/symtab
bounds, surface-slot cap, note/annotation pairing, atomic writeback, and
the H13 rejection the capture-kit gate relies on.
"""

import os
import re
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SRC = ROOT / "tools" / "hwx_normalise.cpp"
FRESH64 = ROOT / "tools" / "fresh-64.hwx.sample"  # real ANECCompile H13 output

MAGIC = 0xBEEFFACE
H16, H17, H13 = 7, 9, 4


def u32(v):
    return struct.pack("<I", v)


def u64(v):
    return struct.pack("<Q", v)


def command(cmd, body, declared_len=None):
    """One command: 8-byte header + body, zero-padded to a multiple of 8.
    declared_len overrides the length word (for malformed fixtures)."""
    pad = (-len(body)) % 8
    body = body + b"\0" * pad
    return u32(cmd) + u32(8 + len(body) if declared_len is None else declared_len) + body


def section(sectname, offset=0, size=0, reloff=0):
    return (sectname.encode().ljust(16, b"\0") + b"\0" * 16 + u64(0) + u64(size) +
            u32(offset) + u32(0) + u32(reloff) + u32(0) * 6)


def segment(segname, vmaddr, nsects=(), declared_nsects=None, declared_len=None):
    body = (segname.encode().ljust(16, b"\0") + u64(vmaddr) + u64(0) + u64(0) + u64(0) +
            u32(0) + u32(0) +
            u32(len(nsects) if declared_nsects is None else declared_nsects) +
            u32(0))
    for name, offset, size in nsects:
        body += section(name, offset, size)
    return command(0x19, body, declared_len=declared_len)


def annotation(text, declared_len=None):
    return command(8, text + b"\0", declared_len=declared_len)


def note(text, declared_len=None):
    return command(0x31, text + b"\0", declared_len=declared_len)


def program():
    return command(4, u32(4) + b"\0" * (0x8A0 - 12))


def symtab_cmd(symoff, nsyms, stroff, strsize):
    return command(2, u32(symoff) + u32(nsyms) + u32(stroff) + u32(strsize))


def symbol(strx, ntype, sect, value=0x1000):
    return u32(strx) + bytes([ntype, sect]) + b"\0" * 2 + u64(value)


def container(subtype, cmds, text_bytes=b"\0" * 32, syms=b"", strtab=b"\0"):
    header = (u32(MAGIC) + u32(0x80) + u32(subtype) + u32(2) +
              u32(len(cmds)) + u32(sum(len(c) for c in cmds)) +
              u32(0x200000) + u32(0))
    text_off = len(header) + sum(len(c) for c in cmds)
    offs = {"text_data_off": text_off, "symoff": text_off + len(text_bytes),
            "stroff": text_off + len(text_bytes) + len(syms)}
    return header + b"".join(cmds) + text_bytes + syms + strtab, offs


def valid_cmds(surfaces=2, with_symtab=True):
    """Minimal command set the normaliser accepts: __text segment, N surface
    segments, kernel, annotation+note pair, 0x8a0 program, symtab."""
    cmds = [segment("__TEXT", 0x10000, [("__text", 0, 32)])]
    for i in range(surfaces):
        cmds.append(segment("__FVMLIB", 0x200000 + i * 0x1000))
    cmds.append(segment("__KERN_0", 0x30000))
    cmds += [annotation(b"version"), note(b"rtv=1"), program()]
    if with_symtab:
        cmds.append(symtab_cmd(0, 2, 0, 8))
    return cmds


def valid_file(subtype=H17, surfaces=2):
    """Fully wired valid container; symtab/__text fields point at the data
    region. Returns (bytes, command offsets, field offsets)."""
    syms = symbol(1, 0x0E, 1) + symbol(0, 0x66, 0)  # section sym + stab
    strtab = b"\0__text\0"
    cmds = valid_cmds(surfaces)
    _, offs = container(subtype, cmds, syms=syms, strtab=strtab)
    cmds[0] = segment("__TEXT", 0x10000, [("__text", offs["text_data_off"], 32)])
    cmds[-1] = symtab_cmd(offs["symoff"], 2, offs["stroff"], len(strtab))
    b, offs = container(subtype, cmds, syms=syms, strtab=strtab)
    return b, cmd_offsets(b), offs


def cmd_offsets(buf):
    """File offsets of each command, walked by the header's command count."""
    count = struct.unpack_from("<I", buf, 16)[0]
    pos, out = 32, []
    for _ in range(count):
        out.append(pos)
        pos += struct.unpack_from("<I", buf, pos + 4)[0]
    return out


def field(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


@pytest.fixture(scope="session")
def norm_bin(tmp_path_factory):
    binary = tmp_path_factory.mktemp("norm") / "hwx-normalise"
    r = subprocess.run(["g++", "-std=c++17", "-O2", "-o", str(binary), str(SRC)],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"normaliser build failed:\n{r.stderr}"
    return binary


@pytest.fixture(scope="session")
def norm_bin_asan(tmp_path_factory):
    binary = tmp_path_factory.mktemp("norm-asan") / "hwx-normalise-asan"
    r = subprocess.run(["g++", "-std=c++17", "-O1", "-fsanitize=address",
                        "-o", str(binary), str(SRC)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip(f"no ASan toolchain: {r.stderr.strip()[:200]}")
    return binary


def run_norm(binary, path):
    cmd = [str(binary), str(path)]
    # This host's ASan flakes ~25% of runs on any binary (high-ASLR entropy);
    # setarch -R disables ASLR and stops the noise without hiding real OOB.
    if shutil.which("setarch"):
        cmd = ["setarch", os.uname().machine, "-R", *cmd]
    return subprocess.run(cmd, capture_output=True, text=True,
                          env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0"})


def assert_unchanged(r, original, path):
    assert r.returncode != 0, f"expected rejection, got rc 0: {r.stdout}"
    assert Path(path).read_bytes() == original, "failed run modified the file"
    assert not list(Path(path).parent.glob("*.hwx-normalise-tmp")), \
        "failed run left a temp file behind"


# ---- malformed corpus: every entry must be rejected, file untouched ----

def malformed_cases():
    cases = {}

    # 40-byte file whose header claims a 0x1000-byte command area.
    cases["command_area_past_eof"] = (
        u32(MAGIC) + u32(0x80) + u32(H17) + u32(2) + u32(1) + u32(0x1000) +
        u32(0x200000) + u32(0) + u32(4) + u32(8))

    # __TEXT segment of exactly 64 physical bytes (len 64 < the 72-byte fixed
    # part): the nsects field would be read from the next command.
    cases["segment_shorter_than_fixed_part"] = container(H17, [
        command(0x19, b"__TEXT\0".ljust(16, b"\0") + u64(0x10000) + u64(0) +
                u64(0) + u64(0) + u32(0) + u32(0) + u32(1) + u32(0),
                declared_len=64),
        *valid_cmds()[1:]])[0]

    # __TEXT segment claiming two sections but reserving room for one.
    cases["segment_sections_exceed_command"] = container(H17, [
        segment("__TEXT", 0x10000, [("__text", 0x100, 32)], declared_nsects=2),
        *valid_cmds()[1:]])[0]

    # cmd 4 with len 8 at end of file: reading pos+8 must not happen.
    cases["program_command_too_short"] = (
        u32(MAGIC) + u32(0x80) + u32(H17) + u32(2) + u32(1) + u32(8) +
        u32(0x200000) + u32(0) + u32(4) + u32(8))

    # LC_SYMTAB with a consistent but non-24 length.
    cases["symtab_bad_length"] = container(H17, valid_cmds()[:-1] + [
        u32(2) + u32(16) + b"\0" * 8])[0]

    # LC_SYMTAB whose symbol table lies past EOF.
    cmds = valid_cmds()
    cmds[-1] = u32(2) + u32(24) + u32(0xFFFFFF) + u32(1) + u32(0) + u32(8)
    cases["symtab_past_eof"] = container(H17, cmds)[0]

    # __text section whose offset sits 2 bytes before EOF (put32 writes 4).
    b, pos, offs = valid_file()
    buf = bytearray(b)
    struct.pack_into("<I", buf, pos[0] + 72 + 48, len(buf) - 2)
    cases["text_offset_past_eof"] = bytes(buf)

    # Five surfaces: kernel_vm must not be silently dropped from a 5-slot table.
    cases["too_many_surfaces"] = valid_file(surfaces=5)[0]

    # Note with no preceding annotation.
    cases["note_without_annotation"] = container(
        H17, valid_cmds()[:4] + [note(b"rtv=1")] + valid_cmds()[5:])[0]

    # Annotation, then the program, then the note: annotation is not adjacent.
    syms = symbol(1, 0x0E, 1) + symbol(0, 0x66, 0)
    cmds = valid_cmds()[:4] + [annotation(b"version"), program(),
                               note(b"rtv=1"), symtab_cmd(0, 2, 0, 8)]
    _, offs = container(H17, cmds, syms=syms)
    cmds[0] = segment("__TEXT", 0x10000, [("__text", offs["text_data_off"], 32)])
    cmds[7] = symtab_cmd(offs["symoff"], 2, offs["stroff"], 8)
    cases["note_detached_from_annotation"] = container(H17, cmds, syms=syms)[0]

    # H13 container.
    cases["h13_subtype"] = valid_file(subtype=H13)[0]

    # Annotation + note merge would exceed 4096.
    cmds = valid_cmds()
    cmds[4] = annotation(b"v", declared_len=4088)
    cases["merged_annotation_too_big"] = container(H17, cmds)[0]

    return cases


MALFORMED = malformed_cases()

EXPECTED_MSG = {
    "command_area_past_eof": "command area",
    "segment_shorter_than_fixed_part": "segment command",
    "segment_sections_exceed_command": "section",
    "symtab_bad_length": "symbol table command",
    "symtab_past_eof": "symbol table",
    "text_offset_past_eof": "text",
    "too_many_surfaces": "surfaces",
    "note_detached_from_annotation": "annotation does not end",
    "h13_subtype": "subtype",
}


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_malformed_rejected_and_file_untouched(norm_bin, tmp_path, name):
    original = MALFORMED[name]
    p = tmp_path / "bad.hwx"
    p.write_bytes(original)
    r = run_norm(norm_bin, p)
    assert_unchanged(r, original, p)
    if name in EXPECTED_MSG:
        assert EXPECTED_MSG[name] in r.stderr, r.stderr


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_malformed_rejected_under_asan(norm_bin_asan, tmp_path, name):
    original = MALFORMED[name]
    p = tmp_path / "bad.hwx"
    p.write_bytes(original)
    r = run_norm(norm_bin_asan, p)
    assert "AddressSanitizer" not in r.stderr, f"OOB on {name}:\n{r.stderr}"
    assert r.returncode != 0


def test_rejects_real_h13_sample(norm_bin, tmp_path):
    p = tmp_path / "fresh64.hwx"
    shutil.copy(FRESH64, p)
    original = p.read_bytes()
    r = run_norm(norm_bin, p)
    assert_unchanged(r, original, p)
    assert "subtype" in r.stderr


def test_usage_exit_code(norm_bin):
    assert subprocess.run([str(norm_bin)], capture_output=True).returncode == 2
    r = subprocess.run([str(norm_bin), "a", "b"], capture_output=True)
    assert r.returncode == 2


# ---- success paths ----

def run_valid(binary, tmp_path, name, subtype=H17, surfaces=2):
    b, pos, offs = valid_file(subtype=subtype, surfaces=surfaces)
    p = tmp_path / name
    p.write_bytes(b)
    r = run_norm(binary, p)
    return b, pos, offs, r, p


def test_normalises_h17(norm_bin, tmp_path):
    original, pos, offs, r, p = run_valid(norm_bin, tmp_path, "h17.hwx")
    assert r.returncode == 0, r.stderr
    out = p.read_bytes()
    assert len(out) == len(original)
    text_seg, ann, note_pos, prog, sym = pos[0], pos[4], pos[5], pos[6], pos[7]
    assert field(out, text_seg + 68) == 0                    # __TEXT flags
    assert field(out, offs["text_data_off"]) == 0            # H17 prologue
    assert field(out, prog + 0x880) == 0x461C4000            # trailer
    assert field(out, prog + 0x60) == 0 and field(out, prog + 0x64) == 0
    assert field(out, 16) == 7                               # 8 cmds - 1 note
    assert field(out, ann + 4) == 32                         # merged annotation
    assert out[note_pos:note_pos + 16] == b"\0" * 16         # note zeroed
    # base table: surfaces then kernel, zero tails
    slots = [struct.unpack_from("<Q", out, prog + 0x70 + i * 16)[0]
             for i in range(5)]
    assert slots == [0x200000, 0x201000, 0x30000, 0, 0]
    assert struct.unpack_from("<Q", out, prog + 0x78)[0] == 0
    assert field(out, sym + 12) == 1                         # stab dropped
    assert out[offs["symoff"] + 16:offs["symoff"] + 32] == b"\0" * 16
    assert re.search(r"1 note command\(s\) removed, 1 symbols kept", r.stdout)


def test_normalises_h16_prologue_word(norm_bin, tmp_path):
    _, _, offs, r, p = run_valid(norm_bin, tmp_path, "h16.hwx", subtype=H16)
    assert r.returncode == 0, r.stderr
    assert field(p.read_bytes(), offs["text_data_off"]) == 1


def test_interleaved_annotation_note_pairs(norm_bin, tmp_path):
    """A note must fold into the annotation recorded at parse time, so a
    later annotation cannot break or corrupt an earlier fold."""
    syms = symbol(1, 0x0E, 1) + symbol(0, 0x66, 0)
    cmds = valid_cmds()[:4] + [annotation(b"a1"), note(b"n1"),
                               annotation(b"a2"), note(b"n2"), program(),
                               symtab_cmd(0, 2, 0, 8)]
    _, offs = container(H17, cmds, syms=syms)
    cmds[0] = segment("__TEXT", 0x10000, [("__text", offs["text_data_off"], 32)])
    cmds[-1] = symtab_cmd(offs["symoff"], 2, offs["stroff"], 8)
    b, _ = container(H17, cmds, syms=syms)
    pos = cmd_offsets(b)  # 10 commands
    p = tmp_path / "pairs.hwx"
    p.write_bytes(b)
    r = run_norm(norm_bin, p)
    assert r.returncode == 0, r.stderr
    out = p.read_bytes()
    assert field(out, 16) == 8                    # 10 commands - 2 notes
    assert field(out, pos[4] + 4) == 32           # a1 folded over n1
    assert field(out, pos[6] + 4) == 32           # a2 folded over n2
    assert out[pos[5]:pos[5] + 16] == b"\0" * 16
    assert out[pos[7]:pos[7] + 16] == b"\0" * 16


def test_idempotent(norm_bin, tmp_path):
    _, _, _, r1, p = run_valid(norm_bin, tmp_path, "idem.hwx")
    assert r1.returncode == 0, r1.stderr
    once = p.read_bytes()
    r2 = run_norm(norm_bin, p)
    assert r2.returncode == 0, r2.stderr
    assert p.read_bytes() == once
    assert "0 note command(s) removed" in r2.stdout


def test_success_leaves_no_temp_file(norm_bin, tmp_path):
    _, _, _, r, p = run_valid(norm_bin, tmp_path, "clean.hwx")
    assert r.returncode == 0
    assert [q.name for q in p.parent.iterdir()] == ["clean.hwx"]


def test_success_under_asan(norm_bin_asan, tmp_path):
    _, _, _, r, p = run_valid(norm_bin_asan, tmp_path, "asan.hwx")
    assert r.returncode == 0, r.stderr
    assert "AddressSanitizer" not in r.stderr
