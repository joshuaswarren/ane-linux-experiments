#!/usr/bin/env python3
"""Minimal FAT32 reader for raw partition images (e.g. Asahi ESP on hosts
where msdosfs mount is broken). Read-only: list and extract files.

Usage:
  fat32-raw.py list   IMG [path]
  fat32-raw.py cat    IMG path
  fat32-raw.py extract IMG path DEST
"""
import sys
import struct


class Fat32:
    def __init__(self, path):
        self.f = open(path, "rb")
        bpb = self.f.read(512)
        self.byts_per_sec = struct.unpack_from("<H", bpb, 11)[0]
        self.sec_per_clus = bpb[13]
        self.rsvd = struct.unpack_from("<H", bpb, 14)[0]
        self.num_fats = bpb[16]
        self.fatsz = struct.unpack_from("<I", bpb, 36)[0]
        self.rootclus = struct.unpack_from("<I", bpb, 44)[0]
        self.fat_off = self.rsvd * self.byts_per_sec
        self.data_off = (self.rsvd + self.num_fats * self.fatsz) * self.byts_per_sec
        self.clus_sz = self.sec_per_clus * self.byts_per_sec
        self._fat = None

    @property
    def fat(self):
        if self._fat is None:
            n = self.fatsz * self.byts_per_sec
            self.f.seek(self.fat_off)
            self._fat = self.f.read(n)
        return self._fat

    def next(self, clus):
        v = struct.unpack_from("<I", self.fat, clus * 4)[0] & 0x0FFFFFFF
        return None if v >= 0x0FFFFFF8 else v

    def chain(self, clus):
        out = []
        while clus and clus < 0x0FFFFFF8:
            out.append(clus)
            clus = self.next(clus)
            if len(out) > 1 << 22:
                raise RuntimeError("FAT chain runaway")
        return out

    def read_clus(self, clus):
        self.f.seek(self.data_off + (clus - 2) * self.clus_sz)
        return self.f.read(self.clus_sz)

    def read_chain(self, clus, size=None):
        data = b"".join(self.read_clus(c) for c in self.chain(clus))
        return data[:size] if size is not None else data

    def entries(self, clus):
        data = self.read_chain(clus)
        out, lfn = [], []
        for i in range(0, len(data), 32):
            e = data[i:i + 32]
            if e[0] == 0:
                break
            if e[0] == 0xE5 or e[11] == 0x0F:
                if e[11] == 0x0F and e[0] != 0xE5:
                    part = e[1:11] + e[14:26] + e[28:32]
                    lfn.append(part.decode("utf-16le").split("\uffff")[0].split("\x00")[0])
                continue
            name = e[0:8].decode("ascii", "replace").rstrip()
            ext = e[8:11].decode("ascii", "replace").rstrip()
            short = name + ("." + ext if ext else "")
            longname = "".join(reversed(lfn)) if lfn else None
            lfn = []
            attr = e[11]
            clus_hi, clus_lo = struct.unpack_from("<H", e, 20)[0], struct.unpack_from("<H", e, 26)[0]
            out.append({
                "name": longname or short,
                "short": short,
                "dir": bool(attr & 0x10),
                "size": struct.unpack_from("<I", e, 28)[0],
                "clus": (clus_hi << 16) | clus_lo,
            })
        return out

    def lookup(self, path):
        clus, name = self.rootclus, ""
        for part in [p for p in path.split("/") if p]:
            hit = next((e for e in self.entries(clus) if e["name"].lower() == part.lower()), None)
            if not hit:
                raise FileNotFoundError(f"{path}: no {part!r} (at /{name})")
            clus, name = hit["clus"], hit["name"]
            if not hit["dir"]:
                return hit
        return {"name": name, "dir": True, "size": 0, "clus": clus}

    def read(self, path):
        e = self.lookup(path)
        if e["dir"]:
            raise IsADirectoryError(path)
        return self.read_chain(e["clus"], e["size"])


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("list", "cat", "extract"):
        sys.exit(__doc__)
    fs, cmd, img = Fat32(sys.argv[2]), sys.argv[1], sys.argv[2]
    path = sys.argv[3] if len(sys.argv) > 3 else "/"
    if cmd == "list":
        e = fs.lookup(path)
        for x in (fs.entries(e["clus"]) if e["dir"] else [e]):
            print(f"{'d' if x['dir'] else '-'} {x['size']:>10} {x['clus']:#010x}  {x['name']}")
    elif cmd == "cat":
        sys.stdout.buffer.write(fs.read(path))
    else:
        open(sys.argv[4], "wb").write(fs.read(path))
        print(f"wrote {sys.argv[4]}")


if __name__ == "__main__":
    main()
