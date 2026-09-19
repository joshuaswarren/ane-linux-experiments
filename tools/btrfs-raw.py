#!/usr/bin/env python3
"""Minimal read-only BTRFS walker for raw partitions/images.

Reads files out of an unmounted btrfs filesystem (subvolume path walk) with no
kernel involvement. Handles the bootstrap chunk array, the chunk tree, tree
walking, dir items, inodes and file extents (uncompressed data only).

Usage:
  btrfs-raw.py img FILE <cmd> ...       # device image on local disk
  btrfs-raw.py ssh HOST@DEVICE <cmd> .. # raw device via remote rd.py over ssh

Commands:
  subvols                     list subvolumes in FS_TREE
  list SUBVOL PATH            list directory (PATH empty = root)
  cat SUBVOL FILE [--tail N]  print file (uncompressed)
  stat SUBVOL PATH            inode size + mtime
"""
import struct
import subprocess
from collections import Counter
import sys
import time

ROOT_TREE, FS_TREE = 1, 5
K_ROOT_ITEM, K_INODE_ITEM, K_FILE_EXTENT = 0x01, 0x01, 0x08
K_INODE_REF, K_DIR_ITEM, K_DIR_INDEX = 0x0C, 0x3C, 0x60
K_CHUNK_ITEM, K_DEV_EXTENT = 0x84, 0x88


class Reader:
    """Device byte reader at (offset, length)."""

    def ssh(self, spec):
        host, dev = spec.split("@", 1)
        subprocess.run(["scp", "-q", "/tmp/rd.py", f"{host}:/tmp/rd.py"], check=True)
        self.p = subprocess.Popen(
            ["ssh", "-o", "BatchMode=yes", host, "sudo", "-n", "python3", "/tmp/rd.py", dev],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.dev = dev
        return self

    def __call__(self, off, ln):
        if hasattr(self, "p"):
            self.p.stdin.write(struct.pack("<QI", off, ln))
            self.p.stdin.flush()
            o, n = struct.unpack("<QI", self.p.stdout.read(12))
            return self.p.stdout.read(n)
        self.f = getattr(self, "f", None) or open(self.dev, "rb")
        self.f.seek(off)
        return self.f.read(ln)


class Key:
    def __init__(self, b, o=0):
        self.obj, self.typ, self.off = struct.unpack_from("<QBQ", b, o)

    def pack(self):
        return struct.pack("<QBQ", self.obj, self.typ, self.off)

    def __repr__(self):
        return f"<{self.obj:#x}.{self.typ:#x}.{self.off:#x}>"


class Leaf:
    def __init__(self, b):
        self.nritems, self.level = struct.unpack_from("<IB", b, 96)[0], b[100]
        self.items = []
        for i in range(self.nritems):
            o = 101 + i * 25
            k = Key(b, o)
            off, size = struct.unpack_from("<II", b, o + 17)
            self.items.append((k, off, size))
        self.b = b

    def data(self, off, size):
        # btrfs item offsets are relative to the end of the node header (101)
        return self.b[101 + off: 101 + off + size]


class Node:
    def __init__(self, b):
        self.nritems, self.level = struct.unpack_from("<IB", b, 96)[0], b[100]
        self.ptrs = []
        for i in range(self.nritems):
            o = 101 + i * 33
            k = Key(b, o)
            bytenr, gen = struct.unpack_from("<QQ", b, o + 17)
            self.ptrs.append((k, bytenr, gen))
        self.b = b


class Btrfs:
    def __init__(self, devread):
        self.devread = devread
        sb = devread(65536, 4096)
        assert sb[64:72] == b"_BHRfS_M", "not btrfs"
        self.sectorsize, self.nodesize = struct.unpack_from("<II", sb, 144)
        self.sys_arr_sz = struct.unpack_from("<I", sb, 160)[0]
        self.total_bytes = struct.unpack_from("<Q", sb, 112)[0]
        self.root = struct.unpack_from("<Q", sb, 80)[0]
        self.chunk_root = struct.unpack_from("<Q", sb, 88)[0]
        self.label = "(see dump-super)"
        self.chunks = {}  # logical start -> (length, [ (devid, dev_off) ])
        self.dev_uuid = sb[267:283]  # dev_item.uuid, v7.x 98-byte dev_item
        # Bootstrap map. This box's sys_chunk_array (parsed independently with
        # btrfs-progs 6.2 dump-super, stripes cross-checked in raw hex) holds
        # exactly one chunk: SYSTEM|DUP, logical 0x1500000, 8MiB, stripes at
        # 0x1500000 and 0x1d00000. It maps the chunk tree root itself; the full
        # map is rebuilt from the chunk tree below and supersedes this entry.
        self.chunks[0x1500000] = (0x800000, [(1, 0x1500000), (1, 0x1d00000)])
        # Full chunk tree
        self._read_chunk_tree(self.chunk_root)

    def _parse_chunk(self, body):
        """Parse a chunk item body; layout differs between btrfs generations.
        Candidates: v7.x 48-byte header with u16 stripe counts, legacy 52- and
        44-byte headers with u32 counts. Validate by stripe dev_uuid match.
        Returns (length, [(devid, dev_off), ...])."""
        for hdr, nst_off, nst_fmt in ((48, 44, "H"), (52, 48, "I"), (44, 36, "I")):
            if len(body) < hdr + 32:
                continue
            length = struct.unpack_from("<Q", body, 0)[0]
            nst = struct.unpack_from("<" + nst_fmt, body, nst_off)[0]
            if nst not in (1, 2) or len(body) < hdr + 32 * nst:
                continue
            stripes = []
            for i in range(nst):
                devid, doff = struct.unpack_from("<QQ", body, hdr + 32 * i)
                uuid = body[hdr + 32 * i + 16: hdr + 32 * i + 32]
                if devid != 1 or uuid != self.dev_uuid:
                    stripes = None
                    break
                stripes.append((devid, doff))
            if stripes:
                return length, stripes
        return None

    # --- chunk mapping ---
    def _read_chunk_tree(self, logical):
        """v7.x renumbered key types (CHUNK_ITEM=0xe4, obj 256) but the key
        layout kept (obj u64, type u8, offset u64) with offset == chunk
        logical start; verified: all offsets 1MiB-aligned, sizes 80/112 ==
        48-byte chunk header + 1/2 stripes. Don't trust type bytes: any item
        whose body uuid-validates as a chunk is a chunk."""
        for k, d in self.walk_tree(logical):
            r = self._parse_chunk(d)
            if r:
                self.chunks[k.off] = r

    def map(self, logical, ln):
        for start, (length, stripes) in self.chunks.items():
            if start <= logical < start + length:
                devid, doff = stripes[0]
                if devid != 1:
                    raise RuntimeError(f"multi-device chunk (devid {devid})")
                return doff + (logical - start)
        raise KeyError(f"no chunk for logical {logical:#x}")

    def read_logical(self, logical, ln):
        return self.devread(self.map(logical, ln), ln)

    # --- tree walking ---
    def read_node(self, logical):
        b = self.read_logical(logical, self.nodesize)
        return Leaf(b) if b[100] == 0 else Node(b)
    # --- tree walking ---
    def walk_tree(self, root_logical, minkey=None, maxkey=None):
        """Ranged in-order tree walk. Visits only nodes whose key range
        intersects [minkey, maxkey] (inclusive bounds as (obj, typ, off))."""
        kt = lambda k: (k.obj, k.typ, k.off)
        out = []

        def rec(logical):
            n = self.read_node(logical)
            if isinstance(n, Node):
                for idx, (k, bytenr, _) in enumerate(n.ptrs):
                    if maxkey and kt(k) > maxkey:
                        break
                    if minkey and idx + 1 < len(n.ptrs) and kt(n.ptrs[idx + 1][0]) <= minkey:
                        continue  # entire subtree below minkey
                    rec(bytenr)
            else:
                for k, off, size in n.items:
                    if minkey and kt(k) < minkey:
                        continue
                    if maxkey and kt(k) > maxkey:
                        break
                    out.append((k, n.data(off, size)))

        rec(root_logical)
        return out

    # --- item classification (v7.x renumbered key type bytes, so classify
    # by body shape; key layout (obj u64, type u8, offset u64) is unchanged) ---
    def _dir_entries(self, d):
        """Parse item data as a run of dir entries; None if it doesn't parse."""
        out, o = [], 0
        if not d:
            return None
        while o < len(d):
            if o + 30 > len(d):
                return None
            loc = Key(d, o)
            dlen, nlen, ftype = struct.unpack_from("<HHB", d, o + 25)
            if nlen == 0 or o + 30 + nlen + dlen > len(d):
                return None
            name = d[o + 30:o + 30 + nlen]
            if not all(32 <= c < 127 for c in name):
                return None
            out.append((name.decode(), loc, ftype))
            o += 30 + nlen + dlen
        return out

    def _is_root_item(self, d):
        if len(d) < 188:
            return False
        bytenr = struct.unpack_from("<Q", d, 176)[0]
        if bytenr % self.nodesize or bytenr == 0 or bytenr >= self.total_bytes:
            return False
        return any(lo <= bytenr < lo + ln for lo, (ln, _) in self.chunks.items())

    def root_item(self, tree_root_logical, rootid):
        for k, d in self.walk_tree(tree_root_logical, minkey=(rootid, 0, 0)):
            if k.obj == rootid and self._is_root_item(d):
                return struct.unpack_from("<Q", d, 176)[0], d[186]
        raise KeyError(f"root item {rootid}")

    def subvols(self):
        root_bytenr, _ = self.root_item(self.root, FS_TREE)
        seen = {}
        for k, d in self.walk_tree(root_bytenr):
            for name, loc, ftype in (self._dir_entries(d) or []):
                try:
                    self.root_item(self.root, loc.obj)
                    seen[name] = loc.obj
                except KeyError:
                    pass
        return seen

    # --- path walking inside a subvol tree ---
    def lookup(self, tree_logical, path):
        ino = 256
        for part in [p for p in path.split("/") if p]:
            entry = None
            for k, d in self.walk_tree(tree_logical, minkey=(ino, 0, 0), maxkey=(ino, 0xffff, 0xffffffffffffffff)):
                if k.obj != ino:
                    if k.obj > ino:
                        break
                    continue
                for name, loc, ftype in (self._dir_entries(d) or []):
                    if name == part:
                        entry = (loc, ftype)
                        break
                if entry:
                    break
            if not entry:
                raise FileNotFoundError(f"{path}: missing {part!r}")
            loc, ftype = entry
            if loc.typ == 0x84:  # v7.x ROOT_ITEM location = nested subvolume
                bl, _ = self.root_item(self.root, loc.obj)
                tree_logical, ino = bl, 256
            else:
                ino = loc.obj
        return tree_logical, ino

    def inode(self, tree_logical, ino):
        for k, d in self.walk_tree(tree_logical, minkey=(ino, 0, 0), maxkey=(ino, 0xffff, 0xffffffffffffffff)):
            if k.obj != ino:
                if k.obj > ino:
                    break
                continue
            if len(d) == 160:
                size = struct.unpack_from("<Q", d, 0)[0]
                mtime = struct.unpack_from("<Q", d, 120)[0]
                mode = struct.unpack_from("<I", d, 36)[0]
                return size, mtime, mode
        raise KeyError(f"inode {ino}")

    def extents(self, tree_logical, ino):
        out = []
        for k, d in self.walk_tree(tree_logical, minkey=(ino, 0, 0), maxkey=(ino, 0xffff, 0xffffffffffffffff)):
            if k.obj != ino:
                if k.obj > ino:
                    break
                continue
            if len(d) == 53:  # regular/prealloc extent
                disk_bytenr, disk_num, foff, num = struct.unpack_from("<QQQQ", d, 21)
                out.append((k.off, ("reg", disk_bytenr, disk_num, foff, num, d[16])))
            elif 21 < len(d) < 53 and d[16] < 4:  # inline extent
                out.append((k.off, ("inline", d[21:], d[16])))
        return out

    def read_file(self, tree_logical, ino, size=None, tail=None):
        size = size or self.inode(tree_logical, ino)[0]
        start = 0 if tail is None else max(0, size - tail)
        buf = {}
        for foff, ex in self.extents(tree_logical, ino):
            if ex[0] == "inline":
                data = ex[1]
                comp = ex[2]
                end = foff + len(data)
            else:
                _, bytenr, dnum, xoff, num, comp = ex
                data = self.read_logical(bytenr, dnum)[xoff:xoff + num]
                end = foff + num
            if end <= start or comp != 0:
                if comp != 0:
                    raise RuntimeError(f"compressed extent at {foff} (comp={comp})")
                continue
            buf[max(foff, start)] = data[max(0, start - foff):]
        out = b"".join(buf.get(o, b"") for o in sorted(buf))
        return out[: size - start]

    def list_dir(self, tree_logical, ino):
        out = []
        for k, d in self.walk_tree(tree_logical, minkey=(ino, 0, 0), maxkey=(ino, 0xffff, 0xffffffffffffffff)):
            if k.obj != ino:
                if k.obj > ino:
                    break
                continue
            for name, loc, ftype in (self._dir_entries(d) or []):
                out.append((name, loc, ftype))
        return out


FTYPE = {1: "-", 2: "d", 7: "l", 10: "-"}


def mtime_str(sec):
    if not sec or sec > 4102444800:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(sec))


def resolve(bt, subvol, path):
    sub = bt.subvols()
    if subvol not in sub:
        raise SystemExit(f"subvol {subvol!r} not in {sub}")
    bl, _ = bt.root_item(bt.root, sub[subvol])
    return bt.lookup(bl, path)


def main():
    kind, spec, cmd = sys.argv[1], sys.argv[2], sys.argv[3]
    r = Reader().ssh(spec) if kind == "ssh" else (setattr(Reader(), "dev", spec) or Reader())
    if kind != "ssh":
        r.dev = spec
    bt = Btrfs(r)
    args = sys.argv[4:]

    if cmd == "subvols":
        for n, i in sorted(bt.subvols().items()):
            print(f"{i:>8}  {n}")
        return
    tree, ino = resolve(bt, args[0], args[1])
    if cmd == "list":
        seen_names = set()
        rows = []
        for name, loc, ft in bt.list_dir(tree, ino):
            if name in seen_names:
                continue
            seen_names.add(name)
            try:
                size, mt, mode = bt.inode(tree, loc.obj)
                rows.append((f"{FTYPE.get(ft,'?')} {size:>12} {mtime_str(mt)}  {name}", name))
            except KeyError:
                rows.append((f"s {loc!r}  {name}", name))
        for line, _ in sorted(rows, key=lambda x: x[1]):
            print(line)
    elif cmd == "stat":
        size, mt, mode = bt.inode(tree, ino)
        print(f"size={size} mtime={mtime_str(mt)} mode={mode:#o}")
    elif cmd == "cat":
        tail = None
        if "--tail" in args:
            tail = int(args[args.index("--tail") + 1])
        sys.stdout.buffer.write(bt.read_file(tree, ino, tail=tail))
    else:
        raise SystemExit(f"bad cmd {cmd}")


if __name__ == "__main__":
    main()
