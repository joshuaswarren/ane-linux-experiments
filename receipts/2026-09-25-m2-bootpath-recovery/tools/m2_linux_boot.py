"""One proxy session: pull the M2's Linux boot files (first catch only) and
chainload the kernel over the m1n1 proxy, bypassing U-Boot.

Usage: m2_linux_boot.py <cache-dir> [extra bootargs...]
The session must not close between extraction and boot: 43ec stage 1 falls
through to U-Boot the moment the proxy client disconnects.
The boot sequence is tools/linux.py's, inlined so it shares this session.
"""
import gzip
import json
import os
import re
import subprocess
import sys

os.environ.setdefault("M1N1DEVICE", "/dev/ttyACM0")
from m1n1.setup import *  # noqa: E402,F401,F403

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m2boot  # noqa: E402

cache = sys.argv[1]
extra = " ".join(sys.argv[2:])
print("chipid", hex(p.get_chipid()), flush=True)
# iBoot routes boots to recoveryOS once its failure counter builds up;
# only a booted OS clears it, and U-Boot hangs never reach one.
try:
    from m1n1.hw.pmu import PMU
    PMU(u).reset_panic_counter()
    print("panic counter reset", flush=True)
except Exception as e:  # noqa: BLE001 - log and boot anyway
    print("pmu reset_panic_counter:", e, flush=True)
manifest_path = os.path.join(cache, "manifest.json")
if not os.path.exists(manifest_path):
    print("nvme_init", p.nvme_init(), flush=True)
    parts = m2boot.gpt()
    for pt in parts:
        print(f"part{pt['n']} {pt['name']!r} {pt['fs']} lba {pt['first']}-{pt['last']}", flush=True)
    m2boot.extract_boot(parts, cache)
    print("nvme_shutdown", p.nvme_shutdown(), flush=True)
manifest = json.load(open(manifest_path))


def load(rel):
    return open(os.path.join(cache, rel.replace("/", "__")), "rb").read()


def rel_of(path):
    """grub paths are relative to the /boot partition root."""
    rel = path.lstrip("/")
    if rel not in manifest:
        raise SystemExit(f"grub names {path}, not extracted: {sorted(manifest)}")
    return rel


# Boot exactly what grub's first menuentry boots (grub-mkconfig default 0).
if "grub/grub.cfg" not in manifest:
    raise SystemExit("no grub/grub.cfg on /boot")
cfg = load("grub/grub.cfg").decode(errors="replace")
print("grub:", [ln.strip() for ln in cfg.splitlines() if ln.strip().startswith("set default")],
      re.findall(r"menuentry\s+['\"]([^'\"]*)", cfg), flush=True)
body = re.search(r"menuentry\s[^{]*\{(.*?)\n\s*\}", cfg, re.S)
if not body:
    raise SystemExit("no menuentry in grub.cfg")
body = body.group(1)
lin = re.search(r"^\s*linux\s+(\S+)\s*(.*)$", body, re.M)
ini = re.search(r"^\s*initrd\s+(.+)$", body, re.M)
dtl = re.search(r"^\s*devicetree\s+(\S+)", body, re.M)
if not lin or not ini:
    raise SystemExit(f"first menuentry lacks linux/initrd: {body!r}")
kname = rel_of(lin.group(1))
inames = [rel_of(x) for x in ini.group(1).split()]
if dtl:
    dname = rel_of(dtl.group(1))
else:
    dname = [k for k in manifest if k.endswith("t6021-j414c.dtb")]
    if not dname:
        raise SystemExit(f"no devicetree line and no t6021-j414c.dtb in {sorted(manifest)}")
    dname = dname[0]
bootargs = f"{lin.group(2).strip()} {extra}".strip()
print("kernel", kname, "initrd", inames, "dtb", dname, "(grub devicetree)" if dtl else "(package dtb)",
      flush=True)
print("bootargs", bootargs, flush=True)

kdata = load(kname)
if kdata[:2] == b"\x1f\x8b":
    comp, payload = "gz", kdata
elif kdata[0x38:0x3c] == b"ARM\x64":
    comp, payload = "none", kdata
elif kdata[:2] == b"MZ" and kdata[4:8] == b"zimg":
    off, size = int.from_bytes(kdata[8:12], "little"), int.from_bytes(kdata[12:16], "little")
    ctype = kdata[24:56].split(b"\0")[0].decode()
    body = kdata[off:off + size]
    if ctype == "gzip":
        comp, payload = "gz", body
    else:
        payload = subprocess.run(["zstd" if ctype == "zstd" else ctype, "-dc"], input=body,
                                 check=True, capture_output=True).stdout
        comp = "none"
    print("zboot", ctype, flush=True)
else:
    raise SystemExit(f"unknown kernel format {kdata[:8].hex()}")
if comp == "gz":
    # Validate host-side before sending; m1n1 decompresses on the device.
    raw_len = len(gzip.decompress(payload))
    print("gz ok, raw", raw_len, flush=True)
dtb = load(dname)
initramfs = b"".join(load(x) for x in inames)

p.kboot_set_chosen("bootargs", bootargs)
if comp == "gz":
    compressed_addr = u.malloc(len(payload))
    print(f"Loading {len(payload)} compressed bytes", flush=True)
    iface.writemem(compressed_addr, payload, True)
dtb_addr = u.malloc(len(dtb))
iface.writemem(dtb_addr, dtb)
kernel_size = 512 * 1024 * 1024
kernel_base = u.memalign(2 * 1024 * 1024, kernel_size)
initramfs_base = u.memalign(65536, len(initramfs))
print(f"Loading {len(initramfs)} initramfs bytes", flush=True)
iface.writemem(initramfs_base, initramfs, True)
p.kboot_set_initrd(initramfs_base, len(initramfs))
p.cpufreq_init()
p.smp_start_secondaries()
if p.kboot_prepare_dt(dtb_addr):
    raise SystemExit("DT prepare failed")
iface.dev.timeout = 40
if comp == "none":
    kernel_size = len(payload)
    iface.writemem(kernel_base, payload, True)
else:
    kernel_size = p.gzdec(compressed_addr, len(payload), kernel_base, kernel_size)
if kernel_size < 0:
    raise SystemExit("Decompression error")
print("kernel bytes", kernel_size, flush=True)
p.dc_cvau(kernel_base, kernel_size)
p.ic_ivau(kernel_base, kernel_size)
u.msr(DAIF, 0xc0)
print("BOOTING", flush=True)
p.kboot_boot(kernel_base)
