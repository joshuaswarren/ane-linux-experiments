import plistlib

D = "~/.local/share/apple-silicon-lab/artifacts/jwm1-parity/macos-window6/"
with open(D + "iodevicetree.plist", "rb") as f:
    root = plistlib.load(f)


def walk(node, path=""):
    name = node.get("IORegistryEntryName", "?")
    yield path + "/" + name, node
    for c in node.get("IORegistryEntryChildren", []) or []:
        yield from walk(c, path + "/" + name)


for p, n in walk(root[0] if isinstance(root, list) else root):
    if p.endswith("/arm-io/ane") or p.endswith("/arm-io/dart-ane"):
        print("=====", p)
        for k in sorted(n):
            if k in ("IORegistryEntryChildren", "IOReportLegend", "IOReportLegendPublic"):
                continue
            v = n[k]
            if isinstance(v, bytes):
                v = v.hex() if len(v) <= 64 else v[:32].hex() + "...(%d bytes)" % len(v)
            print(" ", k, "=", str(v)[:300])
