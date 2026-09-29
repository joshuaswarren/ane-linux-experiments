#!/usr/bin/env python3
"""Build T6021 legacy-sequencer step files for the H14 fw-13.5 kext-init commands.

Post-HELLO, pre-first-inference CSNE commands recovered from the macOS 13.5
AppleH11ANEInterface kext (receipts/2026-09-28-h14-fsm-secure-park-decode/
kext135-command-sequence.md); firmware handlers decoded from /tmp/fw135.macho.

Wire format: +0 u32 0, +4 u16 command id (written by the driver at load time,
left zero in the file), +6 u16 0, +8.. payload.

Modes:
  --self-check              round-trip every generated step through parse
  emit OUTDIR [--order O]   write NN.bin for ordering init|kext|safe
  list                      print the orderings
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h14_seq_pack import Step, pack, parse

KEY_RO_MAP = 0x000010A400000000
KEY_SANITY = 0x000010A600000000
KEY_LOAD_LO = 0x0000180300000000
KEY_LOAD_HI = 0x0000180400000000
KEY_FW_LOG = 0x000000A100000000

DEFAULTS = {
    "ro_map": 1,           # kext literal 1 (0xfffffe00094e2694)
    "sanity": 1,           # kext sends u8 [this+0xc0]; default [INFERENCE]
    "load_lo": 0,          # kext sends u32(u16 [this+0x1ce]); default [INFERENCE]
    "load_hi": 0,          # kext sends u32(u16 [this+0x1cc]); default [INFERENCE]
    "fw_log": 1,           # kext: 0 if guard bytes fail else (flags&0x8000 ? 3 : 1)
    "ctx_lt": 0xFFFFFFFF,  # aneCtxSwitchLT default when property absent
    "pmu_base": 0x292280000,  # kext T6021 aneType 0xe0 branch [INFERENCE]
}

ORDERS = {
    "init": ["resource_info", "prop_ro_map", "prop_sanity", "prop_load_lo",
             "prop_load_hi", "prop_fw_log", "default_sub1", "default_sub2"],
    "kext": ["pmu_base2", "config_get", "prop_ro_map", "resource_info",
             "prop_sanity", "prop_load_lo", "prop_load_hi", "prop_fw_log",
             "default_sub1", "default_sub2"],
    "safe": ["resource_info", "prop_ro_map", "prop_sanity", "prop_load_lo",
             "prop_load_hi", "prop_fw_log"],
}


def command_step(opcode: int, length: int, fields=()) -> Step:
    cmd = bytearray(length)
    for off, fmt, *values in fields:
        struct.pack_into(fmt, cmd, off, *values)
    return Step(opcode, bytes(cmd), timeout_ms=3000, dump_reply=length)


def steps(values: dict) -> dict:
    prop = lambda key, val: [(0x08, "<Q", key), (0x10, "<I", val)]
    return {
        "resource_info": command_step(0x22, 0x64),
        "prop_ro_map": command_step(0x1F, 0x14, prop(KEY_RO_MAP, values["ro_map"])),
        "prop_sanity": command_step(0x1F, 0x14, prop(KEY_SANITY, values["sanity"])),
        "prop_load_lo": command_step(0x1F, 0x14, prop(KEY_LOAD_LO, values["load_lo"])),
        "prop_load_hi": command_step(0x1F, 0x14, prop(KEY_LOAD_HI, values["load_hi"])),
        "prop_fw_log": command_step(0x1F, 0x14, prop(KEY_FW_LOG, values["fw_log"])),
        "default_sub1": command_step(0x2E, 0x18, [(0x08, "<Q", 1), (0x10, "<II", 2, values["ctx_lt"])]),
        "default_sub2": command_step(0x2E, 0x20, [(0x08, "<Q", 2), (0x10, "<II", 4, 0x33), (0x18, "<II", 3, 0x0E)]),
        "pmu_base2": command_step(0x29, 0x10, [(0x08, "<Q", values["pmu_base"])]),
        "config_get": command_step(0x03, 0x10),
    }


def demo() -> None:
    all_steps = steps(DEFAULTS)
    for order in ORDERS.values():
        for key in order:
            step = all_steps[key]
            back = parse(pack(step))
            assert back == step, key
            assert back.command[:8] == bytes(8), f"{key}: id slot must stay zero"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", nargs="?", choices=("emit", "list"))
    ap.add_argument("outdir", nargs="?")
    ap.add_argument("--order", choices=tuple(ORDERS), default="init")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VAL",
                    help="override a default: " + ", ".join(DEFAULTS))
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args(argv)

    if a.self_check:
        demo()
        print("ok")
        return 0
    if a.mode == "list" or not a.mode:
        for name, order in ORDERS.items():
            print(f"{name}:")
            all_steps = steps(DEFAULTS)
            for i, key in enumerate(order, 1):
                s = all_steps[key]
                print(f"  {i:02d}.bin  op 0x{s.opcode:02x}  len 0x{len(s.command):02x}  {key}")
        return 0
    if not a.outdir:
        ap.error("emit needs OUTDIR")

    values = dict(DEFAULTS)
    for item in a.set:
        name, _, raw = item.partition("=")
        if name not in values:
            ap.error(f"unknown --set name {name}")
        values[name] = int(raw, 0)

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    all_steps = steps(values)
    for i, key in enumerate(ORDERS[a.order], 1):
        s = all_steps[key]
        blob = pack(s)
        (out / f"{i:02d}.bin").write_bytes(blob)
        print(f"{out / f'{i:02d}.bin'}  op 0x{s.opcode:02x}  len 0x{len(s.command):02x}  {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
