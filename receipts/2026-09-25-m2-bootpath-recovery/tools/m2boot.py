"""M2 boot-partition access over the m1n1 proxy (NVMe reads only).

gpt() lists partitions with a filesystem guess; extract_boot() copies the
Linux boot files out of the ext4 /boot partition with a minimal extent-only
ext4 reader. The caller owns nvme_init/nvme_shutdown.
"""
import hashlib
import json
import os
import re
import struct
import uuid

from m1n1.setup import iface, p, u

LBA = 4096
BATCH = 64
_buf = None


def read_lbas(lba, n=1):
    global _buf
    if _buf is None:
        _buf = u.heap.memalign(LBA, LBA * BATCH)
    data = bytearray()
    while n:
        k = min(n, BATCH)
        for i in range(k):
            if not p.nvme_read(1, lba + i, _buf + LBA * i):
                raise RuntimeError(f"nvme_read FAIL lba {lba + i}")
        data += iface.readmem(_buf, LBA * k)
        lba += k
        n -= k
    return bytes(data)


def gpt():
    h = read_lbas(1)
    if h[:8] != b"EFI PART":
        raise RuntimeError("no GPT at LBA 1")
    ent_lba, n_ent, ent_sz = struct.unpack_from("<QII", h, 72)
    raw = read_lbas(ent_lba, (n_ent * ent_sz + LBA - 1) // LBA)
    parts = []
    for i in range(n_ent):
        e = raw[i * ent_sz:(i + 1) * ent_sz]
        if not any(e[:16]):
            continue
        first, last = struct.unpack_from("<QQ", e, 32)
        head = read_lbas(first)
        if head[1080:1082] == b"\x53\xef":
            fs = "ext4"
        elif head[:6] == b"LUKS\xba\xbe":
            fs = "luks"
        elif head[82:87] == b"FAT32" or head[54:59] in (b"FAT16", b"FAT12"):
            fs = "fat"
        elif head[32:36] == b"NXSB":
            fs = "apfs"
        elif read_lbas(first + 16)[0x40:0x48] == b"_BHRfS_M":
            fs = "btrfs"
        else:
            fs = "unknown"
        parts.append({"n": i + 1, "type": str(uuid.UUID(bytes_le=e[:16])),
                      "first": first, "last": last, "fs": fs,
                      "name": e[56:128].decode("utf-16-le").rstrip("\0")})
    return parts


class Ext4:
    def __init__(self, first_lba):
        self.first = first_lba
        sb = read_lbas(first_lba)[1024:2048]
        if sb[56:58] != b"\x53\xef":
            raise RuntimeError("not ext4")
        self.bsz = 1024 << struct.unpack_from("<I", sb, 24)[0]
        self.per = self.bsz // LBA
        if self.per < 1:
            raise RuntimeError("block size below the 4 KiB LBA is not handled")
        self.first_data = struct.unpack_from("<I", sb, 20)[0]
        self.ipg = struct.unpack_from("<I", sb, 40)[0]
        self.isz = struct.unpack_from("<H", sb, 88)[0]
        incompat = struct.unpack_from("<I", sb, 96)[0]
        self.dsz = struct.unpack_from("<H", sb, 254)[0] if incompat & 0x80 else 32
        self.gdt = {}

    def blocks(self, b, n=1):
        return read_lbas(self.first + b * self.per, n * self.per)

    def inode(self, num):
        g, idx = divmod(num - 1, self.ipg)
        gblk, goff = divmod(g * self.dsz, self.bsz)
        if gblk not in self.gdt:
            self.gdt[gblk] = self.blocks(self.first_data + 1 + gblk)
        d = self.gdt[gblk][goff:goff + self.dsz]
        itab = struct.unpack_from("<I", d, 8)[0]
        if self.dsz >= 64:
            itab |= struct.unpack_from("<I", d, 0x28)[0] << 32
        ib, io = divmod(idx * self.isz, self.bsz)
        return self.blocks(itab + ib)[io:io + self.isz]

    def _extents(self, node):
        magic, n, _, depth = struct.unpack_from("<HHHH", node, 0)
        if magic != 0xF30A:
            raise RuntimeError("not an extent-mapped inode")
        for i in range(n):
            e = node[12 + 12 * i:24 + 12 * i]
            if depth == 0:
                lblk, ln, hi, lo = struct.unpack("<IHHI", e)
                if ln > 32768:
                    yield lblk, None, ln - 32768
                else:
                    yield lblk, (hi << 32) | lo, ln
            else:
                _, lo, hi, _ = struct.unpack("<IIHH", e)
                yield from self._extents(self.blocks((hi << 32) | lo))

    def read(self, ino):
        i = self.inode(ino)
        size = (struct.unpack_from("<I", i, 4)[0] |
                struct.unpack_from("<I", i, 108)[0] << 32)
        data = bytearray(size)
        for lblk, pblk, ln in self._extents(i[40:100]):
            off = lblk * self.bsz
            if off >= size:
                continue
            chunk = self.blocks(pblk, ln) if pblk is not None else bytes(ln * self.bsz)
            data[off:off + len(chunk)] = chunk[:size - off]
        return bytes(data)

    def is_file(self, ino):
        return struct.unpack_from("<H", self.inode(ino), 0)[0] & 0xF000 == 0x8000

    def listdir(self, ino):
        raw = self.read(ino)
        ents, pos = {}, 0
        while pos + 8 <= len(raw):
            e_ino, rec, nl, _ = struct.unpack_from("<IHBB", raw, pos)
            if rec < 8:
                break
            if e_ino:
                ents[raw[pos + 8:pos + 8 + nl].decode(errors="replace")] = e_ino
            pos += rec
        return ents

    def lookup(self, path):
        ino = 2
        for comp in [c for c in path.split("/") if c]:
            ents = self.listdir(ino)
            if comp not in ents:
                return None
            ino = ents[comp]
        return ino


def extract_boot(parts, out):
    """Copy vmlinuz*, initramfs*, grub.cfg, loader entries and the
    t6021 DTBs from the smallest ext4 partition into out/."""
    ext = [pt for pt in parts if pt["fs"] == "ext4"]
    if not ext:
        raise RuntimeError(f"no ext4 partition: {parts}")
    part = min(ext, key=lambda pt: pt["last"] - pt["first"])
    fs = Ext4(part["first"])
    root = fs.listdir(2)
    print("boot root:", sorted(root), flush=True)
    picks = [n for n in root if n.startswith(("vmlinuz", "initramfs", "Image"))]
    gino = fs.lookup("grub/grub.cfg")
    if gino:
        picks.append("grub/grub.cfg")
        cfg = fs.read(gino).decode(errors="replace")
        picks += [m.lstrip("/") for m in re.findall(r"^\s*devicetree\s+(\S+)", cfg, re.M)]
    lino = fs.lookup("loader/entries")
    if lino:
        picks += [f"loader/entries/{n}" for n in fs.listdir(lino) if n.endswith(".conf")]
    for dtdir in ("dtbs/apple", "dtbs/linux-asahi/apple", "dtbs"):
        dino = fs.lookup(dtdir)
        if dino:
            picks += [f"{dtdir}/{n}" for n in fs.listdir(dino)
                      if "t6021" in n and n.endswith(".dtb")]
            break
    os.makedirs(out, exist_ok=True)
    manifest = {"partition": part}
    for rel in picks:
        ino = fs.lookup(rel)
        if ino is None or not fs.is_file(ino):
            print("skip", rel, flush=True)
            continue
        data = fs.read(ino)
        open(os.path.join(out, rel.replace("/", "__")), "wb").write(data)
        manifest[rel] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        print(f"got {rel} {len(data)} {manifest[rel]['sha256'][:16]}", flush=True)
    json.dump(manifest, open(os.path.join(out, "manifest.json"), "w"), indent=1)
    return manifest
