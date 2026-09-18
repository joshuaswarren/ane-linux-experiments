#!/usr/bin/env python3
"""macOS 26/27 ANE enablement capture for t6021-test-host (T6021). Run ON the Mac.

Read-only: ioreg, sysctl, system_profiler, sw_vers, plutil. No sudo, no
installs. Writes into ART_DIR (argv[1]). Stdlib only.

Patterns reused from the community quick-collector's ane_port_detail macOS
probe (parakeet-mel-exact/scripts + .local/ane-v064-wt/scripts, v0.6.4) with
the community caps REMOVED: reg blobs are captured in full (the v0.6.4 cap
truncated the 1168-byte pmgr reg to 64 bytes — the known gap).
"""
import gzip
import json
import plistlib
import re
import subprocess
import sys
from pathlib import Path

ART = Path(sys.argv[1])
ART.mkdir(parents=True, exist_ok=True)

ANE_RE = re.compile(r"^(ane\d*|dart-ane\d*|mapper-ane\d*)$")


def run(cmd, timeout=120):
    p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def u64le_ranges(blob):
    """DT `reg` blob = u64-LE (addr, size) pairs (matches the 2026-09-17
    decode: ane0 3 ranges = 48 B, pmgr 73 ranges = 1168 B)."""
    out = []
    for off in range(0, len(blob) - len(blob) % 16, 16):
        addr = int.from_bytes(blob[off:off + 8], "little")
        size = int.from_bytes(blob[off + 8:off + 16], "little")
        out.append(["0x%x" % addr, "0x%x" % size])
    return out


def u32le_list(blob):
    return [int.from_bytes(blob[i:i + 4], "little")
            for i in range(0, len(blob) - len(blob) % 4, 4)]


def as_text(v):
    if isinstance(v, bytes):
        return v.split(b"\x00")[0].decode("utf-8", "replace")
    return v


def compatible_list(v):
    if isinstance(v, bytes):
        return [t.decode("utf-8", "replace") for t in v.split(b"\x00") if t]
    return None


def data_list(v):
    """ioreg -a wraps data blobs in arrays; hex any bytes so JSON never
    stringifies them as b'...' reprs."""
    if isinstance(v, list):
        return [e.hex() if isinstance(e, bytes) else e for e in v]
    if isinstance(v, bytes):
        return v.hex()
    return v


def prop_block(node):
    """DT-shaped props of an AppleARMIODevice node, fully decoded."""
    out = {}
    for key in ("compatible", "interrupts", "interrupt-parent",
                "AAPL,phandle", "clock-gates", "power-gates", "clock-ids",
                "ane-id", "ane-subtype", "ane-type", "die-id", "die-ane-id",
                "iommu-parent", "pre-loaded", "dart-id", "dart-options"):
        v = node.get(key)
        if v is None:
            continue
        if isinstance(v, bytes):
            out[key] = {"hex": v.hex(), "u32le": u32le_list(v)}
        else:
            out[key] = v
    out["compatible_text"] = compatible_list(node.get("compatible"))
    reg = node.get("reg")
    if isinstance(reg, bytes):
        out["reg_ranges"] = u64le_ranges(reg)
        out["reg_hex_full"] = reg.hex()
        out["reg_bytes"] = len(reg)
    return out


def main():
    status = {"truncated": []}

    # --- raw IORegistry dumps (authoritative archive) -------------------
    rc, raw_full, _ = run(["ioreg", "-a", "-l"], timeout=180)
    (ART / "ioreg-full.txt.gz").write_bytes(gzip.compress(raw_full))
    rc, raw_svc, _ = run(["ioreg", "-a", "-p", "IOService", "-l"], timeout=180)
    (ART / "ioreg-ioservice.plist.gz").write_bytes(gzip.compress(raw_svc))
    rc, raw_ane, _ = run(["ioreg", "-a", "-rc", "H11ANEIn", "-l"], timeout=60)
    (ART / "h11anein.plist").write_bytes(raw_ane)

    # --- parse the IOService tree ---------------------------------------
    tree = plistlib.loads(raw_svc)
    stack = list(tree) if isinstance(tree, list) else [tree]
    nodes = {"ane0": None, "dart-ane0": None, "mapper-ane0": None,
             "pmgr": None}
    pmgr_props = {}
    while stack:
        n = stack.pop()
        if not isinstance(n, dict):
            continue
        name = as_text(n.get("name"))
        if name in nodes and nodes[name] is None:
            nodes[name] = n
        if name == "pmgr":
            pmgr_props = sorted(k for k in n if not k.startswith("IO"))
        kids = n.get("IORegistryEntryChildren")
        if isinstance(kids, list):
            stack.extend(kids)

    decoded = {"machine": None, "date": None, "macos": {}, "nodes": {}}

    # --- H11ANEIn driver instances (generation strings) ------------------
    try:
        inst = []
        for node in plistlib.loads(raw_ane):
            dp = node.get("DeviceProperties") or {}
            inst.append({
                "IOClass": as_text(node.get("IOClass")),
                "CFBundleIdentifier": as_text(node.get("CFBundleIdentifier")),
                "IONameMatched": as_text(node.get("IONameMatched")),
                "FirmwareLoaded": node.get("FirmwareLoaded") is True,
                "arch": as_text(dp.get(
                    "ANEDevicePropertyTypeANEArchitectureTypeStr")),
                "cores": dp.get("ANEDevicePropertyNumANECores"),
                "ANEVersion": dp.get("ANEDevicePropertyANEVersion"),
                "MinorVersion": dp.get("ANEDevicePropertyANEMinorVersion"),
                "HWBoardType": dp.get("ANEDevicePropertyANEHWBoardType"),
                "CPUSubType": dp.get("ANEDevicePropertyANECPUSubType"),
                "device_properties_raw": {
                    k: (v.hex() if isinstance(v, bytes) else v)
                    for k, v in dp.items()},
            })
        decoded["h11anein"] = inst
    except Exception as exc:
        status["truncated"].append("h11anein:%s" % type(exc).__name__)

    # --- per-node decode --------------------------------------------------
    for name, node in nodes.items():
        if node is None:
            decoded["nodes"][name] = None
            status["truncated"].append("missing:%s" % name)
            continue
        entry = {
            "location": as_text(node.get("IORegistryEntryLocation")),
            "IOClass": as_text(node.get("IOClass")),
            "IOInterruptControllers": as_text(
                node.get("IOInterruptControllers")),
            "IOInterruptSpecifiers": data_list(
                node.get("IOInterruptSpecifiers")),
        }
        entry.update(prop_block(node))
        decoded["nodes"][name] = entry

    # pmgr property NAME inventory (values kept out: voltage tables are
    # large; full node rides in the raw dumps above)
    decoded["pmgr_prop_names"] = pmgr_props

    # --- SoC identity ------------------------------------------------------
    ident = {}
    for key in ("hw.model", "machdep.cpu.brand_string", "hw.ncpu",
                "hw.activecpu", "hw.memsize", "hw.target", "hw.platform",
                "kern.osproductversion", "kern.osversion"):
        rc, out, _ = run(["sysctl", "-n", key], timeout=10)
        ident[key] = out.decode().strip() if rc == 0 else None
    for flag in ("-productVersion", "-buildVersion"):
        rc, out, _ = run(["sw_vers", flag], timeout=10)
        ident["sw_vers" + flag] = out.decode().strip() if rc == 0 else None
    decoded["macos"] = ident
    rc, sp, _ = run(["system_profiler", "SPHardwareDataType",
                     "SPSoftwareDataType"], timeout=90)
    (ART / "system-profiler.txt").write_bytes(
        sp if rc == 0 else b"system_profiler failed rc=%d\n%s"
        % (rc, sp[:2000]))
    decoded["machine"] = "%s / %s / %s" % (
        ident.get("hw.model"), ident.get("hw.target"),
        ident.get("machdep.cpu.brand_string"))
    decoded["date"] = subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                                     capture_output=True,
                                     text=True).stdout.strip()

    # --- ANE compiler/driver provenance (plists on disk) -------------------
    prov = ["ANE compiler backend provenance — live reads, %s"
            % decoded["date"]]
    fw = Path("/System/Library/PrivateFrameworks/ANECompiler.framework"
              "/Versions/A/Resources/Info.plist")
    if not fw.exists():
        fw = Path("/System/Library/PrivateFrameworks/ANECompiler.framework"
                  "/Resources/Info.plist")
    try:
        pl = plistlib.loads(fw.read_bytes())
        prov += [
            "ANECompiler.framework: version=%s bundleVersion=%s "
            "DTPlatformVersion=%s minSystem=%s" % (
                pl.get("CFBundleShortVersionString"),
                pl.get("CFBundleVersion"), pl.get("DTPlatformVersion"),
                pl.get("LSMinimumSystemVersion")),
        ]
    except Exception as exc:
        prov.append("ANECompiler.framework Info.plist: MISS (%s)" % exc)
    kdir = Path("/System/Library/Extensions")
    if kdir.is_dir():
        for kext in sorted(kdir.glob("Apple*ANE*.kext")):
            pl_path = next(kext.rglob("Info.plist"), None)
            ver = None
            if pl_path:
                try:
                    ver = plistlib.loads(
                        pl_path.read_bytes()).get("CFBundleVersion")
                except Exception:
                    pass
            prov.append("kext %s CFBundleVersion=%s"
                        % (kext.name, ver))
    for daemon in ("/usr/libexec/aned", "/usr/libexec/aneuserd"):
        prov.append("daemon %s exists=%s"
                    % (daemon, Path(daemon).exists()))
    (ART / "ane-compiler-provenance.txt").write_text("\n".join(prov) + "\n")

    decoded["status"] = status
    (ART / "decoded-nodes.json").write_text(
        json.dumps(decoded, indent=2, default=str) + "\n")
    print("ANE_PROBE_OK nodes=%s" % ",".join(
        k for k, v in nodes.items() if v is not None))


if __name__ == "__main__":
    main()
