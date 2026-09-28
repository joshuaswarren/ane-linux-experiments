#!/usr/bin/env python3
"""Fix the LOAD_PROGRAM descriptor gate and rebuild the rtclient module.

Run on the Linux ANE host:

    sudo python3 tools/h14_load_program_identity_gate.py

Firmware 0x3ed30 reads descriptor offset 8 and skips the section unless
that word is 1. Offset 4 keeps the section id. Command offset 8 must
already name a program id whose slot is in use; this script does not
set that word. It does not unload a held module. It insmods only when
no ane_t6021 client is loaded.
"""
import pathlib
import subprocess
import sys

HEADER = pathlib.Path("/var/tmp/m2-primitive-driver/t6021/ane_t6021_legacy_load.h")
TREE = HEADER.parent
KO = TREE / "ane_t6021_rtclient.ko"
ID0 = "\tdesc->identity[0] = cpu_to_le32(spec->identity);\n"
ID1 = "\tdesc->identity[1] = cpu_to_le32(1); /* fw 0x3ed30: +8 must be 1 */\n"
WRONG = "desc->identity[1] = cpu_to_le32(spec->identity);"
INSMOD = [
    "insmod", str(KO),
    "fw_diag_retention=0", "fw_extra_ram=0x200000", "fw_load=1",
    "fw_diag_marker=0", "fw_start=1", "fw_start_stop_after=0",
    "fw_start_table_mode=2", "fw_start_rtb_mode=0", "fw_alias_reserved=1",
    "fw_start_venc_gates=0", "fw_start_mpm_off=0", "fw_start_state_report=0",
    "fw_start_dart_single_stream=0", "fw_start_mbox_ctrl_bit19=0",
    "fw_start_core1_run=0", "fw_start_wrapper_b80_unmask=0", "fw_start_dapf=0",
    "patch_timer_freq=0", "scratch3_ack=1", "legacy_only=1", "legacy_query=1",
    "legacy_load=1", "legacy_silent=0", "legacy_notify_ack=1",
    "legacy_fast_poll=1", "csne_ping=0", "poll_rx=0", "hello_wait_ms=0",
    "fw_load_stamp_base=0", "boot_prevent_nap=1",
]

def patch():
    lines = []
    for line in HEADER.read_text().splitlines(keepends=True):
        if WRONG in line:
            lines.append(ID0)
            lines.append(ID1)
            continue
        if "desc->identity[1] = cpu_to_le32(1)" in line:
            continue
        lines.append(line)
        if "desc->identity[0] = cpu_to_le32(spec->identity);" in line:
            lines.append(ID1)
    if not any("desc->identity[0] = cpu_to_le32(spec->identity);" in line for line in lines):
        raise SystemExit("identity[0] assignment missing")
    body = "".join(lines)
    if body.count("desc->identity[1] = cpu_to_le32(1)") != 1:
        raise SystemExit("identity[1] gate missing or duplicated")
    HEADER.write_text(body)


def loaded():
    return "ane_t6021" in pathlib.Path("/proc/modules").read_text()


def main():
    if not HEADER.is_file():
        raise SystemExit(f"missing {HEADER}")
    patch()
    subprocess.run(["make", "-C", str(TREE), "-j"], check=True)
    if not KO.is_file():
        raise SystemExit("rebuild did not produce the ko")
    if loaded():
        print("rebuilt; module already loaded — not insmodded")
        return 0
    if "--no-insmod" in sys.argv:
        print(f"rebuilt {KO}; insmod skipped")
        return 0
    subprocess.run(INSMOD, check=True)
    print("insmodded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
