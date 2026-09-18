#!/usr/bin/env python3
"""Offline SET-block derivation-input validator (runs on the Linux box).

Consumes a decoded-nodes.json from the macOS capture kit and validates the
T6021 SET-block derivation inputs against the 2026-09-17 T6021 receipt
constants (receipts/2026-09-17-t6021-macos-capture.md) and the M1-family
+0xc000 rule (receipts/2026-09-17-t6021-plane-derivation.md §6.2).

Usage: validate_set_block.py DECODED_JSON [BASELINE_JSON] [-o OUT_JSON]
Capture-only: validates inputs, never derives pwrstate offsets from anything
but the recorded addresses, and never instructs a register write.
"""
import json
import sys

# --- constants of record (2026-09-17 receipts) --------------------------
ANE0_MMIO = (0x84000000, 0x2000000)     # ANE MMIO window
PMGR_BASE = 0x8E080000                  # pmgr block base (node + reg range 1)
PMGR_WINDOW = (0x8E080000, 0x4034)      # ane0 reg range 2: pmgr base window
SET_OFFSET = 0xC000                     # the rule: SET = pmgr_base + 0xc000
SET_WINDOW = (0x8E08C000, 0x4000)       # ane0 reg range 3 (expected)
PMGR_RANGE0_SIZE = 0x80000              # pmgr node first reg range = 512 KiB
DART_RANGES = [(0x85800000, 0x4000), (0x85810000, 0x4000),
               (0x85820000, 0x4000), (0x85804000, 0x4000)]
ANE_INTERRUPT = 0x374                   # AIC interrupt (LE blob 74 03 00 00)
# M1-family rule cross-check (verified live 2026-09-17, m1-test-host/t6001-test-host):
RULE_CHECKS = [
    ("t8103_m1-test-host", 0x23B700000, 0x23B70C000),
    ("t6001_t6001-test-host", 0x28E080000, 0x28E08C000),
]


def norm_reg(node):
    """Accept the 2026-09-17 shapes (`reg`: [[str, str], ...]; pmgr archived
    as `first_range`) and the kit shape (`reg_ranges`)."""
    for key in ("reg_ranges", "reg", "first_range"):
        v = node.get(key)
        if v:
            if isinstance(v[0], str):          # flat [addr, size]
                return [(int(v[0], 16), int(v[1], 16))]
            return [(int(a, 16), int(s, 16)) for a, s in v]
    return []


def norm_intr(node):
    v = node.get("IOInterruptSpecifiers")
    if isinstance(v, list) and v:      # ioreg -a wraps the blob in an array
        v = v[0]
    if isinstance(v, str):
        v = v.strip("<>")
        return int.from_bytes(bytes.fromhex(v), "little")  # u32-LE blob
    return None


def validate(decoded, baseline):
    checks = []

    def chk(name, ok, detail):
        checks.append({"name": name, "pass": bool(ok), "detail": detail})

    nodes = decoded.get("nodes", decoded)  # kit shape or legacy shape
    ane0 = nodes.get("ane0") or {}
    pmgr = nodes.get("pmgr") or {}
    dart = nodes.get("dart-ane0") or {}

    ane_reg = norm_reg(ane0)
    chk("ane0_three_ranges", len(ane_reg) == 3, str(ane_reg))
    if len(ane_reg) == 3:
        chk("ane0_mmio_window", ane_reg[0] == ANE0_MMIO,
            "%s == %s" % (ane_reg[0], (ANE0_MMIO,)))
        chk("ane0_pmgr_window", ane_reg[1] == PMGR_WINDOW,
            "%s == %s" % (ane_reg[1], (PMGR_WINDOW,)))
        chk("ane0_set_window", ane_reg[2] == SET_WINDOW,
            "%s == %s" % (ane_reg[2], (SET_WINDOW,)))

    pmgr_reg = norm_reg(pmgr)
    chk("pmgr_base", bool(pmgr_reg) and pmgr_reg[0][0] == PMGR_BASE,
        "first range %s" % (pmgr_reg[0],))
    chk("pmgr_range0_size_512k", bool(pmgr_reg)
        and pmgr_reg[0][1] == PMGR_RANGE0_SIZE,
        str(pmgr_reg[0][1] if pmgr_reg else None))

    # THE derivation input: SET candidate = pmgr_base + 0xc000, and Apple's
    # own ane0 node must be granted its 16 KiB window exactly there.
    set_candidate = PMGR_BASE + SET_OFFSET
    set_from_ane0 = ane_reg[2][0] if len(ane_reg) == 3 else None
    chk("set_block_derivation", set_candidate == set_from_ane0,
        "pmgr_base(0x%x) + 0x%x == 0x%x ; ane0 range3 base = %s"
        % (PMGR_BASE, SET_OFFSET, set_candidate,
           hex(set_from_ane0) if set_from_ane0 is not None else None))

    # rule-form cross-check on the M1 family (static, from live 2026-09-17)
    for name, block, ps_map in RULE_CHECKS:
        chk("rule_%s" % name, block + SET_OFFSET == ps_map,
            "0x%x + 0x%x == 0x%x" % (block, SET_OFFSET, ps_map))

    dart_reg = norm_reg(dart)
    chk("dart_ane0_ranges", dart_reg == DART_RANGES, str(dart_reg))
    intr = norm_intr(ane0)
    chk("ane0_interrupt", intr == ANE_INTERRUPT,
        "%s == 0x%x" % (hex(intr) if intr is not None else None, ANE_INTERRUPT))

    # delta vs baseline
    delta = {}
    if baseline:
        bnodes = baseline.get("nodes", baseline)
        for name, ref in (("ane0", ane0), ("pmgr", pmgr),
                          ("dart-ane0", dart)):
            base = bnodes.get(name) or {}
            b_reg, n_reg = norm_reg(base), norm_reg(ref)
            if name == "pmgr":
                # baseline archives only range 0; capture has all ranges
                b_reg, n_reg = b_reg[:1], n_reg[:1]
            if b_reg != n_reg:
                delta[name + ":reg"] = {"baseline": b_reg, "capture": n_reg}
            b_i, n_i = norm_intr(base), norm_intr(ref)
            if b_i != n_i:
                delta[name + ":interrupts"] = {
                    "baseline": b_i, "capture": n_i}
    return checks, delta


def main():
    args = [a for a in sys.argv[1:] if a != "-o"]
    out_path = sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else None
    decoded = json.loads(open(args[0]).read())
    baseline = json.loads(open(args[1]).read()) if len(args) > 1 else None
    checks, delta = validate(decoded, baseline)
    failed = [c for c in checks if not c["pass"]]
    verdict = {
        "verdict": "SET_BLOCK_INPUTS_VALID" if not failed
        else "SET_BLOCK_INPUTS_INVALID",
        "capture_date": decoded.get("date"),
        "capture_machine": decoded.get("machine"),
        "capture_macos": decoded.get("macos", {}),
        "checks": checks,
        "baseline_delta": delta,
        "note": "capture-only: SET base stays a hypothesis until the "
                "Linux/m1n1 pmgr probe confirms the ane_* cluster at "
                "pmgr_base+0xc000 (receipts/2026-09-17-t6021-macos-capture.md)",
    }
    text = json.dumps(verdict, indent=2) + "\n"
    if out_path:
        open(out_path, "w").write(text)
    print(text)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
